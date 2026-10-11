"""switch_embedding_to_384_dimensions

Revision ID: 2c9e71a9dd54
Revises: c38ab889b22a
Create Date: 2026-10-11 15:09:11.081206

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '2c9e71a9dd54'
down_revision: Union[str, Sequence[str], None] = 'c38ab889b22a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: alter vector dimensions from 1536 to 384."""
    op.execute("ALTER TABLE resumes ALTER COLUMN embedding TYPE vector(384) USING NULL;")
    op.execute("ALTER TABLE job_postings ALTER COLUMN embedding TYPE vector(384) USING NULL;")


def downgrade() -> None:
    """Downgrade schema: alter vector dimensions back to 1536."""
    op.execute("ALTER TABLE resumes ALTER COLUMN embedding TYPE vector(1536) USING NULL;")
    op.execute("ALTER TABLE job_postings ALTER COLUMN embedding TYPE vector(1536) USING NULL;")
