from sqlalchemy import text

from app.database.connection import SessionLocal
from app.core.security import hash_password


email = input("Enter demo customer email: ")
password =input("Enter new demo password: ")

hashed_password = hash_password(password)

db = SessionLocal()

try:
    result = db.execute(
        text("""
            UPDATE system.app_users
            SET password_hash = :password_hash
            WHERE LOWER(email) = LOWER(:email)
        """),
        {
            "password_hash": hashed_password,
            "email": email
        }
    )

    if result.rowcount != 1:
        db.rollback()
        print("Customer not found or update unsuccessful.")
    else:
        db.commit()
        print("Password hash successfully saved!")

finally:
    db.close()