"""add_refresh_tokens_table

Revision ID: 002
Revises: 001
Create Date: 2026-01-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create refresh_tokens table for JWT authentication
    """
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False, comment='JWT refresh token string'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, comment='User who owns this refresh token'),
        sa.Column('expires_at', sa.DateTime(), nullable=False, comment='Timestamp when this refresh token expires'),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false', comment='Whether this token has been revoked (logout)'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
        comment='Refresh tokens for JWT authentication'
    )

    # Create indexes
    op.create_index('ix_refresh_tokens_token', 'refresh_tokens', ['token'], unique=False)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)
    op.create_index('ix_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'], unique=False)


def downgrade() -> None:
    """
    Drop refresh_tokens table
    """
    op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_token', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
