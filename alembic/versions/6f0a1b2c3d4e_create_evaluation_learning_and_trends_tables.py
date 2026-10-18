"""create_evaluation_learning_and_trends_tables

Revision ID: 6f0a1b2c3d4e
Revises: 5e9f2b3c4d5a
Create Date: 2026-10-18 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6f0a1b2c3d4e'
down_revision: Union[str, Sequence[str], None] = '5e9f2b3c4d5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evaluation_logs, learning_resources, and job_market_trends tables."""
    # 1. evaluation_logs table
    op.create_table(
        'evaluation_logs',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('experiment_name', sa.Text(), nullable=False),
        sa.Column('run_id', sa.Text(), nullable=False),
        sa.Column('component', sa.Text(), nullable=False),
        sa.Column('metric_name', sa.Text(), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('n_samples', sa.Integer(), nullable=True),
        sa.Column('ci_low', sa.Float(), nullable=True),
        sa.Column('ci_high', sa.Float(), nullable=True),
        sa.Column('model_name', sa.Text(), nullable=True),
        sa.Column('model_hash', sa.Text(), nullable=True),
        sa.Column('dataset_sha256', sa.Text(), nullable=False),
        sa.Column('git_commit', sa.Text(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'component', 'metric_name', name='uq_evaluation_logs_run_component_metric'),
    )
    op.create_index('ix_evaluation_logs_experiment_created', 'evaluation_logs', ['experiment_name', 'created_at'], unique=False)

    # 2. learning_resources table
    op.create_table(
        'learning_resources',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('provider', sa.Text(), nullable=True),
        sa.Column('resource_type', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.Text(), nullable=False),
        sa.Column('est_hours', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('url_status', sa.Integer(), nullable=True),
        sa.Column('url_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.Text(), server_default=sa.text("'curated_seed'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "resource_type IN ('official_docs', 'course', 'book', 'tutorial', 'practice')",
            name='ck_learning_resources_resource_type',
        ),
        sa.CheckConstraint(
            "difficulty IN ('beginner', 'intermediate', 'advanced')",
            name='ck_learning_resources_difficulty',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('skill_name', 'title', 'provider', name='uq_learning_resources_skill_title_provider'),
    )
    op.create_index('ix_learning_resources_skill_name', 'learning_resources', ['skill_name'], unique=False)
    op.create_index('ix_learning_resources_is_active', 'learning_resources', ['is_active'], unique=False)

    # 3. job_market_trends table
    op.create_table(
        'job_market_trends',
        sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('skill_name', sa.Text(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('period_type', sa.Text(), nullable=False),
        sa.Column('postings_with_skill', sa.Integer(), nullable=False),
        sa.Column('total_postings', sa.Integer(), nullable=False),
        sa.Column('demand_share', sa.Float(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('source_snapshot_sha256', sa.Text(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "period_type IN ('snapshot', 'month')",
            name='ck_job_market_trends_period_type',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'skill_name', 'period_start', 'period_end', 'period_type', 'source',
            name='uq_job_market_trends_skill_period_source',
        ),
    )
    op.create_index('ix_job_market_trends_skill_period', 'job_market_trends', ['skill_name', 'period_start'], unique=False)


def downgrade() -> None:
    """Drop only the three newly added tables in reverse order."""
    op.drop_index('ix_job_market_trends_skill_period', table_name='job_market_trends')
    op.drop_table('job_market_trends')

    op.drop_index('ix_learning_resources_is_active', table_name='learning_resources')
    op.drop_index('ix_learning_resources_skill_name', table_name='learning_resources')
    op.drop_table('learning_resources')

    op.drop_index('ix_evaluation_logs_experiment_created', table_name='evaluation_logs')
    op.drop_table('evaluation_logs')
