"""intakes, programmes on offer, applications and their history

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
    op.create_table('intakes',
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('intro', sa.Text(), nullable=False),
    sa.Column('opens_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('closes_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_intakes_slug'), 'intakes', ['slug'], unique=True)
    op.create_table('offerings',
    sa.Column('intake_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('programme', sa.String(length=160), nullable=False),
    sa.Column('department', sa.String(length=40), nullable=False),
    sa.Column('level', sa.String(length=20), nullable=False),
    sa.Column('seats', sa.Integer(), nullable=False),
    sa.Column('eligibility', sa.Text(), nullable=False),
    sa.Column('fee_note', sa.String(length=300), nullable=False),
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('published', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.String(length=254), nullable=False),
    sa.ForeignKeyConstraint(['intake_id'], ['intakes.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_offerings_intake_id'), 'offerings', ['intake_id'], unique=False)
    op.create_table('applications',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('reference', sa.String(length=24), nullable=True),
    sa.Column('user_id', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('intake_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('offering_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('second_choice_id', sa.Uuid(as_uuid=False), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('date_of_birth', sa.String(length=10), nullable=False),
    sa.Column('gender', sa.String(length=20), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('address', sa.String(length=300), nullable=False),
    sa.Column('guardian_name', sa.String(length=160), nullable=False),
    sa.Column('guardian_phone', sa.String(length=30), nullable=False),
    sa.Column('school', sa.String(length=200), nullable=False),
    sa.Column('board', sa.String(length=80), nullable=False),
    sa.Column('passed_year', sa.String(length=4), nullable=False),
    sa.Column('grade', sa.String(length=20), nullable=False),
    sa.Column('entrance_score', sa.String(length=20), nullable=False),
    sa.Column('photo', sa.String(length=120), nullable=False),
    sa.Column('transcript', sa.String(length=120), nullable=False),
    sa.Column('citizenship', sa.String(length=120), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('officer_note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['intake_id'], ['intakes.id'], ),
    sa.ForeignKeyConstraint(['offering_id'], ['offerings.id'], ),
    sa.ForeignKeyConstraint(['second_choice_id'], ['offerings.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', 'intake_id', name='uq_application_email_intake'),
    sa.UniqueConstraint('reference')
    )
    op.create_index(op.f('ix_applications_email'), 'applications', ['email'], unique=False)
    op.create_index(op.f('ix_applications_intake_id'), 'applications', ['intake_id'], unique=False)
    op.create_index(op.f('ix_applications_offering_id'), 'applications', ['offering_id'], unique=False)
    op.create_index(op.f('ix_applications_status'), 'applications', ['status'], unique=False)
    op.create_index(op.f('ix_applications_submitted_at'), 'applications', ['submitted_at'], unique=False)
    op.create_table('application_events',
    sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('application_id', sa.Uuid(as_uuid=False), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('by', sa.String(length=254), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=False),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('emailed', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_events_application_id'), 'application_events', ['application_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_application_events_application_id'), table_name='application_events')
    op.drop_table('application_events')
    op.drop_index(op.f('ix_applications_submitted_at'), table_name='applications')
    op.drop_index(op.f('ix_applications_status'), table_name='applications')
    op.drop_index(op.f('ix_applications_offering_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_intake_id'), table_name='applications')
    op.drop_index(op.f('ix_applications_email'), table_name='applications')
    op.drop_table('applications')
    op.drop_index(op.f('ix_offerings_intake_id'), table_name='offerings')
    op.drop_table('offerings')
    op.drop_index(op.f('ix_intakes_slug'), table_name='intakes')
    op.drop_table('intakes')
