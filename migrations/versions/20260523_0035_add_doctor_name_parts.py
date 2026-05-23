"""Add first and last name columns to doctors

Revision ID: 20260523_0035
Revises: 20260522_0034
Create Date: 2026-05-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260523_0035"
down_revision: str | None = "20260522_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE doctors
        ADD COLUMN IF NOT EXISTS first_name VARCHAR(160);

        ALTER TABLE doctors
        ADD COLUMN IF NOT EXISTS last_name VARCHAR(160);

        UPDATE doctors
        SET
            first_name = CASE
                WHEN position(' ' in trim(name)) = 0 THEN trim(name)
                ELSE split_part(trim(name), ' ', 1)
            END,
            last_name = CASE
                WHEN position(' ' in trim(name)) = 0 THEN NULL
                ELSE trim(substr(trim(name), length(split_part(trim(name), ' ', 1)) + 2))
            END
        WHERE first_name IS NULL
          AND last_name IS NULL
          AND name IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE doctors
        DROP COLUMN IF EXISTS last_name;

        ALTER TABLE doctors
        DROP COLUMN IF EXISTS first_name;
    """)
