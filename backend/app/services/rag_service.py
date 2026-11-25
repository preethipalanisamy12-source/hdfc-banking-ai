
from dotenv import load_dotenv

# Load backend .env before importing the RAG module.
load_dotenv()

from rag.retrieval.retriever import (
    retrieve_context,
    RagUnavailable
)


def get_relevant_context(
    question: str,
    top_k: int = 5
) -> dict:
    """
    Retrieve relevant knowledge-base context.

    Returns:
        {
            "context": str,
            "sources": list,
            "retrieval_metadata": dict
        }
    """

    try:
        result = retrieve_context(
            question=question,
            top_k=top_k
        )

        return result

    except RagUnavailable:
        # Do not expose database or model internals to customers.
        raise
