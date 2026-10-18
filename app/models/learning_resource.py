"""
app/models/learning_resource.py
-------------------------------
SQLAlchemy ORM model for curated educational and documentation resources mapped to canonical skills.
"""

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)

from app.db.base import Base


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    skill_name = Column(Text, nullable=False, index=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    provider = Column(Text, nullable=True)
    resource_type = Column(Text, nullable=False)
    difficulty = Column(Text, nullable=False)
    est_hours = Column(Numeric(6, 2), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    url_status = Column(Integer, nullable=True)
    url_checked_at = Column(DateTime(timezone=True), nullable=True)
    source = Column(Text, nullable=False, default="curated_seed", server_default=text("'curated_seed'"))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "resource_type IN ('official_docs', 'course', 'book', 'tutorial', 'practice')",
            name="ck_learning_resources_resource_type",
        ),
        CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name="ck_learning_resources_difficulty",
        ),
        UniqueConstraint(
            "skill_name", "title", "provider",
            name="uq_learning_resources_skill_title_provider",
        ),
        Index("ix_learning_resources_is_active", "is_active"),
    )
