"""email log

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
    op.create_table('messages',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('queue_id', sa.String(length=32), nullable=False),
    sa.Column('to', sa.String(length=254), nullable=False),
    sa.Column('template', sa.String(length=40), nullable=False),
    sa.Column('service', sa.String(length=40), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('error', sa.String(length=500), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('sensitive', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('queue_id')
    )
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'], unique=False)
    op.create_index(op.f('ix_messages_status'), 'messages', ['status'], unique=False)
    op.create_index(op.f('ix_messages_template'), 'messages', ['template'], unique=False)
    op.create_index(op.f('ix_messages_to'), 'messages', ['to'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_messages_to'), table_name='messages')
    op.drop_index(op.f('ix_messages_template'), table_name='messages')
    op.drop_index(op.f('ix_messages_status'), table_name='messages')
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_table('messages')
