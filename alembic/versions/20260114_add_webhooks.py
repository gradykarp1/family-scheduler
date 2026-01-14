"""Add webhooks table for event notifications

Revision ID: a1b2c3d4e5f6
Revises: 9c3d5e82f4a6
Create Date: 2026-01-14

This migration adds the webhooks table for storing webhook registrations.
Webhooks allow external services to receive push notifications when
calendar events are created, updated, or deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9c3d5e82f4a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('webhooks',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('secret', sa.String(length=255), nullable=False),
        sa.Column('event_types', sa.String(length=255), nullable=False,
                  server_default='event.created,event.updated,event.deleted'),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.create_index('ix_webhooks_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_webhooks_user_active', ['user_id', 'active'], unique=False)
        batch_op.create_index('ix_webhooks_deleted', ['deleted_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.drop_index('ix_webhooks_deleted')
        batch_op.drop_index('ix_webhooks_user_active')
        batch_op.drop_index('ix_webhooks_user_id')
    op.drop_table('webhooks')
