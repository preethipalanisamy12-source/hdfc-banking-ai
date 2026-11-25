
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth_dependency import get_current_user
from app.database.connection import get_db

router = APIRouter(
    prefix="/api/profile",
    tags=["Profile"]
)


@router.get("/me")
def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            c.customer_id,
            c.customer_code,
            c.full_name,
            u.email,
            c.phone,
            c.city,
            c.customer_status
        FROM banking.customers c
        JOIN system.app_users u
            ON c.user_id = u.user_id
        WHERE c.user_id = :user_id
    """)

    profile = db.execute(
        query,
        {"user_id": current_user["user_id"]}
    ).mappings().first()

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Customer profile not found"
        )

    return dict(profile)
