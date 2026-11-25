from app.database.connection import SessionLocal
from app.services.session_service import create_session

db = SessionLocal()

try:
    token = create_session(
        db,
        user_id=1
    )

    print("Session created successfully!")

    # Do not print the actual token in production.
    print("Token generated:", bool(token))

finally:
    db.close()