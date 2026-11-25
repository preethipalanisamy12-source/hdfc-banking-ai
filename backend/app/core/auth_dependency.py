
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.security import hash_session_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
):
    # Step 1: Read session token from cookie
    token = request.cookies.get("session_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # Step 2: Hash the received token
    token_hash = hash_session_token(token)

    # Step 3: Find session and user
    query = text("""
        SELECT
            u.user_id,
            u.email,
            u.is_active,
            u.role,
            s.expires_at,
            s.revoked_at
        FROM system.user_sessions s
        JOIN system.app_users u
            ON s.user_id = u.user_id
        WHERE s.token_hash = :token_hash
    """)

    user = db.execute(
        query,
        {"token_hash": token_hash}
    ).mappings().first()

    # Step 4: Check session existence
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session"
        )

    # Step 5: Check expiry and revocation
    if (
        user["expires_at"] <= datetime.now(timezone.utc)
        or user["revoked_at"] is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked"
        )

    # Step 6: Check account status
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"]
    }


# Admin authorization dependency
def require_admin(
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return current_user
