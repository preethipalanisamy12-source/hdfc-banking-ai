from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session


from app.database.connection import get_db
from app.schemas.auth import LoginRequest
from app.services.auth_service import authenticate_user
from fastapi import Response
from app.services.session_service import create_session

#signup auth 
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database.connection import get_db
from app.schemas.auth import LoginRequest, SignupRequest
from app.services.auth_service import authenticate_user
from app.services.session_service import create_session
from app.core.security import hash_password

from app.core.auth_dependency import get_current_user
from app.core.security import hash_session_token
from fastapi import Request
from sqlalchemy import text


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db)
):

    # Step 1: Authenticate user
    user = authenticate_user(
        db,
        request.email,
        request.password
    )
    print("LOGIN EMAIL:", request.email)
    print("AUTHENTICATION RESULT:", user)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Step 2: Create login session
    token = create_session(
        db,
        user["user_id"]
    )

    # Step 3: Set token in browser cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400
    )

    # Step 4: Return login response
    return {
        "message": "Login successful",
        "user": user
    }

#signup process
@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    request: SignupRequest,
    db: Session = Depends(get_db)
):
    try:
        with db.begin():

            # 1. Create login user
            user = db.execute(
                text("""
                    INSERT INTO system.app_users
                        (email, password_hash, is_active, role)
                    VALUES
                        (:email, :password_hash, TRUE, 'CUSTOMER')
                    RETURNING user_id, email
                """),
                {
                    "email": request.email.lower(),
                    "password_hash": hash_password(request.password)
                }
            ).mappings().one()

            # 2. Generate customer code
            customer_code = f"CUST{user['user_id']:06d}"

            # 3. Create customer profile
            customer = db.execute(
                text("""
                    INSERT INTO banking.customers
                        (customer_code, user_id, full_name,
                         phone, city, customer_status)
                    VALUES
                        (:customer_code, :user_id, :full_name,
                         :phone, :city, 'ACTIVE')
                    RETURNING customer_id
                """),
                {
                    "customer_code": customer_code,
                    "user_id": user["user_id"],
                    "full_name": request.full_name,
                    "phone": request.phone,
                    "city": request.city
                }
            ).mappings().one()

            # 4. Generate one unique demo account number
            account_number = f"DEMO{user['user_id']:012d}"

            # 5. Create one savings account
            db.execute(
                text("""
                    INSERT INTO banking.accounts
                        (customer_id, account_number,
                         account_type, balance, account_status)
                    VALUES
                        (:customer_id, :account_number,
                         'SAVINGS', 0.00, 'ACTIVE')
                """),
                {
                    "customer_id": customer["customer_id"],
                    "account_number": account_number
                }
            )

        return {
            "message": "Registration successful",
            "customer_code": customer_code,
            "account_number": account_number,
            "email": user["email"]
        }

    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="This email is already registered or the registration conflicts with existing data."
        )

        
# logout part
@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    token = request.cookies.get("session_token")
    token_hash = hash_session_token(token)

    query = text("""
        UPDATE system.user_sessions
        SET revoked_at = NOW()
        WHERE token_hash = :token_hash
    """)

    db.execute(query, {"token_hash": token_hash})
    db.commit()

    response.delete_cookie(
        key="session_token",
        httponly=True,
        secure=False,
        samesite="lax"
    )

    return {"message": "Logout successful"}