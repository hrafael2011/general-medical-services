"""Add whatsapp_phone to users and start_hour to service_areas

Revision ID: 20260524_0040
Revises: 20260524_0039
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0040"
down_revision: str | None = "20260524_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS whatsapp_phone VARCHAR(40);
    """)
    op.execute("""
        ALTER TABLE service_areas
        ADD COLUMN IF NOT EXISTS start_hour INTEGER NOT NULL DEFAULT 7;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS whatsapp_phone;")
    op.execute("ALTER TABLE service_areas DROP COLUMN IF EXISTS start_hour;")
