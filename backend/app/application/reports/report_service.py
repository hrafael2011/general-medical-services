"""
ReportService — generates Excel, JSON and PDF reports.
Reads from existing repos; no writes to DB.
"""
import io
from datetime import UTC, date, datetime


class ReportService:
    def __init__(
        self,
        calendar_repo,        # CalendarRepository
        notification_repo,    # NotificationRepository
        doctor_repo,          # DoctorRepository
        mission_repo=None,    # MissionRepository (opcional, para PDF ranking)
        catalog_repo=None,    # CatalogRepository (opcional, para firmas PDF)
    ) -> None:
        self.calendar_repo = calendar_repo
        self.notification_repo = notification_repo
        self.doctor_repo = doctor_repo
        self.mission_repo = mission_repo
        self.catalog_repo = catalog_repo

    def _load_signatures(self):
        """Load PDF signature config from system_settings, falling back to defaults."""
        from backend.app.application.reports.pdf_templates import DEFAULT_SIGNATURES, SignatureConfig

        if self.catalog_repo is None:
            return DEFAULT_SIGNATURES

        def _get(key: str, default: str) -> str:
            setting = self.catalog_repo.get_setting(key)
            return setting.value if setting is not None else default

        d = DEFAULT_SIGNATURES
        return SignatureConfig(
            left_name=_get("pdf.sig_left_name", d.left_name),
            left_title1=_get("pdf.sig_left_title1", d.left_title1),
            left_title2=_get("pdf.sig_left_title2", d.left_title2),
            left_title3=_get("pdf.sig_left_title3", d.left_title3),
            right_name=_get("pdf.sig_right_name", d.right_name),
            right_title1=_get("pdf.sig_right_title1", d.right_title1),
            right_title2=_get("pdf.sig_right_title2", d.right_title2),
            right_title3=_get("pdf.sig_right_title3", d.right_title3),
        )

    # ------------------------------------------------------------------
    # Excel: calendar assignments
    # ------------------------------------------------------------------

    def generate_calendar_excel(self, calendar_id: str) -> bytes:
        """Return an xlsx workbook for a specific calendar as raw bytes."""
        import openpyxl  # lazy import

        calendar = self.calendar_repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise ValueError("Calendario no encontrado")

        version = self.calendar_repo.get_latest_version(calendar.id)
        if version is None:
            raise ValueError("Calendario no encontrado")

        assignments = self.calendar_repo.list_assignments(version.id)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Calendario {calendar.month}/{calendar.year}"

        # Header row
        ws.append(["Fecha", "Area", "Doctor ID", "Estado"])

        # Data rows — already sorted by list_assignments (service_date, service_area_id)
        for a in assignments:
            ws.append([
                str(a.service_date),
                str(a.service_area_id),
                str(a.doctor_id),
                str(a.assignment_source),
            ])

        # Column widths
        ws.column_dimensions["A"].width = 15
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 15

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Excel: doctor history for a period
    # ------------------------------------------------------------------

    def generate_doctor_history_excel(self, year: int, month: int) -> bytes:
        """Return an xlsx workbook with per-doctor assignment counts for a period."""
        import openpyxl  # lazy import

        # Collect assignments for the period (if a calendar exists)
        assignments: list = []
        calendar = self.calendar_repo.get_calendar_by_period(year, month)
        if calendar is not None:
            version = self.calendar_repo.get_latest_version(calendar.id)
            if version is not None:
                assignments = self.calendar_repo.list_assignments(version.id)

        # Build aggregation: doctor_id -> {count, areas}
        agg: dict[str, dict] = {}
        for a in assignments:
            entry = agg.setdefault(a.doctor_id, {"count": 0, "areas": set()})
            entry["count"] += 1
            entry["areas"].add(str(a.service_area_id))

        # Load all doctors
        doctors = self.doctor_repo.list_all()

        # Build rows: include every doctor (even those with 0 services)
        rows = []
        for doctor in doctors:
            entry = agg.get(doctor.id, {"count": 0, "areas": set()})
            rows.append({
                "doctor_id": doctor.id,
                "name": doctor.name,
                "count": entry["count"],
                "areas": ", ".join(sorted(entry["areas"])),
            })

        # Sort by service count descending, then name ascending
        rows.sort(key=lambda r: (-r["count"], r["name"]))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Historial {month}/{year}"

        ws.append(["Doctor ID", "Nombre", "Servicios Mes", "Areas"])
        for row in rows:
            ws.append([row["doctor_id"], row["name"], row["count"], row["areas"]])

        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 40
        ws.column_dimensions["C"].width = 15
        ws.column_dimensions["D"].width = 60

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # JSON: notifications summary
    # ------------------------------------------------------------------

    def generate_notifications_summary(self, year: int, month: int) -> dict:
        """Return a JSON-serialisable summary of notifications for a period."""
        period_notifications = self.notification_repo.list_by_period(year, month)

        by_status: dict[str, int] = {"pending": 0, "sent": 0, "failed": 0, "skipped": 0}
        by_type: dict[str, int] = {}

        for n in period_notifications:
            status_key = str(n.status)
            if status_key in by_status:
                by_status[status_key] += 1
            else:
                by_status[status_key] = by_status.get(status_key, 0) + 1

            ntype = str(n.notification_type)
            by_type[ntype] = by_type.get(ntype, 0) + 1

        return {
            "period": {"year": year, "month": month},
            "total": len(period_notifications),
            "by_status": by_status,
            "by_type": by_type,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # JSON: operational summary
    # ------------------------------------------------------------------

    def generate_operational_summary(self, year: int, month: int) -> dict:
        """Return a JSON-serialisable operational summary for a period."""
        # Active doctors (service_active=True and active=True)
        all_doctors = self.doctor_repo.list_all(active_only=True)
        active_doctors = sum(1 for d in all_doctors if d.service_active)

        # Calendar data
        calendar_status: str | None = None
        total_assignments = 0
        unresolved_gaps = 0

        calendar = self.calendar_repo.get_calendar_by_period(year, month)
        if calendar is not None:
            calendar_status = str(calendar.status)
            version = self.calendar_repo.get_latest_version(calendar.id)
            if version is not None:
                assignments = self.calendar_repo.list_assignments(version.id)
                total_assignments = len(assignments)
                gaps = self.calendar_repo.list_gaps(version.id)
                unresolved_gaps = len(gaps)

        return {
            "period": {"year": year, "month": month},
            "active_doctors": active_doctors,
            "calendar_status": calendar_status,
            "total_assignments": total_assignments,
            "unresolved_gaps": unresolved_gaps,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # PDF: calendar report
    # ------------------------------------------------------------------

    def generate_calendar_pdf(self, calendar_id: str) -> bytes:
        """Return a PDF report for a specific calendar."""
        from backend.app.application.reports.pdf_templates import generate_calendar_pdf

        calendar = self.calendar_repo.get_calendar_by_id(calendar_id)
        if calendar is None:
            raise ValueError("Calendario no encontrado")

        version = self.calendar_repo.get_latest_version(calendar.id)
        if version is None:
            raise ValueError("Calendario no encontrado")

        assignments = self.calendar_repo.list_assignments(version.id)
        doctors = {d.id: d.name for d in self.doctor_repo.list_all()}
        areas = self.calendar_repo.list_service_areas() if hasattr(self.calendar_repo, "list_service_areas") else {}
        area_map = {a.id: a.display_name for a in areas} if areas else {}

        rows = []
        for a in assignments:
            rows.append({
                "service_date": str(a.service_date),
                "service_area_id": area_map.get(a.service_area_id, a.service_area_id),
                "doctor_id": a.doctor_id,
                "doctor_name": doctors.get(a.doctor_id, a.doctor_id),
                "assignment_source": a.assignment_source,
            })

        return generate_calendar_pdf(rows, calendar.month, calendar.year, self._load_signatures())

    # ------------------------------------------------------------------
    # PDF: doctor history
    # ------------------------------------------------------------------

    def generate_doctor_history_pdf(self, year: int, month: int) -> bytes:
        """Return a PDF report with per-doctor assignment counts for a period."""
        from backend.app.application.reports.pdf_templates import generate_doctor_history_pdf

        assignments: list = []
        calendar = self.calendar_repo.get_calendar_by_period(year, month)
        if calendar is not None:
            version = self.calendar_repo.get_latest_version(calendar.id)
            if version is not None:
                assignments = self.calendar_repo.list_assignments(version.id)

        agg: dict[str, dict] = {}
        for a in assignments:
            entry = agg.setdefault(a.doctor_id, {"count": 0, "areas": set()})
            entry["count"] += 1
            entry["areas"].add(str(a.service_area_id))

        doctors = self.doctor_repo.list_all()
        rows = []
        for doctor in doctors:
            entry = agg.get(doctor.id, {"count": 0, "areas": set()})
            rows.append({
                "doctor_id": doctor.id,
                "name": doctor.name,
                "count": entry["count"],
                "areas": ", ".join(sorted(entry["areas"])),
                "load": "",
            })
        rows.sort(key=lambda r: (-r["count"], r["name"]))

        return generate_doctor_history_pdf(rows, month, year, self._load_signatures())

    # ------------------------------------------------------------------
    # PDF: operational summary
    # ------------------------------------------------------------------

    def generate_operational_summary_pdf(self, year: int, month: int) -> bytes:
        """Return a PDF report with the operational summary for a period."""
        from backend.app.application.reports.pdf_templates import generate_operational_summary_pdf

        summary = self.generate_operational_summary(year, month)
        return generate_operational_summary_pdf(summary, self._load_signatures())

    # ------------------------------------------------------------------
    # PDF: mission ranking
    # ------------------------------------------------------------------

    def generate_mission_ranking_pdf(self, year: int, month: int) -> bytes:
        """Return a PDF report with the mission candidate ranking for a period."""
        from backend.app.application.reports.pdf_templates import generate_mission_ranking_pdf

        if self.mission_repo is None:
            raise ValueError("MissionRepository no disponible")

        ranking = self.mission_repo.get_ranking_by_period(year, month)
        if ranking is None:
            raise ValueError("No hay ranking generado para ese periodo")

        entries = self.mission_repo.list_ranking_entries(ranking.id)
        doctors = {d.id: d.name for d in self.doctor_repo.list_all()}

        rows = []
        for e in entries:
            rows.append({
                "position": e.ranking_position,
                "doctor_id": e.doctor_id,
                "doctor_name": doctors.get(e.doctor_id, e.doctor_id),
                "total_load_score": e.total_load_score,
                "eligible": e.eligible,
            })

        return generate_mission_ranking_pdf(rows, month, year, self._load_signatures())

    # ------------------------------------------------------------------
    # PDF: weekly schedule (formato SERVICIOS)
    # ------------------------------------------------------------------

    def generate_weekly_schedule_pdf(
        self,
        schedule_data: list[dict],
        week_label: str,
        month: int,
        year: int,
        date_str: str | None = None,
    ) -> bytes:
        """Return a PDF weekly schedule in the institutional SERVICIOS format."""
        from backend.app.application.reports.pdf_templates import generate_weekly_schedule_pdf

        return generate_weekly_schedule_pdf(schedule_data, week_label, month, year, date_str, self._load_signatures())

    def build_weekly_schedule(
        self,
        *,
        year: int,
        month: int,
        calendar_version_id: str | None = None,
    ) -> bytes:
        """Build a weekly schedule PDF from calendar data for the given period.

        Groups all assignments in the calendar version by day and generates
        the institutional SERVICIOS-format PDF.
        """
        from calendar import monthrange

        calendar = self.calendar_repo.get_calendar_by_period(year, month)
        if calendar is None:
            raise ValueError("Calendario no encontrado")

        version = None
        if calendar_version_id:
            version = self.calendar_repo.get_version_by_id(calendar_version_id)
        else:
            version = self.calendar_repo.get_latest_version(calendar.id)
        if version is None:
            raise ValueError("Versión del calendario no encontrada")

        assignments = self.calendar_repo.list_assignments(version.id)
        if not assignments:
            raise ValueError("No hay asignaciones para el período")

        # Load doctor names
        doctors = {d.id: d.name for d in self.doctor_repo.list_all()}

        # Load service area display names if CatalogRepository is available
        areas: dict[str, str] = {}
        if hasattr(self.calendar_repo, "list_service_areas"):
            area_list = self.calendar_repo.list_service_areas()
            areas = {a.id: a.display_name for a in area_list}

        # Group assignments by day number
        DAY_NAMES = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        day_assignments: dict[int, list[dict]] = {}

        for a in assignments:
            day = a.service_date.day
            day_assignments.setdefault(day, []).append({
                "rank_name": doctors.get(a.doctor_id, a.doctor_id),
                "location": areas.get(a.service_area_id, a.service_area_id),
            })

        # Build schedule_data in day order
        schedule_data: list[dict] = []
        last_day = monthrange(year, month)[1]
        for day in range(1, last_day + 1):
            if day in day_assignments:
                date_obj = date(year, month, day)
                day_name = DAY_NAMES[date_obj.weekday()]
                schedule_data.append({
                    "day_name": day_name,
                    "day_number": day,
                    "assignments": day_assignments[day],
                })

        if not schedule_data:
            raise ValueError("No hay asignaciones para el período")

        week_label = f"{month}/{year}"
        return self.generate_weekly_schedule_pdf(schedule_data, week_label, month, year)

    # ------------------------------------------------------------------
    # PDF: generic doctor listing
    # ------------------------------------------------------------------

    def generate_doctor_list_pdf(
        self,
        doctors: list[dict],
        title: str,
        subtitle: str = "",
        columns: list[str] | None = None,
        col_widths: list[float] | None = None,
    ) -> bytes:
        """Return a PDF listing of doctors in institutional format."""
        from backend.app.application.reports.pdf_templates import generate_doctor_list_pdf

        return generate_doctor_list_pdf(doctors, title, subtitle, columns, col_widths, self._load_signatures())
