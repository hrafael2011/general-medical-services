"""Regla de cobertura obligatoria: cada día necesita médico en cada área requerida.

Un calendario no se puede aprobar si algún día del período queda sin cubrir en
alguna de las áreas marcadas como `required_for_daily_coverage`. Este módulo
solo calcula qué falta; decidir si se bloquea es cosa del servicio.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

WEEKDAY_NAMES = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
]

# Cuántos días se nombran en el mensaje antes de resumir el resto. La lista
# completa viaja en `details`; el texto es para leerlo de un vistazo.
_MESSAGE_DAY_LIMIT = 7


@dataclass(frozen=True)
class RequiredArea:
    code: str
    display_name: str


@dataclass(frozen=True)
class CoverageGap:
    service_date: date
    area_names: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        """`lunes 04/05` — como se nombra un día en la pantalla."""
        return f"{WEEKDAY_NAMES[self.service_date.weekday()]} {self.service_date.strftime('%d/%m')}"

    def to_detail(self) -> dict:
        return {"date": self.service_date.isoformat(), "areas": list(self.area_names)}


def find_coverage_gaps(
    *,
    start_date: date,
    end_date: date,
    required_areas: Sequence[RequiredArea],
    assignments: Iterable[tuple[date, str]],
) -> list[CoverageGap]:
    """Return every day in the range missing at least one required area.

    `assignments` yields `(service_date, area_code)` pairs — one per turno.
    Days outside `start_date`..`end_date` are ignored: en la última semana del
    mes, los días del mes siguiente pertenecen a otro calendario.
    """
    if not required_areas:
        return []

    covered = set(assignments)
    gaps: list[CoverageGap] = []

    cursor = start_date
    while cursor <= end_date:
        missing = [
            area.display_name
            for area in required_areas
            if (cursor, area.code) not in covered
        ]
        if missing:
            gaps.append(CoverageGap(service_date=cursor, area_names=missing))
        cursor += timedelta(days=1)

    return gaps


def format_coverage_message(gaps: Sequence[CoverageGap]) -> str:
    """Texto para el operador: qué días y qué áreas quedaron sin médico."""
    if not gaps:
        return ""

    shown = gaps[:_MESSAGE_DAY_LIMIT]
    parts = [
        f"{gap.label} ({', '.join(gap.area_names)})"
        for gap in shown
    ]
    message = "No se puede aprobar: faltan médicos en " + "; ".join(parts)

    remaining = len(gaps) - len(shown)
    if remaining > 0:
        message += f" y {remaining} días más sin cubrir"

    return message + "."
