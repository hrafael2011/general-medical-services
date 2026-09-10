"""Handlers deterministas del catálogo MCP (2026-09-05).

Cada handler del catálogo de 22 tools delega en un service de
``application/`` o en consultas de solo lectura de los repositorios.
Ningún handler ejecuta SQL del modelo ni acepta texto SQL como entrada.
``sql_query`` no existe como handler: el SQL Agent es un fallback interno
del path enrutado, nunca elegible por el LLM.

Los handlers devuelven dicts estructurados (rows/total) que la capa NL
convierte a español usando SOLO esos datos.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select

from backend.app.infrastructure.db.models.catalogs import DepartmentModel, RankModel
from backend.app.infrastructure.db.models.doctors import (
    DoctorAllowedAreaModel,
    DoctorModel,
)
from backend.app.infrastructure.db.models.user import UserModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today() -> date:
    return date.today()


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    from calendar import monthrange

    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _parse_date(value: str | None, *, field: str) -> date:
    if not value:
        raise ValueError(f"Falta el campo '{field}' con formato YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Fecha inválida en '{field}': {value!r}. Usa YYYY-MM-DD.") from None


def _iso(d: date | datetime | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def _normalize(value: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode().casefold()


def _sex_label(sex: str | None) -> str:
    return "Femenino" if sex == "F" else ("Masculino" if sex == "M" else "—")


def _ok(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True}
    payload.update(extra)
    return payload


def _err(message: str) -> dict[str, Any]:
    return {"ok": False, "error": message}


def _doctor_query() -> Any:
    return select(DoctorModel).where(DoctorModel.deleted_at.is_(None))


def _match_doctors_by_name(deps: dict[str, Any], name: str) -> list[DoctorModel]:
    """Doctores no borrados cuyo nombre coincide (sin acentos ni mayúsculas)."""
    if not name:
        return []
    rows = list(
        deps["session"].scalars(
            _doctor_query().where(DoctorModel.name.ilike(f"%{name}%")).limit(50)
        )
    )
    target = _normalize(name)
    exact = [d for d in rows if _normalize(d.name) == target]
    return exact or rows


def _resolve_doctor(deps: dict[str, Any], doctor_name: str) -> dict[str, Any]:
    """Devuelve {"id", "name"} o {"error"} o {"ambiguous": [...]}."""
    if not doctor_name:
        return {"error": "Falta el nombre del médico."}
    matches = _match_doctors_by_name(deps, doctor_name)
    if not matches:
        return {"error": f"No encontré un médico llamado «{doctor_name}»."}
    if len(matches) > 1:
        return {"ambiguous": [{"id": d.id, "name": d.name} for d in matches[:10]]}
    doctor = matches[0]
    return {"id": doctor.id, "name": doctor.name}


def _resolve_area(deps: dict[str, Any], area_name: str) -> dict[str, Any]:
    """Devuelve {"id", "display_name"} o {"error"}."""
    if not area_name:
        return {"error": "Falta el área de servicio."}
    target = _normalize(area_name)
    areas = deps["catalog_repo"].list_service_areas()
    exact = [
        a
        for a in areas
        if _normalize(a.display_name) == target or _normalize(a.code) == target
    ]
    candidates = exact or [a for a in areas if target in _normalize(a.display_name)]
    if not candidates:
        return {
            "error": f"No existe el área «{area_name}». Áreas: Emergencia, Pista, Disponible."
        }
    area = candidates[0]
    return {"id": area.id, "display_name": area.display_name}


def _guard(fn):
    """Envuelve un handler: errores → dict {ok: False, error} (nunca excepción)."""

    def wrapper(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
        try:
            result = fn(params, deps)
            return result if isinstance(result, dict) else _ok(result=result)
        except ValueError as exc:
            return _err(str(exc))
        except Exception:
            logger.exception("Tool handler failed: %s", getattr(fn, "__name__", "handler"))
            return _err("Ocurrió un error al consultar el sistema. Intenta nuevamente.")

    return wrapper


# ---------------------------------------------------------------------------
# Doctors
# ---------------------------------------------------------------------------


@_guard
def handle_list_doctors(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Lista/cuenta médicos con filtros. Soporta group_by y no_assignments_in."""
    session = deps["session"]
    stmt = _doctor_query()
    if params.get("sex") in ("M", "F"):
        stmt = stmt.where(DoctorModel.sex == params["sex"])
    if params.get("service_active") is not False:
        stmt = stmt.where(DoctorModel.service_active.is_(True))
    if params.get("pool_active") is not False:
        stmt = stmt.where(DoctorModel.pool_active.is_(True))
    if params.get("participa_misiones") is True:
        stmt = stmt.where(DoctorModel.participa_misiones.is_(True))
    elif params.get("participa_misiones") is False:
        stmt = stmt.where(DoctorModel.participa_misiones.is_(False))

    if params.get("rank"):
        rank_id = deps["rank_ids"].get(_normalize(params["rank"]))
        if rank_id is None:
            return _err(f"No existe el rango «{params['rank']}».")
        stmt = stmt.where(DoctorModel.rank_id == rank_id)
    if params.get("department"):
        dept_id = deps["department_ids"].get(_normalize(params["department"]))
        if dept_id is None:
            return _err(f"No existe el departamento «{params['department']}».")
        stmt = stmt.where(DoctorModel.department_id == dept_id)
    if params.get("service_area"):
        area = _resolve_area(deps, params["service_area"])
        if "error" in area:
            return area
        allowed = select(DoctorAllowedAreaModel.doctor_id).where(
            DoctorAllowedAreaModel.service_area_id == area["id"]
        )
        stmt = stmt.where(DoctorModel.id.in_(allowed))

    doctors = list(session.scalars(stmt.order_by(DoctorModel.name)))

    # no_assignments_in: excluye médicos con asignación en ese mes/año.
    period = params.get("no_assignments_in")
    if period and isinstance(period, dict):
        try:
            month = int(period["month"])
            year = int(period["year"])
        except (KeyError, TypeError, ValueError):
            return _err("no_assignments_in requiere month y year.")
        start, end = _month_bounds(year, month)
        assigned = deps["calendar_repo"].list_assignments_in_date_range(start, end)
        assigned_ids = {a.doctor_id for a in assigned}
        doctors = [d for d in doctors if d.id not in assigned_ids]

    if not doctors:
        return _ok(total=0, rows=[])

    group_by = params.get("group_by")
    if group_by in ("sex", "rank", "department"):
        buckets: dict[str, int] = {}
        for d in doctors:
            if group_by == "sex":
                key = _sex_label(d.sex)
            elif group_by == "rank":
                key = d.rank.name if d.rank else "Sin rango"
            else:
                key = d.department.name if d.department else "Sin departamento"
            buckets[key] = buckets.get(key, 0) + 1
        return _ok(
            total=len(doctors),
            rows=[{"grupo": k, "cantidad": v} for k, v in buckets.items()],
        )

    rows = [
        {
            "name": d.name,
            "sex": _sex_label(d.sex),
            "rank": d.rank.name if d.rank else None,
            "department": d.department.name if d.department else None,
            "service_active": d.service_active,
        }
        for d in doctors
    ]
    if params.get("count"):
        return _ok(total=len(doctors))
    return _ok(total=len(doctors), rows=rows)


@_guard
def handle_doctor_info(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Ficha de un médico: rango, departamento, áreas, límites y estado."""
    resolved = _resolve_doctor(deps, params.get("doctor_name", ""))
    if "error" in resolved:
        return _err(resolved["error"])
    if "ambiguous" in resolved:
        return _ok(ambiguous=resolved["ambiguous"])

    doctor = deps["session"].get(DoctorModel, resolved["id"])
    if doctor is None:
        return _err("No encontré al médico.")

    allowed_ids = deps["doctor_repo"].get_allowed_areas(doctor.id)
    area_names = [
        a.display_name
        for a in deps["catalog_repo"].list_service_areas()
        if a.id in allowed_ids
    ]
    inactive_reason = None
    if doctor.service_inactive_reason_id:
        reason = deps["catalog_repo"].get_deactivation_reason_by_id(
            doctor.service_inactive_reason_id
        )
        inactive_reason = reason.reason if reason else None

    return _ok(
        rows=[{
            "name": doctor.name,
            "sex": _sex_label(doctor.sex),
            "rank": doctor.rank.name if doctor.rank else None,
            "department": doctor.department.name if doctor.department else None,
            "areas_permitidas": area_names or ["Ninguna"],
            "meta_mensual": doctor.monthly_service_target,
            "maximo_mensual": doctor.monthly_service_max,
            "modo_limite": doctor.monthly_service_limit_mode,
            "modalidad_disponibilidad": doctor.availability_mode,
            "activo": bool(doctor.active and doctor.service_active),
            "en_pool": bool(doctor.pool_active),
            "participa_misiones": bool(doctor.participa_misiones),
            "motivo_inactividad": inactive_reason or doctor.service_inactive_detail,
        }]
    )


@_guard
def handle_doctor_availability(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Disponibilidad de un médico: días reportados, patrón semanal y prioridad."""
    resolved = _resolve_doctor(deps, params.get("doctor_name", ""))
    if "error" in resolved:
        return _err(resolved["error"])
    if "ambiguous" in resolved:
        return _ok(ambiguous=resolved["ambiguous"])

    doctor = deps["session"].get(DoctorModel, resolved["id"])
    if doctor is None:
        return _err("No encontré al médico.")

    today = _today()
    year = int(params.get("year") or today.year)
    month = int(params.get("month") or today.month)
    records = deps["availability_repo"].list_availability_for_doctor(doctor.id)

    monthly = [
        r
        for r in records
        if r.availability_type == "monthly_variable"
        and r.year == year
        and r.month == month
    ]
    if doctor.availability_mode == "monthly":
        if not monthly:
            return _ok(
                rows=[{
                    "doctor": doctor.name,
                    "estado": "NO reportó disponibilidad para este mes",
                }],
                submitted=False,
            )
        days = sorted(
            {
                d
                for r in monthly
                for d in (
                    getattr(r, "available_days", None)
                    or getattr(r, "available_dates", None)
                    or []
                )
            }
        )
        priority = next(
            (
                r.day_priority
                for r in monthly
                if getattr(r, "day_priority", "available") != "available"
            ),
            None,
        )
        return _ok(
            rows=[{
                "doctor": doctor.name,
                "estado": "reportó",
                "dias_reportados": days,
                "total_dias": len(days),
                "dia_prioritario": priority,
            }],
            submitted=True,
        )

    weekday_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    pattern_rows: list[dict[str, Any]] = []
    for r in records:
        if r.availability_type == "weekly_fixed":
            pattern_rows.append({
                "tipo": "semanal fijo",
                "dias": [weekday_names[d] for d in (r.days_of_week or []) if d < 7],
                "vigente_hasta": _iso(r.effective_to),
            })
        elif r.availability_type == "recurring":
            pattern_rows.append({
                "tipo": "regla recurrente",
                "dia_semana": weekday_names[r.weekday] if r.weekday is not None else None,
                "semana": "última" if r.week_number == -1 else r.week_number,
            })
    if not pattern_rows:
        return _ok(
            rows=[{"doctor": doctor.name, "estado": "Sin disponibilidad registrada"}]
        )
    return _ok(rows=[{"doctor": doctor.name, **row} for row in pattern_rows])


@_guard
def handle_doctor_restrictions(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Restricciones activas de un médico (o de todos) en el período."""
    from backend.app.infrastructure.db.models.availability import DoctorRestrictionModel

    session = deps["session"]
    today = _today()
    year = int(params.get("year") or today.year)
    month = int(params.get("month") or today.month)
    start, end = _month_bounds(year, month)

    stmt = select(DoctorRestrictionModel).where(
        DoctorRestrictionModel.review_status == "approved",
        DoctorRestrictionModel.lifted_at.is_(None),
        DoctorRestrictionModel.starts_at <= end,
        or_(
            DoctorRestrictionModel.ends_at.is_(None),
            DoctorRestrictionModel.ends_at >= start,
        ),
    )
    if params.get("doctor_name"):
        resolved = _resolve_doctor(deps, params["doctor_name"])
        if "error" in resolved:
            return _err(resolved["error"])
        if "ambiguous" in resolved:
            return _ok(ambiguous=resolved["ambiguous"])
        stmt = stmt.where(DoctorRestrictionModel.doctor_id == resolved["id"])

    rows = [
        {
            "doctor": deps["doctor_names"].get(r.doctor_id, r.doctor_id),
            "tipo": r.restriction_type,
            "severidad": r.severity,
            "descripcion": r.description,
            "desde": _iso(r.starts_at),
            "hasta": _iso(r.ends_at),
        }
        for r in session.scalars(stmt.order_by(DoctorRestrictionModel.starts_at))
    ]
    return _ok(total=len(rows), rows=rows)


@_guard
def handle_doctor_service_history(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Historial de guardias de un médico en el período."""
    resolved = _resolve_doctor(deps, params.get("doctor_name", ""))
    if "error" in resolved:
        return _err(resolved["error"])
    if "ambiguous" in resolved:
        return _ok(ambiguous=resolved["ambiguous"])

    today = _today()
    year = int(params.get("year") or today.year)
    month = int(params.get("month") or today.month)
    start, end = _month_bounds(year, month)
    assignments = deps["calendar_repo"].list_assignments_in_date_range(start, end)
    mine = [a for a in assignments if a.doctor_id == resolved["id"]]
    area_names = {a.id: a.display_name for a in deps["catalog_repo"].list_service_areas()}
    rows = [
        {
            "fecha": _iso(a.service_date),
            "area": area_names.get(a.service_area_id, a.service_area_id),
        }
        for a in sorted(mine, key=lambda a: a.service_date)
    ]
    last = max((a.service_date for a in mine), default=None)
    return _ok(rows=rows, total=len(mine), ultima_guardia=_iso(last))


@_guard
def handle_workload_ranking(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Ranking de carga: servicios asignados vs meta mensual."""
    year = int(params["year"])
    month = int(params["month"])
    criterion = params.get("criterion", "load")
    start, end = _month_bounds(year, month)
    assignments = deps["calendar_repo"].list_assignments_in_date_range(start, end)
    counts: dict[str, int] = {}
    for a in assignments:
        counts[a.doctor_id] = counts.get(a.doctor_id, 0) + 1

    ranking = []
    for d in deps["doctor_repo"].list_service_active():
        count = counts.get(d.id, 0)
        target = getattr(d, "monthly_service_target", 3) or 3
        ranking.append({
            "name": d.name,
            "servicios": count,
            "meta": target,
            "faltante_para_meta": max(0, target - count),
        })
    ranking.sort(
        key=lambda r: (
            r["faltante_para_meta"] if criterion == "target_gap" else -r["servicios"]
        )
    )
    return _ok(rows=ranking, total=len(ranking))


# ---------------------------------------------------------------------------
# Calendar / slots
# ---------------------------------------------------------------------------


@_guard
def handle_calendar_assignments(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Guardias en un rango de fechas con filtros opcionales."""
    start = _parse_date(params.get("start_date"), field="start_date")
    end = _parse_date(params.get("end_date"), field="end_date")
    if end < start:
        return _err("end_date no puede ser anterior a start_date.")

    assignments = deps["calendar_repo"].list_assignments_in_date_range(start, end)
    area_names = {a.id: a.display_name for a in deps["catalog_repo"].list_service_areas()}
    doctor_names = deps["doctor_names"]

    doctor_id: str | None = None
    if params.get("doctor_name"):
        resolved = _resolve_doctor(deps, params["doctor_name"])
        if "error" in resolved:
            return _err(resolved["error"])
        if "ambiguous" in resolved:
            return _ok(ambiguous=resolved["ambiguous"])
        doctor_id = resolved["id"]

    area_id: str | None = None
    if params.get("service_area"):
        area = _resolve_area(deps, params["service_area"])
        if "error" in area:
            return _err(area["error"])
        area_id = area["id"]

    source = params.get("source")
    rows = []
    for a in sorted(assignments, key=lambda x: x.service_date):
        if doctor_id and a.doctor_id != doctor_id:
            continue
        if area_id and a.service_area_id != area_id:
            continue
        if source and a.assignment_source != source:
            continue
        rows.append({
            "fecha": _iso(a.service_date),
            "area": area_names.get(a.service_area_id, a.service_area_id),
            "medico": doctor_names.get(a.doctor_id, a.doctor_id),
        })
    return _ok(rows=rows, total=len(rows))


@_guard
def handle_calendar_status(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Estado del calendario mensual: semanas, asignaciones por área y huecos."""
    from sqlalchemy import select as _select

    from backend.app.infrastructure.db.models.calendars import UnresolvedGapModel

    year = int(params["year"])
    month = int(params["month"])

    calendar = deps["calendar_repo"].get_calendar_by_period(year, month)
    if calendar is None:
        return _ok(rows=[], total=0, calendar_exists=False)

    version = deps["calendar_repo"].get_latest_version(calendar.id)
    assignments = (
        deps["calendar_repo"].list_assignments(version.id) if version else []
    )
    weeks = deps["calendar_repo"].list_weeks(calendar.id)
    area_names = {a.id: a.display_name for a in deps["catalog_repo"].list_service_areas()}

    by_area: dict[str, int] = {}
    for a in assignments:
        name = area_names.get(a.service_area_id, a.service_area_id)
        by_area[name] = by_area.get(name, 0) + 1

    gaps: list[dict[str, Any]] = []
    if version:
        session = deps["session"]
        gaps = [
            {
                "fecha": _iso(g.service_date),
                "area": area_names.get(g.service_area_id, g.service_area_id),
                "razon": g.reason_code,
            }
            for g in session.scalars(
                _select(UnresolvedGapModel).where(
                    UnresolvedGapModel.calendar_version_id == version.id
                )
            )
        ]

    return _ok(
        calendar_exists=True,
        rows=[{
            "estado": calendar.status,
            "semanas_aprobadas": sum(1 for w in weeks if w.status == "approved"),
            "semanas_totales": len(weeks),
            "asignaciones_por_area": by_area,
            "total_asignaciones": len(assignments),
            "huecos_sin_cubrir": len(gaps),
        }],
        gaps=gaps[:20],
    )


@_guard
def handle_slot_recommendation(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Candidatos para un slot (día + área) con razones del backend (Fase 2)."""
    target = _parse_date(params.get("date"), field="date")
    area = _resolve_area(deps, params.get("service_area", ""))
    if "error" in area:
        return _err(area["error"])

    calendar = deps["calendar_repo"].get_calendar_by_period(target.year, target.month)
    if calendar is None:
        return _ok(rows=[], total=0, message="No hay calendario creado para ese mes.")
    version = deps["calendar_repo"].get_latest_version(calendar.id)
    if version is None:
        return _ok(rows=[], total=0, message="El calendario no tiene versión activa.")

    result = deps["assignment_service"].get_eligible_doctors_for_slot(
        version_id=version.id,
        target_date=target,
        service_area_id=area["id"],
    )
    eligible = [
        {
            "name": item["doctor"].name,
            "respeta_orden": item["altera_orden"],
        }
        for item in result["eligible"]
    ]
    unavailable = [
        {
            "name": item["full_name"],
            "razon": item["description"],
            "bloqueo_duro": item["is_hard"],
        }
        for item in result["unavailable"]
    ]
    return _ok(
        rows=eligible,
        total=len(eligible),
        area=area["display_name"],
        date=_iso(target),
        unavailable=unavailable,
    )


@_guard
def handle_slot_explanation(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Explica por qué un médico está o no está en un slot."""
    target = _parse_date(params.get("date"), field="date")
    area = _resolve_area(deps, params.get("service_area", ""))
    if "error" in area:
        return _err(area["error"])
    resolved = _resolve_doctor(deps, params.get("doctor_name", ""))
    if "error" in resolved:
        return _err(resolved["error"])
    if "ambiguous" in resolved:
        return _ok(ambiguous=resolved["ambiguous"])

    calendar = deps["calendar_repo"].get_calendar_by_period(target.year, target.month)
    if calendar is None:
        return _ok(rows=[], message="No hay calendario creado para ese mes.")
    version = deps["calendar_repo"].get_latest_version(calendar.id)
    if version is None:
        return _ok(rows=[], message="El calendario no tiene versión activa.")

    existing = deps["calendar_repo"].get_assignment_for_slot(version.id, target, area["id"])
    if existing is not None and existing.doctor_id == resolved["id"]:
        return _ok(
            rows=[{
                "medico": resolved["name"],
                "asignado": True,
                "origen": existing.assignment_source,
                "rationale": existing.rationale,
                "justificacion": existing.override_justification,
            }]
        )

    evaluation = deps["assignment_service"].evaluate_slot(
        version_id=version.id,
        doctor_id=resolved["id"],
        target_date=target,
        service_area_id=area["id"],
    )
    if existing is not None:
        other = deps["doctor_names"].get(existing.doctor_id, existing.doctor_id)
        reasons = [f"El slot está ocupado por {other}."]
        reasons += [h["description"] for h in evaluation["hard_blocks"]]
        reasons += [w["description"] for w in evaluation["warnings"]]
        return _ok(rows=[{"medico": resolved["name"], "asignado": False, "razones": reasons}])

    blocks = evaluation["hard_blocks"] + evaluation["warnings"]
    if not blocks:
        return _ok(
            rows=[{
                "medico": resolved["name"],
                "asignado": False,
                "razones": ["Cumple las reglas pero no fue seleccionado para este slot."],
            }]
        )
    return _ok(
        rows=[{
            "medico": resolved["name"],
            "asignado": False,
            "razones": [b["description"] for b in blocks],
        }]
    )


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@_guard
def handle_doctors_available_on(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Quiénes reportaron disponibilidad para una fecha (sin evaluar reglas)."""
    target = _parse_date(params.get("date"), field="date")
    doctor_ids = deps["availability_service"].get_available_doctor_ids(target)
    if not doctor_ids:
        return _ok(rows=[], total=0)
    doctors = list(
        deps["session"].scalars(
            _doctor_query()
            .where(DoctorModel.id.in_(doctor_ids))
            .order_by(DoctorModel.name)
        )
    )
    rows = [{"name": d.name} for d in doctors]
    return _ok(rows=rows, total=len(rows), date=_iso(target))


@_guard
def handle_availability_report_status(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Quiénes reportaron / faltan por reportar disponibilidad en el mes."""
    from backend.app.infrastructure.db.models.availability import DoctorAvailabilityModel

    year = int(params["year"])
    month = int(params["month"])
    session = deps["session"]
    reporters = set(
        session.scalars(
            select(DoctorAvailabilityModel.doctor_id).where(
                DoctorAvailabilityModel.availability_type == "monthly_variable",
                DoctorAvailabilityModel.year == year,
                DoctorAvailabilityModel.month == month,
                DoctorAvailabilityModel.review_status == "approved",
            )
        )
    )
    doctors = deps["doctor_repo"].list_service_active()
    reported = [{"name": d.name} for d in doctors if d.id in reporters]
    missing = [{"name": d.name} for d in doctors if d.id not in reporters]
    return _ok(
        rows=[*reported, *missing],
        reportados=reported,
        faltantes=missing,
        total_reportados=len(reported),
        total_faltantes=len(missing),
    )


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------


def _mission_label(m) -> str:
    parts = [m.location, m.description]
    if m.mission_date:
        parts.append(m.mission_date.strftime("%d/%m/%Y"))
    return " — ".join(p for p in parts if p) or m.id


@_guard
def handle_mission_list(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    year = params.get("year")
    month = params.get("month")
    if year is not None and month is not None:
        missions = deps["mission_repo"].list_missions_for_month(int(year), int(month))
    else:
        missions = deps["mission_repo"].list_missions()

    status = params.get("status")
    if status:
        missions = [m for m in missions if m.status == status]

    sorted_missions = sorted(missions, key=lambda x: x.mission_date, reverse=True)
    rows = [
        {
            "id": m.id,
            "mision": _mission_label(m),
            "fecha": _iso(m.mission_date),
            "estado": m.status,
            "participantes": m.participant_count,
        }
        for m in sorted_missions
    ]
    if params.get("include_participants") and sorted_missions:
        participants = deps["mission_repo"].list_participants_bulk(
            [m.id for m in sorted_missions]
        )
        doctor_names = deps["doctor_names"]
        for row, m in zip(rows, sorted_missions):
            row["nombres"] = [
                doctor_names.get(p.doctor_id, p.doctor_id)
                for p in participants.get(m.id, [])
            ]
    return _ok(rows=rows, total=len(rows))


@_guard
def handle_mission_status(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    name = params.get("mission_name", "")
    if not name:
        return _err("Falta mission_name.")
    missions = deps["mission_repo"].list_missions()
    target_norm = _normalize(name)
    matches = [
        m
        for m in missions
        if target_norm in _normalize(_mission_label(m))
    ]
    if not matches:
        return _ok(rows=[], total=0, message="No encontré esa misión en el sistema.")
    if len(matches) > 1:
        return _ok(ambiguous=[{"id": m.id, "mision": _mission_label(m)} for m in matches[:10]])

    mission = matches[0]
    participants = deps["mission_repo"].list_participants(mission.id)
    doctor_names = deps["doctor_names"]
    ranking = deps["mission_repo"].get_ranking_by_period(
        mission.mission_date.year, mission.mission_date.month
    )
    return _ok(
        rows=[{
            "mision": _mission_label(mission),
            "fecha": _iso(mission.mission_date),
            "estado": mission.status,
            "participantes": [
                {
                    "name": doctor_names.get(p.doctor_id, p.doctor_id),
                    "posicion_ranking": p.ranking_position,
                    "score": p.score,
                }
                for p in participants
            ],
            "ranking_guardado": ranking is not None,
        }]
    )


@_guard
def handle_mission_candidates(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Candidatos para una misión desde el ranking mensual guardado."""
    mission_date = _parse_date(params.get("mission_date"), field="mission_date")
    count = int(params.get("count") or 3)
    if count < 1 or count > 20:
        return _err("count debe estar entre 1 y 20.")

    result = deps["candidate_service"].recommend_candidates(
        year=mission_date.year,
        month=mission_date.month,
        mission_date=mission_date,
        participant_count=count,
    )
    if not result:
        return _ok(rows=[], total=0, message="No hay candidatos para esa fecha.")
    if isinstance(result, dict) and "error" in result:
        return _err(result["error"])
    return _ok(result=result, date=_iso(mission_date))


# ---------------------------------------------------------------------------
# Confirmations / notifications
# ---------------------------------------------------------------------------


@_guard
def handle_confirmation_status(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Solicitudes de confirmación del período con su estado."""
    from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel

    session = deps["session"]
    stmt = select(ConfirmationRequestModel).order_by(
        ConfirmationRequestModel.created_at.desc()
    )
    stmt = stmt.limit(200)

    if params.get("doctor_name"):
        resolved = _resolve_doctor(deps, params["doctor_name"])
        if "error" in resolved:
            return _err(resolved["error"])
        if "ambiguous" in resolved:
            return _ok(ambiguous=resolved["ambiguous"])
        stmt = stmt.where(ConfirmationRequestModel.doctor_id == resolved["id"])

    today = _today()
    year = int(params.get("year") or today.year)
    month = int(params.get("month") or today.month)
    start, end = _month_bounds(year, month)

    doctor_names = deps["doctor_names"]
    rows = []
    for req in session.scalars(stmt):
        created = req.created_at.date() if req.created_at else None
        if created and (created < start or created > end):
            continue
        rows.append({
            "doctor": doctor_names.get(req.doctor_id, req.doctor_id),
            "tipo": req.confirmation_type,
            "estado": req.status,
            "creado": _iso(req.created_at),
            "vencimiento": _iso(req.due_at),
        })
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["estado"]] = summary.get(row["estado"], 0) + 1
    return _ok(rows=rows, total=len(rows), resumen=summary)


@_guard
def handle_notification_status(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Notificaciones del período: pendientes, enviadas, fallidas (con error)."""
    from backend.app.infrastructure.db.models.notifications import NotificationEventModel

    session = deps["session"]
    today = _today()
    year = int(params.get("year") or today.year)
    month = int(params.get("month") or today.month)
    start, end = _month_bounds(year, month)

    stmt = select(NotificationEventModel).where(
        NotificationEventModel.created_at >= datetime.combine(start, datetime.min.time()),
        NotificationEventModel.created_at <= datetime.combine(end, datetime.max.time()),
    )
    status = params.get("status")
    if status:
        stmt = stmt.where(NotificationEventModel.status == status)
    stmt = stmt.order_by(NotificationEventModel.created_at.desc()).limit(200)

    doctor_id: str | None = None
    if params.get("doctor_name"):
        resolved = _resolve_doctor(deps, params["doctor_name"])
        if "error" in resolved:
            return _err(resolved["error"])
        if "ambiguous" in resolved:
            return _ok(ambiguous=resolved["ambiguous"])
        doctor_id = resolved["id"]

    doctor_names = deps["doctor_names"]
    rows = []
    for ev in session.scalars(stmt):
        if doctor_id and ev.recipient_doctor_id != doctor_id:
            continue
        rows.append({
            "doctor": doctor_names.get(ev.recipient_doctor_id, ev.recipient_doctor_id),
            "tipo": ev.notification_type,
            "estado": ev.status,
            "error": ev.error_message if ev.status == "failed" else None,
            "fecha": _iso(ev.created_at),
        })
    summary: dict[str, int] = {}
    for row in rows:
        summary[row["estado"]] = summary.get(row["estado"], 0) + 1
    return _ok(rows=rows, total=len(rows), resumen=summary)


# ---------------------------------------------------------------------------
# Alerts / audit / config
# ---------------------------------------------------------------------------


@_guard
def handle_action_alerts(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    status = params.get("status") or "open"
    if status not in ("open", "resolved"):
        return _err("status debe ser 'open' o 'resolved'.")
    alerts = deps["alert_repo"].list_all(
        status=status,
        section=params.get("section"),
        severity=params.get("severity"),
        limit=100,
    )
    rows = [
        {
            "seccion": a.section,
            "titulo": a.title,
            "mensaje": a.message,
            "severidad": a.severity,
            "creado": _iso(a.created_at),
        }
        for a in alerts
    ]
    return _ok(rows=rows, total=len(rows))


@_guard
def handle_audit_history(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    entity_id: str | None = None
    entity_type: str | None = None
    if params.get("doctor_name"):
        resolved = _resolve_doctor(deps, params["doctor_name"])
        if "error" in resolved:
            return _err(resolved["error"])
        if "ambiguous" in resolved:
            return _ok(ambiguous=resolved["ambiguous"])
        entity_id = resolved["id"]
        entity_type = "doctor"

    from_dt = None
    to_dt = None
    if params.get("start_date"):
        from_dt = datetime.combine(
            _parse_date(params["start_date"], field="start_date"), datetime.min.time()
        )
    if params.get("end_date"):
        to_dt = datetime.combine(
            _parse_date(params["end_date"], field="end_date"), datetime.max.time()
        )

    events = deps["audit_repo"].list(
        action_type=params.get("action_type"),
        entity_type=entity_type,
        entity_id=entity_id,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=50,
    )
    rows = [
        {
            "actor": deps["user_names"].get(e.actor_id, e.actor_id),
            "accion": e.action_type,
            "entidad": e.entity_type,
            "cuando": _iso(e.occurred_at),
        }
        for e in events
    ]
    return _ok(rows=rows, total=len(rows))


@_guard
def handle_system_config(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Configuración vigente: áreas con pesos y límites por defecto."""
    areas = deps["catalog_repo"].list_service_areas()
    return _ok(
        rows=[{
            "areas": [
                {
                    "nombre": a.display_name,
                    "peso": float(a.load_weight or 1),
                    "requerida_cobertura": bool(a.required_for_daily_coverage),
                    "activa": bool(a.active),
                }
                for a in sorted(areas, key=lambda x: x.display_name)
            ],
            "limites_por_defecto": {
                "meta_mensual": 3,
                "maximo_mensual": 3,
                "modo_limite": "warn_only",
            },
            "reglas_activas": [
                "Espaciado 14 días entre turnos de emergencia/pista",
                "Máximo mensual configurable por médico (advertencia confirmable)",
                "Bloqueos duros: inactivo, restricción dura o área no permitida",
                "Resto de reglas de fairness: advertencias confirmables",
            ],
        }]
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@_guard
def handle_generate_report(params: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Genera el PDF mensual o semanal usando ReportService (application)."""
    from backend.app.application.telegram.report_contracts import (
        ReportContractValidator,
        TelegramReportRequest,
    )

    report_type = params.get("type")
    if report_type not in ("monthly", "weekly"):
        return _err("type debe ser 'monthly' o 'weekly'.")
    month = int(params["month"])
    year = int(params["year"])

    calendar = deps["calendar_repo"].get_calendar_by_period(year, month)
    if calendar is None:
        return _ok(rows=[], message="No hay calendario creado para ese mes.")

    if report_type == "monthly":
        contract = TelegramReportRequest(
            report_type="calendar",
            output_format="pdf",
            month=month,
            year=year,
        )
        validator = ReportContractValidator()
        validation = validator.validate(contract)
        if not validation.get("ok", True):
            return _err(validation.get("error", "Parámetros de reporte inválidos."))
        try:
            gen_result = validator.generate_report(contract, deps["report_service"])
        except Exception as exc:
            return _err(f"No se pudo generar el reporte: {exc}")
        if not gen_result.get("ok"):
            # El contrato de generate_report devuelve {ok: False, error} en vez
            # de lanzar: nunca filtrar ese dict como documento.
            return _err(gen_result.get("error") or "No se pudo generar el reporte.")
        document = gen_result.get("document_bytes")
        if not isinstance(document, bytes | bytearray):
            return _err("El servicio de reportes no devolvió un documento PDF.")
        return _ok(
            document=document,
            filename=gen_result.get("filename") or f"calendario-{year}-{month:02d}.pdf",
            message="Calendario mensual en PDF.",
        )

    # weekly: lista semanal del mes.
    weeks = deps["calendar_repo"].list_weeks(calendar.id)
    if not weeks:
        return _ok(rows=[], message="El calendario no tiene semanas.")
    week = weeks[0]
    if params.get("week"):
        from backend.app.domain.calendars.weeks import compute_weeks

        target_norm = _normalize(str(params["week"]))
        for w in compute_weeks(year, month):
            week_num, _, _sd, _sm, _sd_day, _e, _em, _ed = w
            if target_norm in (str(week_num), _normalize(f"{_sd_day:02d}-{_sm:02d}")):
                candidate = next(
                    (x for x in weeks if x.week_number == week_num),
                    None,
                )
                if candidate is not None:
                    week = candidate
                    break

    version = deps["calendar_repo"].get_latest_version(calendar.id)
    schedule_data = deps["report_service"].build_weekly_schedule(
        year=year,
        month=month,
        calendar_version_id=version.id if version else None,
        week_id=week.id,
    )
    pdf_bytes = deps["report_service"].generate_weekly_schedule_pdf(
        schedule_data=schedule_data,
        week_label=week.label,
        month=month,
        year=year,
    )
    return _ok(
        document=pdf_bytes,
        filename=f"semana-{week.week_number}-{year}-{month:02d}.pdf",
        message=f"Lista semanal «{week.label}» en PDF.",
    )


# ---------------------------------------------------------------------------
# Construcción del mapa tool → handler con dependencias
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "list_doctors": handle_list_doctors,
    "doctor_info": handle_doctor_info,
    "doctor_availability": handle_doctor_availability,
    "doctor_restrictions": handle_doctor_restrictions,
    "doctor_service_history": handle_doctor_service_history,
    "workload_ranking": handle_workload_ranking,
    "calendar_assignments": handle_calendar_assignments,
    "calendar_status": handle_calendar_status,
    "slot_recommendation": handle_slot_recommendation,
    "slot_explanation": handle_slot_explanation,
    "doctors_available_on": handle_doctors_available_on,
    "availability_report_status": handle_availability_report_status,
    "mission_list": handle_mission_list,
    "mission_status": handle_mission_status,
    "mission_candidates": handle_mission_candidates,
    "confirmation_status": handle_confirmation_status,
    "notification_status": handle_notification_status,
    "action_alerts": handle_action_alerts,
    "audit_history": handle_audit_history,
    "system_config": handle_system_config,
    "generate_report": handle_generate_report,
}


def build_tool_handlers(*, session) -> dict[str, Any]:
    """Mapa {tool_name: handler(**params)} con las dependencias de lectura.

    Todos los handlers son de solo lectura: ninguno invoca session.flush(),
    session.commit() ni métodos de escritura de los repositorios.
    """
    from backend.app.application.availability.service import AvailabilityService
    from backend.app.application.calendars.assignment_service import AssignmentService
    from backend.app.application.missions.candidate_service import MissionCandidateService
    from backend.app.application.reports.report_service import ReportService
    from backend.app.infrastructure.repositories.action_alerts import ActionAlertRepository
    from backend.app.infrastructure.repositories.audit import AuditRepository
    from backend.app.infrastructure.repositories.availability import AvailabilityRepository
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    from backend.app.infrastructure.repositories.catalogs import CatalogRepository
    from backend.app.infrastructure.repositories.confirmations import (
        ConfirmationRequestRepository,
    )
    from backend.app.infrastructure.repositories.doctors import DoctorRepository
    from backend.app.infrastructure.repositories.missions import MissionRepository
    from backend.app.infrastructure.repositories.notifications import NotificationRepository

    doctor_repo = DoctorRepository(session)
    calendar_repo = CalendarRepository(session)
    catalog_repo = CatalogRepository(session)
    mission_repo = MissionRepository(session)
    availability_repo = AvailabilityRepository(session)

    deps: dict[str, Any] = {
        "session": session,
        "doctor_repo": doctor_repo,
        "calendar_repo": calendar_repo,
        "catalog_repo": catalog_repo,
        "mission_repo": mission_repo,
        "availability_repo": availability_repo,
        "alert_repo": ActionAlertRepository(session),
        "audit_repo": AuditRepository(session),
        "confirmation_repo": ConfirmationRequestRepository(session),
        "availability_service": AvailabilityService(
            availability_repo, doctor_repo, catalog_repo
        ),
        "assignment_service": AssignmentService(
            calendar_repo, doctor_repo, availability_repo
        ),
        "candidate_service": MissionCandidateService(
            mission_repo, calendar_repo, availability_repo
        ),
        "report_service": ReportService(
            calendar_repo=calendar_repo,
            notification_repo=NotificationRepository(session),
            doctor_repo=doctor_repo,
            mission_repo=mission_repo,
            catalog_repo=catalog_repo,
        ),
        "doctor_names": {},
        "user_names": {},
        "rank_ids": {},
        "department_ids": {},
    }

    # Catálogos de nombres para match y filtros.
    doctors = session.scalars(_doctor_query()).all()
    deps["doctor_names"] = {d.id: d.name for d in doctors}
    users = session.scalars(select(UserModel).limit(2000)).all()
    deps["user_names"] = {u.id: u.name or u.email for u in users}
    deps["rank_ids"] = {
        _normalize(r.name): r.id for r in session.scalars(select(RankModel)).all()
    }
    deps["department_ids"] = {
        _normalize(d.name): d.id for d in session.scalars(select(DepartmentModel)).all()
    }

    def _make(name: str):
        handler = _HANDLERS[name]

        def _call(**params: Any) -> Any:
            return handler(params, deps)

        return _call

    return {name: _make(name) for name in _HANDLERS}
