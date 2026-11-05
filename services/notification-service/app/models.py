"""notification-service data: every email the website sent (or tried to)."""

from datetime import datetime

from ncit_common.models import UTCDateTime, new_id, utcnow
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    queue_id: Mapped[str] = mapped_column(String(32), unique=True)  # id given by the sending service (idempotency)
    to: Mapped[str] = mapped_column(String(254), index=True)
    template: Mapped[str] = mapped_column(String(40), index=True)
    service: Mapped[str] = mapped_column(String(40), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    # sent | logged (no mail server configured) | failed
    status: Mapped[str] = mapped_column(String(10), default="failed", index=True)
    error: Mapped[str] = mapped_column(String(500), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Notification(Base):
    """An in-app notification (the bell): for one person (to_email) or for everyone with a role."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_role_scope", "to_role", "to_scope", "created_at"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    queue_id: Mapped[str] = mapped_column(String(32), unique=True)  # id given by the sending service (idempotency)
    to_email: Mapped[str] = mapped_column(String(254), default="", index=True)
    to_role: Mapped[str] = mapped_column(String(40), default="")
    to_scope: Mapped[str] = mapped_column(String(80), default="*")
    kind: Mapped[str] = mapped_column(String(10), default="info")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(300), default="")
    service: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class NotificationRead(Base):
    """Who has read what. One row per person per notification (role notifications are shared)."""

    __tablename__ = "notification_reads"

    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
