import logging

from fastapi import APIRouter, Depends, HTTPException, status
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
