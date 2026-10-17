"""create users table and resume ownership
 
Revision ID: 4d8f1a2b3c4e
Revises: 2c9e71a9dd54
Create Date: 2026-10-17 12:30:00.000000
 
"""
from typing import Sequence, Union
 
from alembic import op
import sqlalchemy as sa
 
 
# revision identifiers, used by Alembic.
revision: str = '4d8f1a2b3c4e'
down_revision: Union[str, Sequence[str], None] = '2c9e71a9dd54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
 
 
def upgrade() -> None:
    """Upgrade schema: create users table and add user_id relationship to resumes."""
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
 
    op.add_column("resumes", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_resumes_user_id_users",
        "resumes",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
 
 
def downgrade() -> None:
    """Downgrade schema: drop resume ownership and users table."""
    op.drop_constraint("fk_resumes_user_id_users", "resumes", type_="foreignkey")
    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_column("resumes", "user_id")
 
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
