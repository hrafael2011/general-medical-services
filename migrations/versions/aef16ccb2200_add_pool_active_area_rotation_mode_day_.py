"""add pool_active, area_rotation_mode, day_priority

Revision ID: aef16ccb2200
Revises: 20260611_audit_append_only
Create Date: 2026-09-05 19:12:52.143437
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'aef16ccb2200'
down_revision: str | None = '20260611_audit_append_only'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'doctors',
        sa.Column('pool_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        'doctors',
        sa.Column('area_rotation_mode', sa.String(length=20), nullable=False, server_default='auto'),
    )
    op.add_column(
        'doctor_availability',
        sa.Column('day_priority', sa.String(length=20), nullable=False, server_default='available'),
    )


def downgrade() -> None:
    op.drop_column('doctor_availability', 'day_priority')
    op.drop_column('doctors', 'area_rotation_mode')
    op.drop_column('doctors', 'pool_active')
