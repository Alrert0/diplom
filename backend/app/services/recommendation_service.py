"""Orchestrates ML models: recommendations, reading speed, clustering."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, Chapter
from app.models.rating import Rating
from app.models.reading import ReadingProgress, ReadingSession
from app.models.user import User
from app.ml.recommender import BookRecommender
from app.ml.reading_speed import ReadingSpeedPredictor, DEFAULT_WPM
from app.ml.clustering import ReaderClustering, GENRES

logger = logging.getLogger(__name__)

# Singleton instances — loaded once, reused across requests
_recommender = BookRecommender()
_speed_predictor = ReadingSpeedPredictor()
_clustering = ReaderClustering()
_models_loaded = False


def _ensure_loaded():
    global _models_loaded
    if not _models_loaded:
        _recommender.load()
        _speed_predictor.load()
        _clustering.load()
        _models_loaded = True


# ------------------------------------------------------------------
# Recommendations
# ------------------------------------------------------------------

async def get_recommendations(user_id: int, db: AsyncSession, n: int = 10) -> list[dict]:
    """Get personalized book recommendations for a user."""
    _ensure_loaded()

    # Fetch user's rated books
    result = await db.execute(
        select(Rating.book_id, Rating.score).where(Rating.user_id == user_id)
    )
    user_ratings = result.all()
    rated_ids = {r.book_id for r in user_ratings}

    # All book IDs
    result = await db.execute(select(Book.id))
    all_book_ids = [row[0] for row in result.all()]

    recommended_ids: list[int] = []

    # Try SVD first (requires ≥3 ratings)
    if len(user_ratings) >= 3 and _recommender.svd_model is not None:
        recommended_ids = _recommender.get_recommendations(
            user_id, all_book_ids, rated_ids, n=n
        )

    # Fallback: content-based
    if not recommended_ids:
        liked_ids = [r.book_id for r in user_ratings if r.score >= 4]
        if liked_ids and _recommender.tfidf_matrix is not None:
            recommended_ids = _recommender.content_based_recommendations(
                liked_ids, rated_ids, n=n
            )

    # Final fallback: top-rated books the user hasn't rated
    if not recommended_ids:
        result = await db.execute(
            select(Book.id)
            .outerjoin(Rating, (Rating.book_id == Book.id) & (Rating.user_id == user_id))
            .where(Rating.id.is_(None))
            .order_by(Book.created_at.desc())
            .limit(n)
        )
        recommended_ids = [row[0] for row in result.all()]

    if not recommended_ids:
        return []

    # Fetch book details
    result = await db.execute(
        select(Book).where(Book.id.in_(recommended_ids))
    )
    books_map = {b.id: b for b in result.scalars().all()}

    # Preserve recommendation order
    recommendations = []
    for bid in recommended_ids:
        book = books_map.get(bid)
        if book:
            recommendations.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "genre": book.genre,
                "language": book.language,
                "cover_url": book.cover_url,
                "description": book.description,
            })

    return recommendations


# ------------------------------------------------------------------
# Reading time estimate
# ------------------------------------------------------------------

async def get_reading_time_estimate(
    user_id: int, book_id: int, chapter_number: int, db: AsyncSession
) -> dict:
    """Personalized reading time estimate for chapter and book."""
    _ensure_loaded()

    # Get chapter and book info
    result = await db.execute(
        select(Chapter).where(Chapter.book_id == book_id, Chapter.chapter_number == chapter_number)
    )
    chapter = result.scalar_one_or_none()

    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()

    if not chapter or not book:
        return {"chapter_minutes": 0, "book_minutes": 0, "wpm": DEFAULT_WPM}

    # Get user's average reading speed from sessions
    result = await db.execute(
        select(
            func.sum(ReadingSession.words_read),
            func.sum(ReadingSession.time_spent_seconds),
            func.count(ReadingSession.id),
        ).where(ReadingSession.user_id == user_id)
    )
    row = result.one()
    total_words = row[0] or 0
    total_seconds = row[1] or 0
    total_sessions = row[2] or 0

    user_avg_speed = (total_words / total_seconds * 60) if total_seconds > 0 else 0.0

    # Predict WPM
    now = datetime.now()
    wpm = _speed_predictor.predict(
        chapter_word_count=chapter.word_count,
        genre=book.genre,
        hour_of_day=now.hour,
        day_of_week=now.weekday(),
        user_avg_speed=user_avg_speed,
        user_total_sessions=total_sessions,
    )

    # Calculate remaining words for book
    result = await db.execute(
        select(func.sum(Chapter.word_count))
        .where(Chapter.book_id == book_id, Chapter.chapter_number >= chapter_number)
    )
    book_words_left = result.scalar() or 0

    chapter_minutes = _speed_predictor.estimate_time(chapter.word_count, wpm)
    book_minutes = _speed_predictor.estimate_time(book_words_left, wpm)

    return {
        "chapter_minutes": chapter_minutes,
        "book_minutes": book_minutes,
        "wpm": round(wpm, 1),
        "chapter_words": chapter.word_count,
        "book_words_remaining": book_words_left,
    }


# ------------------------------------------------------------------
# User stats
# ------------------------------------------------------------------

async def get_user_stats(user_id: int, db: AsyncSession) -> dict:
    """Aggregate reading statistics for a user."""
    _ensure_loaded()

    # Total books read (have reading progress)
    result = await db.execute(
        select(func.count(ReadingProgress.id)).where(ReadingProgress.user_id == user_id)
    )
    total_books = result.scalar() or 0

    # Reading sessions stats
    result = await db.execute(
        select(
            func.sum(ReadingSession.words_read),
            func.sum(ReadingSession.time_spent_seconds),
            func.count(ReadingSession.id),
        ).where(ReadingSession.user_id == user_id)
    )
    row = result.one()
    total_words_read = row[0] or 0
    total_seconds = row[1] or 0
    total_sessions = row[2] or 0
    avg_speed = (total_words_read / total_seconds * 60) if total_seconds > 0 else DEFAULT_WPM

    # Ratings stats
    result = await db.execute(
        select(func.count(Rating.id), func.avg(Rating.score)).where(Rating.user_id == user_id)
    )
    row = result.one()
    total_ratings = row[0] or 0
    avg_rating = float(row[1]) if row[1] else 0.0

    # Cluster info
    cluster = _clustering.get_cluster(user_id)

    return {
        "total_books": total_books,
        "total_words_read": total_words_read,
        "total_reading_hours": round(total_seconds / 3600, 1),
        "total_sessions": total_sessions,
        "avg_speed_wpm": round(avg_speed, 1),
        "total_ratings": total_ratings,
        "avg_rating_given": round(avg_rating, 2),
        "cluster": cluster,
    }


# ------------------------------------------------------------------
# Model training
# ------------------------------------------------------------------

async def retrain_models(db: AsyncSession) -> dict:
    """Retrain all ML models with latest data."""
    results = {}
    loop = asyncio.get_event_loop()

    # 1. Train recommender (SVD)
    rating_rows = await db.execute(select(Rating.user_id, Rating.book_id, Rating.score))
    ratings_data = [(r[0], r[1], float(r[2])) for r in rating_rows.all()]

    if ratings_data:
        svd_result = await loop.run_in_executor(None, _recommender.train, ratings_data)
        results["svd"] = svd_result

    # 1b. Train content-based
    book_rows = await db.execute(select(Book.id, Book.description))
    books_data = [(r[0], r[1] or "") for r in book_rows.all()]
    if books_data:
        await loop.run_in_executor(None, _recommender.train_content_based, books_data)
        results["tfidf"] = {"n_books": len(books_data)}

    # 2. Train reading speed predictor
    session_rows = await db.execute(
        select(
            ReadingSession.user_id,
            ReadingSession.words_read,
            ReadingSession.time_spent_seconds,
            ReadingSession.session_start,
            Chapter.word_count,
            Book.genre,
        )
        .join(Chapter, ReadingSession.chapter_id == Chapter.id)
        .join(Book, ReadingSession.book_id == Book.id)
        .where(ReadingSession.time_spent_seconds > 0)
    )
    raw_sessions = session_rows.all()

    if raw_sessions:
        # Compute per-user aggregates
        user_stats: dict[int, dict] = {}
        for s in raw_sessions:
            uid = s[0]
            if uid not in user_stats:
                user_stats[uid] = {"total_words": 0, "total_seconds": 0, "count": 0}
            user_stats[uid]["total_words"] += s[1]
            user_stats[uid]["total_seconds"] += s[2]
            user_stats[uid]["count"] += 1

        sessions_data = []
        for s in raw_sessions:
            uid = s[0]
            words_read, time_seconds = s[1], s[2]
            if time_seconds <= 0:
                continue
            actual_wpm = words_read / time_seconds * 60
            if actual_wpm < 10 or actual_wpm > 2000:
                continue  # filter outliers

            us = user_stats[uid]
            avg_speed = (us["total_words"] / us["total_seconds"] * 60) if us["total_seconds"] > 0 else DEFAULT_WPM
            session_start = s[3]

            sessions_data.append({
                "chapter_word_count": s[4],
                "genre": s[5],
                "hour_of_day": session_start.hour if session_start else 12,
                "day_of_week": session_start.weekday() if session_start else 0,
                "user_avg_speed": avg_speed,
                "user_total_sessions": us["count"],
                "actual_wpm": actual_wpm,
            })

        if sessions_data:
            speed_result = await loop.run_in_executor(None, _speed_predictor.train, sessions_data)
            results["speed"] = speed_result

    # 3. Train clustering
    user_rows = await db.execute(select(User.id))
    all_user_ids = [r[0] for r in user_rows.all()]

    users_data = []
    for uid in all_user_ids:
        # Genre counts
        genre_rows = await db.execute(
            select(Book.genre, func.count(Book.id))
            .join(ReadingProgress, ReadingProgress.book_id == Book.id)
            .where(ReadingProgress.user_id == uid)
            .group_by(Book.genre)
        )
        genre_counts = {r[0]: r[1] for r in genre_rows.all() if r[0]}

        # Aggregates
        sess_row = await db.execute(
            select(
                func.sum(ReadingSession.words_read),
                func.sum(ReadingSession.time_spent_seconds),
                func.count(ReadingSession.id),
            ).where(ReadingSession.user_id == uid)
        )
        sr = sess_row.one()
        total_w = sr[0] or 0
        total_s = sr[1] or 0
        n_sess = sr[2] or 0

        rating_row = await db.execute(
            select(func.avg(Rating.score)).where(Rating.user_id == uid)
        )
        avg_r = rating_row.scalar() or 3.0

        progress_row = await db.execute(
            select(func.count(ReadingProgress.id)).where(ReadingProgress.user_id == uid)
        )
        total_books = progress_row.scalar() or 0

        avg_speed = (total_w / total_s * 60) if total_s > 0 else DEFAULT_WPM
        avg_session_min = (total_s / max(n_sess, 1)) / 60

        users_data.append({
            "user_id": uid,
            "genre_counts": genre_counts,
            "total_books": total_books,
            "avg_speed": avg_speed,
            "avg_rating": float(avg_r),
            "avg_session_minutes": avg_session_min,
        })

    if len(users_data) >= 6:
        vectors = _clustering.build_user_vectors(users_data)
        cluster_result = await loop.run_in_executor(None, _clustering.train, vectors)
        results["clustering"] = cluster_result
    else:
        results["clustering"] = {"skipped": True, "reason": f"need ≥6 users, have {len(users_data)}"}

    return results
