"""
app/models/job_market_trend.py
------------------------------
SQLAlchemy ORM model for historical per-skill labor market trends and demand shares.
Note: velocity is dynamically derived at query time, not stored.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)

from app.db.base import Base


class JobMarketTrend(Base):
    __tablename__ = "job_market_trends"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    skill_name = Column(Text, nullable=False, index=True)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    period_type = Column(Text, nullable=False)
    postings_with_skill = Column(Integer, nullable=False)
    total_postings = Column(Integer, nullable=False)
    demand_share = Column(Float, nullable=False)
    source = Column(Text, nullable=False)
    source_snapshot_sha256 = Column(Text, nullable=True)
    computed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "period_type IN ('snapshot', 'month')",
            name="ck_job_market_trends_period_type",
        ),
        UniqueConstraint(
            "skill_name", "period_start", "period_end", "period_type", "source",
            name="uq_job_market_trends_skill_period_source",
        ),
        Index("ix_job_market_trends_skill_period", "skill_name", "period_start"),
    )
