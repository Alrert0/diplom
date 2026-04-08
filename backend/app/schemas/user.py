from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=128)
    language_pref: str = Field(default="en", max_length=2)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    language_pref: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    language_pref: str | None = Field(default=None, max_length=2)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
