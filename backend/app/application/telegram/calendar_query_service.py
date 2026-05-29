"""Deterministic calendar queries for Telegram conversations."""

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.application.telegram.sanitize import format_rows
from backend.app.application.telegram.types import AgentResult
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
)
from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel


class CalendarQueryService:
    """Runs controlled calendar assignment queries with status awareness."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, query_type: str, params: dict[str, Any]) -> AgentResult | None:
        if query_type == "list_calendar_assignments_by_date_range":
            return self._list_assignments_by_date_range(params)
        if query_type == "count_assigned_doctors_by_month":
            return self._count_assigned_doctors_by_month(params)
        return None

    def _count_assigned_doctors_by_month(self, params: dict[str, Any]) -> AgentResult:
        year = int(params["year"])
        month = int(params["month"])
        approved_total = self._assigned_doctor_count_by_month(year, month, status="approved")
        draft_total = self._assigned_doctor_count_by_month(year, month, status="draft")
        columns = ["total"]
        period = {"year": year, "month": month}

        if approved_total:
            rows = [{"total": approved_total}]
            return AgentResult(
                response_text=format_rows(rows, columns),
                agent_action="query",
                tool_name="calendar_query_service",
                tool_entities={"query_type": "count_assigned_doctors_by_month", "period": period},
                tool_result={
                    "ok": True,
                    "status_used": "approved",
                    "draft_count": draft_total,
                    "data": {"columns": columns, "rows": rows},
                },
            )

        if draft_total:
            return AgentResult(
                response_text=(
                    "No hay calendario aprobado para ese mes. "
                    f"Existe un borrador con {draft_total} médico(s) incluido(s), pendiente de aprobación."
                ),
                agent_action="query",
                tool_name="calendar_query_service",
                tool_entities={"query_type": "count_assigned_doctors_by_month", "period": period},
                tool_result={
                    "ok": True,
                    "status_used": "approved",
                    "draft_count": draft_total,
                    "data": {"columns": columns, "rows": [{"total": 0}]},
                },
            )

        rows = [{"total": 0}]
        return AgentResult(
            response_text=format_rows(rows, columns),
            agent_action="query",
            tool_name="calendar_query_service",
            tool_entities={"query_type": "count_assigned_doctors_by_month", "period": period},
            tool_result={
                "ok": True,
                "status_used": "approved",
                "draft_count": 0,
                "data": {"columns": columns, "rows": rows},
            },
        )

    def _list_assignments_by_date_range(self, params: dict[str, Any]) -> AgentResult:
        start_date = date.fromisoformat(str(params["start_date"]))
        end_date = date.fromisoformat(str(params["end_date"]))

        approved_rows = self._assignment_rows(start_date, end_date, status="approved")
        draft_count = self._assignment_count(start_date, end_date, status="draft")
        columns = ["service_date", "doctor_name", "area"]
        period = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        if approved_rows:
            return AgentResult(
                response_text=format_rows(approved_rows, columns),
                agent_action="query",
                tool_name="calendar_query_service",
                tool_entities={"query_type": "list_calendar_assignments_by_date_range", "period": period},
                tool_result={
                    "ok": True,
                    "status_used": "approved",
                    "draft_count": draft_count,
                    "data": {"columns": columns, "rows": approved_rows},
                },
            )

        if draft_count:
            return AgentResult(
                response_text=(
                    "No hay calendario aprobado para ese periodo. "
                    f"Existe un borrador con {draft_count} asignación(es), pendiente de aprobación."
                ),
                agent_action="query",
                tool_name="calendar_query_service",
                tool_entities={"query_type": "list_calendar_assignments_by_date_range", "period": period},
                tool_result={
                    "ok": True,
                    "status_used": "approved",
                    "draft_count": draft_count,
                    "data": {"columns": columns, "rows": []},
                },
            )

        return AgentResult(
            response_text="No se encontraron servicios aprobados para ese periodo.",
            agent_action="query",
            tool_name="calendar_query_service",
            tool_entities={"query_type": "list_calendar_assignments_by_date_range", "period": period},
            tool_result={
                "ok": True,
                "status_used": "approved",
                "draft_count": 0,
                "data": {"columns": columns, "rows": []},
            },
        )

    def _assignment_rows(self, start_date: date, end_date: date, *, status: str) -> list[dict]:
        stmt = (
            select(
                CalendarAssignmentModel.service_date.label("service_date"),
                DoctorModel.name.label("doctor_name"),
                ServiceAreaModel.display_name.label("area"),
            )
            .select_from(CalendarAssignmentModel)
            .join(CalendarVersionModel, CalendarAssignmentModel.calendar_version_id == CalendarVersionModel.id)
            .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
            .join(DoctorModel, CalendarAssignmentModel.doctor_id == DoctorModel.id)
            .join(ServiceAreaModel, CalendarAssignmentModel.service_area_id == ServiceAreaModel.id)
            .where(
                CalendarAssignmentModel.service_date.between(start_date, end_date),
                CalendarModel.status == status,
                CalendarVersionModel.status == status,
                CalendarModel.deleted_at.is_(None),
                CalendarVersionModel.deleted_at.is_(None),
            )
            .order_by(CalendarAssignmentModel.service_date, ServiceAreaModel.display_name, DoctorModel.name)
        )
        return [dict(row) for row in self._session.execute(stmt).mappings().all()]

    def _assignment_count(self, start_date: date, end_date: date, *, status: str) -> int:
        stmt = (
            select(func.count(CalendarAssignmentModel.id))
            .select_from(CalendarAssignmentModel)
            .join(CalendarVersionModel, CalendarAssignmentModel.calendar_version_id == CalendarVersionModel.id)
            .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
            .where(
                CalendarAssignmentModel.service_date.between(start_date, end_date),
                CalendarModel.status == status,
                CalendarVersionModel.status == status,
                CalendarModel.deleted_at.is_(None),
                CalendarVersionModel.deleted_at.is_(None),
            )
        )
        return int(self._session.execute(stmt).scalar() or 0)

    def _assigned_doctor_count_by_month(self, year: int, month: int, *, status: str) -> int:
        stmt = (
            select(func.count(func.distinct(CalendarAssignmentModel.doctor_id)))
            .select_from(CalendarAssignmentModel)
            .join(CalendarVersionModel, CalendarAssignmentModel.calendar_version_id == CalendarVersionModel.id)
            .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
            .where(
                CalendarModel.year == year,
                CalendarModel.month == month,
                CalendarModel.status == status,
                CalendarVersionModel.status == status,
                CalendarModel.deleted_at.is_(None),
                CalendarVersionModel.deleted_at.is_(None),
            )
        )
        return int(self._session.execute(stmt).scalar() or 0)
