
from sqlalchemy.exc import SQLAlchemyError

from app.services.intent_router import intent_router
from app.services.llm_service import generate_customer_answer
from app.services.rag_service import get_relevant_context
from rag.retrieval.retriever import RagUnavailable

from app.services.sql_service import (
    get_customer_id,
    get_customer_accounts,
    get_account_balance,
    get_transaction_summary,
    get_recent_transactions,
    get_failed_transactions,
    get_pending_transactions,
)

from app.database.connection import SessionLocal


# =========================================================
# SUPPORTED SQL TASKS
# =========================================================

SUPPORTED_SQL_TASKS = {
    "GET_CUSTOMER_ACCOUNTS",
    "GET_ACCOUNT_BALANCE",
    "GET_TRANSACTION_SUMMARY",
    "GET_RECENT_TRANSACTIONS",
    "GET_FAILED_TRANSACTIONS",
    "GET_PENDING_TRANSACTIONS",
}


SUPPORTED_FIXED_PERIODS = {
    "THIS_MONTH",
    "LAST_MONTH",
    "LAST_7_DAYS",
    "LAST_30_DAYS",
    "THIS_YEAR",
}


# =========================================================
# COMMON RESPONSE
# =========================================================

def _make_response(
    answer,
    message,
    intent,
    task,
    current_user,
    sources=None,
    retrieval_metadata=None,
):
    return {
        "question": message,
        "intent": intent,
        "task": task,
        "answer": answer,
        "sources": sources or [],
        "retrieval_metadata": retrieval_metadata,
        "user": (current_user or {}).get("email"),
    }


# =========================================================
# EXTRACT QWEN ANSWER
# =========================================================

def _get_answer(model_result: dict) -> str:

    if not isinstance(model_result, dict):
        raise RuntimeError(
            "Invalid response received from Qwen API."
        )

    for key in ("answer", "response", "generated_text"):

        value = model_result.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    raise RuntimeError(
        "Qwen API did not return an answer. "
        f"Received response keys: {list(model_result.keys())}"
    )


# =========================================================
# VALIDATE SQL REQUEST
# =========================================================

def validate_sql_request(task, parameters=None):

    parameters = parameters or {}

    if not isinstance(parameters, dict):
        return False, "INVALID_PARAMETERS"

    if task not in SUPPORTED_SQL_TASKS:
        return False, "UNSUPPORTED_SQL_TASK"

    # Validate period.
    period = parameters.get("period")

    if period:

        if not isinstance(period, str):
            return False, "UNSUPPORTED_PERIOD"

        period = period.upper()

        if period not in SUPPORTED_FIXED_PERIODS:

            import re

            match = re.fullmatch(
                r"(?:LAST_)?(\d+)_YEARS?",
                period
            )

            if not match:
                return False, "UNSUPPORTED_PERIOD"

            years = int(match.group(1))

            if years < 1 or years > 100:
                return False, "UNSUPPORTED_PERIOD"

        parameters["period"] = period

    # Validate transaction limit.
    if "limit" in parameters:

        limit = parameters["limit"]

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1
            or limit > 100
        ):
            return False, "INVALID_LIMIT"

    # Validate minimum transaction amount.
    if parameters.get("min_amount") is not None:

        try:

            amount = float(parameters["min_amount"])

            if amount < 0:
                return False, "INVALID_AMOUNT"

            parameters["min_amount"] = amount

        except (ValueError, TypeError):
            return False, "INVALID_AMOUNT"

    return True, None


# =========================================================
# SQL TASK EXECUTION
# =========================================================

def _execute_sql_task(db, customer_id, task, params):

    if task == "GET_CUSTOMER_ACCOUNTS":

        return get_customer_accounts(
            db,
            customer_id
        )

    elif task == "GET_ACCOUNT_BALANCE":

        return get_account_balance(
            db,
            customer_id,
            account_type=params.get("account_type")
        )

    elif task == "GET_TRANSACTION_SUMMARY":

        return get_transaction_summary(
            db,
            customer_id,
            period=params.get("period"),
            payment_mode=params.get("payment_mode")
        )

    elif task == "GET_RECENT_TRANSACTIONS":

        return get_recent_transactions(
            db,
            customer_id,
            limit=params.get("limit", 5),
            txn_type=params.get("txn_type"),
            payment_mode=params.get("payment_mode"),
            min_amount=params.get("min_amount"),
            period=params.get("period")
        )

    elif task == "GET_FAILED_TRANSACTIONS":

        return get_failed_transactions(
            db,
            customer_id,
            limit=params.get("limit", 100),
            period=params.get("period"),
            payment_mode=params.get("payment_mode")
        )

    elif task == "GET_PENDING_TRANSACTIONS":

        return get_pending_transactions(
            db,
            customer_id,
            limit=params.get("limit", 100),
            period=params.get("period"),
            payment_mode=params.get("payment_mode")
        )

    raise ValueError(f"Unsupported SQL task: {task}")


# =========================================================
# RUN CUSTOMER-SPECIFIC SQL
# =========================================================

def _run_customer_sql(current_user, task, parameters):

    user_id = current_user.get("user_id")

    if user_id is None:
        raise ValueError("Authenticated user ID is missing.")

    db = SessionLocal()

    try:

        # Always resolve customer using authenticated user.
        customer_id = get_customer_id(db, user_id)

        if customer_id is None:
            raise ValueError("No active customer account found.")

        return _execute_sql_task(
            db=db,
            customer_id=customer_id,
            task=task,
            params=parameters
        )

    finally:
        db.close()


# =========================================================
# RAG RETRIEVAL
# =========================================================

def _retrieve_rag(message):

    return get_relevant_context(
        question=message,
        top_k=5
    )


# =========================================================
# CHECK RAG EVIDENCE
# =========================================================

def _has_retrieved_evidence(rag_result):
    """
    Check whether RAG returned usable evidence.

    This checks retrieval availability, not semantic answerability.
    The GROUNDED prompt still controls what Qwen may answer.
    """

    if not isinstance(rag_result, dict):
        return False

    metadata = rag_result.get("retrieval_metadata") or {}

    context = rag_result.get("context") or ""

    # Support both possible abstention locations.
    abstained = (
        rag_result.get("abstained", False)
        or metadata.get("abstained", False)
    )

    return (
        not abstained
        and isinstance(context, str)
        and bool(context.strip())
    )


# =========================================================
# GENERAL FALLBACK GENERATION
# =========================================================

def _generate_general_fallback(
    message,
    task,
    parameters=None,
    sql_result=None
):
    """
    Generate a cautious general-knowledge response when RAG
    has insufficient evidence or is unavailable.

    The Colab GENERAL_FALLBACK_SYSTEM_PROMPT must prevent
    unsupported HDFC-specific claims.
    """

    return generate_customer_answer(
        message=message,
        task=task or "GENERAL_BANKING_FALLBACK",
        query_params=parameters or {},
        sql_result=sql_result,
        retrieved_chunks=None,
        answer_mode="GENERAL_FALLBACK",
    )


# =========================================================
# SQL ERROR RESPONSE
# =========================================================

def _sql_error_message(error_code):

    messages = {

        "UNSUPPORTED_SQL_TASK": (
            "Sorry, I currently cannot retrieve this information. "
            "This banking operation is not supported yet."
        ),

        "UNSUPPORTED_PERIOD": (
            "Sorry, I cannot retrieve information for the "
            "requested time period. Please try a supported "
            "time period."
        ),

        "INVALID_LIMIT": (
            "Please request between 1 and 100 transactions."
        ),

        "INVALID_AMOUNT": (
            "Please provide a valid non-negative transaction amount."
        ),

        "INVALID_PARAMETERS": (
            "I could not understand the requested SQL parameters. "
            "Please try rephrasing your question."
        ),
    }

    return messages.get(
        error_code,
        "I could not retrieve your banking information. "
        "Please try again later."
    )


# =========================================================
# SQL PROCESSOR
# =========================================================

def _process_sql(
    message,
    current_user,
    task,
    parameters,
    intent,
):

    is_valid, error_code = validate_sql_request(
        task,
        parameters
    )

    if not is_valid:

        return _make_response(
            answer=_sql_error_message(error_code),
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    try:

        sql_result = _run_customer_sql(
            current_user=current_user,
            task=task,
            parameters=parameters
        )

    except ValueError:

        return _make_response(
            answer=(
                "I could not retrieve your banking information. "
                "Please check your account or try again."
            ),
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    except SQLAlchemyError:

        return _make_response(
            answer=(
                "There was a temporary database problem while "
                "retrieving your banking information. "
                "Please try again later."
            ),
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    # SQL-only requests use authenticated SQL information.
    model_result = generate_customer_answer(
        message=message,
        task=task,
        query_params=parameters,
        sql_result=sql_result,
        answer_mode="GROUNDED"
    )

    answer = _get_answer(model_result)

    return _make_response(
        answer=answer,
        message=message,
        intent=intent,
        task=task,
        current_user=current_user,
    )


# =========================================================
# MAIN CHAT PROCESSOR
# =========================================================

def process_chat(message: str, current_user: dict) -> dict:

    if not isinstance(message, str) or not message.strip():

        return _make_response(
            answer="Please enter a question.",
            message=message or "",
            intent=None,
            task=None,
            current_user=current_user,
        )

    if not isinstance(current_user, dict):

        raise ValueError(
            "Authenticated user information is missing."
        )

    message = message.strip()

    # -----------------------------------------------------
    # STEP 1: INTENT CLASSIFICATION
    # -----------------------------------------------------

    routing = intent_router.predict_intent(message)

    if not isinstance(routing, dict):
        raise ValueError("Invalid response from intent router.")

    intent = str(
        routing.get("intent", "")
    ).upper()

    task = routing.get("task")

    parameters = routing.get("parameters") or {}

    if not isinstance(parameters, dict):

        return _make_response(
            answer="Invalid request parameters.",
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    if routing.get("unsupported_sql_task"):

        return _make_response(
            answer=(
                "Sorry, I currently cannot retrieve this information. "
                "This banking operation is not supported yet."
            ),
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    sources = []
    retrieval_metadata = None

    # -----------------------------------------------------
    # STEP 2: SQL ONLY
    # -----------------------------------------------------

    if intent == "SQL":

        if not routing.get("requires_sql"):

            return _make_response(
                answer=(
                    "I could not understand the banking operation "
                    "required for this question."
                ),
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
            )

        return _process_sql(
            message=message,
            current_user=current_user,
            task=task,
            parameters=parameters,
            intent=intent,
        )

    # -----------------------------------------------------
    # STEP 3: RAG ONLY
    # -----------------------------------------------------

    elif intent == "RAG":

        try:

            rag_result = _retrieve_rag(message)

        except RagUnavailable:

            # RAG service unavailable.
            # Ask Qwen using GENERAL_FALLBACK mode.

            model_result = _generate_general_fallback(
                message=message,
                task=task or "RAG_FALLBACK",
                parameters=parameters,
            )

            answer = _get_answer(model_result)

            return _make_response(
                answer=answer,
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
                retrieval_metadata={
                    "status": "RAG_UNAVAILABLE"
                },
            )

        if not isinstance(rag_result, dict):
            raise RuntimeError("Invalid response from RAG service.")

        sources = rag_result.get("sources", [])

        retrieval_metadata = (
            rag_result.get("retrieval_metadata", {})
        )

        if _has_retrieved_evidence(rag_result):

            # Evidence found: GROUNDED mode.
            model_result = generate_customer_answer(
                message=message,
                task=task or "RAG_ONLY",
                query_params=parameters,
                retrieved_chunks=rag_result,
                answer_mode="GROUNDED",
            )

        else:

            # Evidence missing or abstained:
            # GENERAL_FALLBACK mode.
            model_result = _generate_general_fallback(
                message=message,
                task=task or "RAG_FALLBACK",
                parameters=parameters,
            )

        answer = _get_answer(model_result)

        return _make_response(
            answer=answer,
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
            sources=sources,
            retrieval_metadata=retrieval_metadata,
        )

    # -----------------------------------------------------
    # STEP 4: SQL + RAG
    # -----------------------------------------------------

    elif intent == "SQL_RAG":

        if (
            not routing.get("requires_sql")
            or not routing.get("requires_rag")
        ):

            return _make_response(
                answer="Invalid SQL and RAG routing response.",
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
            )

        # Validate SQL request before accessing database.
        is_valid, error_code = validate_sql_request(
            task,
            parameters
        )

        if not is_valid:

            return _make_response(
                answer=_sql_error_message(error_code),
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
            )

        # First retrieve authenticated customer information.
        try:

            sql_result = _run_customer_sql(
                current_user=current_user,
                task=task,
                parameters=parameters
            )

        except ValueError:

            return _make_response(
                answer=(
                    "I could not retrieve your banking information. "
                    "Please check your account or try again."
                ),
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
            )

        except SQLAlchemyError:

            return _make_response(
                answer=(
                    "There was a temporary database problem. "
                    "Please try again later."
                ),
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
            )

        # Retrieve banking knowledge.
        try:

            rag_result = _retrieve_rag(message)

        except RagUnavailable:

            # Preserve SQL result even if RAG is unavailable.
            model_result = _generate_general_fallback(
                message=message,
                task=task or "SQL_RAG_FALLBACK",
                parameters=parameters,
                sql_result=sql_result,
            )

            answer = _get_answer(model_result)

            return _make_response(
                answer=answer,
                message=message,
                intent=intent,
                task=task,
                current_user=current_user,
                retrieval_metadata={
                    "status": "RAG_UNAVAILABLE"
                },
            )

        if not isinstance(rag_result, dict):
            raise RuntimeError("Invalid response from RAG service.")

        sources = rag_result.get("sources", [])

        retrieval_metadata = (
            rag_result.get("retrieval_metadata", {})
        )

        if _has_retrieved_evidence(rag_result):

            # Both SQL and RAG evidence are available.
            model_result = generate_customer_answer(
                message=message,
                task=task,
                query_params=parameters,
                sql_result=sql_result,
                retrieved_chunks=rag_result,
                answer_mode="GROUNDED",
            )

        else:

            # Preserve SQL result and use fallback for the
            # policy-related part of the customer's question.
            model_result = _generate_general_fallback(
                message=message,
                task=task or "SQL_RAG_FALLBACK",
                parameters=parameters,
                sql_result=sql_result,
            )

        answer = _get_answer(model_result)

        return _make_response(
            answer=answer,
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
            sources=sources,
            retrieval_metadata=retrieval_metadata,
        )

    # -----------------------------------------------------
    # STEP 5: GENERAL LLM
    # -----------------------------------------------------

    elif intent == "LLM_ONLY":

        # General banking questions use fallback mode.
        model_result = _generate_general_fallback(
            message=message,
            task=task or "LLM_ONLY",
            parameters=parameters,
        )

        answer = _get_answer(model_result)

        return _make_response(
            answer=answer,
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    # -----------------------------------------------------
    # STEP 6: OUT OF SCOPE
    # -----------------------------------------------------

    elif intent == "OUT_OF_SCOPE":

        return _make_response(
            answer=(
                "I am not trained to answer these types of "
                "questions. I can assist with supported "
                "HDFC banking queries."
            ),
            message=message,
            intent=intent,
            task=task,
            current_user=current_user,
        )

    # -----------------------------------------------------
    # STEP 7: UNKNOWN INTENT
    # -----------------------------------------------------

    return _make_response(
        answer=(
            "I could not identify the type of your question. "
            "Please rephrase it as a banking-related question."
        ),
        message=message,
        intent=intent,
        task=task,
        current_user=current_user,
    )
