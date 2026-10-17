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
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str

    # Neo4j (Graph Database)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str

    @field_validator("SECRET_KEY", "DATABASE_URL", "NEO4J_PASSWORD")
    @classmethod
    def validate_mandatory_credentials(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} is required and must not be empty or whitespace.")
        return v

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
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # AI API Keys & Models
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    ANTHROPIC_API_KEY: str | None = None

    # LLM Provider Configuration
    LLM_PROVIDER: str = "ollama"  # "ollama" | "gemini"

    # Local Ollama LLM Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"


    # Matcher Agent Weights & Penalty Configuration
    WEIGHT_SEMANTIC: float = 0.25
    WEIGHT_MUST_HAVE: float = 0.35
    WEIGHT_NICE_TO_HAVE: float = 0.15
    WEIGHT_EXPERIENCE: float = 0.15
    WEIGHT_EDUCATION: float = 0.10
    EXPERIENCE_PENALTY_THRESHOLD: float = 1.5
    EXPERIENCE_PENALTY_FACTOR: float = 0.08
    MATCHER_MODEL_PATH: str = "artifacts/models/matcher_xgboost.json"

    # Job Freshness & Scheduled Ingestion Settings (Phase 6)
    JOB_STALE_DAYS_THRESHOLD: int = 14
    JOB_EXPIRED_DAYS_THRESHOLD: int = 30
    JOB_REFRESH_INTERVAL_HOURS: int = 24
    JOB_INGESTION_MAX_RETRIES: int = 3
    JOB_INGESTION_TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
