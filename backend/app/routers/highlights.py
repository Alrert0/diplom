from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.book import Book
from app.models.highlight import Highlight
from app.models.user import User

router = APIRouter(prefix="/api/highlights", tags=["highlights"])


class HighlightCreate(BaseModel):
    book_id: int
    cfi_range: str
    text: str
    color: str = "yellow"
    note: str | None = None


class HighlightResponse(BaseModel):
    id: int
    book_id: int
    cfi_range: str
    text: str
    color: str
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HighlightWithBook(HighlightResponse):
    book_title: str = ""
    book_author: str = ""
    book_cover_url: str | None = None


@router.get("/{book_id}", response_model=list[HighlightResponse])
async def get_highlights(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Highlight)
        .where(Highlight.user_id == user.id, Highlight.book_id == book_id)
        .order_by(Highlight.created_at)
    )
    return result.scalars().all()


@router.post("", response_model=HighlightResponse, status_code=status.HTTP_201_CREATED)
async def create_highlight(
    data: HighlightCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = Highlight(
        user_id=user.id,
        book_id=data.book_id,
        cfi_range=data.cfi_range,
        text=data.text,
        color=data.color,
        note=data.note,
    )
    db.add(h)
    await db.commit()
    await db.refresh(h)
    return h


@router.get("", response_model=list[HighlightWithBook])
async def get_all_my_highlights(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All highlights for the current user, joined with book info."""
    result = await db.execute(
        select(Highlight, Book.title, Book.author, Book.cover_url)
        .join(Book, Book.id == Highlight.book_id)
        .where(Highlight.user_id == user.id)
        .order_by(Highlight.book_id, Highlight.created_at)
    )
    rows = result.all()
    out = []
    for h, title, author, cover_url in rows:
        data = HighlightResponse.model_validate(h).model_dump()
        data["book_title"] = title
        data["book_author"] = author
        data["book_cover_url"] = cover_url
        out.append(HighlightWithBook(**data))
    return out


@router.delete("/{highlight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_highlight(
    highlight_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == user.id)
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")
    await db.delete(h)
    await db.commit()
