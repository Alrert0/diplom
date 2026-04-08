from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    language_pref: Mapped[str] = mapped_column(String(2), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ratings: Mapped[list["Rating"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reading_progress: Mapped[list["ReadingProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    reading_sessions: Mapped[list["ReadingSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")
