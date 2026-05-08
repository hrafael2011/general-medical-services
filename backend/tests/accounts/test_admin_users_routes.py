import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.dependencies import require_admin
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models import audit as _audit  # noqa: F401
from backend.app.infrastructure.db.models import availability as _availability  # noqa: F401
from backend.app.infrastructure.db.models import calendars as _calendars  # noqa: F401
from backend.app.infrastructure.db.models import catalogs as _catalogs  # noqa: F401
from backend.app.infrastructure.db.models import doctors as _doctors  # noqa: F401
from backend.app.infrastructure.db.models import import_staging as _import_staging  # noqa: F401
from backend.app.infrastructure.db.models import missions as _missions  # noqa: F401
from backend.app.infrastructure.db.models import notifications as _notifications  # noqa: F401
from backend.app.infrastructure.db.models import telegram as _telegram  # noqa: F401
from backend.app.infrastructure.db.models import user as _user  # noqa: F401
from backend.app.infrastructure.db.session import get_db_session
from backend.app.infrastructure.repositories.users import UserRepository
from backend.app.main import create_app


@pytest.fixture()
def session():
    # StaticPool ensures all connections share the same in-memory SQLite database,
    # which is necessary because FastAPI runs sync route handlers in a thread pool.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def admin_user(session):
    service = AccountService(UserRepository(session))
    result = service.ensure_admin_password(
        email="admin@example.com",
        name="Admin Test",
        temporary_password="Temporary123!",
    )
    # Change password so must_change_password=False (required by _require_admin check)
    service.change_own_password(
        user=result.user,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    session.commit()
    return result.user


@pytest.fixture()
def client(session, admin_user):
    app = create_app()

    # get_db_session is a generator dependency — override must also yield
    def override_get_db_session():
        yield session

    # The route imports get_db_session from backend.app.infrastructure.db.session
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[require_admin] = lambda: admin_user
    return TestClient(app)


def test_list_users_returns_200(client):
    # GET /api/admin/users — default role filter is "doctor", so returns empty list
    response = client.get("/api/admin/users")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_encargado_returns_201(client):
    response = client.post(
        "/api/admin/users/encargados",
        json={
            "name": "Encargado Test",
            "email": "encargado@example.com",
            "temporary_password": "TempEnc123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "encargado@example.com"
    assert data["user"]["role"] == "encargado"
    assert "temporary_password" in data


def test_create_encargado_duplicate_email_returns_409(client):
    payload = {
        "name": "Enc",
        "email": "dup@example.com",
        "temporary_password": "TempEnc123!",
    }
    client.post("/api/admin/users/encargados", json=payload)
    response = client.post("/api/admin/users/encargados", json=payload)
    assert response.status_code == 409


def test_reset_encargado_password_returns_200(client):
    # Create an encargado first
    create_resp = client.post(
        "/api/admin/users/encargados",
        json={
            "name": "Reset Target",
            "email": "reset@example.com",
            "temporary_password": "TempEnc123!",
        },
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["user"]["id"]

    response = client.post(
        f"/api/admin/users/{user_id}/reset-password",
        json={"temporary_password": "NewTemp456!"},
    )
    assert response.status_code == 200
    assert response.json()["temporary_password"] == "NewTemp456!"


def test_reset_nonexistent_user_returns_404(client):
    response = client.post(
        "/api/admin/users/nonexistent-uuid/reset-password",
        json={"temporary_password": "NewTemp456!"},
    )
    assert response.status_code == 404
