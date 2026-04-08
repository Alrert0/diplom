"""
Bulk import books from Project Gutenberg into AI Book Reader.

Usage:
    cd backend
    python -m scripts.bulk_import_gutenberg --count 50

Downloads EPUB files, parses them with book_service.parse_epub(),
and stores books + chapters in the database. Skips duplicates by title.
Does NOT run embeddings (too slow for bulk import).
"""

import argparse
import asyncio
import logging
import os
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

# Add backend/ to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.models.book import Book, Chapter
from app.models.rating import Rating
from app.models.reading import ReadingProgress, ReadingSession
from app.models.user import User
from app.database import Base
from app.services.book_service import parse_epub, save_cover

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# Curated list of ~200 popular Project Gutenberg book IDs
# ──────────────────────────────────────────────────────────────────

GUTENBERG_BOOKS: list[tuple[int, str, str]] = [
    # (id, expected_title, genre)
    # ── Fiction Classics ──
    (1342, "Pride and Prejudice", "fiction"),
    (11, "Alice's Adventures in Wonderland", "children"),
    (1661, "The Adventures of Sherlock Holmes", "mystery"),
    (84, "Frankenstein", "science-fiction"),
    (1952, "The Yellow Wallpaper", "fiction"),
    (98, "A Tale of Two Cities", "fiction"),
    (2701, "Moby Dick", "fiction"),
    (1400, "Great Expectations", "fiction"),
    (46, "A Christmas Carol", "fiction"),
    (174, "The Picture of Dorian Gray", "fiction"),
    (345, "Dracula", "fiction"),
    (16328, "Beowulf", "fiction"),
    (1232, "The Prince", "philosophy"),
    (25344, "The Scarlet Letter", "fiction"),
    (5200, "Metamorphosis", "fiction"),
    (2591, "Grimms' Fairy Tales", "children"),
    (2554, "Crime and Punishment", "fiction"),
    (1080, "A Modest Proposal", "fiction"),
    (74, "The Adventures of Tom Sawyer", "adventure"),
    (76, "Adventures of Huckleberry Finn", "adventure"),
    (1260, "Jane Eyre", "fiction"),
    (768, "Wuthering Heights", "fiction"),
    (35, "The Time Machine", "science-fiction"),
    (36, "The War of the Worlds", "science-fiction"),
    (43, "The Strange Case of Dr. Jekyll and Mr. Hyde", "mystery"),
    (120, "Treasure Island", "adventure"),
    (2852, "The Hound of the Baskervilles", "mystery"),
    (161, "Sense and Sensibility", "fiction"),
    (1184, "The Count of Monte Cristo", "adventure"),
    (16, "Peter Pan", "children"),
    (55, "The Wonderful Wizard of Oz", "children"),
    (1727, "The Odyssey", "fiction"),
    (6130, "The Iliad", "fiction"),
    (2600, "War and Peace", "fiction"),
    (28054, "The Brothers Karamazov", "fiction"),
    (730, "Oliver Twist", "fiction"),
    (1998, "Thus Spake Zarathustra", "philosophy"),
    (3207, "Leviathan", "philosophy"),
    (1497, "The Republic", "philosophy"),
    (996, "Don Quixote", "fiction"),
    (244, "A Study in Scarlet", "mystery"),
    (2097, "The Sign of the Four", "mystery"),
    (108, "Tarzan of the Apes", "adventure"),
    (3600, "Essays of Michel de Montaigne", "philosophy"),
    (135, "Les Misérables", "fiction"),
    (1399, "Anna Karenina", "fiction"),
    (2542, "A Doll's House", "fiction"),
    (514, "Little Women", "fiction"),
    (1250, "Anthem", "fiction"),
    (164, "Twenty Thousand Leagues Under the Sea", "science-fiction"),
    (103, "Around the World in Eighty Days", "adventure"),
    (44881, "A Room with a View", "fiction"),
    (5740, "Tractatus Logico-Philosophicus", "philosophy"),
    (815, "Democracy in America — Volume 1", "philosophy"),
    (4300, "Ulysses", "fiction"),
    (1023, "Bleak House", "fiction"),
    (766, "David Copperfield", "fiction"),
    (580, "The Jungle Book", "children"),
    (45, "Anne of Green Gables", "children"),
    (209, "The Turn of the Screw", "mystery"),
    (219, "Heart of Darkness", "fiction"),
    (1322, "Leaves of Grass", "fiction"),
    (2148, "The Phantom of the Opera", "mystery"),
    (1934, "Candide", "fiction"),
    (6761, "The Adventures of Pinocchio", "children"),
    (33, "The Scarlet Pimpernel", "adventure"),
    (58585, "The Prophet", "philosophy"),
    (132, "The Art of War", "philosophy"),
    (10, "The King James Bible", "philosophy"),

    # ── Science Fiction ──
    (62, "A Princess of Mars", "science-fiction"),
    (65, "The Time Machine", "science-fiction"),
    (155, "The Moonstone", "mystery"),
    (215, "The Call of the Wild", "adventure"),
    (236, "The Jungle Book", "children"),
    (829, "Gulliver's Travels", "adventure"),
    (1164, "The Iron Heel", "science-fiction"),
    (2009, "The Origin of Species", "science"),
    (5230, "The Invisible Man", "science-fiction"),
    (1695, "The Island of Doctor Moreau", "science-fiction"),
    (159, "The Last of the Mohicans", "adventure"),
    (3825, "Pygmalion", "fiction"),
    (4363, "The Food of the Gods", "science-fiction"),
    (19942, "Candide", "fiction"),
    (8800, "The Divine Comedy", "fiction"),
    (2500, "Siddhartha", "fiction"),
    (73540, "R.U.R.", "science-fiction"),

    # ── Mystery & Detective ──
    (1661, "Sherlock Holmes (dup guard)", "mystery"),
    (2350, "The Memoirs of Sherlock Holmes", "mystery"),
    (1661, "Adventures of Sherlock Holmes", "mystery"),
    (3289, "The Return of Sherlock Holmes", "mystery"),
    (244, "A Study in Scarlet (dup)", "mystery"),
    (834, "The Moonstone", "mystery"),
    (863, "The Mysterious Affair at Styles", "mystery"),
    (58866, "The Secret Adversary", "mystery"),

    # ── Adventure ──
    (234, "The Count of Monte Cristo (dup)", "adventure"),
    (27827, "The Kama Sutra", "philosophy"),
    (30254, "The Romance of Lust", "fiction"),
    (140, "The Jungle", "fiction"),
    (4217, "A Portrait of the Artist as a Young Man", "fiction"),
    (5827, "The Problems of Philosophy", "philosophy"),
    (4705, "A Room with a View", "fiction"),
    (1727, "The Odyssey (dup)", "fiction"),

    # ── More Fiction ──
    (2814, "Dubliners", "fiction"),
    (1794, "The Importance of Being Earnest", "fiction"),
    (110, "Tess of the d'Urbervilles", "fiction"),
    (1260, "Jane Eyre (dup)", "fiction"),
    (47629, "Persuasion", "fiction"),
    (105, "Persuasion", "fiction"),
    (158, "Emma", "fiction"),
    (141, "Mansfield Park", "fiction"),
    (121, "Northanger Abbey", "fiction"),
    (375, "The Yellow Wallpaper", "fiction"),
    (41, "The Legend of Sleepy Hollow", "fiction"),
    (2148, "Phantom Opera (dup)", "mystery"),
    (408, "The Souls of Black Folk", "fiction"),
    (910, "White Fang", "adventure"),
    (5348, "The Secret Garden", "children"),
    (32, "Herland", "fiction"),
    (17396, "Walden", "philosophy"),
    (10007, "Meditations", "philosophy"),
    (10681, "Uncle Tom's Cabin", "fiction"),
    (28885, "Nicomachean Ethics", "philosophy"),
    (2680, "Meditations", "philosophy"),
    (15399, "Aesop's Fables", "children"),
    (23, "Narrative of the Life of Frederick Douglass", "fiction"),
    (7370, "Second Treatise of Government", "philosophy"),
    (3296, "The Confessions of St. Augustine", "philosophy"),

    # ── Russian Literature (English translations on Gutenberg) ──
    (600, "Notes from the Underground", "fiction"),
    (2554, "Crime and Punishment (dup)", "fiction"),
    (28054, "Brothers Karamazov (dup)", "fiction"),
    (1399, "Anna Karenina (dup)", "fiction"),
    (986, "Dead Souls", "fiction"),
    (7100, "The Death of Ivan Ilyich", "fiction"),
    (1399, "Anna Karenina (dup2)", "fiction"),

    # ── Children's & Young Adult ──
    (19033, "A Little Princess", "children"),
    (113, "The Secret Garden", "children"),
    (514, "Little Women (dup)", "fiction"),
    (1260, "Jane Eyre (dup2)", "fiction"),
    (932, "The Wind in the Willows", "children"),
    (1184, "Monte Cristo (dup)", "adventure"),
    (2680, "Meditations (dup)", "philosophy"),
    (844, "The Importance of Being Earnest", "fiction"),

    # ── Science & Non-Fiction ──
    (4280, "The Federalist Papers", "philosophy"),
    (4657, "A Vindication of the Rights of Woman", "philosophy"),
    (3076, "On Liberty", "philosophy"),
    (7142, "The Communist Manifesto", "philosophy"),
    (36, "War of the Worlds (dup)", "science-fiction"),
    (30, "The Bible, King James (dup)", "philosophy"),
    (5001, "The Koran", "philosophy"),
    (2346, "The Social Contract", "philosophy"),
    (3300, "An Inquiry into the Nature and Causes of the Wealth of Nations", "philosophy"),
    (15776, "Beyond Good and Evil", "philosophy"),
    (34901, "The Communist Manifesto (dup)", "philosophy"),
    (100, "The Complete Works of Shakespeare", "fiction"),
    (37106, "The Critique of Pure Reason", "philosophy"),
    (1228, "On the Origin of Species (dup)", "science"),

    # ── Poetry ──
    (1322, "Leaves of Grass (dup)", "fiction"),
    (8147, "The Raven", "fiction"),
    (10, "Bible (dup)", "philosophy"),

    # ── Horror & Gothic ──
    (345, "Dracula (dup)", "fiction"),
    (84, "Frankenstein (dup)", "science-fiction"),
    (14833, "The Legend of Sleepy Hollow", "fiction"),
    (209, "Turn of the Screw (dup)", "mystery"),
    (25525, "The Haunted House", "fiction"),

    # ── More Science Fiction ──
    (20869, "Flatland", "science-fiction"),
    (17157, "Fantastic Fables", "fiction"),
    (35, "Time Machine (dup)", "science-fiction"),
    (624, "Looking Backward: 2000-1887", "science-fiction"),
    (3597, "The Lost World", "adventure"),
    (13415, "She", "adventure"),

    # ── Historical Fiction ──
    (2160, "The Three Musketeers", "adventure"),
    (1257, "The Three Musketeers", "adventure"),
    (1259, "Twenty Years After", "adventure"),
    (696, "The Castle of Otranto", "fiction"),
    (42324, "Ivanhoe", "adventure"),
    (82, "Ivanhoe", "adventure"),

    # ── Fill to ~200 unique IDs ──
    (6593, "History of Tom Jones", "fiction"),
    (27780, "The Decameron", "fiction"),
    (14591, "Utopia", "philosophy"),
    (33283, "Calculus Made Easy", "science"),
    (8492, "The Three Musketeers (Gutenberg)", "adventure"),
    (7849, "The Analects of Confucius", "philosophy"),
    (15532, "Tao Te Ching", "philosophy"),
    (69087, "The Great Gatsby", "fiction"),
    (64317, "The Great Gatsby", "fiction"),
    (4517, "Emile", "philosophy"),
    (394, "Cranford", "fiction"),
    (2084, "The Rime of the Ancient Mariner", "fiction"),
    (1946, "Symposium", "philosophy"),
    (2130, "Phaedo", "philosophy"),
    (1656, "Autobiography of Benjamin Franklin", "fiction"),
    (11030, "The Enchanted April", "fiction"),
    (204, "The Awakening", "fiction"),
    (33, "Scarlet Pimpernel (dup)", "adventure"),
    (203, "Uncle Tom's Cabin", "fiction"),
    (78, "Tarzan of the Apes (dup)", "adventure"),
]

# ──────────────────────────────────────────────────────────────────
# Deduplicate by Gutenberg ID (keep first occurrence)
# ──────────────────────────────────────────────────────────────────

def _unique_books() -> list[tuple[int, str, str]]:
    seen_ids: set[int] = set()
    unique: list[tuple[int, str, str]] = []
    for gid, title, genre in GUTENBERG_BOOKS:
        if gid not in seen_ids:
            seen_ids.add(gid)
            unique.append((gid, title, genre))
    return unique


# ──────────────────────────────────────────────────────────────────
# Download helpers
# ──────────────────────────────────────────────────────────────────

EPUB_URL_TEMPLATES = [
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}-images-3.epub",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}-images.epub",
    "https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.epub",
    "https://www.gutenberg.org/ebooks/{gid}.epub.images",
    "https://www.gutenberg.org/ebooks/{gid}.epub.noimages",
]

HEADERS = {
    "User-Agent": "AIBookReader/1.0 (diploma project; bulk import; respectful crawling)",
}

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


async def download_epub(client: httpx.AsyncClient, gid: int) -> bytes | None:
    """Try multiple URL patterns to download an EPUB from Gutenberg."""
    for template in EPUB_URL_TEMPLATES:
        url = template.format(gid=gid)
        try:
            r = await client.get(url, follow_redirects=True, timeout=30.0)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.content
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────────
# Database (sync — simpler for a one-off script)
# ──────────────────────────────────────────────────────────────────

def get_sync_engine():
    from sqlalchemy import create_engine
    return create_engine(settings.DATABASE_URL_SYNC, echo=False)


def get_existing_titles(engine) -> set[str]:
    """Return set of lowercase book titles already in DB."""
    with Session(engine) as session:
        rows = session.execute(select(Book.title)).all()
        return {r[0].lower().strip() for r in rows if r[0]}


def save_book_to_db(engine, book_data, genre: str, epub_filename: str):
    """Save parsed book + chapters to database. Returns book.id or None."""
    with Session(engine) as session:
        book = Book(
            title=book_data.title,
            author=book_data.author,
            description=book_data.description or "",
            genre=genre,
            language=book_data.language,
            epub_filename=epub_filename,
            total_chapters=len(book_data.chapters),
            total_words=book_data.total_words,
        )
        session.add(book)
        session.flush()

        # Save cover
        if book_data.cover_image_bytes:
            try:
                book.cover_url = save_cover(book_data.cover_image_bytes, book.id)
            except Exception as e:
                logger.warning("  Cover save failed: %s", e)

        # Save chapters
        for ch in book_data.chapters:
            session.add(Chapter(
                book_id=book.id,
                chapter_number=ch.chapter_number,
                title=ch.title,
                content=ch.content,
                word_count=ch.word_count,
            ))

        session.commit()
        return book.id


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Bulk import books from Project Gutenberg")
    parser.add_argument("--count", type=int, default=200, help="Max books to download (default: 200)")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between downloads (default: 2)")
    args = parser.parse_args()

    books = _unique_books()[:args.count]
    total = len(books)

    logger.info("Starting bulk import: %d books (delay=%.1fs)", total, args.delay)

    engine = get_sync_engine()
    existing_titles = get_existing_titles(engine)
    logger.info("Found %d existing books in database", len(existing_titles))

    log_dir = Path(__file__).resolve().parent.parent
    fail_log = log_dir / "failed_imports.log"

    imported = 0
    skipped = 0
    failed = 0

    async with httpx.AsyncClient(headers=HEADERS) as client:
        for i, (gid, expected_title, genre) in enumerate(books, 1):
            # Skip if title already exists
            if expected_title.lower().strip() in existing_titles:
                logger.info("[%d/%d] SKIP (exists): %s", i, total, expected_title)
                skipped += 1
                continue

            logger.info("[%d/%d] Downloading: %s (PG#%d)...", i, total, expected_title, gid)

            # Download
            epub_bytes = await download_epub(client, gid)
            if not epub_bytes:
                logger.warning("[%d/%d] FAILED to download PG#%d: %s", i, total, gid, expected_title)
                failed += 1
                with open(fail_log, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} | PG#{gid} | {expected_title} | download_failed\n")
                await asyncio.sleep(args.delay)
                continue

            # Save EPUB to uploads/
            epub_filename = f"pg{gid}.epub"
            epub_path = UPLOADS_DIR / epub_filename
            epub_path.write_bytes(epub_bytes)

            # Parse
            try:
                book_data = parse_epub(str(epub_path))
            except Exception as e:
                logger.warning("[%d/%d] FAILED to parse PG#%d: %s — %s", i, total, gid, expected_title, e)
                failed += 1
                epub_path.unlink(missing_ok=True)
                with open(fail_log, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} | PG#{gid} | {expected_title} | parse_error: {e}\n")
                await asyncio.sleep(args.delay)
                continue

            if not book_data.chapters:
                logger.warning("[%d/%d] SKIP PG#%d: %s — no chapters extracted", i, total, gid, expected_title)
                failed += 1
                epub_path.unlink(missing_ok=True)
                with open(fail_log, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} | PG#{gid} | {expected_title} | no_chapters\n")
                await asyncio.sleep(args.delay)
                continue

            # Check again by parsed title (may differ from expected)
            if book_data.title.lower().strip() in existing_titles:
                logger.info("[%d/%d] SKIP (exists by parsed title): %s", i, total, book_data.title)
                skipped += 1
                epub_path.unlink(missing_ok=True)
                await asyncio.sleep(args.delay)
                continue

            # Save to DB
            try:
                book_id = save_book_to_db(engine, book_data, genre, epub_filename)
                existing_titles.add(book_data.title.lower().strip())
                imported += 1
                logger.info(
                    "[%d/%d] OK: \"%s\" by %s — %d chapters, %d words (id=%d)",
                    i, total, book_data.title, book_data.author,
                    len(book_data.chapters), book_data.total_words, book_id,
                )
            except Exception as e:
                logger.error("[%d/%d] FAILED to save PG#%d: %s — %s", i, total, gid, expected_title, e)
                failed += 1
                epub_path.unlink(missing_ok=True)
                with open(fail_log, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now().isoformat()} | PG#{gid} | {expected_title} | db_error: {e}\n")

            # Respectful delay
            await asyncio.sleep(args.delay)

    # ── Summary ──
    print()
    print("=" * 60)
    print(f"  BULK IMPORT COMPLETE")
    print(f"  Imported: {imported}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total processed: {imported + skipped + failed}/{total}")
    if failed > 0:
        print(f"  Failed log: {fail_log}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
