"""banners, leadership messages, news, notices, facilities

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ID = sa.Uuid(as_uuid=False)
TS = sa.DateTime(timezone=True)


def tracked():
    return [
        sa.Column("id", ID, primary_key=True),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(254), nullable=False, server_default=""),
    ]


def text(name, length=None):
    kind = sa.String(length) if length else sa.Text()
    return sa.Column(name, kind, nullable=False, server_default="")


def upgrade():
    op.create_table(
        "banners", *tracked(),
        sa.Column("title", sa.String(160), nullable=False),
        text("subtitle", 300), text("image", 300), text("image_alt", 200),
        text("cta_label", 40), text("cta_url", 300), text("cta2_label", 40), text("cta2_url", 300),
        sa.Column("start_at", TS, nullable=True), sa.Column("end_at", TS, nullable=True),
    )
    op.create_table(
        "leadership_messages", *tracked(),
        sa.Column("position", sa.String(40), nullable=False, unique=True),
        sa.Column("person_name", sa.String(120), nullable=False),
        text("role_title", 120), text("excerpt", 400), text("message"), text("photo", 300),
    )
    op.create_table(
        "news", *tracked(),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        text("summary", 400), text("body"), text("cover", 300), text("cover_alt", 200), text("category", 40),
        sa.Column("publish_at", TS, nullable=True),
    )
    op.create_index("ix_news_slug", "news", ["slug"], unique=True)
    op.create_index("ix_news_publish_at", "news", ["publish_at"])
    op.create_table(
        "notices", *tracked(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(20), nullable=False, server_default="general"),
        text("body"), text("attachment", 300), text("link_url", 300),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publish_at", TS, nullable=True), sa.Column("expires_at", TS, nullable=True),
    )
    op.create_index("ix_notices_publish_at", "notices", ["publish_at"])
    op.create_table(
        "facilities", *tracked(),
        sa.Column("name", sa.String(120), nullable=False),
        text("description"),
        sa.Column("icon", sa.String(40), nullable=False, server_default="building-2"),
        text("photo", 300),
    )


def downgrade():
    for table in ("facilities", "notices", "news", "leadership_messages", "banners"):
        op.drop_table(table)
