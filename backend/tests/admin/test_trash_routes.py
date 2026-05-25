from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db_session
from backend.app.core.security import create_access_token
from backend.app.infrastructure.db.models.catalogs import DeactivationReasonModel, RankModel
from backend.app.infrastructure.db.models.doctors import DoctorAllowedAreaModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import PasswordHistoryModel, UserModel
from backend.app.main import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
    token = create_access_token(
        subject=user.id,
        role=user.role,
        token_version=user.token_version,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# GET /api/admin/trash?type=...
# ---------------------------------------------------------------------------


def test_list_trash_requires_admin(client: TestClient, db_session: Session) -> None:
    """Non-admin users should receive 403."""
    user = _create_user(db_session, role="encargado")
    headers = _auth_headers(user)
    resp = client.get("/api/admin/trash?type=doctors", headers=headers)
    assert resp.status_code == 403


def test_list_trash_doctors(client: TestClient, db_session: Session) -> None:
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
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.get("/api/admin/trash?type=doctors", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Deleted Doc"


def test_list_trash_deactivation_reasons(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    reason = DeactivationReasonModel(
        id=str(uuid4()),
        code="training",
        display_name="Capacitación",
        active=False,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(reason)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.get("/api/admin/trash?type=deactivation_reasons", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Capacitación"
    assert data[0]["code"] == "training"


def test_list_trash_empty(client: TestClient, db_session: Session) -> None:
    """Returns empty list when no deleted entities of the given type exist."""
    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.get("/api/admin/trash?type=users", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# POST /api/admin/trash/{entity_type}/{entity_id}/restore
# ---------------------------------------------------------------------------


def test_restore_doctor(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Restore Me",
        normalized_name="restore me",
        sex="male",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(doctor)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.post(
        f"/api/admin/trash/doctors/{doctor.id}/restore", headers=headers
    )
    assert resp.status_code == 204


def test_restore_not_found(client: TestClient, db_session: Session) -> None:
    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.post(
        "/api/admin/trash/doctors/nonexistent/restore", headers=headers
    )
    assert resp.status_code == 404


def test_restore_active_entity_returns_422(
    client: TestClient, db_session: Session
) -> None:
    """Restoring a non-deleted entity should yield 422."""
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Active Doc",
        normalized_name="active doc",
        sex="male",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db_session.add(doctor)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.post(
        f"/api/admin/trash/doctors/{doctor.id}/restore", headers=headers
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/admin/trash/{entity_type}/{entity_id}
# ---------------------------------------------------------------------------


def test_hard_delete_rank(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    rank = RankModel(
        id=str(uuid4()),
        name="Delete Me",
        abbreviation="DM",
        normalized_name="delete me",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(rank)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(
        f"/api/admin/trash/ranks/{rank.id}", headers=headers
    )
    assert resp.status_code == 204


def test_hard_delete_deactivation_reason(client: TestClient, db_session: Session) -> None:
    now = datetime.now(UTC)
    reason = DeactivationReasonModel(
        id=str(uuid4()),
        code="training",
        display_name="Capacitación",
        active=False,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(reason)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(
        f"/api/admin/trash/deactivation_reasons/{reason.id}", headers=headers
    )
    assert resp.status_code == 204
    assert db_session.get(DeactivationReasonModel, reason.id) is None


def test_hard_delete_deactivation_reason_clears_doctor_references(
    client: TestClient,
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    reason = DeactivationReasonModel(
        id=str(uuid4()),
        code="training",
        display_name="Capacitación",
        active=False,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Inactive Doctor",
        normalized_name="inactive doctor",
        sex="male",
        service_active=False,
        service_inactive_reason_id=reason.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(reason)
    db_session.add(doctor)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(
        f"/api/admin/trash/deactivation_reasons/{reason.id}", headers=headers
    )

    assert resp.status_code == 204
    assert db_session.get(DeactivationReasonModel, reason.id) is None
    assert db_session.get(DoctorModel, doctor.id).service_inactive_reason_id is None


def test_hard_delete_user_removes_password_history(
    client: TestClient, db_session: Session
) -> None:
    now = datetime.now(UTC)
    user = UserModel(
        id=str(uuid4()),
        email="deleted-user@test.com",
        password_hash="hash",
        name="Deleted User",
        role="encargado",
        active=True,
        must_change_password=False,
        token_version=1,
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(user)
    db_session.add(
        PasswordHistoryModel(
            id=str(uuid4()),
            user_id=user.id,
            password_hash="old-hash",
            created_at=now,
        )
    )
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(f"/api/admin/trash/users/{user.id}", headers=headers)

    assert resp.status_code == 204
    assert db_session.get(UserModel, user.id) is None
    assert (
        db_session.query(PasswordHistoryModel)
        .filter(PasswordHistoryModel.user_id == user.id)
        .count()
        == 0
    )


def test_hard_delete_doctor_removes_allowed_areas(
    client: TestClient, db_session: Session
) -> None:
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Deleted Doctor",
        normalized_name="deleted doctor",
        sex="male",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(doctor)
    db_session.add(
        DoctorAllowedAreaModel(
            doctor_id=doctor.id,
            service_area_id=str(uuid4()),
        )
    )
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(f"/api/admin/trash/doctors/{doctor.id}", headers=headers)

    assert resp.status_code == 204
    assert db_session.get(DoctorModel, doctor.id) is None
    assert (
        db_session.query(DoctorAllowedAreaModel)
        .filter(DoctorAllowedAreaModel.doctor_id == doctor.id)
        .count()
        == 0
    )


def test_hard_delete_not_found(client: TestClient, db_session: Session) -> None:
    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(
        "/api/admin/trash/doctors/nonexistent", headers=headers
    )
    assert resp.status_code == 404


def test_hard_delete_active_entity_returns_422(
    client: TestClient, db_session: Session
) -> None:
    """Hard-deleting a non-deleted entity should yield 422."""
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Active Doc",
        normalized_name="active doc",
        sex="male",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db_session.add(doctor)
    db_session.commit()

    admin = _create_user(db_session, role="admin")
    headers = _auth_headers(admin)

    resp = client.delete(
        f"/api/admin/trash/doctors/{doctor.id}", headers=headers
    )
    assert resp.status_code == 422
