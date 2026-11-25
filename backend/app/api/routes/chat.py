
from fastapi import APIRouter, Depends

from app.schemas.chat import ChatRequest
from app.core.auth_dependency import get_current_user
from app.services.chat_service import process_chat

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"]
)


@router.post("/")
def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    return process_chat(
        message=request.message,
        current_user=current_user
    )
