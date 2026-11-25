
import os
import requests

from dotenv import load_dotenv


load_dotenv()

MODEL_API_URL = os.getenv("MODEL_API_URL", "").rstrip("/")
MODEL_API_TOKEN = os.getenv("MODEL_API_TOKEN")


def _get_headers():
    """
    Prepare authentication headers for the Colab model API.
    """

    if not MODEL_API_URL:
        raise ValueError("MODEL_API_URL is missing from .env")

    if not MODEL_API_TOKEN:
        raise ValueError("MODEL_API_TOKEN is missing from .env")

    return {
        "Authorization": f"Bearer {MODEL_API_TOKEN}",
        "Content-Type": "application/json"
    }


def classify_customer_query(message: str) -> dict:
    """
    Call fine-tuned Qwen to predict:
    intent, task and query parameters.
    """

    if not message or not message.strip():
        raise ValueError("Customer message cannot be empty")

    url = f"{MODEL_API_URL}/predict-intent"

    payload = {
        "message": message
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=_get_headers(),
            timeout=180
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            raise RuntimeError(
                f"Intent prediction failed: {result}"
            )

        if not isinstance(result.get("routing"), dict):
            raise RuntimeError(
                "Invalid routing response from Qwen API"
            )

        return result["routing"]

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Could not connect to Qwen intent API: {exc}"
        ) from exc



def generate_customer_answer(
    message: str,
    task: str,
    query_params: dict = None,
    sql_result: dict = None,
    retrieved_chunks: dict = None,
    answer_mode: str = "GROUNDED"
) -> dict:
    """
    Generate a customer-facing answer using SQL and/or RAG evidence.
    """

    if not MODEL_API_URL or not MODEL_API_TOKEN:
        raise ValueError("Model API configuration is missing.")

    url = f"{MODEL_API_URL}/generate-answer"

    allowed_modes = {"GROUNDED", "GENERAL_FALLBACK"}
    if answer_mode not in allowed_modes:
        raise ValueError(
            f"Unsupported answer_mode: {answer_mode}. "
            f"Allowed values: {sorted(allowed_modes)}"
        )

    payload = {
        "message": message,
        "task": task,
        "query_params": query_params,
        "sql_result": sql_result,
        "retrieved_chunks": retrieved_chunks,
        "answer_mode": answer_mode
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=_get_headers(),
            timeout=180
        )

        response.raise_for_status()

        result = response.json()

        if not result.get("success"):
            raise RuntimeError(
                f"Answer generation failed: {result}"
            )

        return result

    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"Could not connect to Qwen answer API: {exc}"
        ) from exc
