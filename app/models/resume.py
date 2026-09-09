import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String, Text, JSON
from pgvector.sqlalchemy import Vector
from app.core.config import settings
from app.db.base import Base


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1024), nullable=False)
    file_type = Column(String(50), nullable=False)
    raw_text = Column(Text, nullable=False)

    candidate_name = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)

    # Structured JSON data extracted by the Parser Agent
    parsed_data = Column(JSON, nullable=False, default=dict)

    # Dense semantic embedding vector for similarity search (e.g. pgvector 1536 dim)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Resume id={self.id} candidate={self.candidate_name} file={self.filename}>"
