"""Add calendar auto generation setting

Revision ID: 20260512_0019
Revises: 20260512_0018
Create Date: 2026-05-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260512_0019"
down_revision: str | None = "20260512_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at)
        VALUES (
            'calendar_auto_generation_enabled',
            'false',
            'Whether monthly calendar draft generation runs automatically.',
            NOW()
        )
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM system_settings WHERE key = 'calendar_auto_generation_enabled'"
    )
