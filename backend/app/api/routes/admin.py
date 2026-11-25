from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import APIRouter, Depends, Query


from app.database.connection import get_db
from app.core.auth_dependency import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)


@router.get("/customers")
def get_all_customers(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            c.customer_id,
            c.customer_code,
            c.full_name,
            c.phone,
            c.city,
            c.customer_status,
            u.email
        FROM banking.customers c
        JOIN system.app_users u
            ON c.user_id = u.user_id
        LEFT JOIN banking.accounts a
            ON c.customer_id = a.customer_id
        ORDER BY c.customer_id
    """)

    result = db.execute(query).mappings().all()

    return {
        "total_customers": len(result),
        "customers": [dict(row) for row in result]
    }


@router.get("/transactions")
def get_all_transactions(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            t.transaction_id,
            t.reference_number,
            c.customer_code,
            c.full_name AS customer_name,
            a.account_number,
            t.transaction_type,
            t.amount,
            t.transaction_date,
            t.description,
            t.transaction_status
        FROM banking.transactions t
        JOIN banking.accounts a
            ON t.account_id = a.account_id
        JOIN banking.customers c
            ON a.customer_id = c.customer_id
        ORDER BY t.transaction_date DESC
    """)

    result = db.execute(query).mappings().all()

    return {
        "total_transactions": len(result),
        "transactions": [dict(row) for row in result]
    }    



# account details required 


@router.get("/accounts")
def get_all_accounts(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            a.account_id,
            a.customer_id,
            c.customer_code,
            c.full_name AS customer_name,
            a.account_number,
            a.account_type,
            a.balance,
            a.account_status
        FROM banking.accounts a
        JOIN banking.customers c
            ON a.customer_id = c.customer_id
        ORDER BY a.account_id
    """)

    result = db.execute(query).mappings().all()

    return {
        "total_accounts": len(result),
        "accounts": [dict(row) for row in result]
    }


#filter cus

@router.get("/customers/{customer_id}/transactions")
def get_customer_transactions(
    customer_id: int,
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            t.transaction_id,
            t.reference_number,
            c.customer_code,
            c.full_name AS customer_name,
            a.account_number,
            t.transaction_type,
            t.amount,
            t.transaction_date,
            t.description,
            t.transaction_status
        FROM banking.transactions t
        JOIN banking.accounts a
            ON t.account_id = a.account_id
        JOIN banking.customers c
            ON a.customer_id = c.customer_id
        WHERE c.customer_id = :customer_id
        ORDER BY t.transaction_date DESC
    """)

    result = db.execute(
        query,
        {"customer_id": customer_id}
    ).mappings().all()

    return {
        "customer_id": customer_id,
        "total_transactions": len(result),
        "transactions": [dict(row) for row in result]
    }

# get dashboard details
@router.get("/dashboard")
def get_admin_dashboard(
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            (SELECT COUNT(*)
             FROM banking.customers) AS total_customers,

            (SELECT COUNT(*)
             FROM banking.accounts) AS total_accounts,

            (SELECT COUNT(*)
             FROM banking.transactions) AS total_transactions,

            (SELECT COUNT(*)
             FROM banking.transactions
             WHERE transaction_status = 'SUCCESS') AS successful_transactions,

            (SELECT COUNT(*)
             FROM banking.transactions
             WHERE transaction_status = 'FAILED') AS failed_transactions,

            (SELECT COUNT(*)
             FROM banking.transactions
             WHERE transaction_status = 'PENDING') AS pending_transactions
    """)

    result = db.execute(query).mappings().first()

    return dict(result)    

#search for the customer
@router.get("/customers/search")
def search_customers(
    q: str = Query(..., min_length=2),
    current_user: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    query = text("""
        SELECT
            c.customer_id,
            c.customer_code,
            c.full_name,
            c.phone,
            c.city,
            c.customer_status,
            u.email
        FROM banking.customers c
        JOIN system.app_users u
            ON c.user_id = u.user_id
        WHERE
            c.customer_code ILIKE :search
            OR c.full_name ILIKE :search
            OR c.phone ILIKE :search
            OR u.email ILIKE :search
        ORDER BY c.customer_id
    """)

    search_value = f"%{q}%"

    result = db.execute(
        query,
        {"search": search_value}
    ).mappings().all()

    return {
        "search_query": q,
        "total_results": len(result),
        "customers": [dict(row) for row in result]
    }    