"""Create set_password_tokens table

Revision ID: 20260521_0033
Revises: 20260521_0032
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0033"
down_revision: str | None = "20260521_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'set_password_tokens'
            ) THEN
                CREATE TABLE set_password_tokens (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    token_hash VARCHAR(64) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE,
                    created_by VARCHAR(36),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
                CREATE INDEX ix_set_password_tokens_user_id
                    ON set_password_tokens (user_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS set_password_tokens;")
