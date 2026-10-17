"""add_job_freshness_tracking_fields

Revision ID: 5e9f2b3c4d5a
Revises: 4d8f1a2b3c4e
Create Date: 2026-10-17 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e9f2b3c4d5a'
down_revision: Union[str, Sequence[str], None] = '4d8f1a2b3c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add freshness and ingestion tracking fields to job_postings table."""
    op.add_column(
        'job_postings',
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'job_postings',
        sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'job_postings',
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column(
        'job_postings',
        sa.Column('last_refreshed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'job_postings',
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )
    op.add_column(
        'job_postings',
        sa.Column('source_job_id', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'job_postings',
        sa.Column('source_url', sa.Text(), nullable=True),
    )
    op.add_column(
        'job_postings',
        sa.Column('freshness_status', sa.String(length=50), server_default=sa.text("'fresh'"), nullable=False),
    )

    op.create_index(op.f('ix_job_postings_is_active'), 'job_postings', ['is_active'], unique=False)
    op.create_index(op.f('ix_job_postings_source_job_id'), 'job_postings', ['source_job_id'], unique=False)
    op.create_index(op.f('ix_job_postings_freshness_status'), 'job_postings', ['freshness_status'], unique=False)


def downgrade() -> None:
    """Revert job freshness tracking fields."""
    op.drop_index(op.f('ix_job_postings_freshness_status'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_source_job_id'), table_name='job_postings')
    op.drop_index(op.f('ix_job_postings_is_active'), table_name='job_postings')

    op.drop_column('job_postings', 'freshness_status')
    op.drop_column('job_postings', 'source_url')
    op.drop_column('job_postings', 'source_job_id')
    op.drop_column('job_postings', 'is_active')
    op.drop_column('job_postings', 'last_refreshed_at')
    op.drop_column('job_postings', 'last_seen_at')
    op.drop_column('job_postings', 'first_seen_at')
    op.drop_column('job_postings', 'published_at')
