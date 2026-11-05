"""departments, programmes, courses, faculty, labs, testimonials

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ID = sa.Uuid(as_uuid=False)


def _dept_fk():
    return sa.Column("department_id", ID, sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)


def upgrade():
    op.create_table(
        "departments",
        sa.Column("id", ID, primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("tagline", sa.String(300), nullable=False, server_default=""),
        sa.Column("overview", sa.Text(), nullable=False, server_default=""),
        sa.Column("hero_photo", sa.String(300), nullable=False, server_default=""),
        sa.Column("contact_email", sa.String(254), nullable=False, server_default=""),
        sa.Column("contact_phone", sa.String(60), nullable=False, server_default=""),
        sa.Column("office", sa.String(200), nullable=False, server_default=""),
        sa.Column("hod_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("hod_title", sa.String(160), nullable=False, server_default=""),
        sa.Column("hod_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("hod_photo", sa.String(300), nullable=False, server_default=""),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(254), nullable=False, server_default=""),
    )
    op.create_index("ix_departments_slug", "departments", ["slug"], unique=True)

    op.create_table(
        "programmes",
        sa.Column("id", ID, primary_key=True), _dept_fk(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="bachelor"),
        sa.Column("duration_years", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("affiliation", sa.String(120), nullable=False, server_default="Pokhara University"),
        sa.Column("eligibility", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("syllabus_url", sa.String(300), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_programmes_department_id", "programmes", ["department_id"])

    op.create_table(
        "courses",
        sa.Column("id", ID, primary_key=True),
        sa.Column("programme_id", ID, sa.ForeignKey("programmes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semester", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(20), nullable=False, server_default=""),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("credits", sa.Numeric(4, 1), nullable=False, server_default="3"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_courses_programme_id", "courses", ["programme_id"])

    op.create_table(
        "faculty",
        sa.Column("id", ID, primary_key=True), _dept_fk(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("designation", sa.String(120), nullable=False, server_default=""),
        sa.Column("specialization", sa.String(200), nullable=False, server_default=""),
        sa.Column("email", sa.String(254), nullable=False, server_default=""),
        sa.Column("photo", sa.String(300), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_faculty_department_id", "faculty", ["department_id"])

    op.create_table(
        "labs",
        sa.Column("id", ID, primary_key=True), _dept_fk(),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("photo", sa.String(300), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_labs_department_id", "labs", ["department_id"])

    op.create_table(
        "testimonials",
        sa.Column("id", ID, primary_key=True), _dept_fk(),
        sa.Column("student_name", sa.String(120), nullable=False),
        sa.Column("programme_label", sa.String(160), nullable=False, server_default=""),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("photo", sa.String(300), nullable=False, server_default=""),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_testimonials_department_id", "testimonials", ["department_id"])


def downgrade():
    for table in ("testimonials", "labs", "faculty", "courses", "programmes", "departments"):
        op.drop_table(table)
