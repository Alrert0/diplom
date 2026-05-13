"""
Re-parse chapters for books already in the database using the current book_service logic.

Usage:
    cd backend
    python -m scripts.reparse_chapters --all              # rebuild all books
    python -m scripts.reparse_chapters --book-id 12       # rebuild one book
    python -m scripts.reparse_chapters --all --dry-run    # preview only

For each book it:
  1. Reads the original EPUB from book.epub_path
  2. Re-parses chapters via parse_epub()
  3. Deletes old chapters (cascades reading_sessions, book_embeddings)
  4. Inserts new chapters and updates book.total_chapters / total_words
  5. Resets reading_progress.current_chapter to 1 for that book (chapter numbering changes)
"""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import create_engine, select, delete, update
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.models.book import Book, Chapter
from app.models.rating import Rating  # noqa: F401  (registered for FK metadata)
from app.models.reading import ReadingProgress, ReadingSession  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.book_service import parse_epub

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_sync_url() -> str:
    """Convert async DATABASE_URL to sync (asyncpg → psycopg2)."""
    url = settings.DATABASE_URL
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"


def _resolve_epub_path(book: Book) -> Path | None:
    """Find the EPUB file for a book. Backfills book.epub_path from epub_filename if needed."""
    if book.epub_path:
        p = Path(book.epub_path)
        if p.exists():
            return p
    if book.epub_filename:
        p = UPLOADS_DIR / book.epub_filename
        if p.exists():
            # Backfill the missing epub_path
            book.epub_path = str(p)
            return p
    return None


def reparse_one(session: Session, book: Book, dry_run: bool) -> tuple[int, int]:
    """Re-parse a single book. Returns (old_chapter_count, new_chapter_count)."""
    epub_path = _resolve_epub_path(book)
    if epub_path is None:
        logger.warning("[%s] EPUB not found (epub_path=%s, epub_filename=%s) — skipping",
                       book.title[:50], book.epub_path, book.epub_filename)
        return (book.total_chapters, book.total_chapters)

    old_count = session.execute(
        select(Chapter).where(Chapter.book_id == book.id)
    ).scalars().all()
    old_n = len(old_count)

    try:
        data = parse_epub(str(epub_path))
    except Exception as e:
        logger.error("[%s] parse failed: %s", book.title, e)
        return (old_n, old_n)

    new_n = len(data.chapters)
    sample = "; ".join(repr(c.title)[:40] for c in data.chapters[:3])
    logger.info(
        "[%s] %d -> %d chapters | sample: %s",
        book.title[:50], old_n, new_n, sample,
    )

    if dry_run:
        return (old_n, new_n)

    # Delete old chapters (cascades reading_sessions, book_embeddings)
    session.execute(delete(Chapter).where(Chapter.book_id == book.id))
    session.flush()

    # Insert new chapters (strip NUL bytes — Postgres text rejects 0x00)
    for ch in data.chapters:
        session.add(Chapter(
            book_id=book.id,
            chapter_number=ch.chapter_number,
            title=(ch.title or "").replace("\x00", ""),
            content=ch.content.replace("\x00", ""),
            word_count=ch.word_count,
        ))

    # Update book counters
    book.total_chapters = new_n
    book.total_words = data.total_words

    # Reset reading progress for this book — chapter IDs/numbers changed
    session.execute(
        update(ReadingProgress)
        .where(ReadingProgress.book_id == book.id)
        .values(current_chapter=1, current_position=0.0, cfi_position=None)
    )

    session.commit()
    return (old_n, new_n)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="reparse every book")
    parser.add_argument("--book-id", type=int, help="reparse a single book by id")
    parser.add_argument("--dry-run", action="store_true", help="preview only, do not write")
    args = parser.parse_args()

    if not args.all and args.book_id is None:
        parser.error("specify --all or --book-id N")

    engine = create_engine(get_sync_url(), echo=False)
    with Session(engine) as session:
        if args.book_id is not None:
            books = session.execute(
                select(Book).where(Book.id == args.book_id)
            ).scalars().all()
        else:
            books = session.execute(select(Book).order_by(Book.id)).scalars().all()

        if not books:
            logger.warning("No books found")
            return

        logger.info("Reparsing %d book(s) (dry_run=%s)", len(books), args.dry_run)
        total_old = 0
        total_new = 0
        for book in books:
            old_n, new_n = reparse_one(session, book, args.dry_run)
            total_old += old_n
            total_new += new_n

        logger.info(
            "Done. Total chapters: %d -> %d (delta %+d)",
            total_old, total_new, total_new - total_old,
        )


if __name__ == "__main__":
    main()
