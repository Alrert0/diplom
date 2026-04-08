from datetime import datetime

from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SummaryCache(Base):
    __tablename__ = "summary_cache"
    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number", "summary_type", name="uq_summary_cache"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'chapter' or 'progress'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
