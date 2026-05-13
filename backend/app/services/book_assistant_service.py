import logging
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.services.ai_service import _call_ollama, _stream_ollama, _strip_reasoning, OllamaError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a book assistant for an online reading platform. Answer ONLY the question — no reasoning, "
    "no analysis, no 'Alternatively...', no 'Maybe...', no 'Wait...', no 'If the user...', "
    "no 'I need to...', no thinking aloud.\n\n"
    "ANSWER FORMAT: Give a direct, factual answer in 1-3 sentences. Match the user's language.\n\n"
    "QUESTION TYPES:\n"
    "- General book question (who wrote X, what is X about): use your own knowledge. "
    "If you don't know for sure, say so briefly.\n"
    "- Platform question (do you have X, what books are available, recommend from your library): "
    "use the LIBRARY DATABASE section if provided.\n"
    "- Non-book topic: politely refuse in the user's language.\n\n"
    "EXAMPLES of GOOD answers:\n"
    "Q: Кто автор Войны и мира?\nA: Автор — Лев Толстой.\n\n"
    "Q: Who wrote 1984?\nA: George Orwell wrote 1984, published in 1949.\n\n"
    "Q: Есть ли у вас «Анна Каренина»?\nA: Да, есть в нашей библиотеке.\n\n"
    "EXAMPLES of BAD answers (NEVER do this):\n"
    "- 'Let me think...', 'Wait, maybe...', 'Alternatively...', 'The user is asking...'\n"
    "- Repeating the question\n"
    "- Showing your reasoning process"
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

    # Also try every word >= 4 chars from the message as a search term
    words = [w.strip("«»\"'.,!?") for w in message.split() if len(w.strip("«»\"'.,!?")) >= 4]
    all_terms = list(dict.fromkeys(terms + words))  # dedupe, preserve order

    if not all_terms:
        return []

    found: dict[int, Book] = {}
    for term in all_terms[:8]:
        search = f"%{term}%"
        result = await db.execute(
            select(Book).where(
                Book.title.ilike(search) | Book.author.ilike(search)
            ).limit(5)
        )
        for book in result.scalars().all():
            found[book.id] = book
        if found:
            break  # stop early if we already found matches

    return list(found.values())[:5]


_RECOMMENDATION_KEYWORDS = {
    # Recommendations
    "recommend", "suggest", "what to read", "что почитать", "посоветуй", "порекомендуй",
    "what should i read", "reading list", "similar to", "похожее", "список", "подбери",
    "ұсын", "қандай кітап", "оқуым керек",
    # Platform / library availability
    "available", "в наличии", "есть ли у вас", "есть ли в", "have you got",
    "у вас есть", "в вашей библиотеке", "в библиотеке", "на платформе",
    "your library", "your collection", "in your", "do you have",
    "сколько книг", "какие книги", "какие у вас",
}


def _is_recommendation_query(message: str) -> bool:
    """Return True if the user is asking for recommendations or library availability."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _RECOMMENDATION_KEYWORDS)


def _build_user_message(message: str, matching_books: list[Book], total_books: int) -> str:
    """Build the user message, adding DB-sourced book data as authoritative context."""
    is_rec = _is_recommendation_query(message)
    parts: list[str] = []

    if matching_books:
        lines = []
        for b in matching_books:
            line = f'Title: "{b.title}" | Author: {b.author}'
            if b.genre:
                line += f" | Genre: {b.genre}"
            if b.language:
                line += f" | Language: {b.language}"
            lines.append(line)
        parts.append(
            "LIBRARY DATABASE (authoritative — use for availability/recommendation answers):\n"
            + "\n".join(lines)
        )
    elif is_rec:
        parts.append(
            f"LIBRARY DATABASE: {total_books} books available. "
            "No specific matches found for this query — suggest from your general knowledge."
        )

    parts.append(f"User question: {message}")
    return "\n\n".join(parts)


async def _assistant_answer(message: str, matching_books: list[Book], total_books: int) -> str:
    """Call Ollama and return a clean, deduplicated answer."""
    user_message = _build_user_message(message, matching_books, total_books)
    raw = await _call_ollama(SYSTEM_PROMPT, user_message, long=True)
    result = _deduplicate(raw)

    # If model produced only reasoning, retry with minimalist prompt
    if not result:
        minimal_prompt = (
            "Answer in 1 short sentence. Match the user's language. "
            "No thinking, no 'Wait', no 'Alternatively', no 'Maybe'. Just the answer."
        )
        raw2 = await _call_ollama(minimal_prompt, message)
        result = _deduplicate(raw2)

    # Still empty? Return graceful fallback
    if not result:
        result = (
            "Не уверен в точном ответе на этот вопрос. "
            "Попробуйте уточнить запрос или спросить о другой книге."
        )

    return result


def _deduplicate(text: str) -> str:
    """Remove repeated sentences/paragraphs that small models sometimes generate."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for p in paragraphs:
        key = p.lower()[:80]  # compare first 80 chars to catch near-duplicates
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return "\n\n".join(unique)


async def chat_with_assistant(
    message: str,
    language: str,
    db: AsyncSession,
) -> dict:
    """General book assistant chat (non-streaming)."""
    matching_books = await _find_matching_books(db, message)
    count_result = await db.execute(select(func.count(Book.id)))
    total_books = count_result.scalar() or 0

    try:
        answer = await _assistant_answer(message, matching_books, total_books)
        return {"answer": answer, "total_books": total_books}
    except OllamaError as e:
        raise e


async def chat_with_assistant_stream(
    message: str,
    language: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """General book assistant chat. Uses non-streaming call so reasoning is fully stripped."""
    matching_books = await _find_matching_books(db, message)
    count_result = await db.execute(select(func.count(Book.id)))
    total_books = count_result.scalar() or 0

    try:
        answer = await _assistant_answer(message, matching_books, total_books)
        yield answer
    except OllamaError as e:
        yield f"[Ошибка: {e}]"


def get_suggestions(language: str) -> list[str]:
    """Return conversation starter suggestions for the given language."""
    return SUGGESTION_PROMPTS.get(language, SUGGESTION_PROMPTS["en"])
