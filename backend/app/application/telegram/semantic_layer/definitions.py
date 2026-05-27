"""Business definitions for the Semantic Layer.

This module contains the concrete ``Metric`` and ``Dimension`` definitions
for the medical-scheduling domain.  Every SQL template is hand-written,
reviewed, and deterministic — the LLM never touches SQL generation here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .models import Dimension, Filter, Metric, SemanticQuery


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------
def _build_where(filters: list[Filter], param_prefix: str = "f") -> tuple[str, dict[str, Any]]:
    """Translate SemanticQuery filters into a WHERE clause fragment.

    Returns ``(where_fragment, params)``.  The fragment starts with ``AND``
    so it can be appended directly after existing ``WHERE`` conditions.
    """
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for idx, f in enumerate(filters):
        key = f"{param_prefix}_{idx}"
        if f.operator == "eq":
            clauses.append(f"{f.field} = :{key}")
            params[key] = f.value
        elif f.operator == "ne":
            clauses.append(f"{f.field} != :{key}")
            params[key] = f.value
        elif f.operator == "gt":
            clauses.append(f"{f.field} > :{key}")
            params[key] = f.value
        elif f.operator == "gte":
            clauses.append(f"{f.field} >= :{key}")
            params[key] = f.value
        elif f.operator == "lt":
            clauses.append(f"{f.field} < :{key}")
            params[key] = f.value
        elif f.operator == "lte":
            clauses.append(f"{f.field} <= :{key}")
            params[key] = f.value
        elif f.operator == "in":
            clauses.append(f"{f.field} = ANY(:{key})")
            params[key] = f.value if isinstance(f.value, list) else [f.value]
        elif f.operator == "like":
            clauses.append(f"{f.field} ILIKE :{key}")
            params[key] = f"%{f.value}%"
        elif f.operator == "between":
            # value must be a 2-tuple/list
            clauses.append(f"{f.field} BETWEEN :{key}_a AND :{key}_b")
            params[f"{key}_a"] = f.value[0]
            params[f"{key}_b"] = f.value[1]
    if not clauses:
        return "", {}
    return " AND " + " AND ".join(clauses), params


def _build_group_by(dimensions: list[str], dim_map: dict[str, Dimension]) -> tuple[str, list[str]]:
    """Build SELECT expressions and GROUP BY clause from dimensions."""
    select_exprs: list[str] = []
    group_exprs: list[str] = []
    for d in dimensions:
        dim = dim_map[d]
        select_exprs.append(f"{dim.sql_expression} AS {d}")
        group_exprs.append(dim.sql_expression)
    return ", ".join(select_exprs), group_exprs


def _build_order_by(
    order_by: list[tuple[str, str]], dim_map: dict[str, Dimension], default: list[tuple[str, str]]
) -> str:
    """Build ORDER BY clause."""
    effective = order_by if order_by else default
    parts: list[str] = []
    for col, direction in effective:
        # allow raw SQL expressions (for aggregates) or dimension aliases
        expr = dim_map.get(col, Dimension(col, col, col)).sql_expression if col in dim_map else col
        parts.append(f"{expr} {direction.upper()}")
    if not parts:
        return ""
    return "ORDER BY " + ", ".join(parts)


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------
DIMENSIONS: dict[str, Dimension] = {
    "doctor": Dimension(
        name="doctor",
        display_name="Médico",
        sql_expression="d.name",
        supported_metrics=None,  # all metrics
    ),
    "rank": Dimension(
        name="rank",
        display_name="Rango",
        sql_expression="r.name",
        supported_metrics=None,
    ),
    "sex": Dimension(
        name="sex",
        display_name="Sexo",
        sql_expression="d.sex",
        supported_metrics=None,
    ),
    "department": Dimension(
        name="department",
        display_name="Departamento",
        sql_expression="dep.name",
        supported_metrics=None,
    ),
    "service_area": Dimension(
        name="service_area",
        display_name="Área de Servicio",
        sql_expression="sa.display_name",
        supported_metrics=None,
    ),
    "month": Dimension(
        name="month",
        display_name="Mes",
        sql_expression="c.month",
        supported_metrics=None,
    ),
    "year": Dimension(
        name="year",
        display_name="Año",
        sql_expression="c.year",
        supported_metrics=None,
    ),
    "week": Dimension(
        name="week",
        display_name="Semana",
        sql_expression="cw.week_number",
        supported_metrics=None,
    ),
    "date": Dimension(
        name="date",
        display_name="Fecha",
        sql_expression="ca.service_date",
        supported_metrics=None,
    ),
    "status": Dimension(
        name="status",
        display_name="Estado",
        sql_expression="COALESCE(c.status, ma.status)",
        supported_metrics=None,
    ),
    "mission_date": Dimension(
        name="mission_date",
        display_name="Fecha de Misión",
        sql_expression="ma.mission_date",
        supported_metrics=None,
    ),
}


# ---------------------------------------------------------------------------
# Metric SQL templates
# ---------------------------------------------------------------------------
def _tpl_total_doctors(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"COUNT(*) AS total{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}" if group_by else ""
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
WHERE d.active = TRUE AND d.service_active = TRUE AND d.deleted_at IS NULL{where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_doctors_by_sex(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    # force sex dimension
    dims = list({"sex", *sq.dimensions})
    dim_select, group_by = _build_group_by(dims, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"d.sex, COUNT(*) AS total{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
WHERE d.active = TRUE AND d.service_active = TRUE AND d.deleted_at IS NULL{where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_doctors_by_rank(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dims = list({"rank", *sq.dimensions})
    dim_select, group_by = _build_group_by(dims, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"r.name AS rank, COUNT(*) AS total{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM doctors d
JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
WHERE d.active = TRUE AND d.service_active = TRUE AND d.deleted_at IS NULL{where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_doctors_by_department(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dims = list({"department", *sq.dimensions})
    dim_select, group_by = _build_group_by(dims, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"dep.name AS department, COUNT(*) AS total{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN departments dep ON dep.id = d.department_id
LEFT JOIN ranks r ON r.id = d.rank_id
WHERE d.active = TRUE AND d.service_active = TRUE AND d.deleted_at IS NULL{where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_duplicate_doctor_names(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    where_sql, where_params = _build_where(sq.filters)
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 100"
    sql = f"""SELECT d.name, COUNT(*) AS occurrences
FROM doctors d
WHERE d.active = TRUE AND d.service_active = TRUE AND d.deleted_at IS NULL{where_sql}
GROUP BY d.name
HAVING COUNT(*) > 1
ORDER BY occurrences DESC
{limit}""".strip()
    return sql, where_params


def _tpl_active_missions(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"""ma.mission_date,
    ma.location,
    ma.description,
    ma.participant_count,
    ma.status,
    COUNT(mp.id) AS confirmed_participants{', ' + dim_select if dim_select else ''}"""
    group = f"GROUP BY ma.id{', ' + ', '.join(group_by) if group_by else ''}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("ma.mission_date", "ASC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 50"
    sql = f"""SELECT {select}
FROM mission_assignments ma
LEFT JOIN mission_participants mp ON mp.mission_assignment_id = ma.id
WHERE ma.deleted_at IS NULL
  AND ma.status IN ('draft', 'confirmed')
  AND ma.mission_date >= CURRENT_DATE{where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_mission_ranking(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    # Default to current month/year if not filtered
    year = date.today().year
    month = date.today().month
    for f in sq.filters:
        if f.field == "year" and f.operator == "eq":
            year = f.value
        if f.field == "month" and f.operator == "eq":
            month = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field not in ("year", "month")])
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    select = f"""d.name AS doctor,
    mcre.ranking_position,
    mcre.total_load_score,
    mcre.monthly_service_load,
    mcre.monthly_mission_load,
    mcre.eligible{', ' + dim_select if dim_select else ''}"""
    group = f"GROUP BY d.id, mcre.id{', ' + ', '.join(group_by) if group_by else ''}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("mcre.ranking_position", "ASC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 20"
    sql = f"""SELECT {select}
FROM mission_candidate_rankings mcr
JOIN mission_candidate_ranking_entries mcre ON mcre.mission_candidate_ranking_id = mcr.id
JOIN doctors d ON d.id = mcre.doctor_id
WHERE mcr.year = :year AND mcr.month = :month{where_sql}
{group}
{order}
{limit}""".strip()
    params = {"year": year, "month": month, **where_params}
    return sql, params


def _tpl_total_services(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"COUNT(*) AS total_servicios{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}" if group_by else ""
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total_servicios", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM calendar_assignments ca
JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
JOIN calendars c ON c.id = cv.calendar_id
JOIN doctors d ON d.id = ca.doctor_id
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
LEFT JOIN service_areas sa ON sa.id = ca.service_area_id
WHERE c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_assigned_doctors_count(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    where_sql, where_params = _build_where(sq.filters)
    select = f"COUNT(DISTINCT ca.doctor_id) AS total_medicos{', ' + dim_select if dim_select else ''}"
    group = f"GROUP BY {', '.join(group_by)}" if group_by else ""
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total_medicos", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else ""
    sql = f"""SELECT {select}
FROM calendar_assignments ca
JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
JOIN calendars c ON c.id = cv.calendar_id
JOIN doctors d ON d.id = ca.doctor_id
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
LEFT JOIN service_areas sa ON sa.id = ca.service_area_id
WHERE c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_unassigned_doctors(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    year = date.today().year
    month = date.today().month
    for f in sq.filters:
        if f.field == "year" and f.operator == "eq":
            year = f.value
        if f.field == "month" and f.operator == "eq":
            month = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field not in ("year", "month")])
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    select = f"d.name AS doctor, r.name AS rank, dep.name AS department{', ' + dim_select if dim_select else ''}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("d.name", "ASC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 100"
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
WHERE d.active = TRUE
  AND d.service_active = TRUE
  AND d.deleted_at IS NULL
  AND NOT EXISTS (
      SELECT 1
      FROM calendar_assignments ca
      JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
      JOIN calendars c ON c.id = cv.calendar_id
      WHERE ca.doctor_id = d.id
        AND c.year = :year
        AND c.month = :month
        AND c.deleted_at IS NULL
        AND cv.version_number = (
            SELECT MAX(cv2.version_number)
            FROM calendar_versions cv2
            WHERE cv2.calendar_id = c.id
        )
  ){where_sql}
{order}
{limit}""".strip()
    params = {"year": year, "month": month, **where_params}
    return sql, params


def _tpl_doctor_service_load(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    where_sql, where_params = _build_where(sq.filters)
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    select = f"""d.name AS doctor,
    COUNT(ca.id) AS total_servicios,
    COUNT(DISTINCT ca.service_date) AS dias_diferentes,
    MIN(ca.service_date) AS primer_servicio,
    MAX(ca.service_date) AS ultimo_servicio{', ' + dim_select if dim_select else ''}"""
    group = f"GROUP BY d.id{', ' + ', '.join(group_by) if group_by else ''}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("total_servicios", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 100"
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN calendar_assignments ca ON ca.doctor_id = d.id
LEFT JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
LEFT JOIN calendars c ON c.id = cv.calendar_id
LEFT JOIN ranks r ON r.id = d.rank_id
LEFT JOIN departments dep ON dep.id = d.department_id
LEFT JOIN service_areas sa ON sa.id = ca.service_area_id
WHERE d.active = TRUE
  AND d.service_active = TRUE
  AND d.deleted_at IS NULL
  AND c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_unresolved_gaps(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    year = date.today().year
    month = date.today().month
    for f in sq.filters:
        if f.field == "year" and f.operator == "eq":
            year = f.value
        if f.field == "month" and f.operator == "eq":
            month = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field not in ("year", "month")])
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    select = f"""ug.service_date,
    sa.display_name AS area,
    ug.reason_code,
    ug.description{', ' + dim_select if dim_select else ''}"""
    group = f"GROUP BY ug.id, sa.id{', ' + ', '.join(group_by) if group_by else ''}"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("ug.service_date", "ASC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 100"
    sql = f"""SELECT {select}
FROM unresolved_gaps ug
JOIN service_areas sa ON sa.id = ug.service_area_id
JOIN calendar_versions cv ON cv.id = ug.calendar_version_id
JOIN calendars c ON c.id = cv.calendar_id
WHERE c.year = :year
  AND c.month = :month
  AND c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
{group}
{order}
{limit}""".strip()
    params = {"year": year, "month": month, **where_params}
    return sql, params


def _tpl_operational_summary(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    year = date.today().year
    month = date.today().month
    for f in sq.filters:
        if f.field == "year" and f.operator == "eq":
            year = f.value
        if f.field == "month" and f.operator == "eq":
            month = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field not in ("year", "month")])
    sql = f"""SELECT
    (SELECT COUNT(*) FROM doctors WHERE active = TRUE AND service_active = TRUE AND deleted_at IS NULL) AS total_medicos,
    (SELECT COUNT(*) FROM calendar_assignments ca
     JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
     JOIN calendars c ON c.id = cv.calendar_id
     WHERE c.year = :year AND c.month = :month AND c.deleted_at IS NULL
       AND cv.version_number = (SELECT MAX(cv2.version_number) FROM calendar_versions cv2 WHERE cv2.calendar_id = c.id)
    ) AS total_servicios,
    (SELECT COUNT(DISTINCT ca.doctor_id) FROM calendar_assignments ca
     JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
     JOIN calendars c ON c.id = cv.calendar_id
     WHERE c.year = :year AND c.month = :month AND c.deleted_at IS NULL
       AND cv.version_number = (SELECT MAX(cv2.version_number) FROM calendar_versions cv2 WHERE cv2.calendar_id = c.id)
    ) AS medicos_asignados,
    (SELECT COUNT(*) FROM unresolved_gaps ug
     JOIN calendar_versions cv ON cv.id = ug.calendar_version_id
     JOIN calendars c ON c.id = cv.calendar_id
     WHERE c.year = :year AND c.month = :month AND c.deleted_at IS NULL
       AND cv.version_number = (SELECT MAX(cv2.version_number) FROM calendar_versions cv2 WHERE cv2.calendar_id = c.id)
    ) AS huecos_sin_resolver,
    (SELECT status FROM calendars WHERE year = :year AND month = :month AND deleted_at IS NULL ORDER BY updated_at DESC LIMIT 1) AS estado_calendario{where_sql}""".strip()
    params = {"year": year, "month": month, **where_params}
    return sql, params


def _tpl_pending_confirmations(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    confirmation_type = "mission"
    for f in sq.filters:
        if f.field == "confirmation_type" and f.operator == "eq":
            confirmation_type = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field != "confirmation_type"])

    if confirmation_type == "mission":
        sql = f"""SELECT
    d.name AS doctor,
    ma.mission_date,
    ma.location,
    ma.description,
    ma.status
FROM mission_assignments ma
JOIN mission_participants mp ON mp.mission_assignment_id = ma.id
JOIN doctors d ON d.id = mp.doctor_id
WHERE ma.deleted_at IS NULL
  AND ma.status IN ('pending', 'sent')
  AND ma.mission_date >= CURRENT_DATE{where_sql}
ORDER BY ma.mission_date ASC
LIMIT 50""".strip()
    else:
        sql = f"""SELECT
    d.name AS doctor,
    ca.service_date,
    sa.display_name AS area,
    c.year,
    c.month
FROM calendar_assignments ca
JOIN doctors d ON d.id = ca.doctor_id
JOIN service_areas sa ON sa.id = ca.service_area_id
JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
JOIN calendars c ON c.id = cv.calendar_id
WHERE c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  )
  AND ca.confirmed = FALSE{where_sql}
ORDER BY ca.service_date ASC
LIMIT 50""".strip()
    return sql, where_params


def _tpl_last_service_by_doctor(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    """Template for 'last service date per doctor' queries."""
    where_sql, where_params = _build_where(sq.filters)
    dim_select, group_by = _build_group_by(sq.dimensions, DIMENSIONS)
    select = f"""d.name AS doctor,
    MAX(ca.service_date) AS ultimo_servicio,
    sa.display_name AS area{', ' + dim_select if dim_select else ''}"""
    group = f"GROUP BY d.id{', ' + ', '.join(group_by) if group_by else ''}, sa.id"
    order = _build_order_by(sq.order_by, DIMENSIONS, [("ultimo_servicio", "DESC")])
    limit = f"LIMIT {sq.limit}" if sq.limit else "LIMIT 100"
    sql = f"""SELECT {select}
FROM doctors d
LEFT JOIN calendar_assignments ca ON ca.doctor_id = d.id
LEFT JOIN calendar_versions cv ON cv.id = ca.calendar_version_id
LEFT JOIN calendars c ON c.id = cv.calendar_id
LEFT JOIN service_areas sa ON sa.id = ca.service_area_id
WHERE d.active = TRUE
  AND d.service_active = TRUE
  AND d.deleted_at IS NULL
  AND c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
{group}
{order}
{limit}""".strip()
    return sql, where_params


def _tpl_calendar_status(sq: SemanticQuery) -> tuple[str, dict[str, Any]]:
    year = date.today().year
    month = date.today().month
    for f in sq.filters:
        if f.field == "year" and f.operator == "eq":
            year = f.value
        if f.field == "month" and f.operator == "eq":
            month = f.value

    where_sql, where_params = _build_where([f for f in sq.filters if f.field not in ("year", "month")])
    sql = f"""SELECT
    c.year,
    c.month,
    c.status,
    c.generation_mode,
    c.created_at,
    c.approved_at,
    COUNT(ca.id) AS total_asignaciones,
    COUNT(DISTINCT ca.doctor_id) AS medicos_distintos
FROM calendars c
LEFT JOIN calendar_versions cv ON cv.calendar_id = c.id
LEFT JOIN calendar_assignments ca ON ca.calendar_version_id = cv.id
WHERE c.year = :year
  AND c.month = :month
  AND c.deleted_at IS NULL
  AND cv.version_number = (
      SELECT MAX(cv2.version_number)
      FROM calendar_versions cv2
      WHERE cv2.calendar_id = c.id
  ){where_sql}
GROUP BY c.id""".strip()
    params = {"year": year, "month": month, **where_params}
    return sql, params


# ---------------------------------------------------------------------------
# Metric registry
# ---------------------------------------------------------------------------
METRICS: dict[str, Metric] = {
    "total_doctors": Metric(
        name="total_doctors",
        display_name="Total de Médicos",
        description="Cantidad total de médicos activos y operativos.",
        sql_template=_tpl_total_doctors,
        supported_dimensions={"sex", "rank", "department"},
        supported_filters={"sex", "rank", "department"},
    ),
    "doctors_by_sex": Metric(
        name="doctors_by_sex",
        display_name="Médicos por Sexo",
        description="Distribución del personal médico por sexo.",
        sql_template=_tpl_doctors_by_sex,
        supported_dimensions={"rank", "department"},
        supported_filters={"sex", "rank", "department"},
    ),
    "doctors_by_rank": Metric(
        name="doctors_by_rank",
        display_name="Médicos por Rango",
        description="Distribución del personal médico por rango militar.",
        sql_template=_tpl_doctors_by_rank,
        supported_dimensions={"sex", "department"},
        supported_filters={"sex", "rank", "department"},
    ),
    "doctors_by_department": Metric(
        name="doctors_by_department",
        display_name="Médicos por Departamento",
        description="Distribución del personal médico por departamento.",
        sql_template=_tpl_doctors_by_department,
        supported_dimensions={"sex", "rank"},
        supported_filters={"sex", "rank", "department"},
    ),
    "duplicate_doctor_names": Metric(
        name="duplicate_doctor_names",
        display_name="Nombres Duplicados",
        description="Médicos con nombres repetidos en el sistema.",
        sql_template=_tpl_duplicate_doctor_names,
        supported_dimensions=set(),
        supported_filters=set(),
    ),
    "active_missions": Metric(
        name="active_missions",
        display_name="Misiones Activas",
        description="Misiones programadas con fecha actual o futura.",
        sql_template=_tpl_active_missions,
        supported_dimensions={"mission_date", "status"},
        supported_filters={"mission_date", "status"},
    ),
    "mission_ranking": Metric(
        name="mission_ranking",
        display_name="Ranking de Idoneidad",
        description="Ranking de candidatos para misiones basado en carga de trabajo.",
        sql_template=_tpl_mission_ranking,
        supported_dimensions={"rank", "department"},
        supported_filters={"year", "month", "rank", "department"},
    ),
    "total_services": Metric(
        name="total_services",
        display_name="Total de Servicios",
        description="Cantidad total de asignaciones de servicio en el calendario.",
        sql_template=_tpl_total_services,
        supported_dimensions={"doctor", "rank", "department", "service_area", "month", "year", "date", "week"},
        supported_filters={"doctor", "rank", "department", "service_area", "date", "month", "year"},
    ),
    "assigned_doctors_count": Metric(
        name="assigned_doctors_count",
        display_name="Médicos Asignados",
        description="Cantidad de médicos distintos asignados en el período.",
        sql_template=_tpl_assigned_doctors_count,
        supported_dimensions={"month", "year", "department", "service_area"},
        supported_filters={"month", "year", "department", "service_area"},
    ),
    "unassigned_doctors": Metric(
        name="unassigned_doctors",
        display_name="Médicos Sin Asignar",
        description="Médicos activos que no tienen asignación en el mes.",
        sql_template=_tpl_unassigned_doctors,
        supported_dimensions={"rank", "department", "sex"},
        supported_filters={"year", "month", "rank", "department", "sex"},
    ),
    "doctor_service_load": Metric(
        name="doctor_service_load",
        display_name="Carga de Servicios por Médico",
        description="Resumen de servicios realizados por cada médico incluyendo primera y última fecha.",
        sql_template=_tpl_doctor_service_load,
        supported_dimensions={"rank", "department", "service_area", "month", "year"},
        supported_filters={"doctor", "rank", "department", "service_area", "date", "month", "year"},
    ),
    "unresolved_gaps": Metric(
        name="unresolved_gaps",
        display_name="Huecos Sin Resolver",
        description="Asignaciones pendientes sin médico asignado.",
        sql_template=_tpl_unresolved_gaps,
        supported_dimensions={"service_area", "date"},
        supported_filters={"year", "month", "service_area"},
    ),
    "operational_summary": Metric(
        name="operational_summary",
        display_name="Resumen Operativo",
        description="Dashboard ejecutivo con métricas clave del mes.",
        sql_template=_tpl_operational_summary,
        supported_dimensions=set(),
        supported_filters={"year", "month"},
    ),
    "pending_confirmations": Metric(
        name="pending_confirmations",
        display_name="Confirmaciones Pendientes",
        description="Servicios o misiones pendientes de confirmación.",
        sql_template=_tpl_pending_confirmations,
        supported_dimensions={"doctor", "mission_date", "date"},
        supported_filters={"confirmation_type", "doctor", "mission_date", "date"},
    ),
    "last_service_by_doctor": Metric(
        name="last_service_by_doctor",
        display_name="Último Servicio por Médico",
        description="Fecha del último servicio asignado a cada médico.",
        sql_template=_tpl_last_service_by_doctor,
        supported_dimensions={"rank", "department", "service_area"},
        supported_filters={"doctor", "rank", "department", "service_area", "date"},
    ),
    "calendar_status": Metric(
        name="calendar_status",
        display_name="Estado del Calendario",
        description="Estado y estadísticas del calendario mensual.",
        sql_template=_tpl_calendar_status,
        supported_dimensions=set(),
        supported_filters={"year", "month"},
    ),
}
