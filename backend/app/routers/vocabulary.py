import logging

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.services.dictionary_service import define

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("/define")
async def define_word(
    word: str = Query(..., min_length=1, max_length=100),
    lang: str = Query(default="en", pattern=r"^(en|ru|kk)$"),
    online: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
):
    return await define(word, lang, online)
