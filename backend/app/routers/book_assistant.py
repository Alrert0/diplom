from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.services.ai_service import OllamaError
from app.services.book_assistant_service import (
    chat_with_assistant,
    chat_with_assistant_stream,
    get_suggestions,
)

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AssistantChatRequest(BaseModel):
    message: str
    language: str = "en"


class AssistantChatResponse(BaseModel):
    answer: str
    total_books: int


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


@router.post("/chat", response_model=AssistantChatResponse)
async def assistant_chat(
    req: AssistantChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """General AI book assistant chat (non-streaming)."""
    try:
        result = await chat_with_assistant(
            message=req.message,
            language=req.language,
            db=db,
        )
        return result
    except OllamaError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
async def assistant_chat_stream(
    req: AssistantChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """General AI book assistant chat (streaming)."""
    async def generate():
        try:
            async for chunk in chat_with_assistant_stream(
                message=req.message,
                language=req.language,
                db=db,
            ):
                yield chunk
        except OllamaError as e:
            yield f"\n\n[Error: {e}]"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_chat_suggestions(
    language: str = "en",
    user: User = Depends(get_current_user),
):
    """Get conversation starter suggestions."""
    return {"suggestions": get_suggestions(language)}
