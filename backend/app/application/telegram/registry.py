"""
QueryRegistry — stores query types with parametrized SQL templates.

Provides fast-path lookup for known intents and tracks usage statistics.
New query types can be registered at startup (pre-defined) or at runtime
(auto-learned from successful fallback executions).
"""

import uuid
from datetime import UTC, datetime
from typing import Any


class QueryRegistry:
    """In-memory registry of query types with parametrized SQL templates."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def register(
        self,
        query_type: str,
        sql_template: str,
        params_schema: dict[str, str],
        description: str = "",
    ) -> str:
        """Register a new query type.

        Args:
            query_type: Unique identifier (e.g. 'doctors_by_sex').
            sql_template: Parametrized SQL with :param placeholders.
            params_schema: Mapping of param name → type hint ('str', 'int', 'date').
            description: Human-readable description.

        Returns:
            The query_type string.
        """
        if query_type in self._entries:
            return query_type

        self._entries[query_type] = {
            "id": str(uuid.uuid4()),
            "query_type": query_type,
            "sql_template": sql_template,
            "params_schema": params_schema,
            "description": description,
            "hits": 0,
            "created_at": datetime.now(UTC),
            "last_used_at": None,
        }
        return query_type

    def get(self, query_type: str) -> dict[str, Any] | None:
        """Return the entry for *query_type*, or None."""
        return self._entries.get(query_type)

    def list_all(self) -> list[dict[str, Any]]:
        """Return all registered entries."""
        return list(self._entries.values())

    def increment_hit(self, query_type: str) -> None:
        """Increment the usage counter for *query_type*."""
        entry = self._entries.get(query_type)
        if entry is not None:
            entry["hits"] += 1
            entry["last_used_at"] = datetime.now(UTC)

    def delete(self, query_type: str) -> bool:
        """Remove a query_type from the registry. Returns True if existed."""
        if query_type in self._entries:
            del self._entries[query_type]
            return True
        return False

    def register_many(self, definitions: list[dict[str, Any]]) -> None:
        """Register multiple query types from a list of dicts."""
        for d in definitions:
            self.register(
                query_type=d["query_type"],
                sql_template=d["sql_template"],
                params_schema=d.get("params_schema", {}),
                description=d.get("description", ""),
            )


# ---------------------------------------------------------------------------
# Pre-defined query types (cover ~85% of common questions)
# Templates use PostgreSQL-compatible syntax (TRUE/FALSE for booleans).
# ---------------------------------------------------------------------------

DEFAULT_QUERY_TYPES = [
    {
        "query_type": "count_doctors_total",
        "sql_template": "SELECT COUNT(*) AS total FROM doctors WHERE active = TRUE AND service_active = TRUE",
        "params_schema": {},
        "description": "Cuenta total de medicos activos en servicio.",
    },
    {
        "query_type": "count_by_sex",
        "sql_template": "SELECT sex, COUNT(*) AS total FROM doctors WHERE active = TRUE AND service_active = TRUE GROUP BY sex",
        "params_schema": {},
        "description": "Cuantos medicos hay por sexo.",
    },
    {
        "query_type": "doctors_by_sex",
        "sql_template": "SELECT name, sex, availability_mode FROM doctors WHERE sex = :sex AND active = TRUE AND service_active = TRUE",
        "params_schema": {"sex": "str"},
        "description": "Lista los medicos filtrados por sexo.",
    },
    {
        "query_type": "count_by_rank",
        "sql_template": "SELECT r.name AS rank, COUNT(*) AS total FROM doctors d JOIN ranks r ON d.rank_id = r.id WHERE d.active = TRUE AND d.service_active = TRUE GROUP BY r.name ORDER BY total DESC",
        "params_schema": {},
        "description": "Cuantos medicos hay por cada rango (todos los rangos). Usar cuando no se especifica un rango en particular.",
    },
    {
        "query_type": "count_by_specific_rank",
        "sql_template": "SELECT r.name AS rank, COUNT(*) AS total FROM doctors d JOIN ranks r ON d.rank_id = r.id WHERE d.active = TRUE AND d.service_active = TRUE AND LOWER(r.normalized_name) = LOWER(:rank) GROUP BY r.name",
        "params_schema": {"rank": "str"},
        "description": "Cuenta cuantos medicos hay de un rango especifico. Usar cuando preguntan 'cuantos [rango] hay/tengo'.",
    },
    {
        "query_type": "doctors_by_rank",
        "sql_template": "SELECT d.name, d.sex, r.name AS rank FROM doctors d JOIN ranks r ON d.rank_id = r.id WHERE d.active = TRUE AND d.service_active = TRUE AND LOWER(r.normalized_name) = LOWER(:rank)",
        "params_schema": {"rank": "str"},
        "description": "Lista los medicos filtrados por rango.",
    },
    {
        "query_type": "duplicate_doctor_names",
        "sql_template": (
            "SELECT name, COUNT(*) AS count "
            "FROM doctors "
            "WHERE active = TRUE AND service_active = TRUE "
            "GROUP BY name "
            "HAVING COUNT(*) > 1 "
            "ORDER BY count DESC, name"
        ),
        "params_schema": {},
        "description": "Medicos con nombres duplicados en el sistema. Usar cuando preguntan por 'duplicados', 'mismo nombre', o 'se llaman igual'.",
    },
    {
        "query_type": "list_active_doctors",
        "sql_template": "SELECT name, sex, availability_mode FROM doctors WHERE active = TRUE AND service_active = TRUE ORDER BY name",
        "params_schema": {},
        "description": "Lista los medicos activos en servicio.",
    },
    {
        "query_type": "doctor_detail",
        "sql_template": (
            "SELECT d.name, d.sex, r.name AS rank, dep.name AS department, "
            "d.availability_mode, d.active, d.service_active "
            "FROM doctors d "
            "LEFT JOIN ranks r ON d.rank_id = r.id "
            "LEFT JOIN departments dep ON d.department_id = dep.id "
            "WHERE d.name LIKE '%' || :search || '%' OR d.id = :search_id"
        ),
        "params_schema": {"search": "str", "search_id": "str"},
        "description": "Detalle completo de un medico por nombre o ID. Incluye rango y departamento.",
    },
    {
        "query_type": "doctors_pending_availability",
        "sql_template": "SELECT d.name, d.id FROM doctors d WHERE d.active = TRUE AND d.service_active = TRUE AND NOT EXISTS (SELECT 1 FROM doctor_availability da WHERE da.doctor_id = d.id AND da.year = :year AND da.month = :month)",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Medicos sin disponibilidad registrada para un mes y ano.",
    },
    {
        "query_type": "calendar_status_month",
        "sql_template": "SELECT status, month, year FROM calendars WHERE year = :year AND month = :month",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Estado del calendario para un mes y ano especifico.",
    },
    {
        "query_type": "doctors_working_date",
        "sql_template": "SELECT d.name, sa.display_name AS area FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE ca.service_date = :date AND cv.deleted_at IS NULL",
        "params_schema": {"date": "str"},
        "description": "Medicos que trabajaron en una fecha especifica.",
    },
    {
        "query_type": "assignment_count_by_date_range",
        "sql_template": "SELECT d.name, COUNT(*) AS total FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id JOIN calendar_versions cv ON ca.calendar_version_id = cv.id WHERE ca.service_date BETWEEN :start_date AND :end_date AND cv.deleted_at IS NULL GROUP BY d.name ORDER BY total DESC",
        "params_schema": {"start_date": "date", "end_date": "date"},
        "description": "Cantidad de servicios por medico en un rango de fechas.",
    },
    {
        "query_type": "total_services_by_month",
        "sql_template": (
            "SELECT COUNT(*) AS total "
            "FROM calendar_assignments ca "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND cv.deleted_at IS NULL "
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id AND cv2.deleted_at IS NULL"
            ")"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Total de servicios (turnos) programados en un mes. Usar cuando preguntan 'cuantos servicios hay en [mes]'.",
    },
    {
        "query_type": "count_assigned_doctors_by_month",
        "sql_template": (
            "SELECT COUNT(DISTINCT ca.doctor_id) AS total "
            "FROM calendar_assignments ca "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND cv.deleted_at IS NULL "
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id AND cv2.deleted_at IS NULL"
            ")"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Cuenta cuantos medicos distintos fueron asignados a servicios en un mes.",
    },
    {
        "query_type": "list_assigned_doctors_by_month",
        "sql_template": (
            "SELECT d.name, COUNT(ca.id) AS total "
            "FROM doctors d "
            "JOIN calendar_assignments ca ON ca.doctor_id = d.id "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND cv.deleted_at IS NULL "
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id AND cv2.deleted_at IS NULL"
            ") "
            "GROUP BY d.name "
            "ORDER BY d.name"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Lista los medicos asignados a servicios en un mes y cuantos servicios tiene cada uno.",
    },
    {
        "query_type": "unassigned_doctors_by_month",
        "sql_template": (
            "SELECT d.name "
            "FROM doctors d "
            "WHERE d.active = TRUE AND d.service_active = TRUE "
            "AND NOT EXISTS ("
            " SELECT 1 FROM calendar_assignments ca "
            " JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            " JOIN calendars c ON cv.calendar_id = c.id "
            " WHERE ca.doctor_id = d.id AND c.year = :year AND c.month = :month "
            " AND cv.deleted_at IS NULL "
            " AND cv.version_number = ("
            "  SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            "  WHERE cv2.calendar_id = c.id AND cv2.deleted_at IS NULL"
            " )"
            ") "
            "ORDER BY d.name"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Lista los medicos activos que no fueron asignados en un mes.",
    },
    {
        "query_type": "mission_ranking",
        "sql_template": "SELECT mcr.year, mcr.month, mcre.ranking_position, d.name AS doctor_name, mcre.total_load_score, mcre.eligible FROM mission_candidate_rankings mcr JOIN mission_candidate_ranking_entries mcre ON mcre.mission_candidate_ranking_id = mcr.id JOIN doctors d ON mcre.doctor_id = d.id WHERE mcr.year = :year AND mcr.month = :month ORDER BY mcre.ranking_position LIMIT 20",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Ranking de candidatos para misiones en un periodo.",
    },
    {
        "query_type": "list_active_missions",
        "sql_template": (
            "SELECT ma.mission_date AS fecha_mision, "
            "CASE ma.status "
            " WHEN 'confirmed' THEN 'Confirmada' "
            " WHEN 'draft' THEN 'Pendiente de aprobacion' "
            " ELSE ma.status END AS estado, "
            "COALESCE(ma.location, '') AS lugar, "
            "COALESCE(ma.description, '') AS descripcion, "
            "COALESCE(d.name, 'Sin participante asignado') AS medico "
            "FROM mission_assignments ma "
            "LEFT JOIN mission_participants mp ON mp.mission_assignment_id = ma.id "
            "LEFT JOIN doctors d ON d.id = mp.doctor_id "
            "WHERE ma.deleted_at IS NULL "
            "AND ma.status IN ('draft', 'confirmed') "
            "AND ma.mission_date >= CURRENT_DATE "
            "ORDER BY ma.mission_date, ma.location, d.name "
            "LIMIT 50"
        ),
        "params_schema": {},
        "description": "Lista las misiones activas o vigentes, con sus participantes si existen.",
    },
    {
        "query_type": "operational_summary",
        "sql_template": (
            "SELECT "
            "(SELECT COUNT(*) FROM doctors WHERE active = TRUE AND service_active = TRUE) AS active_doctors, "
            "(SELECT status FROM calendars WHERE year = :year AND month = :month AND deleted_at IS NULL LIMIT 1) AS calendar_status, "
            "(SELECT COUNT(*) FROM calendar_assignments ca "
            " JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            " JOIN calendars c ON cv.calendar_id = c.id "
            " WHERE c.year = :year AND c.month = :month AND cv.deleted_at IS NULL) AS total_assignments, "
            "(SELECT COUNT(*) FROM unresolved_gaps ug "
            " JOIN calendar_versions cv ON ug.calendar_version_id = cv.id "
            " JOIN calendars c ON cv.calendar_id = c.id "
            " WHERE c.year = :year AND c.month = :month AND cv.deleted_at IS NULL) AS unresolved_gaps"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Resumen operativo del sistema para un periodo.",
    },
    {
        "query_type": "doctor_history_60d",
        "sql_template": "SELECT ca.service_date, sa.display_name AS area, ca.assignment_source FROM calendar_assignments ca JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE cv.deleted_at IS NULL AND ca.doctor_id = :doctor_id AND ca.service_date >= CURRENT_DATE - INTERVAL '60 days' ORDER BY ca.service_date DESC",
        "params_schema": {"doctor_id": "str"},
        "description": "Historial de servicios de un medico en los ultimos 60 dias.",
    },
    {
        "query_type": "count_doctors_by_department",
        "sql_template": "SELECT d.name AS department, COUNT(*) AS total FROM doctors doc JOIN departments d ON doc.department_id = d.id WHERE doc.active = TRUE AND doc.service_active = TRUE GROUP BY d.name ORDER BY total DESC",
        "params_schema": {},
        "description": "Cuantos medicos hay por departamento.",
    },
    {
        "query_type": "count_by_specific_sex",
        "sql_template": "SELECT COUNT(*) AS total FROM doctors WHERE sex = :sex AND active = TRUE AND service_active = TRUE",
        "params_schema": {"sex": "str"},
        "description": "Cuenta cuantos medicos hay de un sexo especifico. Usar cuando preguntan 'cuantos [hombres|mujeres|varones] hay/tengo'.",
    },
    {
        "query_type": "doctor_history_by_name",
        "sql_template": "SELECT ca.service_date, sa.display_name AS area, ca.assignment_source FROM calendar_assignments ca JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN service_areas sa ON ca.service_area_id = sa.id JOIN doctors d ON ca.doctor_id = d.id WHERE cv.deleted_at IS NULL AND d.name LIKE '%' || :search || '%' AND ca.service_date >= CURRENT_DATE - INTERVAL '60 days' ORDER BY ca.service_date DESC",
        "params_schema": {"search": "str"},
        "description": "Historial de servicios de un medico en los ultimos 60 dias, buscando por nombre en vez de UUID.",
    },
    {
        "query_type": "assignments_by_area",
        "sql_template": "SELECT d.name AS doctor_name, ca.service_date, sa.display_name AS area FROM calendar_assignments ca JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN doctors d ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE cv.deleted_at IS NULL AND sa.code LIKE :area_code AND ca.service_date BETWEEN :start_date AND :end_date ORDER BY ca.service_date, d.name",
        "params_schema": {"area_code": "str", "start_date": "date", "end_date": "date"},
        "description": "Asignaciones en un area especifica durante un rango de fechas.",
    },
    {
        "query_type": "unresolved_gaps_month",
        "sql_template": "SELECT ug.service_date, sa.display_name AS area, ug.reason_code, ug.description FROM unresolved_gaps ug JOIN service_areas sa ON ug.service_area_id = sa.id JOIN calendar_versions cv ON ug.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = :year AND c.month = :month AND cv.deleted_at IS NULL ORDER BY ug.service_date",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Huecos sin medico asignado en un mes y ano especifico.",
    },
    {
        "query_type": "calendar_approval_info",
        "sql_template": (
            "SELECT ae.action_type, ae.occurred_at AS fecha, u.name AS actor "
            "FROM audit_events ae "
            "JOIN users u ON ae.actor_id = u.id "
            "JOIN calendars c ON ae.entity_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND c.deleted_at IS NULL "
            "ORDER BY ae.occurred_at DESC LIMIT 10"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Quien aprobo o hizo cambios en un calendario. Usar cuando preguntan 'quien aprobo', 'quien hizo cambios', 'auditoria del calendario' de un mes y ano.",
    },
    {
        "query_type": "pending_mission_confirmation",
        "sql_template": (
            "SELECT d.name AS medico, mp.mission_date AS fecha_mision, mp.status AS estado "
            "FROM mission_participants mp "
            "JOIN doctors d ON mp.doctor_id = d.id "
            "WHERE mp.status IN ('pending', 'sent') "
            "ORDER BY mp.mission_date, d.name"
        ),
        "params_schema": {},
        "description": "Medicos que no han confirmado su participacion en misiones.",
    },
    {
        "query_type": "pending_service_confirmation",
        "sql_template": (
            "SELECT d.name AS medico, ca.service_date AS fecha, sa.display_name AS area "
            "FROM calendar_assignments ca "
            "JOIN doctors d ON ca.doctor_id = d.id "
            "JOIN service_areas sa ON ca.service_area_id = sa.id "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND cv.deleted_at IS NULL "
            "AND ca.confirmed = FALSE "
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id AND cv2.deleted_at IS NULL"
            ") "
            "ORDER BY ca.service_date, d.name"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Medicos que no han confirmado servicio en un mes y ano.",
    },
    {
        "query_type": "list_calendar_assignments_by_date_range",
        "sql_template": (
            "SELECT ca.service_date, d.name AS doctor_name, sa.display_name AS area "
            "FROM calendar_assignments ca "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "JOIN doctors d ON ca.doctor_id = d.id "
            "JOIN service_areas sa ON ca.service_area_id = sa.id "
            "WHERE ca.service_date BETWEEN :start_date AND :end_date "
            "AND c.status = 'approved' AND cv.status = 'approved' "
            "AND c.deleted_at IS NULL "
            "AND cv.deleted_at IS NULL "
            "ORDER BY ca.service_date, sa.display_name, d.name"
        ),
        "params_schema": {"start_date": "date", "end_date": "date"},
        "description": "Lista las asignaciones de servicio en un rango de fechas del calendario aprobado.",
    },
]
