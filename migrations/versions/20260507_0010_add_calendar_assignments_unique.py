"""add unique constraint on calendar_assignments (version, date, area)

Revision ID: 20260507_0010
Revises: 20260505_0009
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0010"
down_revision: str | None = "20260505_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove any existing duplicates before adding the constraint
    op.execute(
        "DELETE FROM calendar_assignments ca "
        "WHERE EXISTS ( "
        "  SELECT 1 FROM calendar_assignments ca2 "
        "  WHERE ca2.calendar_version_id = ca.calendar_version_id "
        "    AND ca2.service_date = ca.service_date "
        "    AND ca2.service_area_id = ca.service_area_id "
        "    AND ca2.id < ca.id "
        ")"
    )

    op.create_unique_constraint(
        "uq_calendar_assignments_version_date_area",
        "calendar_assignments",
        ["calendar_version_id", "service_date", "service_area_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_calendar_assignments_version_date_area",
        "calendar_assignments",
        type_="unique",
    )
