"""alumni-service data: one profile per alumnus, verified by the Alumni Coordinator."""

from datetime import datetime

from ncit_common.models import UTCDateTime, new_id, utcnow
from sqlalchemy import Boolean, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AlumniProfile(Base):
    __tablename__ = "alumni"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="")
    # what the coordinator checks against the college's records
    full_name: Mapped[str] = mapped_column(String(160), default="")
    programme: Mapped[str] = mapped_column(String(120), default="")
    graduation_year: Mapped[str] = mapped_column(String(4), default="", index=True)
    registration_no: Mapped[str] = mapped_column(String(40), default="")  # Pokhara University registration number
    phone: Mapped[str] = mapped_column(String(30), default="")  # private
    # shown in the directory once verified (if they agree)
    current_role: Mapped[str] = mapped_column(String(120), default="")
    employer: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    country: Mapped[str] = mapped_column(String(80), default="Nepal")
    linkedin_url: Mapped[str] = mapped_column(String(300), default="")
    bio: Mapped[str] = mapped_column(String(400), default="")
    photo: Mapped[str] = mapped_column(String(300), default="")
    show_in_directory: Mapped[bool] = mapped_column(Boolean, default=False)
    # draft | pending | verified | rejected
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    review_note: Mapped[str] = mapped_column(Text, default="")  # reason given to the alumnus when not verified
    featured: Mapped[bool] = mapped_column(Boolean, default=False)  # shown on the home page
    verified_by: Mapped[str] = mapped_column(String(254), default="")
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
