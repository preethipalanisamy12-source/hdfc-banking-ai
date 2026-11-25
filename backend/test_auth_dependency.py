from fastapi import Request
from app.database.connection import SessionLocal
from app.core.auth_dependency import get_current_user

db = SessionLocal()

try:
    token = input("Enter session token: ")

    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (
                b"cookie",
                f"session_token={token}".encode("utf-8")
            )
        ],
        "query_string": b"",
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 50000),
        "scheme": "http"
    })

    user = get_current_user(request, db)

    print("Authenticated user:", user)

except Exception as e:
    print("Authentication failed:", str(e))

finally:
    db.close()