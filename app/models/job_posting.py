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
    country = Column(String(50), nullable=False, default="India")
    currency = Column(String(10), nullable=False, default="INR")
    source = Column(String(100), nullable=False, default="kaggle_linkedin")

    # Dense semantic embedding vector for similarity search (pgvector 1536 dim)
    embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=True)

    # Freshness & Ingestion Tracking (Phase 6)
    published_at = Column(DateTime(timezone=True), nullable=True)
    first_seen_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_refreshed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    source_job_id = Column(String(255), nullable=True, index=True)
    source_url = Column(Text, nullable=True)
    freshness_status = Column(String(50), default="fresh", nullable=False, index=True)

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        now = datetime.now(timezone.utc)
        if self.id is None:
            self.id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
        if self.first_seen_at is None:
            self.first_seen_at = now
        if self.last_seen_at is None:
            self.last_seen_at = now
        if self.last_refreshed_at is None:
            self.last_refreshed_at = now
        if self.is_active is None:
            self.is_active = True
        if self.freshness_status is None:
            self.freshness_status = "fresh"
        if self.skills is None:
            self.skills = []
        if self.country is None:
            self.country = "India"
        if self.currency is None:
            self.currency = "INR"
        if self.source is None:
            self.source = "kaggle_linkedin"

    def calculate_freshness(
        self,
        reference_time: datetime | None = None,
        stale_days: int = 14,
        expired_days: int = 30,
    ) -> str:
        """Calculate freshness classification based on elapsed days since last_seen_at."""
        if not self.is_active:
            if self.freshness_status == "temporarily_unavailable":
                return "temporarily_unavailable"
            return "inactive"

        ref = reference_time or datetime.now(timezone.utc)
        target_ts = self.last_seen_at or self.created_at or ref
        if target_ts.tzinfo is None:
            target_ts = target_ts.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        delta_days = (ref - target_ts).total_seconds() / 86400.0
        if delta_days < stale_days:
            return "fresh"
        if delta_days < expired_days:
            return "stale"
        return "expired"

    def __repr__(self) -> str:
        return f"<JobPosting id={self.id} title={self.title} company={self.company_name} status={self.freshness_status}>"
