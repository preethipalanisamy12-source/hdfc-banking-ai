
from app.services.rag_service import get_relevant_context

question = "What should a customer do if their debit card is lost?"

try:
    result = get_relevant_context(question, top_k=5)

    print("\nCONTEXT:")
    print(result["context"])

    print("\nSOURCES:")
    print(result["sources"])

    print("\nRETRIEVAL METADATA:")
    print(result["retrieval_metadata"])

except Exception as e:
    print("RAG test failed:", type(e).__name__, str(e))
