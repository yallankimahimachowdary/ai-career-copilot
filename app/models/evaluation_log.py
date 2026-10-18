"""
app/models/evaluation_log.py
----------------------------
SQLAlchemy ORM model for experimental benchmarks, evaluation metrics, and model evaluations.
Contains NO user_id or personal data.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

from app.db.base import Base


class EvaluationLog(Base):
    __tablename__ = "evaluation_logs"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
        nullable=False,
    )
    experiment_name = Column(Text, nullable=False)
    run_id = Column(Text, nullable=False)
    component = Column(Text, nullable=False)
    metric_name = Column(Text, nullable=False)
    metric_value = Column(Float, nullable=False)
    n_samples = Column(Integer, nullable=True)
    ci_low = Column(Float, nullable=True)
    ci_high = Column(Float, nullable=True)
    model_name = Column(Text, nullable=True)
    model_hash = Column(Text, nullable=True)
    dataset_sha256 = Column(Text, nullable=False)
    git_commit = Column(Text, nullable=True)
    seed = Column(Integer, nullable=True)
    params = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    notes = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "run_id", "component", "metric_name",
            name="uq_evaluation_logs_run_component_metric",
        ),
        Index("ix_evaluation_logs_experiment_created", "experiment_name", "created_at"),
    )
