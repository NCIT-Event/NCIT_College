"""audit log

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("service", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("actor_email", sa.String(254), nullable=False, server_default=""),
        sa.Column("entity", sa.String(64), nullable=False, server_default=""),
        sa.Column("entity_id", sa.String(254), nullable=False, server_default=""),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("ip", sa.String(64), nullable=False, server_default=""),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_type", "audit_log", ["type"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])
    op.create_index("ix_audit_log_at", "audit_log", ["at"])


def downgrade():
    op.drop_table("audit_log")
