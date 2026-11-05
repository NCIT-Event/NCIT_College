"""events and registrations

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
    op.create_table('events',
    sa.Column('slug', sa.String(length=120), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.String(length=400), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('organizer', sa.String(length=120), nullable=False),
    sa.Column('venue', sa.String(length=160), nullable=False),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cover', sa.String(length=300), nullable=False),
    sa.Column('cover_alt', sa.String(length=200), nullable=False),
    sa.Column('attachment', sa.String(length=300), nullable=False),
    sa.Column('registration_open', sa.Boolean(), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('registration_closes_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('external_url', sa.String(length=300), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_slug'), 'events', ['slug'], unique=True)
    op.create_index(op.f('ix_events_start_at'), 'events', ['start_at'], unique=False)
    op.create_table('registrations',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('event_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('attended', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'email', name='uq_registration_event_email')
    )
    op.create_index(op.f('ix_registrations_event_id'), 'registrations', ['event_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_registrations_event_id'), table_name='registrations')
    op.drop_table('registrations')
    op.drop_index(op.f('ix_events_start_at'), table_name='events')
    op.drop_index(op.f('ix_events_slug'), table_name='events')
    op.drop_table('events')
