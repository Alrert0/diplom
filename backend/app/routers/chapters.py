import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book
from app.models.reading import ReadingProgress
from app.models.user import User
from app.schemas.book import ReadingProgressUpdate, ReadingProgressResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reading", tags=["reading"])


class BookProgressResponse(BaseModel):
    book_id: int
    title: str
    author: str
    cover_url: Optional[str] = None
    current_chapter: int
    total_chapters: int
    percent: float  # 0-100
    last_read_at: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("/in-progress", response_model=list[BookProgressResponse])
async def get_in_progress_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all books the user has started reading, with progress percentage."""
    stmt = select(ReadingProgress, Book).join(
        Book, Book.id == ReadingProgress.book_id
    ).where(
        ReadingProgress.user_id == current_user.id
    ).order_by(ReadingProgress.last_read_at.desc())

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for progress, book in rows:
        total = book.total_chapters or 1
        pct = min(100.0, round(progress.current_chapter / total * 100, 1))
        items.append(BookProgressResponse(
            book_id=book.id,
            title=book.title,
            author=book.author,
            cover_url=book.cover_url,
            current_chapter=progress.current_chapter,
            total_chapters=total,
            percent=pct,
            last_read_at=progress.last_read_at.isoformat() if progress.last_read_at else None,
        ))
    return items


@router.put("/progress", response_model=ReadingProgressResponse)
async def update_reading_progress(
    data: ReadingProgressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify book exists
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    # Find existing progress or create new
    stmt = select(ReadingProgress).where(
        ReadingProgress.user_id == current_user.id,
        ReadingProgress.book_id == data.book_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if progress:
        progress.current_chapter = data.current_chapter
        progress.current_position = data.current_position
        progress.cfi_position = data.cfi_position
    else:
        progress = ReadingProgress(
            user_id=current_user.id,
            book_id=data.book_id,
            current_chapter=data.current_chapter,
            current_position=data.current_position,
            cfi_position=data.cfi_position,
        )
        db.add(progress)

    await db.commit()
    await db.refresh(progress)

    logger.info(
        "Reading progress updated: user=%d book=%d chapter=%d pos=%.2f",
        current_user.id, data.book_id, data.current_chapter, data.current_position,
    )
    return progress


@router.get("/progress/{book_id}", response_model=ReadingProgressResponse)
async def get_reading_progress(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ReadingProgress).where(
        ReadingProgress.user_id == current_user.id,
        ReadingProgress.book_id == book_id,
    )
    result = await db.execute(stmt)
    progress = result.scalar_one_or_none()

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No reading progress found for this book",
        )

    return progress
