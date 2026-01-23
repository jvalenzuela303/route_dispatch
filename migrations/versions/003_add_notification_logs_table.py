"""add_notification_logs_table

Revision ID: 003
Revises: 002
Create Date: 2026-01-21 21:30:00.000000

Adds notification_logs table for tracking customer notifications
across multiple channels (EMAIL, SMS, WhatsApp, Push).

This table supports:
- Multi-channel notification tracking
- Delivery status monitoring (PENDING, SENT, FAILED)
- Retry tracking
- Error logging for debugging
- Audit trail for customer service
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create notification_logs table and related enums
    """
    # Create notification_channel_enum
    op.execute("""
        CREATE TYPE notification_channel_enum AS ENUM (
            'EMAIL',
            'SMS',
            'WHATSAPP',
            'PUSH'
        )
    """)

    # Create notification_status_enum
    op.execute("""
        CREATE TYPE notification_status_enum AS ENUM (
            'PENDING',
            'SENT',
            'FAILED'
        )
    """)

    # Create notification_logs table
    op.create_table(
        'notification_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column(
            'order_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment='Order this notification is about'
        ),
        sa.Column(
            'channel',
            postgresql.ENUM(
                'EMAIL', 'SMS', 'WHATSAPP', 'PUSH',
                name='notification_channel_enum',
                create_type=False
            ),
            nullable=False,
            comment='Channel used: EMAIL, SMS, WHATSAPP, PUSH'
        ),
        sa.Column(
            'recipient',
            sa.String(length=255),
            nullable=False,
            comment='Recipient email address or phone number'
        ),
        sa.Column(
            'status',
            postgresql.ENUM(
                'PENDING', 'SENT', 'FAILED',
                name='notification_status_enum',
                create_type=False
            ),
            nullable=False,
            server_default='PENDING',
            comment='Notification status: PENDING, SENT, FAILED'
        ),
        sa.Column(
            'sent_at',
            sa.DateTime(),
            nullable=True,
            comment='Timestamp when notification was successfully sent'
        ),
        sa.Column(
            'error_message',
            sa.Text(),
            nullable=True,
            comment='Error details if notification failed (for debugging)'
        ),
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Number of retry attempts made'
        ),
        sa.ForeignKeyConstraint(
            ['order_id'],
            ['orders.id'],
            ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        comment='Log of all notifications sent to customers'
    )

    # Create indexes for efficient querying
    op.create_index(
        'ix_notification_logs_order_id',
        'notification_logs',
        ['order_id'],
        unique=False
    )
    op.create_index(
        'ix_notification_logs_status',
        'notification_logs',
        ['status'],
        unique=False
    )
    op.create_index(
        'ix_notification_logs_channel',
        'notification_logs',
        ['channel'],
        unique=False
    )
    op.create_index(
        'ix_notification_logs_created_at',
        'notification_logs',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """
    Drop notification_logs table and related enums
    """
    # Drop indexes
    op.drop_index('ix_notification_logs_created_at', table_name='notification_logs')
    op.drop_index('ix_notification_logs_channel', table_name='notification_logs')
    op.drop_index('ix_notification_logs_status', table_name='notification_logs')
    op.drop_index('ix_notification_logs_order_id', table_name='notification_logs')

    # Drop table
    op.drop_table('notification_logs')

    # Drop enums
    op.execute('DROP TYPE notification_status_enum')
    op.execute('DROP TYPE notification_channel_enum')
