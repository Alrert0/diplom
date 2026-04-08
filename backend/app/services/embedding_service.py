import asyncio
import logging
from typing import Optional

from sqlalchemy import select, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.embedding import BookEmbedding

logger = logging.getLogger(__name__)

# Lazy-loaded singleton for the embedding model
_model = None


def _get_model():
    """Load the sentence-transformers model on first use."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded successfully")
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Encode texts to embedding vectors."""
    model = _get_model()
    # multilingual-e5-large expects "query: " or "passage: " prefix
    prefixed = [f"passage: {t}" for t in texts]
    embeddings = model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


def generate_query_embedding(query: str) -> list[float]:
    """Encode a query string to an embedding vector."""
    model = _get_model()
    embedding = model.encode(f"query: {query}", normalize_embeddings=True, show_progress_bar=False)
    return embedding.tolist()


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks of ~chunk_size words with overlap."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap

    return chunks


async def index_book(book_id: int, chapters: list[dict]) -> None:
    """
    Index all chapters of a book: chunk text, generate embeddings, store in DB.

    chapters: list of {"id": chapter_id, "content": text}
    """
    logger.info("Starting indexing for book %d (%d chapters)", book_id, len(chapters))

    async with async_session() as db:
        # Remove existing embeddings for this book (re-index support)
        await db.execute(delete(BookEmbedding).where(BookEmbedding.book_id == book_id))
        await db.flush()

        all_chunks: list[dict] = []
        for ch in chapters:
            chunks = chunk_text(ch["content"])
            for idx, chunk in enumerate(chunks):
                all_chunks.append({
                    "book_id": book_id,
                    "chapter_id": ch["id"],
                    "chunk_index": idx,
                    "chunk_text": chunk,
                })

        if not all_chunks:
            logger.warning("No chunks generated for book %d", book_id)
            return

        # Generate embeddings in batches (run in thread pool to avoid blocking event loop)
        batch_size = 32
        loop = asyncio.get_event_loop()
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            texts = [c["chunk_text"] for c in batch]
            embeddings = await loop.run_in_executor(None, generate_embeddings, texts)

            for chunk_data, emb in zip(batch, embeddings):
                record = BookEmbedding(
                    book_id=chunk_data["book_id"],
                    chapter_id=chunk_data["chapter_id"],
                    chunk_index=chunk_data["chunk_index"],
                    chunk_text=chunk_data["chunk_text"],
                    embedding=emb,
                )
                db.add(record)

            await db.flush()
            logger.info(
                "Book %d: indexed batch %d-%d of %d chunks",
                book_id, i, min(i + batch_size, len(all_chunks)), len(all_chunks),
            )

        await db.commit()

    logger.info("Indexing complete for book %d: %d chunks stored", book_id, len(all_chunks))


async def search_similar(
    query: str,
    book_id: int,
    top_k: int = 5,
    db: Optional[AsyncSession] = None,
) -> list[str]:
    """Find the most similar chunks to a query using pgvector cosine distance."""
    loop = asyncio.get_event_loop()
    query_emb = await loop.run_in_executor(None, generate_query_embedding, query)

    should_close = False
    if db is None:
        db = async_session()
        should_close = True

    try:
        # pgvector cosine distance operator: <=>
        stmt = (
            select(BookEmbedding.chunk_text)
            .where(BookEmbedding.book_id == book_id)
            .order_by(BookEmbedding.embedding.cosine_distance(query_emb))
            .limit(top_k)
        )
        result = await db.execute(stmt)
        chunks = [row[0] for row in result.all()]
        return chunks
    finally:
        if should_close:
            await db.close()


async def is_book_indexed(book_id: int, db: AsyncSession) -> bool:
    """Check if a book has any embeddings stored."""
    stmt = select(BookEmbedding.id).where(BookEmbedding.book_id == book_id).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
