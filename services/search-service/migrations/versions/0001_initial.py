"""search documents with a full-text index

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

VECTOR_SQL = ("setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') || "
              "setweight(to_tsvector('simple'::regconfig, coalesce(summary, '')), 'B') || "
              "setweight(to_tsvector('simple'::regconfig, coalesce(body, '')), 'C')")


def upgrade():
    op.create_table(
        "documents",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.String(600), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.String(300), nullable=False),
        sa.Column("in_sitemap", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_source", "documents", ["source"])
    op.create_index("ix_documents_kind", "documents", ["kind"])
    op.execute(f"CREATE INDEX ix_documents_search ON documents USING gin (({VECTOR_SQL}))")


def downgrade():
    op.drop_table("documents")
