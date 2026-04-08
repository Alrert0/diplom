from pydantic import BaseModel


class SummaryRequest(BaseModel):
    book_id: int
    chapter_number: int


class SummaryProgressRequest(BaseModel):
    book_id: int


class ChatRequest(BaseModel):
    book_id: int
    message: str


class AIResponse(BaseModel):
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class TextRankResponse(BaseModel):
    sentences: list[str]
