from datetime import UTC, date, timedelta

from backend.app.infrastructure.repositories.availability import AvailabilityRepository
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository




def _now_utc() -> date:
    from datetime import datetime
    return datetime.now(UTC).date()


class ToolGateway:
    """Maps intent IDs to backend queries. Returns plain dicts for LLM formatting."""

    def __init__(
        self,
        doctor_repo: DoctorRepository,
        calendar_repo: CalendarRepository,
        mission_repo: MissionRepository,
        availability_repo: AvailabilityRepository,
        query_executor=None,  # QueryExecutor (Phase 2)
        report_service=None,  # ReportService (Phase 3)
        catalog_repo: CatalogRepository | None = None,
    ) -> None:
        self._doctor_repo = doctor_repo
        self._calendar_repo = calendar_repo
        self._mission_repo = mission_repo
        self._availability_repo = availability_repo
        self._query_executor = query_executor
        self._report_service = report_service
        self._catalog_repo = catalog_repo

        self._handlers = {
            "count_medicos_activos": self._tool_count_medicos_activos,
            "list_medicos_activos": self._tool_list_medicos_activos,
            "estado_calendario_mes": self._tool_estado_calendario_mes,
            "get_mission_candidate_ranking": self._tool_get_mission_candidate_ranking,
            "recommend_mission_candidates": self._tool_recommend_mission_candidates,
            "historial_medico": self._tool_historial_medico,
            "pendientes_disponibilidad_mes": self._tool_pendientes_disponibilidad_mes,
            "confirm_mission_assignment": self._tool_create_mission,  # backward compat
            "create_mission": self._tool_create_mission,
        }

        if query_executor is not None:
            self._handlers["query_database"] = self._tool_query_database
        # PDF report generation tools removed as part of reports redesign.
        # Will be re-added in a later version with new report templates.

    def execute(self, intent: str, entities: dict) -> dict:
        """
        Dispatch intent to the correct tool method.
        Returns {"ok": True, "data": ...} or {"ok": False, "error": "..."}
        Unknown intent → {"ok": False, "error": "out_of_domain"}
        """
        handler = self._handlers.get(intent)
        if handler is None:
            return {"ok": False, "error": "out_of_domain"}
        try:
            return {"ok": True, "data": handler(entities)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Tool methods
    # ------------------------------------------------------------------

    def _tool_query_database(self, entities: dict) -> dict:
        """Execute a natural-language database query via QueryExecutor."""
        query = entities.get("query") or entities.get("question", "")
        if not query:
            return {"found": False, "error": "consulta_vacia"}
        result = self._query_executor.execute(query)
        if not result.get("ok"):
            return {"found": False, "error": result.get("error", "error_desconocido")}
        data = result["data"]
        return {
            "found": True,
            "query": query,
            "columns": data["columns"],
            "rows": data["rows"],
            "row_count": data["row_count"],
            "truncated": data["truncated"],
            "elapsed_seconds": data["elapsed_seconds"],
        }

    def _tool_count_medicos_activos(self, entities: dict) -> dict:
        """Return count of service-active doctors."""
        doctors = self._doctor_repo.list_service_active()
        return {"count": len(doctors)}

    def _tool_list_medicos_activos(self, entities: dict) -> dict:
        """Return list of up to 20 service-active doctors."""
        doctors = self._doctor_repo.list_service_active()
        return {
            "doctors": [
                {
                    "id": d.id,
                    "name": d.name,
                    "sex": d.sex,
                    "availability_mode": d.availability_mode,
                }
                for d in doctors[:20]
            ]
        }

    def _tool_estado_calendario_mes(self, entities: dict) -> dict:
        """Return calendar status for a given month/year."""
        from datetime import datetime

        month: int = int(entities["month"])
        year: int = int(entities.get("year", datetime.now(UTC).year))

        calendar = self._calendar_repo.get_calendar_by_period(year, month)
        if calendar is None:
            return {"found": False}

        version = self._calendar_repo.get_latest_version(calendar.id)
        if version is None:
            return {
                "found": True,
                "calendar_id": calendar.id,
                "status": calendar.status,
                "version_number": None,
                "version_status": None,
                "assignments": 0,
                "gaps": 0,
            }

        assignments = self._calendar_repo.list_assignments(version.id)
        gaps = self._calendar_repo.list_gaps(version.id)

        return {
            "found": True,
            "calendar_id": calendar.id,
            "status": calendar.status,
            "version_number": version.version_number,
            "version_status": version.status,
            "assignments": len(assignments),
            "gaps": len(gaps),
        }

    def _tool_get_mission_candidate_ranking(self, entities: dict) -> dict:
        """Return top 10 entries from the mission candidate ranking for a period."""
        month: int = int(entities["month"])
        year: int = int(entities["year"])

        ranking = self._mission_repo.get_ranking_by_period(year, month)
        if ranking is None:
            return {"found": False}

        entries = self._mission_repo.list_ranking_entries(ranking.id)

        return {
            "found": True,
            "month": month,
            "year": year,
            "entries": [
                {
                    "position": e.ranking_position,
                    "doctor_id": e.doctor_id,
                    "total_load_score": e.total_load_score,
                    "eligible": e.eligible,
                }
                for e in entries[:10]
            ],
        }

    def _tool_recommend_mission_candidates(self, entities: dict) -> dict:
        """Return top eligible candidates using MissionCandidateService."""
        from datetime import date as date_type

        raw_date: str = entities.get("mission_date", "")
        participant_count: int = int(entities.get("participant_count", 1))

        if not raw_date:
            return {"found": False, "reason": "missing_mission_date"}

        try:
            parsed_date = date_type.fromisoformat(raw_date)
        except ValueError:
            return {"found": False, "reason": "invalid_date_format"}

        from backend.app.application.missions.candidate_service import MissionCandidateService

        service = MissionCandidateService(
            mission_repo=self._mission_repo,
            calendar_repo=self._calendar_repo,
            availability_repo=self._availability_repo,
        )

        try:
            result = service.recommend_candidates(
                year=parsed_date.year,
                month=parsed_date.month,
                mission_date=parsed_date,
                participant_count=participant_count,
                include_alternates=True,
            )
        except Exception as exc:
            return {"found": False, "reason": str(exc)}

        return {
            "found": True,
            "mission_date": raw_date,
            "participant_count": participant_count,
            "candidates": [
                {
                    "position": e.ranking_position,
                    "doctor_id": e.doctor_id,
                    "total_load_score": e.total_load_score,
                    "eligible": e.eligible,
                }
                for e in result["primary"]
            ],
            "alternates": [
                {
                    "position": e.ranking_position,
                    "doctor_id": e.doctor_id,
                    "total_load_score": e.total_load_score,
                    "eligible": e.eligible,
                }
                for e in result["alternates"]
            ],
        }

    def _tool_historial_medico(self, entities: dict) -> dict:
        """Return assignment history for a doctor over the last 60 days."""
        doctor_id: str | None = entities.get("doctor_id")
        doctor_name: str | None = entities.get("doctor_name")

        doctor = None

        if doctor_id:
            doctor = self._doctor_repo.get_by_id(doctor_id)
        elif doctor_name:
            all_doctors = self._doctor_repo.list_all()
            name_lower = doctor_name.lower()
            matches = [d for d in all_doctors if name_lower in d.name.lower()]
            if matches:
                doctor = matches[0]

        if doctor is None:
            return {"found": False, "doctor_id": None, "doctor_name": None, "assignments_60d": 0, "load_60d": 0.0}

        end: date = _now_utc()
        start: date = end - timedelta(days=60)

        all_assignments = self._calendar_repo.list_assignments_in_date_range(start, end)
        doctor_assignments = [a for a in all_assignments if a.doctor_id == doctor.id]

        if self._catalog_repo is not None:
            area_weights: dict[str, float] = {
                sa.id: float(sa.load_weight)
                for sa in self._catalog_repo.list_service_areas()
            }
        else:
            area_weights = {}
        load_60d: float = sum(
            area_weights.get(a.service_area_id, 1.0) for a in doctor_assignments
        )

        return {
            "found": True,
            "doctor_id": doctor.id,
            "doctor_name": doctor.name,
            "assignments_60d": len(doctor_assignments),
            "load_60d": load_60d,
        }

    def _tool_pendientes_disponibilidad_mes(self, entities: dict) -> dict:
        """Return doctors who have not submitted monthly variable availability for a period."""
        month: int = int(entities["month"])
        year: int = int(entities["year"])

        active_doctors = self._doctor_repo.list_service_active()
        pending = []

        for doctor in active_doctors:
            records = self._availability_repo.list_monthly_variable_for_period(
                doctor.id, year, month
            )
            if not records:
                pending.append({"doctor_id": doctor.id, "name": doctor.name})

        return {"pending": pending, "count": len(pending)}

    def _tool_create_mission(self, entities: dict) -> dict:
        """
        Create and confirm a mission assignment with selected doctors.
        Expects actor_id injected by the agent layer.
        """
        from datetime import date as date_type

        raw_date: str = entities.get("mission_date", "")
        doctor_ids: list = entities.get("doctor_ids", [])
        actor_id: str | None = entities.get("_actor_id")

        if not raw_date or not doctor_ids:
            return {"ok": False, "error": "Faltan datos: mission_date y doctor_ids son requeridos."}

        if not actor_id:
            return {"ok": False, "error": "No se pudo identificar al usuario."}

        try:
            parsed_date = date_type.fromisoformat(raw_date)
        except ValueError:
            return {"ok": False, "error": "Formato de fecha inválido. Use YYYY-MM-DD."}

        from backend.app.application.missions.candidate_service import MissionCandidateService

        service = MissionCandidateService(
            mission_repo=self._mission_repo,
            calendar_repo=self._calendar_repo,
            availability_repo=self._availability_repo,
        )

        # Step 1: create mission in draft
        mission = service.create_mission(
            actor_id=actor_id,
            mission_date=parsed_date,
            participant_count=len(doctor_ids),
            location=entities.get("location"),
            description=entities.get("description"),
        )

        # Step 2: confirm with selected doctors (stores rationale from ranking)
        confirmed = service.confirm_mission(
            actor_id=actor_id,
            mission_id=mission.id,
            doctor_ids=doctor_ids,
        )

        return {
            "ok": True,
            "data": {
                "mission_id": confirmed.id,
                "mission_date": raw_date,
                "doctor_ids": doctor_ids,
                "participant_count": len(doctor_ids),
                "status": confirmed.status,
            },
            "message": f"Misión creada y confirmada con {len(doctor_ids)} médico(s).",
        }
