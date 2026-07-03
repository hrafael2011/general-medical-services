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

    # 10. Calendar week statuses
    week_statuses = _fetch("SELECT DISTINCT status FROM calendar_weeks WHERE status IS NOT NULL ORDER BY status")
    if week_statuses:
        sections.append("ESTADOS DE SEMANA DE CALENDARIO:\n" + ", ".join(week_statuses))

    # 11. Confirmation request statuses
    conf_statuses = _fetch("SELECT DISTINCT status FROM confirmation_requests WHERE status IS NOT NULL ORDER BY status")
    if conf_statuses:
        sections.append("ESTADOS DE SOLICITUDES DE CONFIRMACIÓN:\n" + ", ".join(conf_statuses))

    # 12. Confirmation types
    conf_types = _fetch("SELECT DISTINCT confirmation_type FROM confirmation_requests WHERE confirmation_type IS NOT NULL ORDER BY confirmation_type")
    if conf_types:
        sections.append("TIPOS DE CONFIRMACIÓN:\n" + ", ".join(conf_types))

    # 13. Notification statuses
    notif_statuses = _fetch("SELECT DISTINCT status FROM notification_events WHERE status IS NOT NULL ORDER BY status")
    if notif_statuses:
        sections.append("ESTADOS DE NOTIFICACIONES:\n" + ", ".join(notif_statuses))

    # 14. Notification providers
    providers = _fetch("SELECT DISTINCT provider FROM notification_events WHERE provider IS NOT NULL ORDER BY provider")
    if providers:
        sections.append("PROVEEDORES DE NOTIFICACIÓN:\n" + ", ".join(providers))

    # 15. Action alert statuses
    alert_statuses = _fetch("SELECT DISTINCT status FROM action_alerts WHERE status IS NOT NULL ORDER BY status")
    if alert_statuses:
        sections.append("ESTADOS DE ALERTAS:\n" + ", ".join(alert_statuses))

    # 16. Action alert severities
    alert_severities = _fetch("SELECT DISTINCT severity FROM action_alerts WHERE severity IS NOT NULL ORDER BY severity")
    if alert_severities:
        sections.append("SEVERIDAD DE ALERTAS:\n" + ", ".join(alert_severities))

    # 17. Mission assignment sources
    mission_sources = _fetch("SELECT DISTINCT source FROM mission_assignments WHERE source IS NOT NULL ORDER BY source")
    if mission_sources:
        sections.append("FUENTES DE ASIGNACIÓN DE MISIONES:\n" + ", ".join(mission_sources))

    # 18. Calendar assignment sources
    assign_sources = _fetch("SELECT DISTINCT assignment_source FROM calendar_assignments WHERE assignment_source IS NOT NULL ORDER BY assignment_source")
    if assign_sources:
        sections.append("FUENTES DE ASIGNACIÓN DE CALENDARIO:\n" + ", ".join(assign_sources))

    # 19. Doctor restriction types
    restr_types = _fetch("SELECT DISTINCT restriction_type FROM doctor_restrictions WHERE restriction_type IS NOT NULL ORDER BY restriction_type")
    if restr_types:
        sections.append("TIPOS DE RESTRICCIÓN DE MÉDICOS:\n" + ", ".join(restr_types))

    # 20. User roles
    roles = _fetch("SELECT DISTINCT role FROM users WHERE role IS NOT NULL ORDER BY role")
    if roles:
        sections.append("ROLES DE USUARIO DEL SISTEMA:\n" + ", ".join(roles))

    # Business rules (static — don't depend on data)
    sections.append("""
REGLAS DE NEGOCIO:
- 'Guardia' (shift) = asignación en calendario para un día específico. Es un servicio diario.
- 'Misión' (mission) = operativo especial de varios días con médicos asignados hacia una ubicación específica.
- Cada calendario mensual tiene semanas (calendar_weeks) que se aprueban individualmente.
- La última versión aprobada de un calendario es la fuente de verdad para asignaciones.
- Un médico no puede estar en dos servicios con fechas y áreas superpuestas.
- Un médico solo puede ser asignado a áreas que tenga en su lista doctor_allowed_areas.
- Los médicos pueden tener restricciones temporales (doctor_restrictions) que limitan dónde/cuándo pueden servir.
- Las confirmaciones tienen tiempo límite configurable (confirmation_overdue_hours). Si expiran, se escalan.
- Notificaciones se envían por Telegram o WhatsApp según el canal configurado del doctor.
- monthly_service_target = meta deseada de servicios por médico al mes.
- monthly_service_max = máximo de servicios que un médico puede tener al mes.
- monthly_service_limit_mode: 'warn_only' = solo advierte, no bloquea.
- Los gaps (unresolved_gaps) son fechas/áreas sin médico asignado por falta de disponibilidad.
- El ranking de candidatos para misiones usa scores de carga (service_load, mission_load).""")

    sections.append("""
RELACIONES ENTRE TABLAS:
- doctors → ranks (FK rank_id): cada médico tiene un rango militar.
- doctors → departments (FK department_id): cada médico pertenece a un departamento.
- doctors → service_areas (FK service_area_id): área principal del médico.
- doctors puede cubrir múltiples áreas vía doctor_allowed_areas (tabla pivot muchos-a-muchos).
- Un doctor sin service_active=false tiene una razón en deactivation_reasons (FK service_inactive_reason_id).
- calendars → calendar_versions: un calendario puede tener múltiples versiones (borrador → aprobado → reemplazado).
- calendar_versions → calendar_weeks: cada versión tiene semanas que se aprueban individualmente.
- calendar_versions → calendar_assignments: cada versión tiene asignaciones de médicos a servicios en fechas específicas.
- calendar_assignments → doctors: qué médico está asignado a qué servicio/fecha/área.
- Única combinación por calendar_version_id + service_date + service_area_id.
- missions (mission_assignments) → mission_participants → doctors: médicos asignados a cada misión.
- missions → mission_candidate_rankings → mission_candidate_ranking_entries → doctors: ranking de candidatos.
- doctors → doctor_availability: disponibilidad por tipo (semanal, mensual, fechas específicas).
- doctors → doctor_restrictions: restricciones temporales con fechas de inicio/fin.
- doctors ← notification_events: notificaciones enviadas a cada doctor.
- notification_events → calendar_assignments (FK assignment_id): notificación sobre asignación específica.
- notification_events → missions (FK mission_id): notificación sobre misión específica.
- doctors → confirmation_requests: solicitudes de confirmación de asignaciones.
- confirmation_requests → notification_events: la notificación que generó la confirmación.
- confirmation_requests → calendar_assignments o missions: qué se está confirmando.
- users: usuarios del sistema con roles (admin, encargado, doctor, viewer).""")

    return "\n\n".join(sections)
