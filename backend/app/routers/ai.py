import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book, Chapter
from app.models.reading import ReadingProgress
from app.models.summary_cache import SummaryCache
from app.models.user import User
from app.schemas.ai import (
    SummaryRequest,
    SummaryProgressRequest,
    ChatRequest,
    AIResponse,
    ChatResponse,
    TextRankResponse,
)
from app.services.ai_service import (
    summarize_chapter,
    summarize_progress,
    chat_about_book,
    chat_about_book_stream,
    OllamaError,
)
from app.services.embedding_service import is_book_indexed
from app.ml.textrank import extract_key_sentences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

CACHE_TTL_DAYS = 7


async def _get_cached_summary(
    db: AsyncSession, book_id: int, chapter_number: int, summary_type: str
) -> str | None:
    """Return cached summary if it exists and is fresh (< 7 days old)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
    result = await db.execute(
        select(SummaryCache).where(
            SummaryCache.book_id == book_id,
            SummaryCache.chapter_number == chapter_number,
            SummaryCache.summary_type == summary_type,
            SummaryCache.created_at >= cutoff,
        )
    )
    cached = result.scalar_one_or_none()
    return cached.content if cached else None


async def _save_cached_summary(
    db: AsyncSession, book_id: int, chapter_number: int, summary_type: str, content: str
) -> None:
    """Save or update a summary in the cache."""
    # Delete old entry if exists
    result = await db.execute(
        select(SummaryCache).where(
            SummaryCache.book_id == book_id,
            SummaryCache.chapter_number == chapter_number,
            SummaryCache.summary_type == summary_type,
        )
    )
    old = result.scalar_one_or_none()
    if old:
        await db.delete(old)

    cache_entry = SummaryCache(
        book_id=book_id,
        chapter_number=chapter_number,
        summary_type=summary_type,
        content=content,
    )
    db.add(cache_entry)
    await db.commit()


@router.post("/summary", response_model=AIResponse)
async def generate_summary(
    data: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize a specific chapter (with caching)."""
    # Check cache first
    cached = await _get_cached_summary(db, data.book_id, data.chapter_number, "chapter")
    if cached:
        logger.info("Cache hit for book %d chapter %d summary", data.book_id, data.chapter_number)
        return AIResponse(content=cached)

    # Fetch chapter
    stmt = select(Chapter).where(
        Chapter.book_id == data.book_id,
        Chapter.chapter_number == data.chapter_number,
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    try:
        summary = await summarize_chapter(
            chapter.content,
            language=current_user.language_pref or "en",
        )
        # Save to cache
        await _save_cached_summary(db, data.book_id, data.chapter_number, "chapter", summary)
        return AIResponse(content=summary)
    except OllamaError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.post("/summary-progress", response_model=AIResponse)
async def generate_progress_summary(
    data: SummaryProgressRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize everything the user has read so far (with caching)."""
    # Get reading progress
    stmt = select(ReadingProgress).where(
        ReadingProgress.user_id == current_user.id,
        ReadingProgress.book_id == data.book_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    current_chapter = progress.current_chapter if progress else 1

    # Check cache — use current_chapter as the chapter_number for progress summaries
    cached = await _get_cached_summary(db, data.book_id, current_chapter, "progress")
    if cached:
        logger.info("Cache hit for book %d progress summary (ch %d)", data.book_id, current_chapter)
        return AIResponse(content=cached)

    # Fetch all chapters up to current
    stmt = (
        select(Chapter)
        .where(
            Chapter.book_id == data.book_id,
            Chapter.chapter_number <= current_chapter,
        )
        .order_by(Chapter.chapter_number)
    )
    result = await db.execute(stmt)
    chapters = result.scalars().all()

    if not chapters:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No chapters found for this book",
        )

    chapter_texts = [ch.content for ch in chapters]

    try:
        summary = await summarize_progress(
            chapter_texts,
            language=current_user.language_pref or "en",
        )
        # Save to cache
        await _save_cached_summary(db, data.book_id, current_chapter, "progress", summary)
        return AIResponse(content=summary)
    except OllamaError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """RAG-based Q&A about a book's content."""
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    indexed = await is_book_indexed(data.book_id, db)
    if not indexed:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Book is being indexed, please try again shortly.",
        )

    try:
        answer, sources = await chat_about_book(
            question=data.message,
            book_id=data.book_id,
            language=current_user.language_pref or "en",
        )
        return ChatResponse(answer=answer, sources=sources)
    except OllamaError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )


@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming RAG-based Q&A about a book's content."""
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )

    indexed = await is_book_indexed(data.book_id, db)
    if not indexed:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail="Book is being indexed, please try again shortly.",
        )

    async def generate():
        try:
            async for chunk in chat_about_book_stream(
                question=data.message,
                book_id=data.book_id,
                language=current_user.language_pref or "en",
            ):
                yield chunk
        except OllamaError as e:
            yield f"\n\n[Error: {e}]"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@router.get("/textrank", response_model=TextRankResponse)
async def textrank_summary(
    book_id: int,
    chapter_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract key sentences from a chapter using TextRank algorithm."""
    stmt = select(Chapter).where(
        Chapter.book_id == book_id,
        Chapter.chapter_number == chapter_number,
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chapter not found",
        )

    sentences = extract_key_sentences(chapter.content, top_n=5)
    return TextRankResponse(sentences=sentences)
