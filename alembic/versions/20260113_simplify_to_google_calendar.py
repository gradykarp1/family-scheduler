"""Simplify schema - Google Calendar as event source of truth

Revision ID: 8a2f4c91d3e5
Revises: b55476051083
Create Date: 2026-01-13

This migration removes tables for local event storage since events are now
stored in Google Calendar. Only family configuration remains in PostgreSQL:
- family_members: Family member profiles and preferences
- calendars: Google Calendar references and configuration
- resources: Shared family resources (with optional Google Calendar for availability)
- constraints: Scheduling rules and preferences

Removed tables:
- events: Events are now stored in Google Calendar
- event_participants: Participants tracked in Google Calendar
- conflicts: Detected dynamically from calendar data
- resource_reservations: Resource availability tracked via Google Calendar
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a2f4c91d3e5'
down_revision: Union[str, None] = 'b55476051083'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop tables that are no longer needed (events are in Google Calendar now)
    # Must drop in correct order due to foreign key constraints

    # 1. Drop resource_reservations (depends on events, resources, family_members)
    with op.batch_alter_table('resource_reservations', schema=None) as batch_op:
        batch_op.drop_index('idx_reservation_status_time')
        batch_op.drop_index('idx_reservation_status')
        batch_op.drop_index('idx_reservation_resource_time')
        batch_op.drop_index('idx_reservation_resource')
        batch_op.drop_index('idx_reservation_reserver')
        batch_op.drop_index('idx_reservation_event')
        batch_op.drop_index('idx_reservation_deleted')
    op.drop_table('resource_reservations')

    # 2. Drop event_participants (depends on events, family_members)
    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.drop_index('idx_participant_required')
        batch_op.drop_index('idx_participant_member')
        batch_op.drop_index('idx_participant_event')
    op.drop_table('event_participants')

    # 3. Drop conflicts (depends on events)
    with op.batch_alter_table('conflicts', schema=None) as batch_op:
        batch_op.drop_index('idx_conflict_type')
        batch_op.drop_index('idx_conflict_status_detected')
        batch_op.drop_index('idx_conflict_status')
        batch_op.drop_index('idx_conflict_severity')
        batch_op.drop_index('idx_conflict_proposed_event')
        batch_op.drop_index('idx_conflict_detected_at')
        batch_op.drop_index('idx_conflict_deleted')
        batch_op.drop_index('idx_conflict_conflicting_event')
    op.drop_table('conflicts')

    # 4. Drop events (depends on calendars, family_members)
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_index('idx_event_time_range')
        batch_op.drop_index('idx_event_status_time')
        batch_op.drop_index('idx_event_status')
        batch_op.drop_index('idx_event_start_time')
        batch_op.drop_index('idx_event_original')
        batch_op.drop_index('idx_event_end_time')
        batch_op.drop_index('idx_event_deleted')
        batch_op.drop_index('idx_event_created_by')
        batch_op.drop_index('idx_event_calendar')
    op.drop_table('events')

    # Add google_calendar_id column to calendars table
    with op.batch_alter_table('calendars', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('google_calendar_id', sa.String(length=255), nullable=True)
        )
        batch_op.create_index('idx_calendar_google_id', ['google_calendar_id'], unique=False)

    # Add google_calendar_id column to resources table
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('google_calendar_id', sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    # Remove google_calendar_id columns
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_column('google_calendar_id')

    with op.batch_alter_table('calendars', schema=None) as batch_op:
        batch_op.drop_index('idx_calendar_google_id')
        batch_op.drop_column('google_calendar_id')

    # Recreate events table
    op.create_table('events',
        sa.Column('calendar_id', sa.CHAR(length=32), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('all_day', sa.Boolean(), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=50), nullable=False),
        sa.Column('flexibility', sa.String(length=50), nullable=False),
        sa.Column('recurrence_rule', sa.String(length=500), nullable=True),
        sa.Column('recurrence_id', sa.String(length=100), nullable=True),
        sa.Column('original_event_id', sa.CHAR(length=32), nullable=True),
        sa.Column('proposed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.CHAR(length=32), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=False),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['calendar_id'], ['calendars.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['family_members.id'], ),
        sa.ForeignKeyConstraint(['original_event_id'], ['events.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.create_index('idx_event_calendar', ['calendar_id'], unique=False)
        batch_op.create_index('idx_event_created_by', ['created_by'], unique=False)
        batch_op.create_index('idx_event_deleted', ['deleted_at'], unique=False)
        batch_op.create_index('idx_event_end_time', ['end_time'], unique=False)
        batch_op.create_index('idx_event_original', ['original_event_id'], unique=False)
        batch_op.create_index('idx_event_start_time', ['start_time'], unique=False)
        batch_op.create_index('idx_event_status', ['status'], unique=False)
        batch_op.create_index('idx_event_status_time', ['status', 'start_time', 'end_time'], unique=False)
        batch_op.create_index('idx_event_time_range', ['calendar_id', 'start_time', 'end_time'], unique=False)

    # Recreate conflicts table
    op.create_table('conflicts',
        sa.Column('proposed_event_id', sa.CHAR(length=32), nullable=False),
        sa.Column('conflicting_event_id', sa.CHAR(length=32), nullable=True),
        sa.Column('conflict_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_participants', sa.JSON(), nullable=False),
        sa.Column('affected_resources', sa.JSON(), nullable=True),
        sa.Column('affected_constraints', sa.JSON(), nullable=True),
        sa.Column('proposed_resolutions', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_applied', sa.String(length=100), nullable=True),
        sa.Column('resolution_method', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conflicting_event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['proposed_event_id'], ['events.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conflicts', schema=None) as batch_op:
        batch_op.create_index('idx_conflict_conflicting_event', ['conflicting_event_id'], unique=False)
        batch_op.create_index('idx_conflict_deleted', ['deleted_at'], unique=False)
        batch_op.create_index('idx_conflict_detected_at', ['detected_at'], unique=False)
        batch_op.create_index('idx_conflict_proposed_event', ['proposed_event_id'], unique=False)
        batch_op.create_index('idx_conflict_severity', ['severity'], unique=False)
        batch_op.create_index('idx_conflict_status', ['status'], unique=False)
        batch_op.create_index('idx_conflict_status_detected', ['status', 'detected_at'], unique=False)
        batch_op.create_index('idx_conflict_type', ['conflict_type'], unique=False)

    # Recreate event_participants table
    op.create_table('event_participants',
        sa.Column('event_id', sa.CHAR(length=32), nullable=False),
        sa.Column('family_member_id', sa.CHAR(length=32), nullable=False),
        sa.Column('required', sa.Boolean(), nullable=False),
        sa.Column('participation_status', sa.String(length=50), nullable=False),
        sa.Column('response_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['family_member_id'], ['family_members.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'family_member_id', name='uq_event_participant')
    )
    with op.batch_alter_table('event_participants', schema=None) as batch_op:
        batch_op.create_index('idx_participant_event', ['event_id'], unique=False)
        batch_op.create_index('idx_participant_member', ['family_member_id'], unique=False)
        batch_op.create_index('idx_participant_required', ['required'], unique=False)

    # Recreate resource_reservations table
    op.create_table('resource_reservations',
        sa.Column('resource_id', sa.CHAR(length=32), nullable=False),
        sa.Column('event_id', sa.CHAR(length=32), nullable=True),
        sa.Column('reserved_by', sa.CHAR(length=32), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('quantity_reserved', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
        sa.ForeignKeyConstraint(['reserved_by'], ['family_members.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('resource_reservations', schema=None) as batch_op:
        batch_op.create_index('idx_reservation_deleted', ['deleted_at'], unique=False)
        batch_op.create_index('idx_reservation_event', ['event_id'], unique=False)
        batch_op.create_index('idx_reservation_reserver', ['reserved_by'], unique=False)
        batch_op.create_index('idx_reservation_resource', ['resource_id'], unique=False)
        batch_op.create_index('idx_reservation_resource_time', ['resource_id', 'start_time', 'end_time'], unique=False)
        batch_op.create_index('idx_reservation_status', ['status'], unique=False)
        batch_op.create_index('idx_reservation_status_time', ['status', 'start_time', 'end_time'], unique=False)
