from typing import List, Union
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Career Copilot"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "temporary-dev-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_career_copilot"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # File Upload & Storage
    UPLOAD_DIR: str = "uploads/resumes"
    MAX_UPLOAD_SIZE_MB: int = 10

    # Vector Embedding
    EMBEDDING_DIMENSION: int = 1536

    # AI API Keys & Models
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash"
    ANTHROPIC_API_KEY: str | None = None

    # Matcher Agent Weights & Penalty Configuration
    WEIGHT_SEMANTIC: float = 0.25
    WEIGHT_MUST_HAVE: float = 0.35
    WEIGHT_NICE_TO_HAVE: float = 0.15
    WEIGHT_EXPERIENCE: float = 0.15
    WEIGHT_EDUCATION: float = 0.10
    EXPERIENCE_PENALTY_THRESHOLD: float = 1.5
    EXPERIENCE_PENALTY_FACTOR: float = 0.08
    MATCHER_MODEL_PATH: str = "artifacts/models/matcher_xgboost.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
