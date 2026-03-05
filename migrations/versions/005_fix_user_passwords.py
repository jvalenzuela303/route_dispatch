"""Fix user password hashes — generated inside Python 3.11 to ensure bcrypt compatibility

Revision ID: 005
Revises: 004
Create Date: 2026-02-13
"""
from alembic import op
from sqlalchemy import text
import bcrypt

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def upgrade():
    conn = op.get_bind()

    users = [
        ('admin@botilleria.cl',      'Admin2024!'),
        ('bodega@botilleria.cl',     'Bodega2024!'),
        ('vendedor@botilleria.cl',   'Vendedor2024!'),
        ('repartidor@botilleria.cl', 'Repartidor2024!'),
    ]

    for email, password in users:
        h = _hash(password)
        conn.execute(
            text("UPDATE users SET password_hash = :h WHERE email = :e"),
            {'h': h, 'e': email}
        )


def downgrade():
    pass  # Cannot reverse a password hash
