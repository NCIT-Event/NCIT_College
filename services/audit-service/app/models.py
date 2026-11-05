"""audit-service data: one row per domain event, written by the worker."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, TypeDecorator, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class AuditEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    # the producer's event id; makes re-delivery from the stream harmless
    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    service: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    actor_email: Mapped[str] = mapped_column(String(254), default="")
    entity: Mapped[str] = mapped_column(String(64), default="")
    entity_id: Mapped[str] = mapped_column(String(254), default="", index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
