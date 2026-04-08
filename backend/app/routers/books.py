import logging
import os
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book, Chapter
from app.models.rating import Rating
from app.models.user import User
from app.schemas.book import BookResponse, ChapterResponse, ChapterDetailResponse
from app.services.book_service import parse_epub, save_cover
from app.services.embedding_service import index_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["books"])

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class BookWithRating(BookResponse):
    avg_rating: float | None = None
    ratings_count: int = 0


@router.post("/upload", response_model=BookWithRating, status_code=status.HTTP_201_CREATED)
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".epub"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only EPUB files are accepted",
        )

    # Generate a safe filename: slugify original name + uuid suffix
    stem = re.sub(r"[^\w\-]", "_", Path(file.filename).stem)
    safe_name = f"{stem}_{uuid.uuid4().hex[:8]}.epub"
    epub_path = UPLOADS_DIR / safe_name
    with open(epub_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse EPUB
    try:
        book_data = parse_epub(str(epub_path))
    except Exception as e:
        os.remove(epub_path)
        logger.error("Failed to parse EPUB: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse EPUB file: {e}",
        )

    # Create book record
    book = Book(
        title=book_data.title,
        author=book_data.author,
        description=book_data.description,
        language=book_data.language,
        epub_filename=safe_name,
        total_chapters=len(book_data.chapters),
        total_words=book_data.total_words,
        epub_path=str(epub_path),
    )
    db.add(book)
    await db.flush()  # Get book.id before saving cover

    # Save cover image
    if book_data.cover_image_bytes:
        try:
            book.cover_url = save_cover(book_data.cover_image_bytes, book.id)
        except Exception as e:
            logger.warning("Failed to save cover: %s", e)

    # Create chapter records
    chapter_records = []
    for ch in book_data.chapters:
        chapter = Chapter(
            book_id=book.id,
            chapter_number=ch.chapter_number,
            title=ch.title,
            content=ch.content,
            word_count=ch.word_count,
        )
        db.add(chapter)
        chapter_records.append((chapter, ch.content))

    await db.flush()  # Get chapter IDs

    # Collect data for background indexing before commit
    indexing_data = [
        {"id": rec.id, "content": content}
        for rec, content in chapter_records
    ]

    await db.commit()
    await db.refresh(book)

    # Trigger background indexing for RAG
    background_tasks.add_task(index_book, book.id, indexing_data)

    logger.info("Book uploaded: %s (id=%d, %d chapters)", book.title, book.id, book.total_chapters)
    return BookWithRating.model_validate(book)


@router.get("", response_model=list[BookWithRating])
async def list_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(
            Book,
            func.avg(Rating.score).label("avg_rating"),
            func.count(Rating.id).label("ratings_count"),
        )
        .outerjoin(Rating, Rating.book_id == Book.id)
        .group_by(Book.id)
        .order_by(Book.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    books = []
    for book, avg_rating, ratings_count in rows:
        data = BookWithRating.model_validate(book)
        data.avg_rating = round(float(avg_rating), 2) if avg_rating else None
        data.ratings_count = ratings_count
        books.append(data)

    return books


@router.get("/{book_id}", response_model=BookWithRating)
async def get_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(
            Book,
            func.avg(Rating.score).label("avg_rating"),
            func.count(Rating.id).label("ratings_count"),
        )
        .outerjoin(Rating, Rating.book_id == Book.id)
        .where(Book.id == book_id)
        .group_by(Book.id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    book, avg_rating, ratings_count = row
    data = BookWithRating.model_validate(book)
    data.avg_rating = round(float(avg_rating), 2) if avg_rating else None
    data.ratings_count = ratings_count
    return data


@router.get("/{book_id}/chapters", response_model=list[ChapterResponse])
async def list_chapters(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify book exists
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    stmt = (
        select(Chapter)
        .where(Chapter.book_id == book_id)
        .order_by(Chapter.chapter_number)
    )
    result = await db.execute(stmt)
    chapters = result.scalars().all()
    return chapters


@router.get("/{book_id}/chapters/{chapter_num}", response_model=ChapterDetailResponse)
async def get_chapter(
    book_id: int,
    chapter_num: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Chapter).where(
        Chapter.book_id == book_id,
        Chapter.chapter_number == chapter_num,
    )
    result = await db.execute(stmt)
    chapter = result.scalar_one_or_none()

    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chapter not found")

    return chapter
