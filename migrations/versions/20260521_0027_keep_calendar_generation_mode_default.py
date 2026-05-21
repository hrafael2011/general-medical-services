"""Keep default generation mode on calendars

Revision ID: 20260521_0027
Revises: 20260521_0026
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0027"
down_revision: str | None = "20260521_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE calendars SET generation_mode = 'manual' WHERE generation_mode IS NULL")
    op.execute("ALTER TABLE calendars ALTER COLUMN generation_mode SET DEFAULT 'manual'")


def downgrade() -> None:
    op.execute("ALTER TABLE calendars ALTER COLUMN generation_mode DROP DEFAULT")
