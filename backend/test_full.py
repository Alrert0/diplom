"""
Comprehensive test script for AI Book Reader — Phases 1-5.

Usage:
    cd backend
    python test_full.py

Requires the server to be running at http://localhost:8000
and PostgreSQL to be available.
"""

import asyncio
import io
import random
import string
import sys
import time

import httpx

API_BASE = "http://localhost:8000"
TIMEOUT_DEFAULT = 15.0
TIMEOUT_AI = 120.0

# ──────────────────────────────────────────────────────────────────────
# Test infrastructure
# ──────────────────────────────────────────────────────────────────────

passed = 0
failed = 0
results: list[tuple[str, str, bool, str]] = []  # (phase, name, ok, detail)


def record(phase: str, name: str, ok: bool, detail: str = ""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    results.append((phase, name, ok, detail))


def random_suffix(n: int = 6) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def print_results():
    current_phase = ""
    for phase, name, ok, detail in results:
        if phase != current_phase:
            current_phase = phase
            print(f"\n{'=' * 60}")
            print(f"  {phase}")
            print(f"{'=' * 60}")
        marker = "[+]" if ok else "[-]"
        line = f"  {marker} {name}"
        if detail:
            line += f"  ({detail})"
        print(line)

    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY: {passed}/{total} tests passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print("  — ALL PASSED")
    print(f"{'=' * 60}\n")


# ──────────────────────────────────────────────────────────────────────
# EPUB creation helper
# ──────────────────────────────────────────────────────────────────────

def create_test_epub() -> bytes:
    """Create a minimal valid EPUB with 3 chapters programmatically."""
    import ebooklib
    from ebooklib import epub
    from PIL import Image

    book = epub.EpubBook()
    book.set_identifier("test-book-001")
    book.set_title("Test Book")
    book.set_language("en")
    book.add_author("Test Author")

    book.add_metadata("DC", "description", "A test book for automated testing of the AI Book Reader platform.")

    # Create a simple cover image (400x600 solid color)
    img = Image.new("RGB", (400, 600), color=(70, 130, 180))
    img_buf = io.BytesIO()
    img.save(img_buf, format="JPEG")
    img_bytes = img_buf.getvalue()

    cover_image = epub.EpubImage()
    cover_image.file_name = "cover.jpg"
    cover_image.media_type = "image/jpeg"
    cover_image.content = img_bytes
    book.add_item(cover_image)
    book.set_cover("cover.jpg", img_bytes)

    lorem_paragraph = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
        "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
        "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
        "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
        "culpa qui officia deserunt mollit anim id est laborum. "
    )

    chapters = []
    for i in range(1, 4):
        ch = epub.EpubHtml(title=f"Chapter {i}", file_name=f"chapter_{i}.xhtml", lang="en")
        # Build ~250 words per chapter
        paragraphs = "".join(
            f"<p>{lorem_paragraph} (Chapter {i}, paragraph {j}.)</p>\n"
            for j in range(1, 5)
        )
        ch.content = f"<h1>Chapter {i}</h1>\n{paragraphs}".encode("utf-8")
        book.add_item(ch)
        chapters.append(ch)

    # Table of contents and spine
    book.toc = [(epub.Section("Chapters"), chapters)]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    buf = io.BytesIO()
    epub.write_epub(buf, book, {})
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# Main test flow
# ──────────────────────────────────────────────────────────────────────

async def main():
    suffix = random_suffix()
    email = f"testuser_{suffix}@test.com"
    username = f"testuser_{suffix}"
    password = "TestPass123!"

    token: str = ""
    book_id: int = 0

    async with httpx.AsyncClient(base_url=API_BASE, timeout=TIMEOUT_DEFAULT) as c:

        # ══════════════════════════════════════════════════════════════
        # PHASE 1: Foundation — Auth
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 1: Foundation — Auth"

        # 1. Register new user
        try:
            r = await c.post("/api/auth/register", json={
                "email": email, "username": username,
                "password": password, "language_pref": "en",
            })
            ok = r.status_code == 201
            record(PHASE, "Register new user", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Register new user", False, str(e))

        # 2. Duplicate register → 400
        try:
            r = await c.post("/api/auth/register", json={
                "email": email, "username": username,
                "password": password, "language_pref": "en",
            })
            ok = r.status_code == 400
            record(PHASE, "Duplicate register blocked (400)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Duplicate register blocked (400)", False, str(e))

        # 3. Login correct password
        try:
            r = await c.post("/api/auth/login", json={"email": email, "password": password})
            ok = r.status_code == 200 and "access_token" in r.json()
            if ok:
                token = r.json()["access_token"]
            record(PHASE, "Login successful", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Login successful", False, str(e))

        # 4. Login wrong password → 401
        try:
            r = await c.post("/api/auth/login", json={"email": email, "password": "wrongpass"})
            ok = r.status_code == 401
            record(PHASE, "Login wrong password (401)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Login wrong password (401)", False, str(e))

        # If login failed, we can't continue with authenticated tests
        if not token:
            for name in [
                "GET /me with token", "GET /me no token (401/403)",
                "PUT /me update language_pref",
            ]:
                record(PHASE, name, False, "Skipped — no token (login failed)")
            print_results()
            sys.exit(1)

        headers = {"Authorization": f"Bearer {token}"}

        # 5. GET /me with token
        try:
            r = await c.get("/api/auth/me", headers=headers)
            ok = r.status_code == 200 and r.json()["email"] == email
            record(PHASE, "GET /me with token", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET /me with token", False, str(e))

        # 6. GET /me without token → 401/403
        try:
            r = await c.get("/api/auth/me")
            ok = r.status_code in (401, 403)
            record(PHASE, "GET /me no token (401/403)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET /me no token (401/403)", False, str(e))

        # 7. PUT /me — update language_pref
        try:
            r = await c.put("/api/auth/me", headers=headers, json={"language_pref": "ru"})
            ok = r.status_code == 200 and r.json()["language_pref"] == "ru"
            record(PHASE, "PUT /me update language_pref", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "PUT /me update language_pref", False, str(e))

        # Reset back to English for subsequent tests
        try:
            await c.put("/api/auth/me", headers=headers, json={"language_pref": "en"})
        except Exception:
            pass

        # ══════════════════════════════════════════════════════════════
        # PHASE 1: Foundation — Books
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 1: Foundation — Books"

        # 8. GET /books (may be empty)
        try:
            r = await c.get("/api/books", headers=headers)
            ok = r.status_code == 200 and isinstance(r.json(), list)
            record(PHASE, "GET /books (list)", ok, f"{r.status_code}, {len(r.json())} books")
        except Exception as e:
            record(PHASE, "GET /books (list)", False, str(e))

        # 9. Upload test EPUB
        try:
            epub_bytes = create_test_epub()
            files = {"file": ("test_book.epub", io.BytesIO(epub_bytes), "application/epub+zip")}
            r = await c.post("/api/books/upload", headers=headers, files=files, timeout=30.0)
            ok = r.status_code == 201
            if ok:
                data = r.json()
                book_id = data["id"]
                ok = (
                    data["title"] == "Test Book"
                    and data["author"] == "Test Author"
                    and data["total_chapters"] == 3
                )
                detail = f"id={book_id}, chapters={data['total_chapters']}, words={data['total_words']}"
            else:
                detail = f"{r.status_code}: {r.text[:200]}"
            record(PHASE, "Upload EPUB", ok, detail)
        except Exception as e:
            record(PHASE, "Upload EPUB", False, str(e))

        # 10. GET /books (verify book appears)
        try:
            r = await c.get("/api/books", headers=headers)
            ok = r.status_code == 200 and any(b["id"] == book_id for b in r.json())
            record(PHASE, "GET /books (book appears)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET /books (book appears)", False, str(e))

        # 11. GET /books/{id}
        try:
            r = await c.get(f"/api/books/{book_id}", headers=headers)
            ok = r.status_code == 200 and r.json()["title"] == "Test Book"
            record(PHASE, "GET /books/{id} detail", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET /books/{id} detail", False, str(e))

        # 12. GET /books/{id}/chapters
        try:
            r = await c.get(f"/api/books/{book_id}/chapters", headers=headers)
            ok = r.status_code == 200 and len(r.json()) == 3
            record(PHASE, "GET chapters list (3)", ok, f"{r.status_code}, count={len(r.json())}")
        except Exception as e:
            record(PHASE, "GET chapters list (3)", False, str(e))

        # 13. GET /books/{id}/chapters/1
        try:
            r = await c.get(f"/api/books/{book_id}/chapters/1", headers=headers)
            ok = r.status_code == 200 and "content" in r.json() and len(r.json()["content"]) > 50
            record(PHASE, "GET chapter 1 content", ok, f"{r.status_code}, len={len(r.json().get('content', ''))}")
        except Exception as e:
            record(PHASE, "GET chapter 1 content", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 1: Foundation — Ratings
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 1: Foundation — Ratings"

        # 14. Rate book 5 stars
        try:
            r = await c.post("/api/ratings", headers=headers, json={
                "book_id": book_id, "score": 5, "review_text": "Excellent test book!",
            })
            ok = r.status_code == 201 and r.json()["score"] == 5
            record(PHASE, "Rate book 5 stars", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Rate book 5 stars", False, str(e))

        # 15. Update to 4 stars (upsert)
        try:
            r = await c.post("/api/ratings", headers=headers, json={
                "book_id": book_id, "score": 4, "review_text": "Updated: very good test book.",
            })
            ok = r.status_code == 201 and r.json()["score"] == 4
            record(PHASE, "Update rating to 4 stars (upsert)", ok, f"{r.status_code}, score={r.json().get('score')}")
        except Exception as e:
            record(PHASE, "Update rating to 4 stars (upsert)", False, str(e))

        # 16. GET /ratings/book/{id}
        try:
            r = await c.get(f"/api/ratings/book/{book_id}", headers=headers)
            ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) >= 1
            record(PHASE, "GET ratings for book", ok, f"{r.status_code}, count={len(r.json())}")
        except Exception as e:
            record(PHASE, "GET ratings for book", False, str(e))

        # 17. GET /ratings/top
        try:
            r = await c.get("/api/ratings/top", headers=headers)
            ok = r.status_code == 200 and isinstance(r.json(), list)
            record(PHASE, "GET /ratings/top", ok, f"{r.status_code}, count={len(r.json())}")
        except Exception as e:
            record(PHASE, "GET /ratings/top", False, str(e))

        # 18. GET /ratings/trending
        try:
            r = await c.get("/api/ratings/trending", headers=headers)
            ok = r.status_code == 200 and isinstance(r.json(), list)
            record(PHASE, "GET /ratings/trending", ok, f"{r.status_code}, count={len(r.json())}")
        except Exception as e:
            record(PHASE, "GET /ratings/trending", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 2: Reader — Reading Progress
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 2: Reader — Reading Progress"

        # 19. Save progress chapter 2, position 0.5
        try:
            r = await c.put("/api/reading/progress", headers=headers, json={
                "book_id": book_id, "current_chapter": 2, "current_position": 0.5,
            })
            ok = r.status_code == 200 and r.json()["current_chapter"] == 2
            record(PHASE, "Save progress (ch.2, pos 0.5)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Save progress (ch.2, pos 0.5)", False, str(e))

        # 20. GET progress
        try:
            r = await c.get(f"/api/reading/progress/{book_id}", headers=headers)
            ok = r.status_code == 200 and r.json()["current_chapter"] == 2
            record(PHASE, "GET progress (verify ch.2)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET progress (verify ch.2)", False, str(e))

        # 21. Update progress to chapter 3
        try:
            r = await c.put("/api/reading/progress", headers=headers, json={
                "book_id": book_id, "current_chapter": 3, "current_position": 0.0,
            })
            ok = r.status_code == 200 and r.json()["current_chapter"] == 3
            record(PHASE, "Update progress (ch.3)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Update progress (ch.3)", False, str(e))

        # 22. GET progress (verify updated)
        try:
            r = await c.get(f"/api/reading/progress/{book_id}", headers=headers)
            ok = r.status_code == 200 and r.json()["current_chapter"] == 3
            record(PHASE, "GET progress (verify ch.3)", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET progress (verify ch.3)", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 3: AI Features
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 3: AI Features"

        # 23. Check Ollama is running
        ollama_ok = False
        try:
            r = await c.get("http://localhost:11434/api/tags", timeout=5.0)
            ollama_ok = r.status_code == 200
            record(PHASE, "Ollama is running", ollama_ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "Ollama is running", False, f"Not reachable: {e}")

        # 24. Wait for book indexing (poll until not 202)
        indexed = False
        if ollama_ok:
            try:
                for attempt in range(12):  # max 60s (12 x 5s)
                    r = await c.post(
                        "/api/ai/summary", headers=headers,
                        json={"book_id": book_id, "chapter_number": 1},
                        timeout=TIMEOUT_AI,
                    )
                    if r.status_code != 202:
                        indexed = True
                        break
                    await asyncio.sleep(5)
                record(PHASE, "Book indexing complete", indexed,
                       f"attempts={attempt + 1}")
            except Exception as e:
                record(PHASE, "Book indexing complete", False, str(e))
        else:
            record(PHASE, "Book indexing complete", False, "Skipped — Ollama not running")

        # 25. AI Summary (chapter 1)
        if ollama_ok:
            try:
                r = await c.post(
                    "/api/ai/summary", headers=headers,
                    json={"book_id": book_id, "chapter_number": 1},
                    timeout=TIMEOUT_AI,
                )
                ok = r.status_code == 200 and len(r.json().get("content", "")) > 10
                record(PHASE, "AI Summary (chapter 1)", ok,
                       f"{r.status_code}, len={len(r.json().get('content', ''))}")
            except Exception as e:
                record(PHASE, "AI Summary (chapter 1)", False, str(e))
        else:
            record(PHASE, "AI Summary (chapter 1)", False, "Skipped — Ollama not running")

        # 26. AI Summary Progress
        if ollama_ok:
            try:
                r = await c.post(
                    "/api/ai/summary-progress", headers=headers,
                    json={"book_id": book_id},
                    timeout=TIMEOUT_AI,
                )
                ok = r.status_code == 200 and len(r.json().get("content", "")) > 10
                record(PHASE, "AI Summary Progress", ok,
                       f"{r.status_code}, len={len(r.json().get('content', ''))}")
            except Exception as e:
                record(PHASE, "AI Summary Progress", False, str(e))
        else:
            record(PHASE, "AI Summary Progress", False, "Skipped — Ollama not running")

        # 27. AI Chat
        if ollama_ok and indexed:
            try:
                r = await c.post(
                    "/api/ai/chat", headers=headers,
                    json={"book_id": book_id, "message": "What is this book about?"},
                    timeout=TIMEOUT_AI,
                )
                ok = r.status_code == 200 and len(r.json().get("answer", "")) > 10
                record(PHASE, "AI Chat", ok,
                       f"{r.status_code}, len={len(r.json().get('answer', ''))}")
            except Exception as e:
                record(PHASE, "AI Chat", False, str(e))
        else:
            record(PHASE, "AI Chat", False, "Skipped — Ollama not running or not indexed")

        # 28. TextRank
        try:
            r = await c.get(
                f"/api/ai/textrank?book_id={book_id}&chapter_number=1", headers=headers,
            )
            ok = r.status_code == 200 and isinstance(r.json().get("sentences"), list)
            n_sent = len(r.json().get("sentences", []))
            record(PHASE, "TextRank key sentences", ok, f"{r.status_code}, sentences={n_sent}")
        except Exception as e:
            record(PHASE, "TextRank key sentences", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 4: TTS
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 4: TTS"

        # 29. GET /tts/voices
        try:
            r = await c.get("/api/tts/voices", headers=headers)
            ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0
            # Check EN/RU/KK present
            langs_present = set()
            for voice in r.json():
                langs_present.add(voice.get("language"))
            has_all = {"en", "ru", "kk"}.issubset(langs_present)
            record(PHASE, "GET /tts/voices", ok and has_all,
                   f"{r.status_code}, {len(r.json())} voices, langs={langs_present}")
        except Exception as e:
            record(PHASE, "GET /tts/voices", False, str(e))

        # 30. POST /tts/synthesize
        try:
            r = await c.post(
                "/api/tts/synthesize", headers=headers,
                json={"text": "Hello, this is a test of text to speech.", "language": "en", "gender": "female"},
                timeout=30.0,
            )
            content_type = r.headers.get("content-type", "")
            ok = r.status_code == 200 and "audio" in content_type and len(r.content) > 100
            record(PHASE, "POST /tts/synthesize (EN female)", ok,
                   f"{r.status_code}, type={content_type}, size={len(r.content)} bytes")
        except Exception as e:
            record(PHASE, "POST /tts/synthesize (EN female)", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 4: Vocabulary
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 4: Vocabulary"

        # 31. English definition
        try:
            r = await c.get("/api/vocabulary/define?word=book&lang=en&online=false", headers=headers)
            ok = r.status_code == 200
            defs = r.json().get("definitions", [])
            record(PHASE, "Define 'book' (EN)", ok and len(defs) > 0,
                   f"{r.status_code}, {len(defs)} definitions")
        except Exception as e:
            record(PHASE, "Define 'book' (EN)", False, str(e))

        # 32. Russian definition
        try:
            r = await c.get("/api/vocabulary/define?word=книга&lang=ru&online=false", headers=headers)
            ok = r.status_code == 200
            defs = r.json().get("definitions", [])
            record(PHASE, "Define 'книга' (RU)", ok and len(defs) > 0,
                   f"{r.status_code}, {len(defs)} definitions")
        except Exception as e:
            record(PHASE, "Define 'книга' (RU)", False, str(e))

        # 33. Kazakh definition
        try:
            r = await c.get("/api/vocabulary/define?word=кітап&lang=kk&online=false", headers=headers)
            ok = r.status_code == 200
            defs = r.json().get("definitions", [])
            record(PHASE, "Define 'кітап' (KK)", ok and len(defs) > 0,
                   f"{r.status_code}, {len(defs)} definitions")
        except Exception as e:
            record(PHASE, "Define 'кітап' (KK)", False, str(e))

        # 34. Nonexistent word — graceful handling
        try:
            r = await c.get(
                "/api/vocabulary/define?word=nonexistentword123&lang=en&online=false",
                headers=headers,
            )
            ok = r.status_code == 200
            defs = r.json().get("definitions", [])
            record(PHASE, "Define nonexistent word (graceful)", ok,
                   f"{r.status_code}, {len(defs)} definitions")
        except Exception as e:
            record(PHASE, "Define nonexistent word (graceful)", False, str(e))

        # ══════════════════════════════════════════════════════════════
        # PHASE 5: ML
        # ══════════════════════════════════════════════════════════════
        PHASE = "PHASE 5: ML — Recommendations & Models"

        # 35. GET /recommendations (may be empty — cold start OK)
        try:
            r = await c.get("/api/recommendations", headers=headers)
            ok = r.status_code == 200 and "recommendations" in r.json()
            recs = r.json().get("recommendations", [])
            record(PHASE, "GET /recommendations", ok,
                   f"{r.status_code}, {len(recs)} recommendations")
        except Exception as e:
            record(PHASE, "GET /recommendations", False, str(e))

        # 36. GET /reading/time-estimate
        try:
            r = await c.get(
                f"/api/reading/time-estimate?book_id={book_id}&chapter=1",
                headers=headers,
            )
            ok = r.status_code == 200
            data = r.json()
            has_fields = all(k in data for k in ("chapter_minutes", "book_minutes", "wpm"))
            record(PHASE, "GET /reading/time-estimate", ok and has_fields,
                   f"{r.status_code}, ch_min={data.get('chapter_minutes')}, wpm={data.get('wpm')}")
        except Exception as e:
            record(PHASE, "GET /reading/time-estimate", False, str(e))

        # 37. GET /reading/stats
        try:
            r = await c.get("/api/reading/stats", headers=headers)
            ok = r.status_code == 200
            data = r.json()
            has_fields = all(k in data for k in ("total_books", "total_reading_hours", "avg_speed_wpm"))
            record(PHASE, "GET /reading/stats", ok and has_fields,
                   f"{r.status_code}, books={data.get('total_books')}, speed={data.get('avg_speed_wpm')}")
        except Exception as e:
            record(PHASE, "GET /reading/stats", False, str(e))

        # 38. POST /ml/retrain
        try:
            r = await c.post("/api/ml/retrain", headers=headers, timeout=60.0)
            ok = r.status_code == 200 and "results" in r.json()
            detail_parts = []
            for key, val in r.json().get("results", {}).items():
                if isinstance(val, dict) and "error" not in val:
                    detail_parts.append(f"{key}:OK")
                else:
                    detail_parts.append(f"{key}:skip")
            record(PHASE, "POST /ml/retrain", ok, f"{r.status_code}, {', '.join(detail_parts)}")
        except Exception as e:
            record(PHASE, "POST /ml/retrain", False, str(e))

        # 39. GET /ml/metrics
        try:
            r = await c.get("/api/ml/metrics", headers=headers, timeout=30.0)
            ok = r.status_code == 200
            data = r.json()
            has_sections = any(k in data for k in ("recommender", "speed_predictor", "clustering", "dataset"))
            record(PHASE, "GET /ml/metrics", ok and has_sections,
                   f"{r.status_code}, sections={list(data.keys())}")
        except Exception as e:
            record(PHASE, "GET /ml/metrics", False, str(e))

        # 40. GET /ml/clustering-visualization
        try:
            r = await c.get("/api/ml/clustering-visualization", headers=headers)
            ok = r.status_code == 200 and "points" in r.json()
            data = r.json()
            record(PHASE, "GET /ml/clustering-visualization", ok,
                   f"{r.status_code}, points={len(data.get('points', []))}, k={data.get('k')}")
        except Exception as e:
            record(PHASE, "GET /ml/clustering-visualization", False, str(e))

        # 41. GET /ml/clustering/visualize (from recommendations router)
        try:
            r = await c.get("/api/ml/clustering/visualize", headers=headers)
            ok = r.status_code == 200 and "points" in r.json()
            record(PHASE, "GET /ml/clustering/visualize", ok, f"{r.status_code}")
        except Exception as e:
            record(PHASE, "GET /ml/clustering/visualize", False, str(e))

    # ──────────────────────────────────────────────────────────────
    # Print results
    # ──────────────────────────────────────────────────────────────
    print_results()
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
