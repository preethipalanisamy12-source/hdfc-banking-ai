
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
import re
from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------
# COMMON HELPERS
# ---------------------------------------------------------

BANK_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _serialize_value(value):
    """
    Convert database values into JSON-friendly values.

    Decimal is converted to string to preserve monetary precision.
    Datetime is converted to ISO format.
    """
    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    return value


def _serialize_rows(rows):
    """Convert SQLAlchemy result rows into dictionaries."""
    return [
        {
            key: _serialize_value(value)
            for key, value in dict(row).items()
        }
        for row in rows
    ]


def _format_result(rows):
    """
    Standard evidence structure expected by the answer model.
    """
    serialized_rows = _serialize_rows(rows)

    return {
        "row_count": len(serialized_rows),
        "rows": serialized_rows
    }



def _get_period_dates(period):
    """
    Convert supported periods into start and end timestamps.
    Supports dynamic periods such as LAST_2_YEARS,
    LAST_3_YEARS, LAST_5_YEARS, etc.
    """

    if not period:
        return None, None

    now = datetime.now(BANK_TIMEZONE)

    if period == "THIS_MONTH":
        start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

    elif period == "LAST_MONTH":
        end = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if end.month == 1:
            start = end.replace(year=end.year - 1, month=12)
        else:
            start = end.replace(month=end.month - 1)

    elif period == "LAST_7_DAYS":
        from datetime import timedelta
        start = now - timedelta(days=7)
        end = now

    elif period == "LAST_30_DAYS":
        from datetime import timedelta
        start = now - timedelta(days=30)
        end = now

    elif period == "THIS_YEAR":
        start = now.replace(
            month=1, day=1, hour=0,
            minute=0, second=0, microsecond=0
        )
        end = start.replace(year=start.year + 1)

    else:
        # Dynamic year support: LAST_2_YEARS, LAST_3_YEARS, etc.
        match = re.fullmatch(r"(?:LAST_)?(\d+)_YEARS?", period)

        if match:
            years = int(match.group(1))

            if years < 1 or years > 100:
                raise ValueError("Year period must be between 1 and 100.")

            try:
                start = now.replace(year=now.year - years)
            except ValueError:
                # Handle February 29 in leap years.
                start = now.replace(
                    year=now.year - years,
                    day=28
                )

            end = now

        else:
            raise ValueError(f"Unsupported period: {period}")

    return start, end



def _build_transaction_filters(
    period=None,
    payment_mode=None,
    txn_type=None,
    min_amount=None,
    status=None
):
    """
    Build parameterized filters.

    Filter values are passed as SQL parameters.
    No payment-mode or transaction-type allowlists are hardcoded.
    """

    conditions = []
    params = {}

    if period:
        start, end = _get_period_dates(period)

        conditions.append(
            "t.transaction_date >= :start_date"
        )
        conditions.append(
            "t.transaction_date < :end_date"
        )

        params["start_date"] = start
        params["end_date"] = end

    if payment_mode:
        conditions.append("t.mode = :payment_mode")
        params["payment_mode"] = payment_mode

    if txn_type:
        conditions.append("t.transaction_type = :txn_type")
        params["txn_type"] = txn_type

    if min_amount is not None:
        conditions.append("t.amount >= :min_amount")
        params["min_amount"] = min_amount

    if status:
        conditions.append("t.transaction_status = :status")
        params["status"] = status

    return conditions, params


def _get_customer_id_or_raise(db: Session, user_id: int):
    customer_id = get_customer_id(db, user_id)

    if customer_id is None:
        raise ValueError("No active customer found for this user.")

    return customer_id


# ---------------------------------------------------------
# 1. GET CUSTOMER ID
# ---------------------------------------------------------

def get_customer_id(db: Session, user_id: int):
    query = text("""
        SELECT customer_id
        FROM banking.customers
        WHERE user_id = :user_id
          AND customer_status = 'ACTIVE'
    """)

    result = db.execute(
        query,
        {"user_id": user_id}
    ).mappings().first()

    if result is None:
        return None

    return result["customer_id"]


# ---------------------------------------------------------
# 2. GET CUSTOMER ACCOUNTS
# ---------------------------------------------------------

def get_customer_accounts(db: Session, customer_id: int):

    query = text("""
        SELECT
            account_id,
            CONCAT('******', RIGHT(account_number, 4))
                AS account_number_masked,
            account_type,
            balance,
            account_status
        FROM banking.accounts
        WHERE customer_id = :customer_id
        ORDER BY account_id
    """)

    result = db.execute(
        query,
        {"customer_id": customer_id}
    ).mappings().all()

    return _format_result(result)


# ---------------------------------------------------------
# 3. GET ACCOUNT BALANCE
# ---------------------------------------------------------

def get_account_balance(
    db: Session,
    customer_id: int,
    account_type: str = None
):

    query = """
        SELECT
            account_type,
            CONCAT('******', RIGHT(account_number, 4))
                AS account_number_masked,
            balance,
            account_status
        FROM banking.accounts
        WHERE customer_id = :customer_id
    """

    params = {"customer_id": customer_id}

    if account_type:
        query += " AND account_type = :account_type"
        params["account_type"] = account_type

    query += " ORDER BY account_id"

    result = db.execute(
        text(query),
        params
    ).mappings().all()

    return _format_result(result)


# ---------------------------------------------------------
# 4. GET TRANSACTION SUMMARY
# ---------------------------------------------------------

def get_transaction_summary(
    db: Session,
    customer_id: int,
    period: str = None,
    payment_mode: str = None
):

    conditions, params = _build_transaction_filters(
        period=period,
        payment_mode=payment_mode
    )

    query = """
        SELECT
            COUNT(*) AS total_transactions,

            COUNT(*) FILTER (
                WHERE t.transaction_status = 'SUCCESS'
            ) AS successful_transactions,

            COUNT(*) FILTER (
                WHERE t.transaction_status = 'FAILED'
            ) AS failed_transactions,

            COUNT(*) FILTER (
                WHERE t.transaction_status = 'PENDING'
            ) AS pending_transactions,

            COUNT(*) FILTER (
                WHERE t.transaction_type = 'DEBIT'
            ) AS debit_count,

            COUNT(*) FILTER (
                WHERE t.transaction_type = 'CREDIT'
            ) AS credit_count,

            COALESCE(
                SUM(t.amount) FILTER (
                    WHERE t.transaction_type = 'DEBIT'
                      AND t.transaction_status = 'SUCCESS'
                ), 0
            ) AS total_debit,

            COALESCE(
                SUM(t.amount) FILTER (
                    WHERE t.transaction_type = 'CREDIT'
                      AND t.transaction_status = 'SUCCESS'
                ), 0
            ) AS total_credit

        FROM banking.transactions t
        JOIN banking.accounts a
            ON t.account_id = a.account_id

        WHERE a.customer_id = :customer_id
    """

    params["customer_id"] = customer_id

    if conditions:
        query += " AND " + " AND ".join(conditions)

    result = db.execute(
        text(query),
        params
    ).mappings().one()

    return _format_result([result])


# ---------------------------------------------------------
# COMMON TRANSACTION FETCHER
# ---------------------------------------------------------

def _get_transactions(
    db: Session,
    customer_id: int,
    limit: int = 100,
    period: str = None,
    payment_mode: str = None,
    txn_type: str = None,
    min_amount=None,
    status: str = None
):

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Transaction limit must be an integer.")

    if limit < 1 or limit > 100:
        raise ValueError("Transaction limit must be between 1 and 100.")

    conditions, params = _build_transaction_filters(
        period=period,
        payment_mode=payment_mode,
        txn_type=txn_type,
        min_amount=min_amount,
        status=status
    )

    query = """
        SELECT
            t.transaction_id AS txn_id,
            t.transaction_date AS date,
            t.description,
            t.amount,
            t.transaction_type AS type,
            t.mode,
            t.transaction_status AS status,
            CONCAT('******', RIGHT(a.account_number, 4))
                AS account_number_masked

        FROM banking.transactions t

        JOIN banking.accounts a
            ON t.account_id = a.account_id

        WHERE a.customer_id = :customer_id
    """

    params["customer_id"] = customer_id
    query += " AND " + " AND ".join(conditions) if conditions else ""

    query += """
        ORDER BY t.transaction_date DESC
        LIMIT :limit
    """

    params["limit"] = limit

    result = db.execute(
        text(query),
        params
    ).mappings().all()

    return _format_result(result)


# ---------------------------------------------------------
# 5. GET RECENT TRANSACTIONS
# ---------------------------------------------------------

def get_recent_transactions(
    db: Session,
    customer_id: int,
    limit: int = 5,
    txn_type: str = None,
    payment_mode: str = None,
    min_amount=None,
    period: str = None
):

    return _get_transactions(
        db=db,
        customer_id=customer_id,
        limit=limit,
        period=period,
        payment_mode=payment_mode,
        txn_type=txn_type,
        min_amount=min_amount
    )


# ---------------------------------------------------------
# 6. GET FAILED TRANSACTIONS
# ---------------------------------------------------------

def get_failed_transactions(
    db: Session,
    customer_id: int,
    limit: int = 100,
    period: str = None,
    payment_mode: str = None
):

    return _get_transactions(
        db=db,
        customer_id=customer_id,
        limit=limit,
        period=period,
        payment_mode=payment_mode,
        status="FAILED"
    )


# ---------------------------------------------------------
# 7. GET PENDING TRANSACTIONS
# ---------------------------------------------------------

def get_pending_transactions(
    db: Session,
    customer_id: int,
    limit: int = 100,
    period: str = None,
    payment_mode: str = None
):

    return _get_transactions(
        db=db,
        customer_id=customer_id,
        limit=limit,
        period=period,
        payment_mode=payment_mode,
        status="PENDING"
    )
