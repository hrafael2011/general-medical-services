"""Seed required service areas

Revision ID: 20260521_0028
Revises: 20260521_0027
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0028"
down_revision: str | None = "20260521_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO service_areas (
            id,
            code,
            display_name,
            active,
            required_for_daily_coverage,
            load_weight,
            created_at,
            updated_at
        )
        VALUES
            ('emergencia', 'emergencia', 'Emergencia', true, true, 3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('pista', 'pista', 'Pista', true, true, 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('disponible', 'disponible', 'Disponible', true, true, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (code) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            active = true,
            required_for_daily_coverage = true,
            load_weight = EXCLUDED.load_weight,
            updated_at = CURRENT_TIMESTAMP;
        """
    )


def downgrade() -> None:
    pass
