"""content-service data: banners, leadership messages, news, notices, facilities.

Text is plain text (escaped when shown). Times are stored in UTC; editors
enter Nepal time in the dashboard.
"""

from datetime import datetime

from ncit_common.models import Tracked, UTCDateTime, new_id, utcnow  # noqa: F401  (re-exported)
from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Banner(Tracked, Base):
    """Home page banner slide (also used for ads and announcements)."""

    __tablename__ = "banners"

    title: Mapped[str] = mapped_column(String(160))
    subtitle: Mapped[str] = mapped_column(String(300), default="")
    image: Mapped[str] = mapped_column(String(300), default="")
    image_alt: Mapped[str] = mapped_column(String(200), default="")
    cta_label: Mapped[str] = mapped_column(String(40), default="")
    cta_url: Mapped[str] = mapped_column(String(300), default="")
    cta2_label: Mapped[str] = mapped_column(String(40), default="")
    cta2_url: Mapped[str] = mapped_column(String(300), default="")
    # shown only between these times (either may be empty = no limit)
    start_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class LeadershipMessage(Tracked, Base):
    __tablename__ = "leadership_messages"

    position: Mapped[str] = mapped_column(String(40), unique=True)  # executive_director | director | principal
    person_name: Mapped[str] = mapped_column(String(120))
    role_title: Mapped[str] = mapped_column(String(120), default="")
    excerpt: Mapped[str] = mapped_column(String(400), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    photo: Mapped[str] = mapped_column(String(300), default="")


class NewsArticle(Tracked, Base):
    __tablename__ = "news"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(400), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    cover: Mapped[str] = mapped_column(String(300), default="")
    cover_alt: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(40), default="")
    # goes live at this time once published (future = scheduled)
    publish_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)


class Notice(Tracked, Base):
    __tablename__ = "notices"

    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(20), default="general")
    body: Mapped[str] = mapped_column(Text, default="")
    attachment: Mapped[str] = mapped_column(String(300), default="")  # uploaded PDF
    link_url: Mapped[str] = mapped_column(String(300), default="")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    publish_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Facility(Tracked, Base):
    __tablename__ = "facilities"

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(40), default="building-2")
    photo: Mapped[str] = mapped_column(String(300), default="")
