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
        "query_type": "list_active_doctors",
        "sql_template": "SELECT name, sex, availability_mode FROM doctors WHERE active = TRUE AND service_active = TRUE ORDER BY name",
        "params_schema": {},
        "description": "Lista los medicos activos en servicio.",
    },
    {
        "query_type": "doctor_detail",
        "sql_template": "SELECT name, sex, availability_mode, active, service_active FROM doctors WHERE name LIKE '%' || :search || '%' OR id = :search_id",
        "params_schema": {"search": "str", "search_id": "str"},
        "description": "Detalle de un medico por nombre o ID.",
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
        "sql_template": "SELECT d.name, sa.display_name AS area FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE ca.service_date = :date",
        "params_schema": {"date": "str"},
        "description": "Medicos que trabajaron en una fecha especifica.",
    },
    {
        "query_type": "assignment_count_by_date_range",
        "sql_template": "SELECT d.name, COUNT(*) AS total FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id WHERE ca.service_date BETWEEN :start_date AND :end_date GROUP BY d.name ORDER BY total DESC",
        "params_schema": {"start_date": "date", "end_date": "date"},
        "description": "Cantidad de servicios por medico en un rango de fechas.",
    },
    {
        "query_type": "count_assigned_doctors_by_month",
        "sql_template": (
            "SELECT COUNT(DISTINCT ca.doctor_id) AS total "
            "FROM calendar_assignments ca "
            "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            "JOIN calendars c ON cv.calendar_id = c.id "
            "WHERE c.year = :year AND c.month = :month "
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id"
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
            "AND cv.version_number = ("
            " SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            " WHERE cv2.calendar_id = c.id"
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
            " AND cv.version_number = ("
            "  SELECT MAX(cv2.version_number) FROM calendar_versions cv2 "
            "  WHERE cv2.calendar_id = c.id"
            " )"
            ") "
            "ORDER BY d.name"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Lista los medicos activos que no fueron asignados en un mes.",
    },
    {
        "query_type": "mission_ranking",
        "sql_template": "SELECT mcr.period_year, mcr.period_month, mcre.ranking_position, d.name AS doctor_name, mcre.total_load_score, mcre.eligible FROM mission_candidate_rankings mcr JOIN mission_candidate_ranking_entries mcre ON mcre.ranking_id = mcr.id JOIN doctors d ON mcre.doctor_id = d.id WHERE mcr.period_year = :year AND mcr.period_month = :month ORDER BY mcre.ranking_position LIMIT 20",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Ranking de candidatos para misiones en un periodo.",
    },
    {
        "query_type": "operational_summary",
        "sql_template": (
            "SELECT "
            "(SELECT COUNT(*) FROM doctors WHERE active = TRUE AND service_active = TRUE) AS active_doctors, "
            "(SELECT status FROM calendars WHERE year = :year AND month = :month LIMIT 1) AS calendar_status, "
            "(SELECT COUNT(*) FROM calendar_assignments ca "
            " JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
            " JOIN calendars c ON cv.calendar_id = c.id "
            " WHERE c.year = :year AND c.month = :month) AS total_assignments, "
            "(SELECT COUNT(*) FROM unresolved_gaps ug "
            " JOIN calendar_versions cv ON ug.calendar_version_id = cv.id "
            " JOIN calendars c ON cv.calendar_id = c.id "
            " WHERE c.year = :year AND c.month = :month) AS unresolved_gaps"
        ),
        "params_schema": {"year": "int", "month": "int"},
        "description": "Resumen operativo del sistema para un periodo.",
    },
    {
        "query_type": "doctor_history_60d",
        "sql_template": "SELECT ca.service_date, sa.display_name AS area, ca.assignment_source FROM calendar_assignments ca JOIN service_areas sa ON ca.service_area_id = sa.id WHERE ca.doctor_id = :doctor_id AND ca.service_date >= CURRENT_DATE - INTERVAL '60 days' ORDER BY ca.service_date DESC",
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
        "sql_template": "SELECT ca.service_date, sa.display_name AS area, ca.assignment_source FROM calendar_assignments ca JOIN service_areas sa ON ca.service_area_id = sa.id JOIN doctors d ON ca.doctor_id = d.id WHERE d.name LIKE '%' || :search || '%' AND ca.service_date >= CURRENT_DATE - INTERVAL '60 days' ORDER BY ca.service_date DESC",
        "params_schema": {"search": "str"},
        "description": "Historial de servicios de un medico en los ultimos 60 dias, buscando por nombre en vez de UUID.",
    },
    {
        "query_type": "assignments_by_area",
        "sql_template": "SELECT d.name AS doctor_name, ca.service_date, sa.display_name AS area FROM calendar_assignments ca JOIN doctors d ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE sa.code LIKE :area_code AND ca.service_date BETWEEN :start_date AND :end_date ORDER BY ca.service_date, d.name",
        "params_schema": {"area_code": "str", "start_date": "date", "end_date": "date"},
        "description": "Asignaciones en un area especifica durante un rango de fechas.",
    },
    {
        "query_type": "unresolved_gaps_month",
        "sql_template": "SELECT ug.service_date, sa.display_name AS area, ug.reason_code, ug.description FROM unresolved_gaps ug JOIN service_areas sa ON ug.service_area_id = sa.id JOIN calendar_versions cv ON ug.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = :year AND c.month = :month ORDER BY ug.service_date",
        "params_schema": {"year": "int", "month": "int"},
        "description": "Huecos sin medico asignado en un mes y ano especifico.",
    },
]
