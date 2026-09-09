import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, String, Text, JSON
from pgvector.sqlalchemy import Vector
from app.core.config import settings
from app.db.base import Base


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    external_id = Column(String(255), unique=True, index=True, nullable=True)
    title = Column(String(500), nullable=False, index=True)
    company_name = Column(String(500), nullable=True, index=True)
    description = Column(Text, nullable=False)
    location = Column(String(500), nullable=True)
    work_type = Column(String(100), nullable=True)
    remote_allowed = Column(Boolean, default=False)
    skills = Column(JSON, nullable=False, default=list)
    min_salary = Column(Float, nullable=True)
    max_salary = Column(Float, nullable=True)
    med_salary = Column(Float, nullable=True)
    pay_period = Column(String(50), nullable=True)
    source = Column(String(100), nullable=False, default="kaggle_linkedin")

    # Dense semantic embedding vector for similarity search (pgvector 1536 dim)
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
        return f"<JobPosting id={self.id} title={self.title} company={self.company_name}>"
