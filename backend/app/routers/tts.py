import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.tts_service import synthesize, get_available_voices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["tts"])

MAX_TEXT_LENGTH = 5000


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    language: str = Field(default="en", pattern=r"^(en|ru|kk)$")
    gender: str = Field(default="female", pattern=r"^(male|female)$")
    offline: bool = False


@router.post("/synthesize")
async def synthesize_text(
    body: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        audio_bytes, content_type = await synthesize(
            text=body.text,
            language=body.language,
            gender=body.gender,
            use_offline=body.offline,
        )
    except Exception as e:
        logger.error("TTS synthesis failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"TTS synthesis failed: {e}",
        )

    return Response(
        content=audio_bytes,
        media_type=content_type,
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )


@router.get("/voices")
async def list_voices(
    current_user: User = Depends(get_current_user),
):
    return get_available_voices()
