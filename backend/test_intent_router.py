from app.services.intent_router import intent_router

result = intent_router.predict_intent(
    "Show my last five transactions"
)

print("Intent:", result["intent"])
print("Task:", result["task"])
print("Parameters:", result["parameters"])
print("Requires SQL:", result["requires_sql"])
print("Requires RAG:", result["requires_rag"])