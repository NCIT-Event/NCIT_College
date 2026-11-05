"""admission-service data: intakes, the programmes offered in each, and applications."""

from datetime import datetime

from ncit_common.models import Tracked, UTCDateTime, new_id, utcnow
from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Intake(Tracked, Base):
    """One admission round, e.g. "Fall 2026", open between two dates."""

    __tablename__ = "intakes"

    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    intro: Mapped[str] = mapped_column(Text, default="")  # what applicants should know
    opens_at: Mapped[datetime] = mapped_column(UTCDateTime())
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime())

    offerings: Mapped[list["Offering"]] = relationship(back_populates="intake", cascade="all, delete-orphan",
                                                       passive_deletes=True, order_by="Offering.sort_order")


class Offering(Tracked, Base):
    """A programme open for applications in an intake."""

    __tablename__ = "offerings"

    intake_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("intakes.id", ondelete="CASCADE"), index=True)
    programme: Mapped[str] = mapped_column(String(160))
    department: Mapped[str] = mapped_column(String(40), default="")  # department code, e.g. computer
    level: Mapped[str] = mapped_column(String(20), default="bachelor")
    seats: Mapped[int] = mapped_column(Integer, default=0)
    eligibility: Mapped[str] = mapped_column(Text, default="")
    fee_note: Mapped[str] = mapped_column(String(300), default="")

    intake: Mapped[Intake] = relationship(back_populates="offerings")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("email", "intake_id", name="uq_application_email_intake"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    reference: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True)  # given on first submit
    user_id: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(254), index=True)
    intake_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("intakes.id"), index=True)
    offering_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("offerings.id"), index=True)
    second_choice_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("offerings.id"), nullable=True)
    # draft | submitted | under_review | documents_requested | accepted | waitlisted | rejected | withdrawn
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)

    # about the applicant
    full_name: Mapped[str] = mapped_column(String(160), default="")
    date_of_birth: Mapped[str] = mapped_column(String(10), default="")  # YYYY-MM-DD
    gender: Mapped[str] = mapped_column(String(20), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    guardian_name: Mapped[str] = mapped_column(String(160), default="")
    guardian_phone: Mapped[str] = mapped_column(String(30), default="")
    # previous study
    school: Mapped[str] = mapped_column(String(200), default="")
    board: Mapped[str] = mapped_column(String(80), default="")  # e.g. NEB, A-Level
    passed_year: Mapped[str] = mapped_column(String(4), default="")
    grade: Mapped[str] = mapped_column(String(20), default="")  # GPA or percentage as written on the transcript
    entrance_score: Mapped[str] = mapped_column(String(20), default="")
    # documents (private file keys, see ncit_common.media)
    photo: Mapped[str] = mapped_column(String(120), default="")
    transcript: Mapped[str] = mapped_column(String(120), default="")
    citizenship: Mapped[str] = mapped_column(String(120), default="")

    # the admissions office
    message: Mapped[str] = mapped_column(Text, default="")  # latest note shown to the applicant
    officer_note: Mapped[str] = mapped_column(Text, default="")  # internal, never shown to the applicant
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, index=True)

    intake: Mapped[Intake] = relationship()
    offering: Mapped[Offering] = relationship(foreign_keys=[offering_id])
    second_choice: Mapped[Offering | None] = relationship(foreign_keys=[second_choice_id])
    history: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application", cascade="all, delete-orphan",
                                                             order_by="ApplicationEvent.at")


class ApplicationEvent(Base):
    """One step in an application's history: submitted, under review, accepted …"""

    __tablename__ = "application_events"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("applications.id", ondelete="CASCADE"), index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    by: Mapped[str] = mapped_column(String(254), default="")
    from_status: Mapped[str] = mapped_column(String(20), default="")
    to_status: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")  # shown to the applicant
    emailed: Mapped[bool] = mapped_column(default=False)

    application: Mapped[Application] = relationship(back_populates="history")
