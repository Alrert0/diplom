import json
import logging
import re
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.services.embedding_service import search_similar

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT = 120.0  # seconds — LLM generation can be slow

OLLAMA_OPTIONS = {"num_ctx": 4096, "num_predict": 300, "temperature": 0.7}

# Regex to strip qwen3 think-aloud blocks from content.
# Matches everything up to and including </think> (with optional whitespace).
_THINK_TAG_RE = re.compile(r"^.*?</think>\s*", re.DOTALL)

# Reasoning-line patterns that qwen3 leaks into content even with think:false.
_REASONING_PREFIXES = (
    "Okay,", "Okay ", "Hmm", "Wait", "Let me", "I need", "I should",
    "I recall", "First,", "First ", "So,", "So ", "Ah!", "Better ",
    "*checks", "*double", "*types", "...User", "...Wait", "Done.",
    "Final decision:", "The user",
)

# System prompts per language
SUMMARY_PROMPTS = {
    "en": (
        "You are a book reading assistant. Write a structured summary of the given chapter text. "
        "Include: key events, important characters, and the main idea. "
        "Keep it concise: 3-5 sentences."
    ),
    "ru": (
        "Ты — помощник по чтению книг. Напиши структурированное резюме данной главы. "
        "Включи: ключевые события, важных персонажей и главную идею. "
        "Будь кратким: 3-5 предложений. Отвечай на русском языке."
    ),
    "kk": (
        "Сен — кітап оқу көмекшісісің. Берілген тараудың құрылымдық түйіндемесін жаз. "
        "Негізгі оқиғалар, маңызды кейіпкерлер және басты идеяны қамти. "
        "Қысқаша жаз: 3-5 сөйлем. Қазақ тілінде жауап бер."
    ),
}

PROGRESS_PROMPTS = {
    "en": (
        "You are a book reading assistant. Summarize everything the reader has read so far. "
        "Highlight the main plot points, character development, and key themes. "
        "Write a cohesive summary in 5-10 sentences."
    ),
    "ru": (
        "Ты — помощник по чтению книг. Подведи итог всему, что читатель прочитал до этого момента. "
        "Выдели основные сюжетные линии, развитие персонажей и ключевые темы. "
        "Напиши связное резюме в 5-10 предложений. Отвечай на русском языке."
    ),
    "kk": (
        "Сен — кітап оқу көмекшісісің. Оқырман осы уақытқа дейін оқығанның бәрін түйіндеп жаз. "
        "Негізгі сюжет желілерін, кейіпкерлердің дамуын және басты тақырыптарды атап өт. "
        "5-10 сөйлемнен тұратын байланысты түйіндеме жаз. Қазақ тілінде жауап бер."
    ),
}

CHAT_PROMPTS = {
    "en": (
        "You are a book reading assistant. Answer the user's question ONLY based on the provided book text excerpts. "
        "If the answer is not in the provided text, clearly state that the information is not available in the book. "
        "Never use outside knowledge. Cite specific parts of the text when possible."
    ),
    "ru": (
        "Ты — помощник по чтению книг. Отвечай на вопрос пользователя ТОЛЬКО на основе предоставленных отрывков из книги. "
        "Если ответа нет в тексте, чётко скажи, что информация в книге отсутствует. "
        "Никогда не используй внешние знания. По возможности ссылайся на конкретные части текста. "
        "Отвечай на русском языке."
    ),
    "kk": (
        "Сен — кітап оқу көмекшісісің. Пайдаланушының сұрағына ТАҚЫРЫПТАН берілген кітап мәтінінің үзінділері негізінде ғана жауап бер. "
        "Егер жауап мәтінде болмаса, ақпарат кітапта жоқ екенін анық айт. "
        "Сыртқы білімді ешқашан пайдаланба. Мүмкіндігінше мәтіннің нақты бөліктеріне сілтеме жаса. "
        "Қазақ тілінде жауап бер."
    ),
}


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""
    pass


def _strip_reasoning(text: str) -> str:
    """Remove qwen3 think-aloud reasoning from the response text.

    qwen3 often outputs a </think> tag — everything before it is reasoning.
    If no tag is present, strip leading paragraphs that look like internal monologue.
    """
    if not text:
        return text

    # 1. If there's a </think> tag, take only what follows it.
    if "</think>" in text:
        text = _THINK_TAG_RE.sub("", text)
        return text.strip()

    # 2. Otherwise, strip leading reasoning paragraphs.
    paragraphs = text.split("\n\n")
    cleaned = []
    found_real = False
    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue
        if not found_real:
            # Check if this paragraph is reasoning
            if any(stripped.startswith(p) for p in _REASONING_PREFIXES):
                continue  # skip this reasoning paragraph
            found_real = True
        cleaned.append(para)

    result = "\n\n".join(cleaned).strip()
    # If we accidentally stripped everything, return original
    return result if result else text.strip()


async def _call_ollama(system_prompt: str, user_message: str) -> str:
    """Send a chat completion request to Ollama (non-streaming)."""
    url = f"{settings.OLLAMA_URL}/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "think": False,
        "options": OLLAMA_OPTIONS,
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["message"].get("content", "")
            return _strip_reasoning(content)
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama at %s", settings.OLLAMA_URL)
        raise OllamaError("Ollama service is not available. Please ensure Ollama is running.")
    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        raise OllamaError("Ollama request timed out. The model may be loading or the text is too long.")
    except httpx.HTTPStatusError as e:
        logger.error("Ollama HTTP error: %s", e.response.text)
        raise OllamaError(f"Ollama returned an error: {e.response.status_code}")
    except Exception as e:
        logger.error("Unexpected Ollama error: %s", e)
        raise OllamaError(f"Unexpected error communicating with Ollama: {e}")


async def _stream_ollama(system_prompt: str, user_message: str) -> AsyncGenerator[str, None]:
    """Send a streaming chat completion request to Ollama, yielding text chunks.

    Buffers output until the </think> tag is found (or until we're past the
    reasoning preamble), then starts yielding clean content.
    """
    url = f"{settings.OLLAMA_URL}/api/chat"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": True,
        "think": False,
        "options": OLLAMA_OPTIONS,
    }

    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                buffer = ""
                think_done = False

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if data.get("done"):
                            # Flush any remaining buffer
                            if buffer and not think_done:
                                cleaned = _strip_reasoning(buffer)
                                if cleaned:
                                    yield cleaned
                            break

                        if not token:
                            continue

                        if think_done:
                            # Already past reasoning — yield directly
                            yield token
                        else:
                            buffer += token
                            # Check if we've hit the </think> boundary
                            if "</think>" in buffer:
                                after = _THINK_TAG_RE.sub("", buffer)
                                think_done = True
                                if after.strip():
                                    yield after
                                buffer = ""
                            # Or check if buffer has enough to detect reasoning end:
                            # If we see 2+ paragraph breaks, check if we're past reasoning
                            elif buffer.count("\n\n") >= 2:
                                cleaned = _strip_reasoning(buffer)
                                # If cleaning removed text, reasoning is still in progress
                                if cleaned != buffer.strip() and cleaned:
                                    # We found real content — emit it and switch to direct mode
                                    think_done = True
                                    yield cleaned
                                    buffer = ""
                    except json.JSONDecodeError:
                        continue
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama at %s", settings.OLLAMA_URL)
        raise OllamaError("Ollama service is not available. Please ensure Ollama is running.")
    except httpx.TimeoutException:
        logger.error("Ollama stream timed out")
        raise OllamaError("Ollama request timed out.")
    except httpx.HTTPStatusError as e:
        logger.error("Ollama HTTP error: %s", e.response.text)
        raise OllamaError(f"Ollama returned an error: {e.response.status_code}")
    except OllamaError:
        raise
    except Exception as e:
        logger.error("Unexpected Ollama stream error: %s", e)
        raise OllamaError(f"Unexpected error communicating with Ollama: {e}")


def _get_prompt(prompts: dict, language: str) -> str:
    """Get prompt for language, falling back to English."""
    return prompts.get(language, prompts["en"])


def _truncate_words(text: str, max_words: int) -> str:
    """Truncate text to max_words, appending a note if truncated."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "\n\n[Text truncated for summary]"


async def summarize_chapter(chapter_text: str, language: str = "en") -> str:
    """Generate a summary of a single chapter."""
    system_prompt = _get_prompt(SUMMARY_PROMPTS, language)
    chapter_text = _truncate_words(chapter_text, 2000)
    return await _call_ollama(system_prompt, chapter_text)


async def summarize_progress(chapters_texts: list[str], language: str = "en") -> str:
    """Summarize everything the reader has read so far."""
    system_prompt = _get_prompt(PROGRESS_PROMPTS, language)

    combined_parts = []
    for i, text in enumerate(chapters_texts, 1):
        truncated = _truncate_words(text, 500)
        combined_parts.append(f"--- Chapter {i} ---\n{truncated}")

    combined = "\n\n".join(combined_parts)
    combined = _truncate_words(combined, 3000)

    return await _call_ollama(system_prompt, combined)


async def chat_about_book(
    question: str,
    book_id: int,
    language: str = "en",
) -> tuple[str, list[str]]:
    """
    RAG-based Q&A about a book (non-streaming).
    Returns (answer, source_chunks).
    """
    system_prompt = _get_prompt(CHAT_PROMPTS, language)

    source_chunks = await search_similar(query=question, book_id=book_id, top_k=3)

    if not source_chunks:
        return (
            "No relevant text found in the book for this question. "
            "The book may not be indexed yet.",
            [],
        )

    context_parts = []
    for i, chunk in enumerate(source_chunks, 1):
        truncated = _truncate_words(chunk, 300)
        context_parts.append(f"[Excerpt {i}]\n{truncated}")
    context = "\n\n".join(context_parts)

    user_message = (
        f"Book text excerpts:\n\n{context}\n\n"
        f"---\n\n"
        f"Question: {question}"
    )

    answer = await _call_ollama(system_prompt, user_message)
    return answer, source_chunks


async def chat_about_book_stream(
    question: str,
    book_id: int,
    language: str = "en",
) -> AsyncGenerator[str, None]:
    """
    RAG-based Q&A about a book (streaming).
    Yields text chunks as they arrive from the LLM.
    """
    system_prompt = _get_prompt(CHAT_PROMPTS, language)

    source_chunks = await search_similar(query=question, book_id=book_id, top_k=3)

    if not source_chunks:
        yield "No relevant text found in the book for this question. The book may not be indexed yet."
        return

    context_parts = []
    for i, chunk in enumerate(source_chunks, 1):
        truncated = _truncate_words(chunk, 300)
        context_parts.append(f"[Excerpt {i}]\n{truncated}")
    context = "\n\n".join(context_parts)

    user_message = (
        f"Book text excerpts:\n\n{context}\n\n"
        f"---\n\n"
        f"Question: {question}"
    )

    async for token in _stream_ollama(system_prompt, user_message):
        yield token
