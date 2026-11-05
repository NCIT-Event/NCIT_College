"""career-service data: job vacancies and the applications for them."""

from datetime import datetime

from ncit_common.models import Tracked, UTCDateTime, new_id, utcnow
from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Tracked, Base):
    __tablename__ = "jobs"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(120), default="")
    kind: Mapped[str] = mapped_column(String(10), default="faculty")  # faculty | staff
    employment: Mapped[str] = mapped_column(String(12), default="full_time")  # full_time | part_time | contract
    positions: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(String(400), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    attachment: Mapped[str] = mapped_column(String(300), default="")  # job description PDF (public)
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)

    applications: Mapped[list["JobApplication"]] = relationship(back_populates="job")


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (UniqueConstraint("job_id", "email", name="uq_job_application_email"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("jobs.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(254), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(30), default="")
    qualification: Mapped[str] = mapped_column(String(200), default="")  # highest degree, e.g. ME Computer, TU
    experience_years: Mapped[str] = mapped_column(String(10), default="")
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    cv: Mapped[str] = mapped_column(String(120), default="")  # private file key
    # submitted | shortlisted | interview | offered | rejected | withdrawn
    status: Mapped[str] = mapped_column(String(12), default="submitted", index=True)
    message: Mapped[str] = mapped_column(Text, default="")  # shown to the applicant (e.g. interview time)
    hr_note: Mapped[str] = mapped_column(Text, default="")  # internal
    history: Mapped[list] = mapped_column(JSON, default=list)  # [{at, status, by, message}]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    job: Mapped[Job] = relationship(back_populates="applications")
