import json
import logging
import re
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.services.embedding_service import search_similar

logger = logging.getLogger(__name__)

OLLAMA_TIMEOUT = 120.0  # seconds — LLM generation can be slow

OLLAMA_OPTIONS = {"num_ctx": 4096, "num_predict": 600, "temperature": 0.7}
OLLAMA_OPTIONS_LONG = {"num_ctx": 4096, "num_predict": 1200, "temperature": 0.7}

# Regex to strip qwen3 think-aloud blocks from content.
# Matches everything up to and including </think> (with optional whitespace).
_THINK_TAG_RE = re.compile(r"^.*?</think>\s*", re.DOTALL)

# Reasoning-line patterns that qwen3 leaks into content even with think:false.
# Covers English, Russian, and Kazakh inner-monologue openers.
_REASONING_PREFIXES = (
    # English
    "Okay,", "Okay ", "Hmm", "Wait", "Let me", "I need", "I should",
    "I recall", "First,", "First ", "So,", "So ", "Ah!", "Better ",
    "*checks", "*double", "*types", "...User", "...Wait", "Done.",
    "Final decision:", "The user", "I'll ", "I will ", "I have to",
    "I want to", "I'm going", "Now I", "Now,", "Now ", "Looking at",
    "Reading", "Analyzing", "Let's ", "Let us ",
    "But the", "But since", "But I", "But this", "But we",
    "Since the", "Since this", "Since I",
    "The question", "The answer", "The rules", "The system",
    "The context", "The library", "The book", "The note",
    "The user's", "The request", "The task", "The prompt",
    "According to", "Based on", "Per the", "Following the",
    "So the answer", "So I", "So this", "So we",
    "I don't", "I do ", "I can ", "I cannot", "I think",
    "Actually,", "Actually ", "Note:", "Note that",
    "Check:", "Step ", "Plan:", "My approach",
    "In this case", "In summary", "To summarize",
    "Possible ", "Possible:", "Option ", "Option:",
    "Alternatively,", "Alternatively ", "Maybe ", "Maybe,",
    "Perhaps,", "Perhaps ", "Wait,", "Wait ",
    "If the", "If it", "If this", "If that", "If we",
    "Given ", "Given that", "Given the",
    "It seems", "It looks", "It appears",
    "We need", "We have", "We can", "We should",
    "There is", "There are", "Here's", "Here is",
    # Russian
    "Хорошо,", "Хорошо ", "Итак,", "Итак ", "Нужно ", "Мне нужно",
    "Сначала,", "Сначала ", "Вижу,", "Вижу ", "Думаю,", "Думаю ",
    "Давайте", "Давай ", "Ок,", "Ок ", "Значит,", "Значит ",
    "Теперь,", "Теперь ", "Смотрю", "Читаю", "Анализирую",
    "Пользователь", "Нужно создать", "Нужно написать",
    "Я должен", "Я буду", "Я вижу", "Я читаю", "Я анализирую",
    "Я прочитаю", "Посмотрим", "Рассмотрим", "Итак, я",
    "Вопрос:", "Из отрывков", "Из предоставленных", "В предоставленных",
    "Но в контексте", "Возможно, ответ", "Возможно,", "Таким образом,",
    "В контексте", "Судя по", "На основе", "Исходя из",
    "Ответ:", "Итоговый ответ", "Финальный ответ",
    # Kazakh
    "Жарайды,", "Жарайды ", "Бірінші,", "Бірінші ",
    "Қарайық,", "Қарайық ", "Мен ", "Енді,", "Енді ",
)

# System prompts per language
_NO_THINK = (
    "Do NOT show your reasoning or thinking process. "
    "Output ONLY the final answer, nothing else."
)
_NO_THINK_RU = (
    "НЕ показывай свои рассуждения или процесс размышления. "
    "Выводи ТОЛЬКО готовый ответ, без предисловий."
)
_NO_THINK_KK = (
    "Ойлану үдерісіңді КӨРСЕТПЕ. ТІКЕЛЕЙ жауапты ғана жаз."
)

SUMMARY_PROMPTS = {
    "en": (
        "You are a book reading assistant. Write a short fluent summary of the given chapter: "
        "3-5 sentences, no headings or labels. "
        "Mention the main characters, key events, and the central idea. " + _NO_THINK
    ),
    "ru": (
        "Ты — помощник по чтению книг. Напиши краткое связное резюме данной главы: "
        "3-5 предложений, без заголовков и меток. "
        "Упомяни главных персонажей, ключевые события и основную идею. "
        "Пиши только на русском языке, готовым текстом. " + _NO_THINK_RU
    ),
    "kk": (
        "Сен — кітап оқу көмекшісісің. Берілген тараудың құрылымдық түйіндемесін жаз. "
        "Негізгі оқиғалар, маңызды кейіпкерлер және басты идеяны қамти. "
        "Қысқаша жаз: 3-5 сөйлем. Қазақ тілінде жауап бер. " + _NO_THINK_KK
    ),
}

PROGRESS_PROMPTS = {
    "en": (
        "You are a book reading assistant. Summarize everything the reader has read so far. "
        "Highlight the main plot points, character development, and key themes. "
        "Write a cohesive summary in 5-10 sentences. " + _NO_THINK
    ),
    "ru": (
        "Ты — помощник по чтению книг. Подведи итог всему, что читатель прочитал до этого момента. "
        "Выдели основные сюжетные линии, развитие персонажей и ключевые темы. "
        "Напиши связное резюме в 5-10 предложений. Отвечай на русском языке. " + _NO_THINK_RU
    ),
    "kk": (
        "Сен — кітап оқу көмекшісісің. Оқырман осы уақытқа дейін оқығанның бәрін түйіндеп жаз. "
        "Негізгі сюжет желілерін, кейіпкерлердің дамуын және басты тақырыптарды атап өт. "
        "5-10 сөйлемнен тұратын байланысты түйіндеме жаз. Қазақ тілінде жауап бер. " + _NO_THINK_KK
    ),
}

_CHAT_BASE = (
    "You are a book reading assistant. Answer the user's question ONLY based on the provided book text excerpts. "
    "If the answer is not in the provided text, clearly state that the information is not available in the book. "
    "Never use outside knowledge. Cite specific parts of the text when possible. "
    "IMPORTANT: Always respond in the same language the user used to ask the question. " + _NO_THINK
)

CHAT_PROMPTS = {
    "en": _CHAT_BASE,
    "ru": _CHAT_BASE,
    "kk": _CHAT_BASE,
}


class OllamaError(Exception):
    """Raised when Ollama is unreachable or returns an error."""
    pass


def _strip_reasoning(text: str) -> str:
    """Remove qwen3 think-aloud reasoning from the response text.

    Handles three cases:
    - <think>...</think> block at the start
    - Reasoning paragraphs at the START of the response
    - Reasoning paragraphs at the END of the response (model second-guesses itself)
    """
    if not text:
        return text

    # 1. Strip <think>...</think> block
    if "</think>" in text:
        text = _THINK_TAG_RE.sub("", text).strip()

    # 2. Split into paragraphs and clean
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text.strip()

    def _is_reasoning(para: str) -> bool:
        s = para.strip()
        return any(s.startswith(p) for p in _REASONING_PREFIXES)

    # Strip leading reasoning paragraphs
    while paragraphs and _is_reasoning(paragraphs[0]):
        paragraphs.pop(0)

    # Truncate at first mid-response reasoning paragraph.
    # Once the model starts thinking aloud, everything after is noise.
    clean: list[str] = []
    for para in paragraphs:
        if _is_reasoning(para):
            break
        clean.append(para)

    # Deduplicate near-identical paragraphs before returning
    seen: set[str] = set()
    deduped: list[str] = []
    for p in clean:
        key = p.strip().lower()[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    result = "\n\n".join(deduped).strip()
    if result:
        return result

    # All paragraphs were reasoning — try to extract the actual answer.
    # Look for sentences that sound like conclusions/answers, not meta-commentary.
    _ANSWER_MARKERS = ("So the answer is ", "The answer is ", "Ответ: ", "Автор: ", "Answer: ")
    for para in reversed(paragraphs):
        for marker in _ANSWER_MARKERS:
            if marker.lower() in para.lower():
                idx = para.lower().index(marker.lower())
                candidate = para[idx + len(marker):].strip().split(".")[0]
                if candidate:
                    return candidate

    # Last resort: return empty string so callers can show their own fallback
    return ""


async def _call_ollama(
    system_prompt: str,
    user_message: str,
    long: bool = False,
    primer: str = "",
) -> str:
    """Send a chat completion request to Ollama (non-streaming).

    `primer` is an optional assistant message prefix that forces the model to
    start generating content immediately instead of reasoning.
    """
    url = f"{settings.OLLAMA_URL}/api/chat"
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    if primer:
        messages.append({"role": "assistant", "content": primer})
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": OLLAMA_OPTIONS_LONG if long else OLLAMA_OPTIONS,
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
    return await _call_ollama(system_prompt, chapter_text, long=True)


async def summarize_progress(chapters_texts: list[str], language: str = "en") -> str:
    """Summarize everything the reader has read so far."""
    system_prompt = _get_prompt(PROGRESS_PROMPTS, language)

    combined_parts = []
    for i, text in enumerate(chapters_texts, 1):
        truncated = _truncate_words(text, 500)
        combined_parts.append(f"--- Chapter {i} ---\n{truncated}")

    combined = "\n\n".join(combined_parts)
    combined = _truncate_words(combined, 3000)

    return await _call_ollama(system_prompt, combined, long=True)


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
