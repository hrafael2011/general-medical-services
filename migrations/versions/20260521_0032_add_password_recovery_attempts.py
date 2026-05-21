"""Add password_recovery_attempts table

Revision ID: 20260521_0032
Revises: 20260521_0031
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0032"
down_revision: str | None = "20260521_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'password_recovery_attempts'
            ) THEN
                CREATE TABLE password_recovery_attempts (
                    id VARCHAR(36) NOT NULL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    ip_address VARCHAR(45) NOT NULL,
                    attempted_at TIMESTAMP WITH TIME ZONE NOT NULL
                );
                CREATE INDEX ix_password_recovery_attempts_email
                    ON password_recovery_attempts (email);
                CREATE INDEX ix_password_recovery_attempts_ip_address
                    ON password_recovery_attempts (ip_address);
                CREATE INDEX ix_password_recovery_attempts_attempted_at
                    ON password_recovery_attempts (attempted_at);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS password_recovery_attempts;")
