"""add expects_return to deactivation_reasons

Añade a cada motivo de desactivación el atributo que dice **si la ausencia espera una fecha
de regreso**. Es lo que permite que la pantalla de "No disponible" acierte sola: un motivo
como DIRECCION (que es un puesto, no una ausencia) propone "Indefinido" y no pide fecha.

Es un **atributo editable del catálogo**, no una regla de código: nada puede decidir por el
`code` del motivo, porque los administradores pueden crear, renombrar y desactivar motivos.
Por eso la clasificación inicial se carga **como dato** en esta migración y a partir de ahí
se cambia desde la pantalla de Catálogos.

Valores iniciales (los 8 motivos reales de producción):
  con regreso  (True)  → LICENCIAS MEDICAS, LICENCIA PRE Y POST NATAL, VACACIONES,
                         PRESTADO BATALLAS DE LAS CARRERAS, CONCURSO, OTROS
  sin regreso  (False) → DIRECCION, GERENCIAS MEDICAS
Los dos dudosos (CONCURSO y OTROS) quedan como "con regreso" a propósito: avisar de más es
más barato que no avisar, y el administrador puede corregirlo en un clic.

Revision ID: a2446a0123b3
Revises: aef16ccb2200
Create Date: 2026-10-10 13:34:53.028757
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a2446a0123b3'
down_revision: str | None = 'aef16ccb2200'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Motivos que NO esperan fecha de regreso: son un puesto o una condición permanente, no una
# ausencia con final. Se identifican por `code` **solo aquí**, en la carga inicial de datos.
NO_RETURN_CODES = (
    "direccion",
    "gerencias_medicas",
    "no_service",
)


def upgrade() -> None:
    op.add_column(
        "deactivation_reasons",
        sa.Column("expects_return", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    reasons = sa.table(
        "deactivation_reasons",
        sa.column("code", sa.String()),
        sa.column("expects_return", sa.Boolean()),
    )
    op.execute(
        reasons.update()
        .where(reasons.c.code.in_(NO_RETURN_CODES))
        .values(expects_return=False)
    )


def downgrade() -> None:
    op.drop_column("deactivation_reasons", "expects_return")
