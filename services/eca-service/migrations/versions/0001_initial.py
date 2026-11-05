"""clubs, activities and memberships

Revision ID: 0001
Revises:
Create Date: 2026-11-02
"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('clubs',
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('tagline', sa.String(length=300), nullable=False),
    sa.Column('about', sa.Text(), nullable=False),
    sa.Column('logo', sa.String(length=300), nullable=False),
    sa.Column('photo', sa.String(length=300), nullable=False),
    sa.Column('photo_alt', sa.String(length=200), nullable=False),
    sa.Column('coordinator_name', sa.String(length=120), nullable=False),
    sa.Column('coordinator_email', sa.String(length=254), nullable=False),
    sa.Column('meeting_info', sa.String(length=200), nullable=False),
    sa.Column('join_open', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clubs_slug'), 'clubs', ['slug'], unique=True)
    op.create_table('activities',
    sa.Column('club_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('happened_on', sa.DateTime(timezone=True), nullable=True),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('photo', sa.String(length=300), nullable=False),
    sa.Column('photo_alt', sa.String(length=200), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activities_club_id'), 'activities', ['club_id'], unique=False)
    op.create_index(op.f('ix_activities_happened_on'), 'activities', ['happened_on'], unique=False)
    op.create_table('memberships',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('club_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('position', sa.String(length=60), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_by', sa.String(length=254), nullable=False),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('club_id', 'email', name='uq_membership_club_email')
    )
    op.create_index(op.f('ix_memberships_club_id'), 'memberships', ['club_id'], unique=False)
    op.create_index(op.f('ix_memberships_status'), 'memberships', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_memberships_status'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_club_id'), table_name='memberships')
    op.drop_table('memberships')
    op.drop_index(op.f('ix_activities_happened_on'), table_name='activities')
    op.drop_index(op.f('ix_activities_club_id'), table_name='activities')
    op.drop_table('activities')
    op.drop_index(op.f('ix_clubs_slug'), table_name='clubs')
    op.drop_table('clubs')
