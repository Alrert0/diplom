import logging
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.services.ai_service import _call_ollama, _stream_ollama, OllamaError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a knowledgeable book assistant. You can discuss ANY book, author, or literary topic — "
    "recommendations, summaries, comparisons, analysis, reading lists, genres, literary history, and more. "
    "You are passionate about books and reading.\n\n"
    "Rules:\n"
    "1. Answer any question about books, authors, literature, reading, and related topics.\n"
    "2. If asked about non-book topics (weather, sports, coding, politics, cooking, math, etc.), "
    "politely say: 'I can only help with questions about books, authors, and literature. "
    "What would you like to know about books?'\n"
    "3. When recommending or discussing books, if any of them are marked as available in our library, "
    "mention that so the user knows they can read them right away.\n"
    "4. Be helpful, enthusiastic, and knowledgeable about world literature.\n"
    "5. You can discuss books in any language — English, Russian, Kazakh, and others.\n"
    "6. Respond in the same language the user writes in."
)

SUGGESTION_PROMPTS = {
    "en": [
        "Recommend me a classic novel",
        "What should I read if I liked 1984?",
        "Tell me about Dostoevsky's best works",
        "Suggest a book for a beginner reader",
    ],
    "ru": [
        "Порекомендуй классический роман",
        "Что почитать, если мне понравился «1984»?",
        "Расскажи о лучших произведениях Достоевского",
        "Посоветуй книгу для начинающего читателя",
    ],
    "kk": [
        "Классикалық роман ұсын",
        "Маған «1984» ұнаса, не оқуым керек?",
        "Абайдың ең жақсы шығармалары туралы айт",
        "Жаңа оқырманға кітап ұсын",
    ],
}


def _extract_search_terms(message: str) -> list[str]:
    """Extract potential book title / author keywords from the user message for DB lookup."""
    quoted = re.findall(r'["\u201c\u201e\u00ab](.+?)["\u201d\u201f\u00bb]', message)
    capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', message)
    terms = quoted + capitalized
    if not terms:
        words = [w for w in message.split() if len(w) > 3 and w[0].isupper()]
        terms = words
    return terms


async def _find_matching_books(db: AsyncSession, message: str) -> list[Book]:
    """Search the database for books that might be mentioned in the user's message."""
    terms = _extract_search_terms(message)
    if not terms:
        return []

    found: dict[int, Book] = {}
    for term in terms[:5]:
        search = f"%{term}%"
        result = await db.execute(
            select(Book).where(
                Book.title.ilike(search) | Book.author.ilike(search)
            ).limit(5)
        )
        for book in result.scalars().all():
            found[book.id] = book

    return list(found.values())[:5]


def _build_user_message(message: str, matching_books: list[Book], total_books: int) -> str:
    """Build the user message with library context."""
    context_parts = []
    if matching_books:
        lines = []
        for b in matching_books:
            line = f'- "{b.title}" by {b.author}'
            if b.genre:
                line += f" ({b.genre})"
            if b.description:
                desc = b.description[:100] + "..." if len(b.description) > 100 else b.description
                line += f" — {desc}"
            lines.append(line)
        context_parts.append(
            "These books are available in our library:\n" + "\n".join(lines)
        )

    context_parts.append(f"Our library has {total_books} books in total.")
    context = "\n\n".join(context_parts)

    return (
        f"Library context:\n{context}\n\n"
        f"---\n\n"
        f"User question: {message}"
    )


async def chat_with_assistant(
    message: str,
    language: str,
    db: AsyncSession,
) -> dict:
    """General book assistant chat (non-streaming)."""
    matching_books = await _find_matching_books(db, message)
    count_result = await db.execute(select(func.count(Book.id)))
    total_books = count_result.scalar() or 0

    user_message = _build_user_message(message, matching_books, total_books)

    try:
        answer = await _call_ollama(SYSTEM_PROMPT, user_message)
        return {"answer": answer, "total_books": total_books}
    except OllamaError as e:
        raise e


async def chat_with_assistant_stream(
    message: str,
    language: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """General book assistant chat (streaming). Yields text chunks."""
    matching_books = await _find_matching_books(db, message)
    count_result = await db.execute(select(func.count(Book.id)))
    total_books = count_result.scalar() or 0

    user_message = _build_user_message(message, matching_books, total_books)

    async for token in _stream_ollama(SYSTEM_PROMPT, user_message):
        yield token


def get_suggestions(language: str) -> list[str]:
    """Return conversation starter suggestions for the given language."""
    return SUGGESTION_PROMPTS.get(language, SUGGESTION_PROMPTS["en"])
