"""Legacy no-op for calendar_weeks branch

Revision ID: 20260516_0019
Revises: 3d7632021cde
Create Date: 2026-05-16
"""

from collections.abc import Sequence

revision: str = "20260516_0019"
down_revision: str | None = "3d7632021cde"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The complete calendar_weeks migration is 3d7632021cde. This legacy
    # revision is kept only to preserve Alembic history with a single head.
    pass


def downgrade() -> None:
    pass
