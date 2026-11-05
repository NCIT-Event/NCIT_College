"""event-service data: events and the people registered for them.

Times are stored in UTC; editors enter Nepal time in the dashboard.
"""

from datetime import datetime

from ncit_common.models import Tracked, UTCDateTime, new_id, utcnow
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    column_property,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Event(Tracked, Base):
    __tablename__ = "events"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(400), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), default="general")
    organizer: Mapped[str] = mapped_column(String(120), default="")
    venue: Mapped[str] = mapped_column(String(160), default="")
    start_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    end_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cover: Mapped[str] = mapped_column(String(300), default="")
    cover_alt: Mapped[str] = mapped_column(String(200), default="")
    attachment: Mapped[str] = mapped_column(String(300), default="")  # programme / brochure PDF
    # registration: off, or open to signed-in college accounts
    registration_open: Mapped[bool] = mapped_column(Boolean, default=False)
    capacity: Mapped[int] = mapped_column(Integer, default=0)  # 0 = no limit
    registration_closes_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    external_url: Mapped[str] = mapped_column(String(300), default="")  # e.g. a ticketing or partner page

    registrations: Mapped[list["Registration"]] = relationship(back_populates="event", cascade="all, delete-orphan",
                                                               passive_deletes=True)


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (UniqueConstraint("event_id", "email", name="uq_registration_event_email"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(160), default="")
    # registered | waitlisted | cancelled
    status: Mapped[str] = mapped_column(String(12), default="registered")
    attended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    event: Mapped[Event] = relationship(back_populates="registrations")


# How many places are taken / waiting, loaded with each event (one subquery, no extra round trips).
Event.registered_count = column_property(
    select(func.count(Registration.id)).where(Registration.event_id == Event.id, Registration.status == "registered")
    .correlate_except(Registration).scalar_subquery())
Event.waitlist_count = column_property(
    select(func.count(Registration.id)).where(Registration.event_id == Event.id, Registration.status == "waitlisted")
    .correlate_except(Registration).scalar_subquery())
