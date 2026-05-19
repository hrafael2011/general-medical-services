"""
ReportService — generates Excel, JSON and PDF reports.
Reads from existing repos; no writes to DB.
"""
import io
from datetime import UTC, date, datetime, timedelta

from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.missions import MissionRepository
from backend.app.infrastructure.repositories.notifications import NotificationRepository


class ReportService:
    def __init__(
        self,
        calendar_repo: CalendarRepository,
        notification_repo: NotificationRepository,
        doctor_repo: DoctorRepository,
        mission_repo: MissionRepository | None = None,
        catalog_repo: CatalogRepository | None = None,
    ) -> None:
        self.calendar_repo = calendar_repo
        self.notification_repo = notification_repo
        self.doctor_repo = doctor_repo
        self.mission_repo = mission_repo
        self.catalog_repo = catalog_repo

    def _load_signatures(self):
        """Load PDF signature config from system_settings, falling back to defaults."""
        from backend.app.application.reports.weasyprint_gen import DEFAULT_SIGNATURES, SignatureConfig

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
        ws.title = f"Calendario {calendar.month:02d}-{calendar.year}"

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
        ws.title = f"Historial {month:02d}-{year}"

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
    # Coverage report
    # ------------------------------------------------------------------

    def generate_coverage(
        self,
        *,
        year_start: int,
        month_start: int,
        year_end: int,
        month_end: int,
        area: str | None = None,
        rank_id: str | None = None,
        sex: str | None = None,
        department_id: str | None = None,
    ) -> dict:
        """Generate coverage report — gaps by area."""
        from calendar import monthrange

        period_label = f"{month_start}/{year_start} - {month_end}/{year_end}"

        # Get doctors filtered by criteria
        filtered_doctor_ids: set[str] | None = None
        if rank_id or sex or department_id:
            doctors = self.doctor_repo.list_with_filters(
                rank_id=rank_id, sex=sex, department_id=department_id, active_only=True
            )
            filtered_doctor_ids = {d.id for d in doctors}

        # Collect all service areas
        service_areas = self.calendar_repo.list_service_areas()
        if area:
            service_areas = [sa for sa in service_areas if sa.display_name == area or sa.id == area]

        by_area_data: list[dict] = []
        area_gaps: dict[str, list[dict]] = {}
        day_of_week_gaps: dict[str, int] = {}
        total_covered = 0
        total_uncovered = 0

        for sa in service_areas:
            covered = 0
            uncovered = 0
            gaps: list[dict] = []

            y, m = year_start, month_start
            while (y < year_end) or (y == year_end and m <= month_end):
                last_day = monthrange(y, m)[1]
                calendar_obj = self.calendar_repo.get_calendar_by_period(y, m)
                version = None
                assignments = []
                if calendar_obj:
                    version = self.calendar_repo.get_latest_version(calendar_obj.id)
                if version:
                    assignments = self.calendar_repo.list_assignments(version.id)

                assignments_for_area = [
                    a for a in assignments
                    if a.service_area_id == sa.id
                    and (not filtered_doctor_ids or a.doctor_id in filtered_doctor_ids)
                ]
                assigned_dates = {a.service_date for a in assignments_for_area}

                for day in range(1, last_day + 1):
                    d = date(y, m, day)
                    if d in assigned_dates:
                        covered += 1
                    else:
                        uncovered += 1
                        gap = {"date": d.isoformat(), "day_name": d.strftime("%A")}
                        gaps.append(gap)
                        day_name_es = d.strftime("%A")
                        day_of_week_gaps[day_name_es] = day_of_week_gaps.get(day_name_es, 0) + 1

                # next month
                if m == 12:
                    y += 1
                    m = 1
                else:
                    m += 1

            total = covered + uncovered
            pct = round((covered / total) * 100, 1) if total > 0 else 0.0
            by_area_data.append({
                "area_id": sa.id,
                "area_name": sa.display_name,
                "days_covered": covered,
                "days_uncovered": uncovered,
                "coverage_pct": pct,
                "gaps": gaps,
            })
            area_gaps[sa.id] = gaps
            total_covered += covered
            total_uncovered += uncovered

        overall_total = total_covered + total_uncovered
        overall_pct = round((total_covered / overall_total) * 100, 1) if overall_total > 0 else 0.0
        total_gaps = total_uncovered
        most_critical = max(by_area_data, key=lambda x: x["days_uncovered"])["area_name"] if by_area_data else None
        weakest_day = max(day_of_week_gaps, key=day_of_week_gaps.get) if day_of_week_gaps else None

        return {
            "period_label": period_label,
            "overall_coverage_pct": overall_pct,
            "total_gaps": total_gaps,
            "most_critical_area": most_critical,
            "weakest_day": weakest_day,
            "by_area": by_area_data,
        }

    # ------------------------------------------------------------------
    # Workload report
    # ------------------------------------------------------------------

    def generate_workload(
        self,
        *,
        year: int,
        month: int,
        area: str | None = None,
        rank_id: str | None = None,
        sex: str | None = None,
        department_id: str | None = None,
        group_by: str = "none",
        order_by: str = "total_desc",
    ) -> dict:
        """Generate workload report — services per doctor."""
        # Get doctors filtered
        doctors = self.doctor_repo.list_with_filters(
            rank_id=rank_id, sex=sex, department_id=department_id, active_only=True
        )
        doctor_map = {d.id: d for d in doctors}
        filtered_ids = {d.id for d in doctors}

        # Get calendar for period
        calendar_obj = self.calendar_repo.get_calendar_by_period(year, month)
        version = None
        assignments = []
        if calendar_obj:
            version = self.calendar_repo.get_latest_version(calendar_obj.id)
        if version:
            assignments = self.calendar_repo.list_assignments(version.id)

        # Filter by area
        area_ids: set[str] | None = None
        if area:
            service_areas = self.calendar_repo.list_service_areas()
            area_ids = {sa.id for sa in service_areas if sa.display_name == area or sa.id == area}

        filtered_assignments = [
            a for a in assignments
            if a.doctor_id in filtered_ids
            and (not area_ids or a.service_area_id in area_ids)
        ]

        # Build area name map
        area_names = {}
        for sa in self.calendar_repo.list_service_areas():
            area_names[sa.id] = sa.display_name

        # Per-doctor aggregation
        entries: dict[str, dict] = {}
        for a in filtered_assignments:
            if a.doctor_id not in entries:
                doc = doctor_map.get(a.doctor_id)
                entries[a.doctor_id] = {
                    "doctor_id": a.doctor_id,
                    "name": doc.name if doc else a.doctor_id,
                    "rank": doc.rank.name if doc and doc.rank else None,
                    "sex": doc.sex if doc else None,
                    "department": doc.department.name if doc and doc.department else None,
                    "emergencia": 0,
                    "pista": 0,
                    "disponible": 0,
                    "total": 0,
                    "details": [],
                }
            e = entries[a.doctor_id]
            area_display = area_names.get(a.service_area_id, a.service_area_id)
            area_key = area_display.lower().replace(" ", "_")
            if area_key in ("emergencia", "pista", "disponible"):
                e[area_key] += 1
            e["total"] += 1
            e["details"].append({
                "date": a.service_date.isoformat(),
                "area": area_display,
            })

        entry_list = list(entries.values())

        # Sort
        if order_by == "alpha":
            entry_list.sort(key=lambda e: e["name"])
        elif order_by == "rank":
            entry_list.sort(key=lambda e: e["rank"] or "")
        else:  # total_desc
            entry_list.sort(key=lambda e: -e["total"])

        totals = [e["total"] for e in entry_list]
        total_services = sum(totals)
        active_doctors = len(entry_list)
        avg_per_doctor = round(total_services / active_doctors, 1) if active_doctors else 0.0
        most = max(entry_list, key=lambda e: e["total"]) if entry_list else None
        least = min(entry_list, key=lambda e: e["total"]) if entry_list else None

        period_label = f"{month}/{year}"
        return {
            "period_label": period_label,
            "total_services": total_services,
            "active_doctors": active_doctors,
            "avg_per_doctor": avg_per_doctor,
            "most_load": {"name": most["name"], "total": most["total"]} if most else None,
            "least_load": {"name": least["name"], "total": least["total"]} if least else None,
            "entries": entry_list,
        }

    # ------------------------------------------------------------------
    # Doctor dossier report
    # ------------------------------------------------------------------

    def generate_doctor_dossier(
        self,
        doctor_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict:
        """Generate doctor dossier — full profile for a period."""
        doctor = self.doctor_repo.get_by_id(doctor_id)
        if doctor is None:
            raise ValueError("Médico no encontrado")

        min_date = date_from
        max_date = date_to

        # Collect assignments for this doctor in the period
        services = []
        services_by_area: dict[str, int] = {}

        # Walk through calendars in the period
        yr_start = min_date.year if min_date else 2026
        yr_end = (max_date if max_date else date(2026, 12, 31)).year
        for y in range(yr_start, yr_end + 1):
            for m in range(1, 13):
                cal = self.calendar_repo.get_calendar_by_period(y, m)
                if not cal:
                    continue
                version = self.calendar_repo.get_latest_version(cal.id)
                if not version:
                    continue
                assignments = self.calendar_repo.list_assignments(version.id)
                for a in assignments:
                    if a.doctor_id != doctor_id:
                        continue
                    if min_date and a.service_date < min_date:
                        continue
                    if max_date and a.service_date > max_date:
                        continue

                    area_name = str(a.service_area_id)
                    services.append({
                        "date": a.service_date.isoformat(),
                        "day_name": a.service_date.strftime("%A"),
                        "area": area_name,
                        "source": a.assignment_source,
                    })
                    services_by_area[area_name] = services_by_area.get(area_name, 0) + 1

        total_services = len(services)

        # Missions via participations
        missions_data = []
        if self.mission_repo and min_date and max_date:
            participations = self.mission_repo.list_participations_for_doctor_in_range(
                doctor_id, min_date, max_date
            )
            for p in participations:
                missions_data.append({
                    "mission": p.mission_assignment_id,
                    "role": p.selection_source,
                    "status": "confirmed",
                })

        # Allowed areas
        areas = self.doctor_repo.get_allowed_areas(doctor_id)

        # Restrictions (graceful if method doesn't exist)
        restrictions_data = []
        if hasattr(self.doctor_repo, "list_restrictions"):
            rest = self.doctor_repo.list_restrictions(doctor_id)
            for r in rest:
                restrictions_data.append({
                    "type": r.restriction_type,
                    "date": r.date.isoformat() if hasattr(r, "date") and r.date else None,
                    "reason": r.reason,
                })

        # Availability (graceful if method doesn't exist)
        availability_days = []
        if hasattr(self.doctor_repo, "get_availability"):
            av = self.doctor_repo.get_availability(doctor_id)
            if av:
                for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                    if getattr(av, day, False):
                        availability_days.append(day.capitalize())

        period_label = f"{min_date.isoformat() if min_date else 'inicio'} - {max_date.isoformat() if max_date else 'actualidad'}"

        return {
            "doctor_id": doctor.id,
            "name": doctor.name,
            "rank": doctor.rank.name if doctor.rank else None,
            "sex": doctor.sex,
            "department": doctor.department.name if doctor.department else None,
            "areas": areas,
            "period_label": period_label,
            "total_services": total_services,
            "services_by_area": services_by_area,
            "avg_weekly": round(total_services / 4.33, 1) if total_services > 0 else 0.0,
            "services": sorted(services, key=lambda s: s["date"]),
            "missions": missions_data,
            "restrictions": restrictions_data,
            "availability": availability_days,
        }

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
        from backend.app.application.reports.weasyprint_gen import generate_weekly_schedule_pdf

        return generate_weekly_schedule_pdf(schedule_data, week_label, month, year, date_str, self._load_signatures())

    def build_weekly_schedule(
        self,
        *,
        year: int,
        month: int,
        calendar_version_id: str | None = None,
        week_id: str | None = None,
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

        # If week_id is specified, filter to only that week's date range
        if week_id:
            week = self.calendar_repo.get_week_by_id(week_id)
            if week is None:
                raise ValueError(f"Week {week_id} not found")
            week_label = week.label
            week_start = week.start_date
            week_end = week.end_date
            assignments = [
                a for a in assignments
                if week_start <= a.service_date <= week_end
            ]

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

        # Build schedule_data — if week_id is given, walk the full Mon-Sun date range
        # to include cross-boundary days from adjacent months
        schedule_data: list[dict] = []
        if week_id and week:
            current = week.start_date
            while current <= week.end_date:
                if current.day in day_assignments:
                    day_name = DAY_NAMES[current.weekday()]
                    schedule_data.append({
                        "day_name": day_name,
                        "day_number": current.day,
                        "assignments": day_assignments[current.day],
                    })
                current += timedelta(days=1)
        else:
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

        if not week_id:
            week_label = f"{month}/{year}"
        return self.generate_weekly_schedule_pdf(schedule_data, week_label, month, year)

    # ------------------------------------------------------------------
    # Full calendar grid data
    # ------------------------------------------------------------------

    def build_full_calendar(self, *, year: int, month: int) -> dict:
        """Build full calendar grid data for single-page PDF export."""
        from calendar import monthrange

        calendar = self.calendar_repo.get_calendar_by_period(year, month)
        if calendar is None:
            raise ValueError(f"No calendar found for {year}-{month}")

        version = self.calendar_repo.get_latest_version(calendar.id)
        if version is None:
            raise ValueError(f"No version found for calendar {calendar.id}")

        assignments = self.calendar_repo.list_assignments(version.id)

        # Load doctor info (name + rank)
        rank_map: dict[str, str] = {}
        if self.catalog_repo:
            for r in self.catalog_repo.list_ranks():
                rank_map[r.id] = r.abbreviation or r.name

        doctor_info: dict[str, dict[str, str]] = {}
        for d in self.doctor_repo.list_all():
            doctor_info[d.id] = {
                "name": d.name,
                "rank": rank_map.get(d.rank_id, "") if d.rank_id else "",
            }

        area_list = self.calendar_repo.list_service_areas()
        areas = sorted(area_list, key=lambda a: a.code)

        # Build cell grid: {day: {area_code: {name: str, rank: str}}}
        cell_map: dict[int, dict[str, dict]] = {}
        for a in assignments:
            d = a.service_date.day
            if d not in cell_map:
                cell_map[d] = {}
            area_name = ""
            for area in areas:
                if area.id == a.service_area_id:
                    area_name = area.code
                    break
            if not area_name:
                area_name = a.service_area_id
            info = doctor_info.get(a.doctor_id, {"name": a.doctor_id, "rank": ""})
            cell_map[d][area_name] = info

        # Load assignments from adjacent months for cross-boundary days
        adjacent_cells: dict[str, dict[str, dict]] = {}  # "YYYY-MM-DD" -> area_code -> doctor_info

        def _load_month_assignments(y: int, m: int) -> None:
            adj_cal = self.calendar_repo.get_calendar_by_period(y, m)
            if adj_cal is None:
                return
            adj_version = self.calendar_repo.get_latest_version(adj_cal.id)
            if adj_version is None:
                return
            for a in self.calendar_repo.list_assignments(adj_version.id):
                date_str = a.service_date.isoformat()
                if date_str not in adjacent_cells:
                    adjacent_cells[date_str] = {}
                area_code = ""
                for area in areas:
                    if area.id == a.service_area_id:
                        area_code = area.code
                        break
                if not area_code:
                    area_code = a.service_area_id
                info = doctor_info.get(a.doctor_id, {"name": a.doctor_id, "rank": ""})
                adjacent_cells[date_str][area_code] = info

        # Previous month
        prev_m = month - 1
        prev_y = year
        if prev_m == 0:
            prev_m = 12
            prev_y -= 1
        _load_month_assignments(prev_y, prev_m)

        # Next month
        next_m = month + 1
        next_y = year
        if next_m == 13:
            next_m = 1
            next_y += 1
        _load_month_assignments(next_y, next_m)

        DAY_NAMES = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        last_day = monthrange(year, month)[1]
        rows = []
        area_codes = [a.code for a in areas]

        for d in range(1, last_day + 1):
            dt = date(year, month, d)
            cells = {}
            for area in areas:
                cells[area.display_name] = cell_map.get(d, {}).get(area.code, {"name": "—", "rank": ""})
            rows.append({
                "day": d,
                "day_name": DAY_NAMES[dt.weekday()],
                "cells": cells,
            })

        total_services = len(assignments)
        unique_doctors = len(set(a.doctor_id for a in assignments))
        total_possible = last_day * len(areas)
        gaps = max(0, total_possible - total_services)
        coverage = round((total_services / total_possible * 100)) if total_possible else 0

        return {
            "month": month,
            "year": year,
            "areas": [a.display_name for a in areas],
            "area_codes": [a.code for a in areas],
            "rows": rows,
            "adjacent_cells": adjacent_cells,
            "summary": {
                "total_services": total_services,
                "gaps": gaps,
                "active_doctors": unique_doctors,
                "coverage_pct": coverage,
            },
        }

    def build_full_calendar_by_id(self, calendar_id: str) -> dict:
        """Build full calendar grid data from a calendar ID."""
        cal = self.calendar_repo.get_calendar_by_id(calendar_id)
        if cal is None:
            raise ValueError(f"Calendar {calendar_id} not found")
        return self.build_full_calendar(year=cal.year, month=cal.month)

