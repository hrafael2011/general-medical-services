"""Tests for catalogs API routes — uses real DB for GET, mocked service for POST."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import require_admin, require_ready_user
from backend.app.api.routes.catalogs import get_catalog_service
from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.main import create_app


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session_local(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture
def user():
    return UserModel(
        id="admin-user", email="admin@test.com", password_hash="hash", name="Admin",
        role="admin", active=True, must_change_password=False, token_version=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )


@pytest.fixture
def seed_data(engine):
    """Seed catalogs data into the shared engine before each test."""
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    sess = SessionLocal()
    repo = CatalogRepository(sess)
    service = CatalogService(repo)
    service.seed_initial_catalogs()
    service.create_rank("Cabo", "CB")
    sess.commit()
    sess.close()


@pytest.fixture
def mock_service():
    return MagicMock(spec=CatalogService)


@pytest.fixture
def client(session_local, user, seed_data, mock_service):
    """TestClient with real DB + seeded catalogs + mocked CatalogService."""
    app = create_app()

    def _get_session():
        s = session_local()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db_session] = _get_session
    app.dependency_overrides[require_ready_user] = lambda: user
    app.dependency_overrides[require_admin] = lambda: user
    app.dependency_overrides[get_catalog_service] = lambda: mock_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/catalogs/service-areas
# ---------------------------------------------------------------------------


def test_list_service_areas_returns_seeded_data(client):
    resp = client.get("/api/catalogs/service-areas")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    codes = {d["code"] for d in data}
    assert codes == {"emergencia", "pista", "disponible"}


def test_list_service_areas_returns_read_schema(client):
    resp = client.get("/api/catalogs/service-areas")
    assert resp.status_code == 200
    item = resp.json()[0]
    assert "id" in item
    assert "code" in item
    assert "display_name" in item
    assert "active" in item
    assert "required_for_daily_coverage" in item
    assert "load_weight" in item


# ---------------------------------------------------------------------------
# GET /api/catalogs/deactivation-reasons
# ---------------------------------------------------------------------------


def test_list_deactivation_reasons_all(client):
    resp = client.get("/api/catalogs/deactivation-reasons")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 9


def test_list_deactivation_reasons_filtered_by_sex(client):
    resp = client.get("/api/catalogs/deactivation-reasons?sex=female")
    assert resp.status_code == 200
    female_codes = {d["code"] for d in resp.json()}
    assert "pregnancy" in female_codes

    resp = client.get("/api/catalogs/deactivation-reasons?sex=male")
    assert resp.status_code == 200
    male_codes = {d["code"] for d in resp.json()}
    assert "pregnancy" not in male_codes


def test_list_deactivation_reasons_invalid_sex(client):
    resp = client.get("/api/catalogs/deactivation-reasons?sex=invalid")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/catalogs/ranks
# ---------------------------------------------------------------------------


def test_list_ranks(client):
    resp = client.get("/api/catalogs/ranks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    names = [d["name"] for d in data]
    assert "Cabo" in names


# ---------------------------------------------------------------------------
# POST /api/catalogs/ranks
# ---------------------------------------------------------------------------


def test_create_rank_success(client, mock_service):
    from backend.app.infrastructure.db.models.catalogs import RankModel

    rank = RankModel(
        id="r-new", name="Coronel", normalized_name="coronel",
        abbreviation="Cnel.", active=True,
    )
    mock_service.create_rank.return_value = rank

    resp = client.post("/api/catalogs/ranks", json={"name": "Coronel", "abbreviation": "Cnel."})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Coronel"
    assert resp.json()["abbreviation"] == "Cnel."
    mock_service.create_rank.assert_called_once_with("Coronel", "Cnel.")


def test_create_rank_empty_name(client):
    resp = client.post("/api/catalogs/ranks", json={"name": "", "abbreviation": "Cnel."})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/catalogs/departments
# ---------------------------------------------------------------------------


def test_list_departments(client):
    resp = client.get("/api/catalogs/departments")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    names = {d["name"] for d in data}
    assert "Licencias Médicas" in names


# ---------------------------------------------------------------------------
# POST /api/catalogs/departments
# ---------------------------------------------------------------------------


def test_create_department_success(client, mock_service):
    from backend.app.infrastructure.db.models.catalogs import DepartmentModel

    dept = DepartmentModel(
        id="d-new", name="New Dept", normalized_name="new dept", active=True,
    )
    mock_service.create_department.return_value = dept

    resp = client.post("/api/catalogs/departments", json={"name": "New Dept"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "New Dept"
    mock_service.create_department.assert_called_once_with("New Dept")


def test_create_department_empty_name(client):
    resp = client.post("/api/catalogs/departments", json={"name": ""})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/catalogs/seed
# ---------------------------------------------------------------------------


def test_seed_catalogs_success(client, mock_service):
    resp = client.post("/api/catalogs/seed")
    assert resp.status_code == 204
    mock_service.seed_initial_catalogs.assert_called_once()


# ---------------------------------------------------------------------------
# PATCH /api/catalogs/ranks/{rank_id}
# ---------------------------------------------------------------------------


def test_update_rank_success(client, mock_service):
    from backend.app.infrastructure.db.models.catalogs import RankModel

    rank = RankModel(
        id="r-1", name="Cabo Actualizado", normalized_name="cabo actualizado",
        abbreviation="CB.", active=True,
    )
    mock_service.update_rank.return_value = rank

    resp = client.patch(
        "/api/catalogs/ranks/r-1",
        json={"name": "Cabo Actualizado", "active": True},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Cabo Actualizado"
    mock_service.update_rank.assert_called_once_with(
        "r-1", name="Cabo Actualizado", abbreviation=None, active=True,
    )


def test_update_rank_not_found(client, mock_service):
    from backend.app.application.catalogs.service import CatalogError
    mock_service.update_rank.side_effect = CatalogError("rank_not_found", "Rank not found")

    resp = client.patch("/api/catalogs/ranks/nonexistent", json={"name": "X"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/catalogs/ranks/{rank_id}
# ---------------------------------------------------------------------------


def test_delete_rank_success(client, mock_service):
    mock_service.soft_delete_rank.return_value = 3
    resp = client.delete("/api/catalogs/ranks/r-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Rank deleted"
    assert data["affected_doctors"] == 3
    mock_service.soft_delete_rank.assert_called_once_with("r-1")


def test_delete_rank_not_found(client, mock_service):
    from backend.app.application.catalogs.service import CatalogError
    mock_service.soft_delete_rank.side_effect = CatalogError("rank_not_found", "Rank not found")

    resp = client.delete("/api/catalogs/ranks/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/catalogs/departments/{department_id}
# ---------------------------------------------------------------------------


def test_update_department_success(client, mock_service):
    from backend.app.infrastructure.db.models.catalogs import DepartmentModel

    dept = DepartmentModel(
        id="d-1", name="Nuevo Dept", normalized_name="nuevo dept", active=True,
    )
    mock_service.update_department.return_value = dept

    resp = client.patch(
        "/api/catalogs/departments/d-1",
        json={"name": "Nuevo Dept", "active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Nuevo Dept"
    mock_service.update_department.assert_called_once_with(
        "d-1", name="Nuevo Dept", active=False,
    )


def test_update_department_not_found(client, mock_service):
    from backend.app.application.catalogs.service import CatalogError
    mock_service.update_department.side_effect = CatalogError("department_not_found", "Department not found")

    resp = client.patch("/api/catalogs/departments/nonexistent", json={"name": "X"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/catalogs/departments/{department_id}
# ---------------------------------------------------------------------------


def test_delete_department_success(client, mock_service):
    mock_service.soft_delete_department.return_value = 0
    resp = client.delete("/api/catalogs/departments/d-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Department deleted"
    assert data["affected_doctors"] == 0
    mock_service.soft_delete_department.assert_called_once_with("d-1")


def test_delete_department_not_found(client, mock_service):
    from backend.app.application.catalogs.service import CatalogError
    mock_service.soft_delete_department.side_effect = CatalogError("department_not_found", "Department not found")

    resp = client.delete("/api/catalogs/departments/nonexistent")
    assert resp.status_code == 404
