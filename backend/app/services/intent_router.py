
import logging

from app.services.llm_service import classify_customer_query


logger = logging.getLogger(__name__)


class IntentRouter:

    # SQL tasks actually implemented in sql_service.py
    SUPPORTED_SQL_TASKS = {
        "GET_CUSTOMER_ACCOUNTS",
        "GET_ACCOUNT_BALANCE",
        "GET_TRANSACTION_SUMMARY",
        "GET_RECENT_TRANSACTIONS",
        "GET_FAILED_TRANSACTIONS",
        "GET_PENDING_TRANSACTIONS",
    }

    SUPPORTED_INTENTS = {
        "SQL",
        "RAG",
        "SQL_RAG",
        "LLM_ONLY",
        "OUT_OF_SCOPE",
    }

    def predict_intent(self, message: str) -> dict:
        """
        Classify the customer question using fine-tuned Qwen.

        Validate the returned intent and SQL task.
        Do not execute unsupported SQL tasks.
        """

        # ---------------------------------------------
        # 1. Validate input
        # ---------------------------------------------

        if not isinstance(message, str) or not message.strip():
            raise ValueError("Message cannot be empty.")

        message = message.strip()

        # ---------------------------------------------
        # 2. Call fine-tuned Qwen
        # ---------------------------------------------

        routing = classify_customer_query(message)

        if not isinstance(routing, dict):
            raise ValueError(
                "Intent classifier returned an invalid response."
            )

        # ---------------------------------------------
        # 3. Check required fields
        # ---------------------------------------------

        required_fields = [
            "intent",
            "task",
            "parameters",
            "requires_sql",
            "requires_rag",
        ]

        missing = [
            field
            for field in required_fields
            if field not in routing
        ]

        if missing:
            raise ValueError(
                f"Missing routing fields: {missing}"
            )

        # ---------------------------------------------
        # 4. Normalize intent
        # ---------------------------------------------

        intent = str(routing["intent"]).strip().upper()

        if intent not in self.SUPPORTED_INTENTS:
            raise ValueError(
                f"Unsupported intent returned by Qwen: {intent}"
            )

        routing["intent"] = intent

        # ---------------------------------------------
        # 5. Validate parameters
        # ---------------------------------------------

        parameters = routing.get("parameters")

        if parameters is None:
            parameters = {}

        if not isinstance(parameters, dict):
            raise ValueError(
                "Intent router parameters must be a dictionary."
            )

        routing["parameters"] = parameters

        # ---------------------------------------------
        # 6. Normalize task
        # ---------------------------------------------

        task = routing.get("task")

        if isinstance(task, str):
            task = task.strip().upper()

        routing["task"] = task

        # ---------------------------------------------
        # 7. Validate routing flags
        # ---------------------------------------------

        if not isinstance(routing["requires_sql"], bool):
            raise ValueError("requires_sql must be boolean.")

        if not isinstance(routing["requires_rag"], bool):
            raise ValueError("requires_rag must be boolean.")

        # ---------------------------------------------
        # 8. Validate intent and routing consistency
        # ---------------------------------------------

        if intent == "SQL":

            if not routing["requires_sql"]:
                raise ValueError(
                    "SQL intent requires requires_sql=True."
                )

        elif intent == "RAG":

            if not routing["requires_rag"]:
                raise ValueError(
                    "RAG intent requires requires_rag=True."
                )

        elif intent == "SQL_RAG":

            if not routing["requires_sql"] or not routing["requires_rag"]:
                raise ValueError(
                    "SQL_RAG requires both SQL and RAG."
                )

        elif intent in {"LLM_ONLY", "OUT_OF_SCOPE"}:

            if routing["requires_sql"] or routing["requires_rag"]:
                raise ValueError(
                    f"{intent} cannot require SQL or RAG."
                )

        # ---------------------------------------------
        # 9. Check supported SQL task
        # ---------------------------------------------

        if routing["requires_sql"]:

            if not task:
                raise ValueError(
                    "SQL routing requires a task name."
                )

            if task not in self.SUPPORTED_SQL_TASKS:

                logger.warning(
                    "Unsupported SQL task returned by Qwen: %s",
                    task
                )

                # Keep the original intent.
                # chat_service.py will return a friendly
                # unsupported-task response before SQL execution.

                routing["unsupported_sql_task"] = True

            else:
                routing["unsupported_sql_task"] = False

        else:
            routing["unsupported_sql_task"] = False

        # ---------------------------------------------
        # 10. Debug logs
        # ---------------------------------------------

        logger.info("========== INTENT ROUTER DEBUG ==========")
        logger.info("Question: %s", message)
        logger.info("Intent: %s", routing["intent"])
        logger.info("Task: %s", routing["task"])
        logger.info("Parameters: %s", routing["parameters"])
        logger.info("Requires SQL: %s", routing["requires_sql"])
        logger.info("Requires RAG: %s", routing["requires_rag"])
        logger.info(
            "Unsupported SQL task: %s",
            routing["unsupported_sql_task"]
        )
        logger.info("=========================================")

        return routing


# =================================================
# SHARED ROUTER INSTANCE
# =================================================

intent_router = IntentRouter()
