"""alumni profiles

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
    op.create_table('alumni',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('programme', sa.String(length=120), nullable=False),
    sa.Column('graduation_year', sa.String(length=4), nullable=False),
    sa.Column('registration_no', sa.String(length=40), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('current_role', sa.String(length=120), nullable=False),
    sa.Column('employer', sa.String(length=120), nullable=False),
    sa.Column('city', sa.String(length=80), nullable=False),
    sa.Column('country', sa.String(length=80), nullable=False),
    sa.Column('linkedin_url', sa.String(length=300), nullable=False),
    sa.Column('bio', sa.String(length=400), nullable=False),
    sa.Column('photo', sa.String(length=300), nullable=False),
    sa.Column('show_in_directory', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('review_note', sa.Text(), nullable=False),
    sa.Column('featured', sa.Boolean(), nullable=False),
    sa.Column('verified_by', sa.String(length=254), nullable=False),
    sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alumni_email'), 'alumni', ['email'], unique=True)
    op.create_index(op.f('ix_alumni_graduation_year'), 'alumni', ['graduation_year'], unique=False)
    op.create_index(op.f('ix_alumni_status'), 'alumni', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_alumni_status'), table_name='alumni')
    op.drop_index(op.f('ix_alumni_graduation_year'), table_name='alumni')
    op.drop_index(op.f('ix_alumni_email'), table_name='alumni')
    op.drop_table('alumni')
