"""Add append-only trigger to audit_events table.

Prevents tampering with audit records by rejecting UPDATE and DELETE
operations at the database level.

Revision ID: 20260611_audit_append_only
Revises: 41f25b95c60a
Create Date: 2026-06-11
"""

from collections.abc import Sequence

from alembic import op

# ── revision identifiers ─────────────────────────────────────────────────────
revision: str = "20260611_audit_append_only"
down_revision: str | None = "41f25b95c60a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDIT_APPEND_ONLY_FUNC = "prevent_audit_tamper"
_AUDIT_APPEND_ONLY_TRIGGER = "audit_events_append_only"


def upgrade() -> None:
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {_AUDIT_APPEND_ONLY_FUNC}()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events table is append-only — UPDATE and DELETE are not allowed';
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute(f"""
        CREATE TRIGGER {_AUDIT_APPEND_ONLY_TRIGGER}
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION {_AUDIT_APPEND_ONLY_FUNC}();
    """)


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {_AUDIT_APPEND_ONLY_TRIGGER} ON audit_events")
    op.execute(f"DROP FUNCTION IF EXISTS {_AUDIT_APPEND_ONLY_FUNC}()")
