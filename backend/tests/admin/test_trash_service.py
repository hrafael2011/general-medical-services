from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from backend.app.application.admin.trash_service import TrashService, TrashServiceError
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.users import UserRepository


@pytest.fixture
def trash_service(db_session: Session) -> TrashService:
    return TrashService(
        DoctorRepository(db_session),
        UserRepository(db_session),
        CatalogRepository(db_session),
    )


def _make_deleted_doctor(db_session: Session) -> DoctorModel:
    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=str(uuid4()),
        name="Dr. Deleted",
        normalized_name="dr. deleted",
        sex="male",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(doctor)
    db_session.flush()
    return doctor


def _make_deleted_user(db_session: Session) -> UserModel:
    now = datetime.now(UTC)
    user = UserModel(
        id=str(uuid4()),
        name="Deleted User",
        email="deleted@test.com",
        password_hash="hash",
        role="encargado",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_deleted_rank(db_session: Session) -> RankModel:
    now = datetime.now(UTC)
    rank = RankModel(
        id=str(uuid4()),
        name="Deleted Rank",
        normalized_name="deleted rank",
        abbreviation="DR",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(rank)
    db_session.flush()
    return rank


def _make_deleted_department(db_session: Session) -> DepartmentModel:
    now = datetime.now(UTC)
    dept = DepartmentModel(
        id=str(uuid4()),
        name="Deleted Dept",
        normalized_name="deleted dept",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(dept)
    db_session.flush()
    return dept


def _make_deleted_deactivation_reason(db_session: Session) -> DeactivationReasonModel:
    now = datetime.now(UTC)
    reason = DeactivationReasonModel(
        id=str(uuid4()),
        code="deleted_reason",
        display_name="Deleted Reason",
        active=False,
        requires_detail=False,
        applies_to_sex=None,
        severity="hard_block",
        created_at=now,
        updated_at=now,
        deleted_at=now,
    )
    db_session.add(reason)
    db_session.flush()
    return reason


class TestListDeleted:
    def test_list_deleted_doctors(self, db_session, trash_service):
        _make_deleted_doctor(db_session)
        result = trash_service.list_deleted("doctors")
        assert len(result) == 1
        assert result[0].name == "Dr. Deleted"

    def test_list_deleted_users(self, db_session, trash_service):
        _make_deleted_user(db_session)
        result = trash_service.list_deleted("users")
        assert len(result) == 1
        assert result[0].email == "deleted@test.com"

    def test_list_deleted_deactivation_reasons(self, db_session, trash_service):
        _make_deleted_deactivation_reason(db_session)
        result = trash_service.list_deleted("deactivation_reasons")
        assert len(result) == 1
        assert result[0].display_name == "Deleted Reason"

    def test_list_deleted_excludes_active(self, db_session, trash_service):
        _make_deleted_doctor(db_session)
        now = datetime.now(UTC)
        active = DoctorModel(
            id=str(uuid4()),
            name="Active Doc",
            normalized_name="active doc",
            sex="male",
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        db_session.add(active)
        db_session.flush()
        result = trash_service.list_deleted("doctors")
        assert len(result) == 1

    def test_list_deleted_invalid_type(self, trash_service):
        with pytest.raises(TrashServiceError, match="Tipo de entidad"):
            trash_service.list_deleted("calendars")


class TestRestore:
    def test_restore_doctor_clears_deleted_at(self, db_session, trash_service):
        doctor = _make_deleted_doctor(db_session)
        trash_service.restore("doctors", doctor.id)
        db_session.expire_all()
        refreshed = db_session.get(DoctorModel, doctor.id)
        assert refreshed.deleted_at is None

    def test_restore_user_clears_deleted_at(self, db_session, trash_service):
        user = _make_deleted_user(db_session)
        trash_service.restore("users", user.id)
        db_session.expire_all()
        refreshed = db_session.get(UserModel, user.id)
        assert refreshed.deleted_at is None

    def test_restore_deactivation_reason_clears_deleted_at(self, db_session, trash_service):
        reason = _make_deleted_deactivation_reason(db_session)
        trash_service.restore("deactivation_reasons", reason.id)
        db_session.expire_all()
        refreshed = db_session.get(DeactivationReasonModel, reason.id)
        assert refreshed.deleted_at is None
        assert refreshed.active is True

    def test_restore_not_found(self, trash_service):
        with pytest.raises(TrashServiceError, match="no encontrado"):
            trash_service.restore("doctors", "nonexistent-id")

    def test_restore_active_entity_raises(self, db_session, trash_service):
        """Restoring an active (non-deleted) entity should raise."""
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
        db_session.flush()
        with pytest.raises(TrashServiceError, match="no está eliminada"):
            trash_service.restore("doctors", doctor.id)


class TestHardDelete:
    def test_hard_delete_removes_row(self, db_session, trash_service):
        doctor = _make_deleted_doctor(db_session)
        trash_service.hard_delete("doctors", doctor.id)
        db_session.expire_all()
        assert db_session.get(DoctorModel, doctor.id) is None

    def test_hard_delete_rank_removes_row(self, db_session, trash_service):
        rank = _make_deleted_rank(db_session)
        trash_service.hard_delete("ranks", rank.id)
        db_session.expire_all()
        assert db_session.get(RankModel, rank.id) is None

    def test_hard_delete_deactivation_reason_removes_row(self, db_session, trash_service):
        reason = _make_deleted_deactivation_reason(db_session)
        trash_service.hard_delete("deactivation_reasons", reason.id)
        db_session.expire_all()
        assert db_session.get(DeactivationReasonModel, reason.id) is None

    def test_hard_delete_deactivation_reason_clears_doctor_references(
        self,
        db_session,
        trash_service,
    ):
        reason = _make_deleted_deactivation_reason(db_session)
        doctor = _make_deleted_doctor(db_session)
        doctor.deleted_at = None
        doctor.service_active = False
        doctor.service_inactive_reason_id = reason.id
        db_session.flush()

        trash_service.hard_delete("deactivation_reasons", reason.id)
        db_session.expire_all()

        refreshed_doctor = db_session.get(DoctorModel, doctor.id)
        assert db_session.get(DeactivationReasonModel, reason.id) is None
        assert refreshed_doctor.service_inactive_reason_id is None

    def test_hard_delete_not_found(self, trash_service):
        with pytest.raises(TrashServiceError, match="no encontrado"):
            trash_service.hard_delete("doctors", "nonexistent-id")

    def test_hard_delete_active_entity_raises(self, db_session, trash_service):
        """Hard-deleting an active (non-deleted) entity should raise."""
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
        db_session.flush()
        with pytest.raises(TrashServiceError, match="no está eliminada"):
            trash_service.hard_delete("doctors", doctor.id)

    def test_hard_delete_doctor_anonymizes_audit(self, db_session):
        from backend.app.infrastructure.db.models.audit import AuditEventModel
        from backend.app.infrastructure.repositories.audit import AuditRepository

        audit_repo = AuditRepository(db_session)
        service = TrashService(
            DoctorRepository(db_session),
            UserRepository(db_session),
            CatalogRepository(db_session),
            audit=audit_repo,
        )

        doctor = _make_deleted_doctor(db_session)
        event = AuditEventModel(
            id=str(uuid4()),
            actor_id=doctor.id,
            action_type="doctor_deleted",
            entity_type="doctor",
            entity_id=doctor.id,
            occurred_at=datetime.now(UTC),
            before_snapshot={"name": doctor.name},
        )
        db_session.add(event)
        db_session.flush()

        service.hard_delete("doctors", doctor.id)
        db_session.expire_all()

        updated = db_session.get(AuditEventModel, event.id)
        assert updated.entity_id is None
        assert updated.actor_id is None
        assert updated.before_snapshot == {"name": doctor.name}

    def test_hard_delete_user_anonymizes_audit(self, db_session):
        from backend.app.infrastructure.db.models.audit import AuditEventModel
        from backend.app.infrastructure.repositories.audit import AuditRepository

        audit_repo = AuditRepository(db_session)
        service = TrashService(
            DoctorRepository(db_session),
            UserRepository(db_session),
            CatalogRepository(db_session),
            audit=audit_repo,
        )

        user = _make_deleted_user(db_session)
        event = AuditEventModel(
            id=str(uuid4()),
            actor_id=user.id,
            action_type="user_deleted",
            entity_type="user",
            entity_id=user.id,
            occurred_at=datetime.now(UTC),
            before_snapshot={"name": user.name},
        )
        db_session.add(event)
        db_session.flush()

        service.hard_delete("users", user.id)
        db_session.expire_all()

        updated = db_session.get(AuditEventModel, event.id)
        assert updated.entity_id is None
        assert updated.actor_id is None

    def test_hard_delete_rank_does_not_anonymize_audit(self, db_session):
        from backend.app.infrastructure.db.models.audit import AuditEventModel
        from backend.app.infrastructure.repositories.audit import AuditRepository

        audit_repo = AuditRepository(db_session)
        service = TrashService(
            DoctorRepository(db_session),
            UserRepository(db_session),
            CatalogRepository(db_session),
            audit=audit_repo,
        )

        rank = _make_deleted_rank(db_session)
        event = AuditEventModel(
            id=str(uuid4()),
            actor_id=rank.id,
            action_type="rank_deleted",
            entity_type="rank",
            entity_id=rank.id,
            occurred_at=datetime.now(UTC),
        )
        db_session.add(event)
        db_session.flush()

        service.hard_delete("ranks", rank.id)
        db_session.expire_all()

        updated = db_session.get(AuditEventModel, event.id)
        assert updated.entity_id == rank.id
