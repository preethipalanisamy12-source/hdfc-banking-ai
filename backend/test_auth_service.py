from app.database.connection import SessionLocal
from app.services.auth_service import authenticate_user


db = SessionLocal()

try:
    # Test Rahul's correct credentials
    user = authenticate_user(
        db,
        "rahul@example.com",
        "rahuldemo@123"
    )

    print("Correct login:", user)

    # Test Rahul's incorrect password
    user = authenticate_user(
        db,
        "rahul@example.com",
        "WrongPassword123"
    )

    print("Wrong password:", user)

    # Test Priya's correct credentials
    user = authenticate_user(
        db,
        "priya@example.com",
        "priyademo@123"
    )

    print("Priya login:", user)

finally:
    db.close()