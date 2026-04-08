from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives in the project root (one level above backend/)
_env_file = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/ai_book_reader"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5433/ai_book_reader"

    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:4b"

    # Embedding
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-large"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8"}


settings = Settings()
