import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
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
    """Save or update a summary in the cache (upsert via DELETE + INSERT)."""
    await db.execute(
        delete(SummaryCache).where(
            SummaryCache.book_id == book_id,
            SummaryCache.chapter_number == chapter_number,
            SummaryCache.summary_type == summary_type,
        )
    )
    db.add(SummaryCache(
        book_id=book_id,
        chapter_number=chapter_number,
        summary_type=summary_type,
        content=content,
    ))
    await db.commit()


@router.post("/summary", response_model=AIResponse)
async def generate_summary(
    data: SummaryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarize a specific chapter (with caching)."""
    # Check cache first (skip if force_refresh)
    if not data.force_refresh:
        cached = await _get_cached_summary(db, data.book_id, data.chapter_number, "chapter")
        if cached:
            logger.info("Cache hit for book %d chapter %d summary", data.book_id, data.chapter_number)
            return AIResponse(content=cached)

    # Fetch book language
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    language = (book.language or "en")[:2].lower()
    if language not in ("en", "ru", "kk"):
        language = "en"

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
            language=language,
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
    if not data.force_refresh:
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

    # Use book language
    book = await db.get(Book, data.book_id)
    language = "en"
    if book:
        language = (book.language or "en")[:2].lower()
        if language not in ("en", "ru", "kk"):
            language = "en"

    try:
        summary = await summarize_progress(
            chapter_texts,
            language=language,
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
        # Fallback: answer from first few chapters directly (no vector search)
        stmt = (
            select(Chapter)
            .where(Chapter.book_id == data.book_id)
            .order_by(Chapter.chapter_number)
            .limit(5)
        )
        fallback_chapters = (await db.execute(stmt)).scalars().all()
        if not fallback_chapters:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No content found for this book.")
        context = "\n\n".join(
            f"[Chapter {ch.chapter_number}: {ch.title}]\n{ch.content[:1500]}"
            for ch in fallback_chapters
        )
        from app.services.ai_service import _call_ollama, _get_prompt
        system = (
            "You are a book reading assistant. Answer the user's question based on the provided book excerpts. "
            "IMPORTANT: Respond in the same language the user used to ask the question. "
            "Do NOT show your reasoning. Output only the final answer."
        )
        user_msg = f"Book excerpts:\n{context}\n\nQuestion: {data.message}"
        try:
            answer = await _call_ollama(system, user_msg, long=True)
            return ChatResponse(answer=answer, sources=[])
        except OllamaError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    try:
        answer, sources = await chat_about_book(
            question=data.message,
            book_id=data.book_id,
            language="en",  # prompt is language-agnostic — model follows question language
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
        # Fallback: stream answer from first few chapters directly (no vector search)
        stmt = (
            select(Chapter)
            .where(Chapter.book_id == data.book_id)
            .order_by(Chapter.chapter_number)
            .limit(5)
        )
        fallback_chapters = (await db.execute(stmt)).scalars().all()
        if not fallback_chapters:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No content found for this book.")
        context = "\n\n".join(
            f"[Chapter {ch.chapter_number}: {ch.title}]\n{ch.content[:1500]}"
            for ch in fallback_chapters
        )
        from app.services.ai_service import _call_ollama
        system = (
            "You are a book reading assistant. Answer the user's question based on the provided book excerpts. "
            "IMPORTANT: Respond in the same language the user used to ask the question. "
            "Do NOT show your reasoning. Output only the final answer."
        )
        user_msg = f"Book excerpts:\n{context}\n\nQuestion: {data.message}"

        async def generate_fallback():
            try:
                answer = await _call_ollama(system, user_msg, long=True)
                yield answer
            except OllamaError as e:
                yield f"[Error: {e}]"

        return StreamingResponse(generate_fallback(), media_type="text/plain; charset=utf-8")

    async def generate():
        try:
            async for chunk in chat_about_book_stream(
                question=data.message,
                book_id=data.book_id,
                language="en",
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
