"""Add permissions JSONB and is_superadmin to users table

Revision ID: 20260524_0037
Revises: 20260524_0036
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260524_0037"
down_revision: str | None = "20260524_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS permissions JSONB NOT NULL DEFAULT '[]'::jsonb;
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_users_permissions
        ON users USING gin (permissions);
    """)
    op.execute("""
        UPDATE users
        SET permissions = '["manage_doctors","manage_calendars","manage_missions","manage_availability","manage_catalogs","manage_users","manage_trash","view_audit","view_notifications","manage_confirmations","manage_alerts","export_reports","receive_escalation_alerts"]'::jsonb
        WHERE role = 'encargado' AND active = TRUE AND deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("""
        DROP INDEX IF EXISTS ix_users_permissions;
    """)
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS permissions;
    """)
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS is_superadmin;
    """)
