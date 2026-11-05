"""academics-service data: departments and everything shown on a department page.

All text is stored as plain text and escaped when shown, so editors cannot
inject markup. Blank lines in long fields become paragraphs on the page.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    # the slug is also the HOD role scope: dept:<slug>
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(300), default="")
    overview: Mapped[str] = mapped_column(Text, default="")
    hero_photo: Mapped[str] = mapped_column(String(300), default="")
    contact_email: Mapped[str] = mapped_column(String(254), default="")
    contact_phone: Mapped[str] = mapped_column(String(60), default="")
    office: Mapped[str] = mapped_column(String(200), default="")
    hod_name: Mapped[str] = mapped_column(String(120), default="")
    hod_title: Mapped[str] = mapped_column(String(160), default="")
    hod_message: Mapped[str] = mapped_column(Text, default="")
    hod_photo: Mapped[str] = mapped_column(String(300), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[str] = mapped_column(String(254), default="")

    programmes: Mapped[list["Programme"]] = relationship(
        back_populates="department", cascade="all, delete-orphan", order_by="Programme.sort_order")
    faculty: Mapped[list["Faculty"]] = relationship(cascade="all, delete-orphan", order_by="Faculty.sort_order")
    labs: Mapped[list["Lab"]] = relationship(cascade="all, delete-orphan", order_by="Lab.sort_order")
    testimonials: Mapped[list["Testimonial"]] = relationship(
        cascade="all, delete-orphan", order_by="Testimonial.sort_order")


class Programme(Base):
    __tablename__ = "programmes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    level: Mapped[str] = mapped_column(String(20), default="bachelor")  # bachelor | master
    duration_years: Mapped[int] = mapped_column(Integer, default=4)
    affiliation: Mapped[str] = mapped_column(String(120), default="Pokhara University")
    eligibility: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    syllabus_url: Mapped[str] = mapped_column(String(300), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    department: Mapped[Department] = relationship(back_populates="programmes")
    courses: Mapped[list["Course"]] = relationship(
        cascade="all, delete-orphan", order_by="(Course.semester, Course.sort_order)")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    programme_id: Mapped[str] = mapped_column(ForeignKey("programmes.id", ondelete="CASCADE"), index=True)
    semester: Mapped[int] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(20), default="")
    title: Mapped[str] = mapped_column(String(200))
    credits: Mapped[float] = mapped_column(Numeric(4, 1), default=3)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Faculty(Base):
    __tablename__ = "faculty"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    designation: Mapped[str] = mapped_column(String(120), default="")
    specialization: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    photo: Mapped[str] = mapped_column(String(300), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    photo: Mapped[str] = mapped_column(String(300), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Testimonial(Base):
    __tablename__ = "testimonials"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True)
    student_name: Mapped[str] = mapped_column(String(120))
    programme_label: Mapped[str] = mapped_column(String(160), default="")  # e.g. "BE Computer, 7th semester"
    quote: Mapped[str] = mapped_column(Text)
    photo: Mapped[str] = mapped_column(String(300), default="")
    # only approved testimonials appear on the public page
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
