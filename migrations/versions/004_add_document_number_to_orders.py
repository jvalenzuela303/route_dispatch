"""Add document_number to orders

Adds the document_number column (boleta/factura number from the buyer)
to the orders table. This field is mandatory for all new orders.
Existing rows are backfilled with an empty string before the default is removed.

Revision ID: 003
Revises: 002
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column with a temporary server default so existing rows are valid
    op.add_column(
        'orders',
        sa.Column(
            'document_number',
            sa.String(length=100),
            nullable=False,
            server_default='',
            comment='Número de boleta o factura del comprador'
        )
    )

    # Remove the server default — new rows must provide the value explicitly
    op.alter_column('orders', 'document_number', server_default=None)

    # Index for fast lookups by document number
    op.create_index(
        'ix_orders_document_number',
        'orders',
        ['document_number']
    )


def downgrade() -> None:
    op.drop_index('ix_orders_document_number', table_name='orders')
    op.drop_column('orders', 'document_number')
