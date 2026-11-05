"""one-time sign-in codes for applicants and alumni

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "one_time_codes",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False),
    )
    op.create_index("ix_one_time_codes_email", "one_time_codes", ["email"])
    op.create_index("ix_one_time_codes_created_at", "one_time_codes", ["created_at"])


def downgrade():
    op.drop_index("ix_one_time_codes_created_at", table_name="one_time_codes")
    op.drop_index("ix_one_time_codes_email", table_name="one_time_codes")
    op.drop_table("one_time_codes")
