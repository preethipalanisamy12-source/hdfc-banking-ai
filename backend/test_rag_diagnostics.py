
from dotenv import load_dotenv

load_dotenv()

from rag.retrieval.retriever import retrieve_context

questions = [
    "Explain the refund policy for failed transactions",
    "What is the minimum balance in a savings account?",
    "How can I update my registered mobile number?"
]

for question in questions:
    print("\n" + "=" * 80)
    print("QUESTION:", question)

    result = retrieve_context(question=question, top_k=5)

    print("\nRETRIEVAL METADATA:")
    print(result["retrieval_metadata"])

    print("\nRETRIEVED SOURCES:")
    for source in result["sources"]:
        print(source)

    print("\nRETRIEVED CONTEXT:")
    print(result["context"][:2500])
