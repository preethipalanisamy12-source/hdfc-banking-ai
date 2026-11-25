
from app.services.chat_service import process_chat

# Use an actual authenticated user's details from your database.
current_user = {
    "user_id": 1,
    "email": "customer@example.com",
    "role": "CUSTOMER"
}

questions = [
    "Show my last five transactions",
    "Show my failed transactions",
    "Show my pending transactions",
    "What is my account balance?",
    "Show my accounts",
    "Give me my transaction summary"
]

for question in questions:
    print("\nQUESTION:", question)

    try:
        result = process_chat(question, current_user)

        print("INTENT:", result["intent"])
        print("TASK:", result["task"])
        print("ANSWER:", result["answer"])

    except Exception as error:
        print("ERROR:", repr(error))
