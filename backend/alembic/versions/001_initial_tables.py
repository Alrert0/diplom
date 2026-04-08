"""Initial tables with pgvector extension

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("language_pref", sa.String(2), server_default="en"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Books
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("genre", sa.String(100)),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("cover_url", sa.String(500)),
        sa.Column("epub_filename", sa.String(500)),
        sa.Column("total_chapters", sa.Integer(), server_default="0"),
        sa.Column("total_words", sa.Integer(), server_default="0"),
        sa.Column("epub_path", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Chapters
    op.create_table(
        "chapters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), server_default="0"),
    )

    # Ratings
    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book_rating"),
        sa.CheckConstraint("score >= 1 AND score <= 5", name="ck_rating_score_range"),
    )

    # Reading Progress
    op.create_table(
        "reading_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_chapter", sa.Integer(), server_default="1"),
        sa.Column("current_position", sa.Float(), server_default="0.0"),
        sa.Column("cfi_position", sa.String(500)),
        sa.Column("last_read_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "book_id", name="uq_user_book_progress"),
    )

    # Reading Sessions
    op.create_table(
        "reading_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("words_read", sa.Integer(), server_default="0"),
        sa.Column("time_spent_seconds", sa.Integer(), server_default="0"),
        sa.Column("session_start", sa.DateTime(timezone=True)),
        sa.Column("session_end", sa.DateTime(timezone=True)),
    )

    # Book Embeddings (pgvector)
    op.create_table(
        "book_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", sa.Integer(), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
    )

    # Index for faster vector search per book
    op.create_index(
        "ix_book_embeddings_book_id",
        "book_embeddings",
        ["book_id"],
    )


def downgrade() -> None:
    op.drop_table("book_embeddings")
    op.drop_table("reading_sessions")
    op.drop_table("reading_progress")
    op.drop_table("ratings")
    op.drop_table("chapters")
    op.drop_table("books")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
