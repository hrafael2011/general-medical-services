"""Tests for report API routes — uses mocked ReportService."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import require_ready_user
from backend.app.api.routes.reports import get_report_service
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def user():
    from datetime import UTC, datetime

    return _user.UserModel(
        id="test-user",
        email="user@test.com",
        password_hash="hash",
        name="Test User",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_service():
    return MagicMock()


@pytest.fixture
def client(session, user, mock_service):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[require_ready_user] = lambda: user
    app.dependency_overrides[get_report_service] = lambda: mock_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /reports/calendar/{calendar_id}/excel
# ---------------------------------------------------------------------------


def test_get_calendar_excel_success(client, mock_service):
    """Returns xlsx for a valid calendar."""
    mock_service.generate_calendar_excel.return_value = b"\x50\x4b\x03\x04"  # PK\x03\x04

    resp = client.get("/api/reports/calendar/cal-123/excel")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in resp.headers["content-disposition"]


def test_get_calendar_excel_not_found(client, mock_service):
    """Returns 404 when calendar does not exist."""
    mock_service.generate_calendar_excel.side_effect = ValueError("Calendario no encontrado")

    resp = client.get("/api/reports/calendar/invalid-id/excel")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Calendario no encontrado"


# ---------------------------------------------------------------------------
# GET /reports/doctor-history/excel
# ---------------------------------------------------------------------------


def test_get_doctor_history_excel_success(client, mock_service):
    """Returns xlsx for valid year/month."""
    mock_service.generate_doctor_history_excel.return_value = b"\x50\x4b\x03\x04"

    resp = client.get("/api/reports/doctor-history/excel?year=2026&month=4")
    assert resp.status_code == 200
    assert "spreadsheetml.sheet" in resp.headers["content-type"]


def test_get_doctor_history_excel_invalid_params(client, mock_service):
    """Returns 422 for invalid year or month."""
    resp = client.get("/api/reports/doctor-history/excel?year=1999&month=4")
    assert resp.status_code == 422

    resp = client.get("/api/reports/doctor-history/excel?year=2026&month=13")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /reports/weekly-schedule
# ---------------------------------------------------------------------------


def test_get_weekly_schedule_success(client, mock_service):
    """Returns PDF for valid year/month."""
    mock_service.build_weekly_schedule.return_value = b"%PDF-1.4 test"

    resp = client.get("/api/reports/weekly-schedule?year=2026&month=4")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_get_weekly_schedule_not_found(client, mock_service):
    """Returns 404 when calendar has no data."""
    mock_service.build_weekly_schedule.side_effect = ValueError("Calendario no encontrado")

    resp = client.get("/api/reports/weekly-schedule?year=2026&month=4")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /reports/coverage
# ---------------------------------------------------------------------------


def test_get_coverage_json(client, mock_service):
    """Returns JSON by default."""
    mock_service.generate_coverage.return_value = {
        "period_label": "4/2026 - 4/2026",
        "overall_coverage_pct": 85.0,
        "total_gaps": 5,
        "most_critical_area": None,
        "weakest_day": None,
        "by_area": [],
    }

    resp = client.get(
        "/api/reports/coverage?year_start=2026&month_start=4&year_end=2026&month_end=4"
    )
    assert resp.status_code == 200
    assert resp.json()["overall_coverage_pct"] == 85.0


def test_get_coverage_pdf(client, mock_service):
    """Returns PDF when format=pdf."""
    mock_service.generate_coverage.return_value = {
        "period_label": "4/2026 - 4/2026",
        "overall_coverage_pct": 85.0,
        "total_gaps": 5,
        "most_critical_area": None,
        "weakest_day": None,
        "by_area": [],
    }

    resp = client.get(
        "/api/reports/coverage?year_start=2026&month_start=4&year_end=2026&month_end=4&format=pdf"
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_get_coverage_with_filters(client, mock_service):
    """Accepts optional filter params."""
    mock_service.generate_coverage.return_value = {"period_label": "test", "by_area": []}

    resp = client.get(
        "/api/reports/coverage?year_start=2026&month_start=4&year_end=2026&month_end=4"
        "&area=Emergencia&rank_id=r1&sex=male"
    )
    assert resp.status_code == 200
    mock_service.generate_coverage.assert_called_with(
        year_start=2026, month_start=4, year_end=2026, month_end=4,
        area="Emergencia", rank_id="r1", sex="male", department_id=None,
    )


# ---------------------------------------------------------------------------
# GET /reports/workload
# ---------------------------------------------------------------------------


def test_get_workload_json(client, mock_service):
    """Returns JSON by default."""
    mock_service.generate_workload.return_value = {
        "period_label": "4/2026",
        "total_services": 10,
        "active_doctors": 5,
        "entries": [],
    }

    resp = client.get("/api/reports/workload?year=2026&month=4")
    assert resp.status_code == 200
    assert resp.json()["total_services"] == 10


def test_get_workload_pdf(client, mock_service):
    """Returns PDF when format=pdf."""
    mock_service.generate_workload.return_value = {
        "period_label": "4/2026",
        "total_services": 10,
        "active_doctors": 5,
        "avg_per_doctor": 2.0,
        "most_load": {"name": "Dr. A", "total": 5},
        "least_load": {"name": "Dr. B", "total": 1},
        "entries": [
            {"name": "Dr. A", "rank": "Cabo", "sex": "male", "department": "Emergencia",
             "emergencia": 4, "pista": 1, "disponible": 0, "total": 5},
            {"name": "Dr. B", "rank": "Sargento", "sex": "female", "department": "Pista",
             "emergencia": 0, "pista": 1, "disponible": 0, "total": 1},
        ],
    }

    resp = client.get("/api/reports/workload?year=2026&month=4&format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


# ---------------------------------------------------------------------------
# GET /reports/doctor-dossier/{doctor_id}
# ---------------------------------------------------------------------------


def test_get_doctor_dossier_json(client, mock_service):
    """Returns JSON by default."""
    mock_service.generate_doctor_dossier.return_value = {
        "name": "Dr. Test",
        "total_services": 5,
    }

    resp = client.get("/api/reports/doctor-dossier/doc-1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Dr. Test"


def test_get_doctor_dossier_pdf(client, mock_service):
    """Returns PDF when format=pdf."""
    mock_service.generate_doctor_dossier.return_value = {
        "name": "Dr. Test",
        "total_services": 5,
    }

    resp = client.get("/api/reports/doctor-dossier/doc-1?format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


def test_get_doctor_dossier_not_found(client, mock_service):
    """Returns 404 when doctor does not exist."""
    mock_service.generate_doctor_dossier.side_effect = ValueError("Médico no encontrado")

    resp = client.get("/api/reports/doctor-dossier/invalid-id")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Médico no encontrado"


def test_get_doctor_dossier_with_dates(client, mock_service):
    """Passes date_from and date_to when provided."""
    mock_service.generate_doctor_dossier.return_value = {"name": "Dr. Test"}

    resp = client.get("/api/reports/doctor-dossier/doc-1?date_from=2026-04-01&date_to=2026-04-30")
    assert resp.status_code == 200
    mock_service.generate_doctor_dossier.assert_called_with(
        doctor_id="doc-1", date_from=date(2026, 4, 1), date_to=date(2026, 4, 30),
    )
