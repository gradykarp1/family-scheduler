"""Add user_tokens table for OAuth token storage

Revision ID: 9c3d5e82f4a6
Revises: 8a2f4c91d3e5
Create Date: 2026-01-14

This migration adds the user_tokens table for storing OAuth tokens.
Each user can have one set of tokens per OAuth provider (currently Google).
Tokens are used to access user's personal Google Calendar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c3d5e82f4a6'
down_revision: Union[str, None] = '8a2f4c91d3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_tokens',
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='google'),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('calendar_id', sa.String(length=255), nullable=True),
        sa.Column('id', sa.CHAR(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.create_index('ix_user_tokens_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_user_tokens_user_provider', ['user_id', 'provider'], unique=True)
        batch_op.create_index('ix_user_tokens_deleted', ['deleted_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('user_tokens', schema=None) as batch_op:
        batch_op.drop_index('ix_user_tokens_deleted')
        batch_op.drop_index('ix_user_tokens_user_provider')
        batch_op.drop_index('ix_user_tokens_user_id')
    op.drop_table('user_tokens')
