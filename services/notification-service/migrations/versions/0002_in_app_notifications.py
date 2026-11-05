"""in-app notifications (the bell)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('queue_id', sa.String(length=32), nullable=False),
    sa.Column('to_email', sa.String(length=254), nullable=False),
    sa.Column('to_role', sa.String(length=40), nullable=False),
    sa.Column('to_scope', sa.String(length=80), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('link', sa.String(length=300), nullable=False),
    sa.Column('service', sa.String(length=40), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('queue_id')
    )
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    op.create_index('ix_notifications_role_scope', 'notifications', ['to_role', 'to_scope', 'created_at'], unique=False)
    op.create_index(op.f('ix_notifications_to_email'), 'notifications', ['to_email'], unique=False)
    op.create_table('notification_reads',
    sa.Column('notification_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('notification_id', 'email')
    )


def downgrade():
    op.drop_table('notification_reads')
    op.drop_index(op.f('ix_notifications_to_email'), table_name='notifications')
    op.drop_index('ix_notifications_role_scope', table_name='notifications')
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_table('notifications')
