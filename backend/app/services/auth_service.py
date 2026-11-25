from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import verify_password


def authenticate_user(
    db: Session,
    email: str,
    password: str
):
    # Step 1: Find user by email
    query = text("""
        SELECT
            user_id,
            email,
            password_hash,
            is_active,
            role
        FROM system.app_users
        WHERE LOWER(email) = LOWER(:email)
    """)

    user = db.execute(
        query,
        {"email": email}
    ).mappings().first()

    # Step 2: Check whether user exists
    if user is None:
        return None

    # Step 3: Check whether account is active
    if not user["is_active"]:
        return None

    # Step 4: Verify entered password
    is_valid = verify_password(
        password,
        user["password_hash"]
    )

    if not is_valid:
        return None

    # Step 5: Return authenticated user details
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"]
    }
