from datetime import date
from pydantic import BaseModel


class CoverageFilterParams(BaseModel):
    year_start: int
    month_start: int
    year_end: int
    month_end: int
    area: str | None = None
    rank_id: str | None = None
    sex: str | None = None
    department_id: str | None = None


class CoverageByArea(BaseModel):
    area_id: str
    area_name: str
    days_covered: int
    days_uncovered: int
    coverage_pct: float
    gaps: list[dict]  # [{date: "2026-01-03", day_name: "Lunes"}]


class CoverageResponse(BaseModel):
    period_label: str
    overall_coverage_pct: float
    total_gaps: int
    most_critical_area: str | None
    weakest_day: str | None
    by_area: list[CoverageByArea]


class WorkloadFilterParams(BaseModel):
    year: int
    month: int
    area: str | None = None
    rank_id: str | None = None
    sex: str | None = None
    department_id: str | None = None
    group_by: str = "none"  # area|rank|department|none
    order_by: str = "total_desc"  # total_desc|alpha|rank


class DoctorWorkloadEntry(BaseModel):
    doctor_id: str
    name: str
    rank: str | None
    sex: str | None
    department: str | None
    emergencia: int = 0
    pista: int = 0
    disponible: int = 0
    total: int = 0
    details: list[dict] | None = None


class WorkloadResponse(BaseModel):
    period_label: str
    total_services: int
    active_doctors: int
    avg_per_doctor: float
    most_load: dict | None  # {name, total}
    least_load: dict | None  # {name, total}
    entries: list[DoctorWorkloadEntry]


class DossierResponse(BaseModel):
    doctor_id: str
    name: str
    rank: str | None
    sex: str | None
    department: str | None
    areas: list[str]
    period_label: str
    total_services: int
    services_by_area: dict[str, int]
    avg_weekly: float
    services: list[dict]
    missions: list[dict]
    restrictions: list[dict]
    availability: list[str]
