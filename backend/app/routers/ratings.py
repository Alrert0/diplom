import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book
from app.models.rating import Rating
from app.models.user import User
from app.schemas.book import RatingCreate, RatingResponse, BookResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


class BookWithRating(BookResponse):
    avg_rating: float | None = None
    ratings_count: int = 0


@router.post("", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def rate_book(
    data: RatingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify book exists
    book = await db.get(Book, data.book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    # Check if user already rated this book — update if so
    stmt = select(Rating).where(
        Rating.user_id == current_user.id,
        Rating.book_id == data.book_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.score = data.score
        existing.review_text = data.review_text
        await db.commit()
        await db.refresh(existing)
        return existing

    rating = Rating(
        user_id=current_user.id,
        book_id=data.book_id,
        score=data.score,
        review_text=data.review_text,
    )
    db.add(rating)
    await db.commit()
    await db.refresh(rating)

    logger.info("User %d rated book %d: %d stars", current_user.id, data.book_id, data.score)
    return rating


@router.get("/book/{book_id}", response_model=list[RatingResponse])
async def get_book_ratings(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    stmt = (
        select(Rating)
        .where(Rating.book_id == book_id)
        .order_by(Rating.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/trending", response_model=list[BookWithRating])
async def trending_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top 10 most rated books in the last 7 days."""
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stmt = (
        select(
            Book,
            func.avg(Rating.score).label("avg_rating"),
            func.count(Rating.id).label("ratings_count"),
        )
        .join(Rating, Rating.book_id == Book.id)
        .where(Rating.created_at >= one_week_ago)
        .group_by(Book.id)
        .order_by(desc("ratings_count"))
        .limit(10)
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


@router.get("/top", response_model=list[BookWithRating])
async def top_rated_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Top 10 highest rated books overall (minimum 1 rating)."""
    stmt = (
        select(
            Book,
            func.avg(Rating.score).label("avg_rating"),
            func.count(Rating.id).label("ratings_count"),
        )
        .join(Rating, Rating.book_id == Book.id)
        .group_by(Book.id)
        .having(func.count(Rating.id) >= 1)
        .order_by(desc("avg_rating"))
        .limit(10)
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
