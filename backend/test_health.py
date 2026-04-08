"""
AI Book Reader — System Health Check
Run: python test_health.py
Requires: backend running at localhost:8000
"""
import httpx
import asyncio
import sys

API = "http://localhost:8000"


async def main():
    token = ""
    async with httpx.AsyncClient(timeout=10) as client:
        checks = []

        # 1. Backend health
        try:
            r = await client.get(f"{API}/api/health")
            checks.append(("Backend API", r.status_code == 200))
        except Exception as e:
            checks.append(("Backend API", False, str(e)))

        # 2. Database (via register)
        try:
            r = await client.post(f"{API}/api/auth/register", json={
                "email": "test@test.com",
                "username": "testuser",
                "password": "Test1234!",
            })
            checks.append(("Database + Register", r.status_code in [200, 201, 400]))
        except Exception as e:
            checks.append(("Database + Register", False, str(e)))

        # 3. Login
        try:
            r = await client.post(f"{API}/api/auth/login", json={
                "email": "test@test.com",
                "password": "Test1234!",
            })
            token = r.json().get("access_token", "") if r.status_code == 200 else ""
            checks.append(("Login + JWT", bool(token)))
        except Exception as e:
            checks.append(("Login + JWT", False, str(e)))

        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 4. Auth me
        try:
            r = await client.get(f"{API}/api/auth/me", headers=headers)
            checks.append(("GET /auth/me", r.status_code == 200))
        except Exception as e:
            checks.append(("GET /auth/me", False, str(e)))

        # 5. Update language preference
        try:
            r = await client.put(f"{API}/api/auth/me", json={"language_pref": "en"}, headers=headers)
            checks.append(("PUT /auth/me", r.status_code == 200))
        except Exception as e:
            checks.append(("PUT /auth/me", False, str(e)))

        # 6. Books list
        try:
            r = await client.get(f"{API}/api/books", headers=headers)
            checks.append(("GET /books", r.status_code == 200))
        except Exception as e:
            checks.append(("GET /books", False, str(e)))

        # 7. Ratings endpoints
        try:
            r = await client.get(f"{API}/api/ratings/top", headers=headers)
            checks.append(("GET /ratings/top", r.status_code == 200))
        except Exception as e:
            checks.append(("GET /ratings/top", False, str(e)))

        # 8. Ratings trending
        try:
            r = await client.get(f"{API}/api/ratings/trending", headers=headers)
            checks.append(("GET /ratings/trending", r.status_code == 200))
        except Exception as e:
            checks.append(("GET /ratings/trending", False, str(e)))

        # 9. Ollama
        try:
            r = await client.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            has_qwen = any("qwen" in m for m in models)
            checks.append(("Ollama running", True))
            checks.append(("Qwen2.5 model loaded", has_qwen, "" if has_qwen else "run: ollama pull qwen2.5:7b"))
        except Exception as e:
            checks.append(("Ollama running", False, str(e)))

        # 10. Static file serving
        try:
            r = await client.get(f"{API}/static/covers/", follow_redirects=True)
            # 404 is fine (no covers yet), 4xx/5xx from missing mount would be different
            checks.append(("Static files mount", r.status_code in [200, 404, 403]))
        except Exception as e:
            checks.append(("Static files mount", False, str(e)))

        # Print results
        print("\n" + "=" * 55)
        print("  AI BOOK READER — SYSTEM CHECK")
        print("=" * 55)
        for check in checks:
            name = check[0]
            passed = check[1]
            note = check[2] if len(check) > 2 else ""
            icon = "+" if passed else "FAIL"
            line = f"  [{icon}] {name}"
            if note:
                line += f"  ({note})"
            print(line)
        print("=" * 55)

        failed = sum(1 for c in checks if not c[1])
        total = len(checks)
        print(f"\n  {total - failed}/{total} checks passed.", end="")
        if failed:
            print(f" {failed} failed.")
        else:
            print(" All good!")
        print()

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
