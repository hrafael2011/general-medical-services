from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db_session
from backend.app.core.security import create_access_token
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.main import create_app


@pytest.fixture
def client(db_session: Session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


def _create_user(session: Session, role: str) -> UserModel:
    now = datetime.now(UTC)
    user = UserModel(
        id=str(uuid4()),
        email=f"{role}@test.com",
        password_hash="hash",
        name=role.title(),
        role=role,
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _auth_headers(user: UserModel) -> dict[str, str]:
    from backend.app.core.security import create_access_token

    token = create_access_token(subject=user.id, role=user.role, token_version=user.token_version)
    return {"Authorization": f"Bearer {token}"}


class TestTrashCounts:
    def test_counts_returns_all_four_types(self, client, db_session):
        admin = _create_user(db_session, "admin")
        resp = client.get("/api/admin/trash/counts", headers=_auth_headers(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"doctors", "users", "ranks", "departments"}
        assert all(isinstance(v, int) for v in data.values())

    def test_counts_requires_admin(self, client, db_session):
        encargado = _create_user(db_session, "encargado")
        resp = client.get("/api/admin/trash/counts", headers=_auth_headers(encargado))
        assert resp.status_code == 403

    def test_counts_reflects_deleted_items(self, client, db_session):
        admin = _create_user(db_session, "admin")
        now = datetime.now(UTC)

        doctor = DoctorModel(
            id=str(uuid4()),
            name="Deleted Doc",
            normalized_name="deleted doc",
            sex="male",
            created_at=now,
            updated_at=now,
            deleted_at=now,
        )
        db_session.add(doctor)
        db_session.flush()

        resp = client.get("/api/admin/trash/counts", headers=_auth_headers(admin))
        assert resp.status_code == 200
        assert resp.json()["doctors"] == 1
        assert resp.json()["users"] == 0
