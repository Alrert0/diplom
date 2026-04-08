from datetime import datetime

from pydantic import BaseModel, Field


class BookResponse(BaseModel):
    id: int
    title: str
    author: str
    description: str | None = None
    genre: str | None = None
    language: str
    cover_url: str | None = None
    epub_filename: str | None = None
    total_chapters: int
    total_words: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChapterResponse(BaseModel):
    id: int
    book_id: int
    chapter_number: int
    title: str | None = None
    word_count: int

    model_config = {"from_attributes": True}


class ChapterDetailResponse(ChapterResponse):
    content: str


class RatingCreate(BaseModel):
    book_id: int
    score: int = Field(ge=1, le=5)
    review_text: str | None = None


class RatingResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    score: int
    review_text: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReadingProgressUpdate(BaseModel):
    book_id: int
    current_chapter: int
    current_position: float = Field(ge=0.0, le=1.0)
    cfi_position: str | None = None


class ReadingProgressResponse(BaseModel):
    id: int
    user_id: int
    book_id: int
    current_chapter: int
    current_position: float
    cfi_position: str | None = None
    last_read_at: datetime

    model_config = {"from_attributes": True}
