from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import (
    generate_session_token,
    hash_session_token
)


SESSION_DURATION_HOURS = 1


def create_session(
    db: Session,
    user_id: int
):
    # Step 1: Generate original token
    token = generate_session_token()

    # Step 2: Hash the token
    token_hash = hash_session_token(token)

    # Step 3: Calculate expiry time
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=SESSION_DURATION_HOURS
    )

    # Step 4: Save session in database
    query = text("""
        INSERT INTO system.user_sessions (
            user_id,
            token_hash,
            expires_at
        )
        VALUES (
            :user_id,
            :token_hash,
            :expires_at
        )
    """)

    db.execute(
        query,
        {
            "user_id": user_id,
            "token_hash": token_hash,
            "expires_at": expires_at
        }
    )

    db.commit()

    # Step 5: Return original token
    return token