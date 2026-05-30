"""Replace phone with whatsapp_phone NOT NULL on doctors

Revision ID: 20260527_0041
Revises: 20260524_0040
Create Date: 2026-05-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260527_0041"
down_revision: str | None = "20260524_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE doctors
        SET whatsapp_phone = phone
        WHERE whatsapp_phone IS NULL AND phone IS NOT NULL;
    """)
    op.execute("""
        UPDATE doctors
        SET whatsapp_phone = '0000000000'
        WHERE whatsapp_phone IS NULL;
    """)
    op.execute("ALTER TABLE doctors DROP COLUMN IF EXISTS phone;")
    op.execute("ALTER TABLE doctors ALTER COLUMN whatsapp_phone SET NOT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE doctors ALTER COLUMN whatsapp_phone DROP NOT NULL;")
    op.execute("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS phone VARCHAR(40);")
    op.execute("""
        UPDATE doctors SET phone = whatsapp_phone WHERE phone IS NULL;
    """)
