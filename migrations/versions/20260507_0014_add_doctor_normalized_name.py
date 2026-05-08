"""Add normalized_name unique constraint to doctors

Revision ID: 20260507_0014
Revises: 20260507_0013
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0014"
down_revision: str | None = "20260507_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def upgrade() -> None:
    op.add_column("doctors", sa.Column("normalized_name", sa.String(160), nullable=True))

    # Backfill from existing names
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, name FROM doctors")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE doctors SET normalized_name = :norm WHERE id = :id"),
            {"norm": _normalize(row.name), "id": row.id},
        )

    # Resolve duplicates with numeric suffix
    dup_names = conn.execute(
        sa.text(
            "SELECT normalized_name FROM doctors "
            "GROUP BY normalized_name HAVING COUNT(*) > 1"
        )
    ).fetchall()
    for (name,) in dup_names:
        dup_rows = conn.execute(
            sa.text("SELECT id FROM doctors WHERE normalized_name = :name ORDER BY id"),
            {"name": name},
        ).fetchall()
        for idx, dup in enumerate(dup_rows[1:], start=2):
            conn.execute(
                sa.text("UPDATE doctors SET normalized_name = :new_name WHERE id = :id"),
                {"new_name": f"{name}-{idx}", "id": dup.id},
            )

    op.alter_column("doctors", "normalized_name", nullable=False)
    op.create_index("ix_doctors_normalized_name", "doctors", ["normalized_name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_doctors_normalized_name")
    op.drop_column("doctors", "normalized_name")
