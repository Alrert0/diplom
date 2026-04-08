import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import auth, books, ratings, chapters, ai, tts, vocabulary, recommendations, ml_metrics, book_assistant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="AI Book Reader",
    description="Advanced AI-Based Application for Personalized Book Reading",
    version="1.0.0",
)

# CORS middleware — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (book covers)
static_dir = Path(__file__).resolve().parent.parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Uploaded EPUB files (served for epub.js client-side rendering)
uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Routers
app.include_router(auth.router)
app.include_router(books.router)
app.include_router(ratings.router)
app.include_router(chapters.router)
app.include_router(ai.router)
app.include_router(tts.router)
app.include_router(vocabulary.router)
app.include_router(recommendations.router)
app.include_router(ml_metrics.router)
app.include_router(book_assistant.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}
