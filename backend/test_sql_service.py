
from app.database.connection import SessionLocal
from app.services.sql_service import (
    get_customer_id,
    get_customer_accounts,
    get_account_balance,
    get_transaction_summary,
    get_recent_transactions,
    get_failed_transactions,
    get_pending_transactions,
)


# Replace with an existing user_id from your database.
USER_ID = 1


def print_result(title, result):
    print(f"\n{'=' * 60}")
    print(title)
    print("=" * 60)
    print(result)


def main():
    db = SessionLocal()

    try:
        # 1. Find customer using authenticated user's ID
        customer_id = get_customer_id(db, USER_ID)

        if customer_id is None:
            print("No active customer found. Check USER_ID.")
            return

        print("Customer ID:", customer_id)

        # 2. Customer accounts
        accounts = get_customer_accounts(db, customer_id)
        print_result("CUSTOMER ACCOUNTS", accounts)

        # 3. Account balances
        balance = get_account_balance(db, customer_id)
        print_result("ACCOUNT BALANCES", balance)

        # 4. Transaction summary
        summary = get_transaction_summary(db, customer_id)
        print_result("TRANSACTION SUMMARY", summary)

        # 5. Recent transactions
        recent = get_recent_transactions(
            db, customer_id, limit=5
        )
        print_result("RECENT TRANSACTIONS", recent)

        # 6. Failed transactions
        failed = get_failed_transactions(
            db, customer_id, limit=10
        )
        print_result("FAILED TRANSACTIONS", failed)

        # 7. Pending transactions
        pending = get_pending_transactions(
            db, customer_id, limit=10
        )
        print_result("PENDING TRANSACTIONS", pending)

    except Exception as e:
        print("TEST FAILED:", repr(e))

    finally:
        db.close()


if __name__ == "__main__":
    main()
