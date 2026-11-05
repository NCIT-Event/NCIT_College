"""eca-service data: clubs, their members and their activities."""

from datetime import datetime

from ncit_common.models import Tracked, UTCDateTime, new_id, utcnow
from sqlalchemy import (
    Boolean,
    ForeignKey,
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


class Club(Tracked, Base):
    __tablename__ = "clubs"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20), default="technical")
    tagline: Mapped[str] = mapped_column(String(300), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    logo: Mapped[str] = mapped_column(String(300), default="")
    photo: Mapped[str] = mapped_column(String(300), default="")
    photo_alt: Mapped[str] = mapped_column(String(200), default="")
    coordinator_name: Mapped[str] = mapped_column(String(120), default="")  # staff coordinator
    coordinator_email: Mapped[str] = mapped_column(String(254), default="")
    meeting_info: Mapped[str] = mapped_column(String(200), default="")  # e.g. "Fridays 15:00, Lab 2"
    join_open: Mapped[bool] = mapped_column(Boolean, default=True)

    activities: Mapped[list["Activity"]] = relationship(back_populates="club", cascade="all, delete-orphan",
                                                        passive_deletes=True)
    memberships: Mapped[list["Membership"]] = relationship(back_populates="club", cascade="all, delete-orphan",
                                                           passive_deletes=True)


class Activity(Tracked, Base):
    """Something a club did or is doing: a workshop, a trip, a competition result."""

    __tablename__ = "activities"

    club_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    happened_on: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    photo: Mapped[str] = mapped_column(String(300), default="")
    photo_alt: Mapped[str] = mapped_column(String(200), default="")

    club: Mapped[Club] = relationship(back_populates="activities")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("club_id", "email", name="uq_membership_club_email"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("clubs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(160), default="")
    # pending | approved | rejected | left
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    position: Mapped[str] = mapped_column(String(60), default="")  # e.g. President; empty = member
    message: Mapped[str] = mapped_column(String(500), default="")  # why they want to join
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(254), default="")

    club: Mapped[Club] = relationship(back_populates="memberships")


def _count(status: str):
    return column_property(
        select(func.count(Membership.id)).where(Membership.club_id == Club.id, Membership.status == status)
        .correlate_except(Membership).scalar_subquery())


Club.member_count = _count("approved")
Club.pending_count = _count("pending")
