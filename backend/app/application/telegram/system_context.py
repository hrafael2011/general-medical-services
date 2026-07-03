"""System context builder — injects domain knowledge into LLM prompts.

Reads catalogs, business rules, and schema descriptions from the database
and formats them as a structured string for LLM context injection.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_system_context(session: Session) -> str:
    """Build a complete system context string from database state.

    Returns a formatted string covering catalogs, business rules, status values,
    and relationships. Designed to be injected into LLM prompts via {system_context}.

    Args:
        session: SQLAlchemy session for database queries.

    Returns:
        A multi-line string with all domain facts.
    """
    sections: list[str] = []

    # Helper: safe query with error handling
    def _fetch(query: str) -> list[Any]:
        try:
            return list(session.execute(text(query)).scalars().all())
        except Exception as exc:
            logger.warning("System context query failed: %s", exc)
            return []

    # 1. Ranks catalog
    ranks = _fetch("SELECT normalized_name FROM ranks ORDER BY id")
    if ranks:
        sections.append("RANGOS MILITARES (orden jerárquico):\n" + ", ".join(ranks))
    else:
        sections.append("RANGOS MILITARES: No hay datos disponibles.")

    # 2. Departments catalog
    depts = _fetch("SELECT name FROM departments ORDER BY name")
    if depts:
        sections.append("DEPARTAMENTOS:\n" + ", ".join(depts))

    # 3. Service areas catalog
    areas = _fetch("SELECT name FROM service_areas ORDER BY name")
    if areas:
        sections.append("ÁREAS DE SERVICIO:\n" + ", ".join(areas))

    # 4. Sex values
    sexes = _fetch("SELECT DISTINCT sex FROM doctors WHERE sex IS NOT NULL ORDER BY sex")
    if sexes:
        sections.append("SEXO (valores en BD):\n" + ", ".join(sexes))

    # 5. Doctor availability modes
    modes = _fetch("SELECT DISTINCT availability_mode FROM doctors WHERE availability_mode IS NOT NULL ORDER BY availability_mode")
    if modes:
        sections.append("MODOS DE DISPONIBILIDAD DE MÉDICOS:\n" + ", ".join(modes))

    # 6. Calendar statuses
    cal_statuses = _fetch("SELECT DISTINCT status FROM calendars WHERE status IS NOT NULL ORDER BY status")
    if cal_statuses:
        sections.append("ESTADOS DE CALENDARIO:\n" + ", ".join(cal_statuses))

    # 7. Calendar version statuses
    ver_statuses = _fetch("SELECT DISTINCT status FROM calendar_versions WHERE status IS NOT NULL ORDER BY status")
    if ver_statuses:
        sections.append("ESTADOS DE VERSIÓN DE CALENDARIO:\n" + ", ".join(ver_statuses))

    # 8. Mission statuses
    mission_statuses = _fetch("SELECT DISTINCT status FROM missions WHERE status IS NOT NULL ORDER BY status")
    if mission_statuses:
        sections.append("ESTADOS DE MISIONES:\n" + ", ".join(mission_statuses))

    # 9. Deactivation reasons
    reasons = _fetch("SELECT reason FROM deactivation_reasons ORDER BY reason")
    if reasons:
        sections.append("RAZONES DE BAJA/INACTIVIDAD DE MÉDICOS:\n" + ", ".join(reasons))

    # Business rules (static — don't depend on data)
    sections.append("""
REGLAS DE NEGOCIO:
- 'Guardia' (shift) = asignación en calendario para un día específico. Es un servicio diario.
- 'Misión' (mission) = operativo especial de varios días con médicos asignados.
- Calendarios tienen versiones: la última versión aprobada es la fuente de verdad.
- Un calendario se aprueba por semanas (cada semana se aprueba independientemente).
- Un médico no puede estar en dos servicios con fechas y áreas superpuestas.
- Las confirmaciones tienen tiempo límite para responder.
- Notificaciones se envían por Telegram o WhatsApp según el canal del doctor.
- monthly_service_target = meta deseada de servicios por médico al mes.
- monthly_service_max = máximo de servicios mensual permitido por médico.""")

    sections.append("""
RELACIONES ENTRE TABLAS:
- doctors → ranks (FK rank_id): cada médico tiene un rango militar.
- doctors → departments (FK department_id): cada médico pertenece a un departamento.
- doctors → service_areas (FK service_area_id): área principal del médico.
- doctors puede cubrir múltiples áreas vía doctor_allowed_areas.
- calendar → calendar_versions: un calendario puede tener múltiples versiones (borrador → aprobado).
- calendar_versions → calendar_assignments: cada versión tiene asignaciones de médicos a servicios.
- calendar_assignments → doctors: qué médico está asignado a cada servicio/fecha.
- missions → mission_participants → doctors: médicos en cada misión.
- missions → mission_candidate_rankings: ranking de candidatos para misión.
- doctors → doctor_availability: disponibilidad semanal del médico.
- doctors → doctor_restrictions: restricciones temporales del médico.""")

    return "\n\n".join(sections)
