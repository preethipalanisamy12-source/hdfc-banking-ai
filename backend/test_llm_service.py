
from app.services.llm_service import classify_customer_query


result = classify_customer_query(
    "Show my last five transactions"
)

print("QWEN ROUTING RESULT:")
print(result)
