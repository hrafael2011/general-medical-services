"""
ReportService — generates Excel and JSON reports.
Reads from existing repos; no writes to DB.
"""
import io
from datetime import datetime, timezone


class ReportService:
    def __init__(
        self,
        calendar_repo,   # CalendarRepository
        notification_repo,  # NotificationRepository
        doctor_repo,     # DoctorRepository
    ) -> None:
        self.calendar_repo = calendar_repo
        self.notification_repo = notification_repo
        self.doctor_repo = doctor_repo

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
        all_notifications = self.notification_repo.list_all(limit=5000)

        # Filter by period
        period_notifications = [
            n for n in all_notifications
            if n.created_at.year == year and n.created_at.month == month
        ]

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
            "generated_at": datetime.now(timezone.utc).isoformat(),
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
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
