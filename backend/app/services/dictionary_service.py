import logging
import sqlite3
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DICT_DIR = Path(__file__).resolve().parent.parent.parent / "dictionaries"

# ---------------------------------------------------------------------------
# English — NLTK WordNet
# ---------------------------------------------------------------------------

_wordnet_ready = False


def _ensure_wordnet():
    global _wordnet_ready
    if _wordnet_ready:
        return
    import nltk
    try:
        from nltk.corpus import wordnet  # noqa: F401
        wordnet.synsets("test")
        _wordnet_ready = True
    except LookupError:
        logger.info("Downloading NLTK wordnet data...")
        nltk.download("wordnet", quiet=True)
        nltk.download("omw-1.4", quiet=True)
        _wordnet_ready = True


_POS_MAP = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb", "s": "adjective"}


def define_english(word: str) -> list[dict]:
    _ensure_wordnet()
    from nltk.corpus import wordnet

    synsets = wordnet.synsets(word.lower())
    if not synsets:
        return []

    definitions = []
    seen = set()
    for syn in synsets:
        defn = syn.definition()
        if defn in seen:
            continue
        seen.add(defn)
        examples = syn.examples()
        definitions.append({
            "definition": defn,
            "pos": _POS_MAP.get(syn.pos(), syn.pos()),
            "examples": examples,
        })
        if len(definitions) >= 6:
            break

    return definitions


# ---------------------------------------------------------------------------
# Russian — SQLite
# ---------------------------------------------------------------------------

def define_russian(word: str) -> list[dict]:
    db_path = DICT_DIR / "russian_dict.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT pos, definition, example FROM words WHERE word = ? COLLATE NOCASE",
        (word.lower(),),
    ).fetchall()
    conn.close()

    return [
        {
            "definition": row["definition"],
            "pos": row["pos"] or "",
            "examples": [row["example"]] if row["example"] else [],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Kazakh — SQLite
# ---------------------------------------------------------------------------

def define_kazakh(word: str) -> list[dict]:
    db_path = DICT_DIR / "kazakh_dict.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT pos, definition, translation_ru, example FROM words WHERE word = ? COLLATE NOCASE",
        (word.lower(),),
    ).fetchall()
    conn.close()

    return [
        {
            "definition": row["definition"],
            "pos": row["pos"] or "",
            "translation_ru": row["translation_ru"] or "",
            "examples": [row["example"]] if row["example"] else [],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Wikipedia enrichment (online)
# ---------------------------------------------------------------------------

async def enrich_with_wikipedia(word: str, language: str) -> dict | None:
    lang_code = {"en": "en", "ru": "ru", "kk": "kk"}.get(language, "en")
    url = f"https://{lang_code}.wikipedia.org/api/rest_v1/page/summary/{word}"

    headers = {"User-Agent": "AIBookReader/1.0 (diploma project; contact: student@example.com)"}
    try:
        async with httpx.AsyncClient(timeout=5, headers=headers) as client:
            r = await client.get(url, follow_redirects=True)
            if r.status_code != 200:
                return None
            data = r.json()
            if data.get("type") == "disambiguation":
                return None
            result: dict = {
                "title": data.get("title", ""),
                "extract": data.get("extract", ""),
            }
            thumbnail = data.get("thumbnail", {})
            if thumbnail and thumbnail.get("source"):
                result["thumbnail"] = thumbnail["source"]
            return result
    except Exception as e:
        logger.debug("Wikipedia lookup failed for %s: %s", word, e)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def define(word: str, language: str, online: bool = True) -> dict:
    """
    Look up a word definition.
    Returns {word, language, definitions: [...], wikipedia: {...}|null}
    """
    word_clean = word.strip()

    if language == "en":
        definitions = define_english(word_clean)
    elif language == "ru":
        definitions = define_russian(word_clean)
    elif language == "kk":
        definitions = define_kazakh(word_clean)
    else:
        definitions = define_english(word_clean)

    wikipedia = None
    if online and word_clean:
        wikipedia = await enrich_with_wikipedia(word_clean, language)

    return {
        "word": word_clean,
        "language": language,
        "definitions": definitions,
        "wikipedia": wikipedia,
    }
