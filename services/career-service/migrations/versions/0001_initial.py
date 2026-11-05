"""vacancies and job applications

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('jobs',
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('department', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('employment', sa.String(length=12), nullable=False),
    sa.Column('positions', sa.Integer(), nullable=False),
    sa.Column('summary', sa.String(length=400), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('requirements', sa.Text(), nullable=False),
    sa.Column('attachment', sa.String(length=300), nullable=False),
    sa.Column('closes_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_closes_at'), 'jobs', ['closes_at'], unique=False)
    op.create_index(op.f('ix_jobs_slug'), 'jobs', ['slug'], unique=True)
    op.create_table('job_applications',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('job_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('qualification', sa.String(length=200), nullable=False),
    sa.Column('experience_years', sa.String(length=10), nullable=False),
    sa.Column('cover_letter', sa.Text(), nullable=False),
    sa.Column('cv', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('hr_note', sa.Text(), nullable=False),
    sa.Column('history', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id', 'email', name='uq_job_application_email')
    )
    op.create_index(op.f('ix_job_applications_created_at'), 'job_applications', ['created_at'], unique=False)
    op.create_index(op.f('ix_job_applications_email'), 'job_applications', ['email'], unique=False)
    op.create_index(op.f('ix_job_applications_job_id'), 'job_applications', ['job_id'], unique=False)
    op.create_index(op.f('ix_job_applications_status'), 'job_applications', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_job_applications_status'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_job_id'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_email'), table_name='job_applications')
    op.drop_index(op.f('ix_job_applications_created_at'), table_name='job_applications')
    op.drop_table('job_applications')
    op.drop_index(op.f('ix_jobs_slug'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_closes_at'), table_name='jobs')
    op.drop_table('jobs')
