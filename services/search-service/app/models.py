"""search-service data: one row per searchable thing on the public website."""

from datetime import datetime

import sqlalchemy.dialects.postgresql  # noqa: F401  (registers to_tsquery & co. before they are used)
from ncit_common.models import UTCDateTime, utcnow
from sqlalchemy import Index, String, Text, literal_column, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)  # e.g. "news:robotics-club-irrigation-sensor"
    source: Mapped[str] = mapped_column(String(20), index=True)  # which service it came from
    kind: Mapped[str] = mapped_column(String(20), index=True)  # department, faculty, news, notice, event, …
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str] = mapped_column(String(600), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(300))
    in_sitemap: Mapped[bool] = mapped_column(default=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)  # when the content changed
    indexed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


# PostgreSQL full-text index: title counts most, then summary, then body.
# "simple" configuration: no English stemming, so Nepali names and words work too.
# The same SQL is used in the index and in queries, so PostgreSQL uses the index.
VECTOR_SQL = ("setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') || "
              "setweight(to_tsvector('simple'::regconfig, coalesce(summary, '')), 'B') || "
              "setweight(to_tsvector('simple'::regconfig, coalesce(body, '')), 'C')")
SEARCH_VECTOR = literal_column(f"({VECTOR_SQL})")
CFG = literal_column("'simple'::regconfig")
Index("ix_documents_search", text(f"({VECTOR_SQL})"), postgresql_using="gin").ddl_if(dialect="postgresql")
