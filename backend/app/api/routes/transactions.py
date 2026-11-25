
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import HTTPException
from sqlalchemy import text
from app.core.auth_dependency import get_current_user
from fastapi import APIRouter, Depends, HTTPException

from app.database.connection import get_db
from app.services.sql_service import (
    get_customer_accounts,
    get_transaction_summary,
    get_recent_transactions
)

router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


@router.get("/my-data")
def get_my_data(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    customer_query = text("""
        SELECT customer_id
        FROM banking.customers
        WHERE user_id = :user_id
    """)

    customer = db.execute(
        customer_query,
        {"user_id": current_user["user_id"]}
    ).mappings().first()

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer profile not found"
        )

    customer_id = customer["customer_id"]

    accounts = get_customer_accounts(db, customer_id)
    summary = get_transaction_summary(db, customer_id)
    recent_transactions = get_recent_transactions(db, customer_id)

    return {
        "customer_id": customer_id,
        "accounts": accounts,
        "transaction_summary": summary,
        "recent_transactions": recent_transactions
    }
