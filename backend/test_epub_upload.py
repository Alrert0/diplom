"""
AI Book Reader — EPUB Upload & AI Features Test
Usage: python test_epub_upload.py <path_to_epub_file>
Requires: backend running at localhost:8000, test user registered (run test_health.py first)
"""
import httpx
import asyncio
import sys
import os

API = "http://localhost:8000"


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_epub_upload.py <path_to_epub_file>")
        sys.exit(1)

    epub_path = sys.argv[1]
    if not os.path.isfile(epub_path):
        print(f"File not found: {epub_path}")
        sys.exit(1)

    async with httpx.AsyncClient(timeout=60) as client:
        # Login
        print("\n--- Login ---")
        r = await client.post(f"{API}/api/auth/login", json={
            "email": "test@test.com",
            "password": "Test1234!",
        })
        if r.status_code != 200:
            print(f"  [FAIL] Login failed: {r.status_code} {r.text}")
            print("  Hint: run test_health.py first to create the test user")
            sys.exit(1)
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  [+] Logged in as test@test.com")

        # Upload EPUB
        print(f"\n--- Upload EPUB ---")
        filename = os.path.basename(epub_path)
        with open(epub_path, "rb") as f:
            r = await client.post(
                f"{API}/api/books/upload",
                files={"file": (filename, f, "application/epub+zip")},
                headers=headers,
            )

        if r.status_code not in [200, 201]:
            print(f"  [FAIL] Upload failed: {r.status_code} {r.text}")
            sys.exit(1)

        book = r.json()
        book_id = book["id"]
        print(f"  [+] Book uploaded: {book['title']} by {book['author']}")
        print(f"      ID: {book_id}")
        print(f"      Chapters: {book['total_chapters']}")
        print(f"      Words: {book['total_words']}")
        print(f"      Cover: {book.get('cover_url') or 'none'}")
        print(f"      EPUB file: {book.get('epub_filename') or 'none'}")

        # Get book details
        print(f"\n--- Book Details ---")
        r = await client.get(f"{API}/api/books/{book_id}", headers=headers)
        if r.status_code == 200:
            detail = r.json()
            print(f"  [+] GET /books/{book_id}: {detail['title']}")
            print(f"      Rating: {detail.get('avg_rating', 'none')} ({detail.get('ratings_count', 0)} ratings)")
        else:
            print(f"  [FAIL] GET /books/{book_id}: {r.status_code}")

        # Get chapters
        print(f"\n--- Chapters ---")
        r = await client.get(f"{API}/api/books/{book_id}/chapters", headers=headers)
        if r.status_code == 200:
            chapters = r.json()
            print(f"  [+] {len(chapters)} chapters loaded")
            for ch in chapters[:5]:
                print(f"      Ch.{ch['chapter_number']}: {ch['title'] or 'Untitled'} ({ch['word_count']} words)")
            if len(chapters) > 5:
                print(f"      ... and {len(chapters) - 5} more")
        else:
            print(f"  [FAIL] GET chapters: {r.status_code}")

        # Get first chapter text
        print(f"\n--- Chapter Content ---")
        r = await client.get(f"{API}/api/books/{book_id}/chapters/1", headers=headers)
        if r.status_code == 200:
            ch_detail = r.json()
            content_preview = ch_detail["content"][:200].replace("\n", " ")
            print(f"  [+] Chapter 1 text: {len(ch_detail['content'])} chars")
            print(f"      Preview: {content_preview}...")
        else:
            print(f"  [FAIL] GET chapter 1: {r.status_code}")

        # Save reading progress
        print(f"\n--- Reading Progress ---")
        r = await client.put(f"{API}/api/reading/progress", json={
            "book_id": book_id,
            "current_chapter": 1,
            "current_position": 0.5,
            "cfi_position": "epubcfi(/6/4!/4/1:0)",
        }, headers=headers)
        if r.status_code == 200:
            print(f"  [+] Progress saved: chapter {r.json()['current_chapter']}")
        else:
            print(f"  [FAIL] PUT progress: {r.status_code}")

        # Get reading progress
        r = await client.get(f"{API}/api/reading/progress/{book_id}", headers=headers)
        if r.status_code == 200:
            prog = r.json()
            print(f"  [+] Progress loaded: chapter {prog['current_chapter']}, cfi={prog.get('cfi_position', 'none')}")
        else:
            print(f"  [FAIL] GET progress: {r.status_code}")

        # Rate the book
        print(f"\n--- Rating ---")
        r = await client.post(f"{API}/api/ratings", json={
            "book_id": book_id,
            "score": 4,
            "review_text": "Great book for testing!",
        }, headers=headers)
        if r.status_code in [200, 201]:
            print(f"  [+] Rated book: {r.json()['score']} stars")
        else:
            print(f"  [FAIL] POST rating: {r.status_code}")

        # Test TextRank (no Ollama needed)
        print(f"\n--- TextRank ---")
        try:
            r = await client.get(
                f"{API}/api/ai/textrank",
                params={"book_id": book_id, "chapter_number": 1},
                headers=headers,
            )
            if r.status_code == 200:
                sentences = r.json()["sentences"]
                print(f"  [+] TextRank: {len(sentences)} key sentences extracted")
                for i, s in enumerate(sentences[:3]):
                    preview = s[:100] + ("..." if len(s) > 100 else "")
                    print(f"      {i + 1}. {preview}")
            else:
                print(f"  [FAIL] TextRank: {r.status_code} {r.text}")
        except Exception as e:
            print(f"  [FAIL] TextRank: {e}")

        # Test AI Summary (requires Ollama)
        print(f"\n--- AI Summary (requires Ollama + qwen2.5:7b) ---")
        try:
            r = await client.post(
                f"{API}/api/ai/summary",
                json={"book_id": book_id, "chapter_number": 1},
                headers=headers,
                timeout=120,
            )
            if r.status_code == 200:
                summary = r.json()["content"]
                preview = summary[:200] + ("..." if len(summary) > 200 else "")
                print(f"  [+] AI Summary:\n      {preview}")
            elif r.status_code == 503:
                print(f"  [SKIP] Ollama not running (start with: ollama serve)")
            else:
                print(f"  [FAIL] Summary: {r.status_code} {r.text[:200]}")
        except httpx.ReadTimeout:
            print(f"  [SKIP] Timed out (Ollama may be loading the model)")
        except Exception as e:
            print(f"  [FAIL] Summary: {e}")

        # Test AI Chat (requires Ollama + embeddings)
        print(f"\n--- AI Chat (requires Ollama + book indexed) ---")
        try:
            r = await client.post(
                f"{API}/api/ai/chat",
                json={"book_id": book_id, "message": "What is this book about?"},
                headers=headers,
                timeout=120,
            )
            if r.status_code == 200:
                answer = r.json()["answer"]
                preview = answer[:200] + ("..." if len(answer) > 200 else "")
                print(f"  [+] AI Chat:\n      {preview}")
            elif r.status_code == 202:
                print(f"  [SKIP] Book still indexing (embeddings being generated)")
            elif r.status_code == 503:
                print(f"  [SKIP] Ollama not running")
            else:
                print(f"  [FAIL] Chat: {r.status_code} {r.text[:200]}")
        except httpx.ReadTimeout:
            print(f"  [SKIP] Timed out")
        except Exception as e:
            print(f"  [FAIL] Chat: {e}")

        # Summary progress
        print(f"\n--- AI Summary Progress ---")
        try:
            r = await client.post(
                f"{API}/api/ai/summary-progress",
                json={"book_id": book_id},
                headers=headers,
                timeout=120,
            )
            if r.status_code == 200:
                summary = r.json()["content"]
                preview = summary[:200] + ("..." if len(summary) > 200 else "")
                print(f"  [+] Progress Summary:\n      {preview}")
            elif r.status_code == 503:
                print(f"  [SKIP] Ollama not running")
            else:
                print(f"  [FAIL] Summary progress: {r.status_code}")
        except httpx.ReadTimeout:
            print(f"  [SKIP] Timed out")
        except Exception as e:
            print(f"  [FAIL] Summary progress: {e}")

        print(f"\n{'=' * 55}")
        print(f"  Test complete for: {book['title']}")
        print(f"{'=' * 55}\n")


if __name__ == "__main__":
    asyncio.run(main())
