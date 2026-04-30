import pytest

from backend.app.application.accounts.errors import (
    InvalidCredentialsError,
    InvalidPasswordChangeError,
    PermissionDeniedError,
)
from backend.app.application.accounts.service import AccountService
from backend.app.infrastructure.repositories.users import UserRepository


def test_admin_bootstrap_requires_password_change(db_session) -> None:
    service = AccountService(UserRepository(db_session))

    result = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    )
    db_session.commit()

    assert result.user.role == "admin"
    assert result.user.must_change_password is True
    assert result.temporary_password == "Temporary123!"


def test_admin_creates_encargado_with_temporary_password(db_session) -> None:
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user
    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )

    result = service.create_encargado(
        actor=admin,
        name="Encargado",
        email="encargado@example.local",
        temporary_password="TempEnc123!",
    )
    db_session.commit()

    assert result.user.role == "encargado"
    assert result.user.must_change_password is True


def test_encargado_cannot_create_users(db_session) -> None:
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user
    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    encargado = service.create_encargado(
        actor=admin,
        name="Encargado",
        email="encargado@example.local",
        temporary_password="TempEnc123!",
    ).user
    service.change_own_password(
        user=encargado,
        current_password="TempEnc123!",
        new_password="Permanent456!",
    )

    with pytest.raises(PermissionDeniedError):
        service.create_encargado(
            actor=encargado,
            name="Other",
            email="other@example.local",
            temporary_password="OtherTemp123!",
        )


def test_login_and_password_change_flow(db_session) -> None:
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user

    login = service.authenticate("admin@example.local", "Temporary123!")

    assert login.access_token
    assert login.user.must_change_password is True

    service.change_own_password(
        user=admin,
        current_password="Temporary123!",
        new_password="Permanent123!",
    )
    second_login = service.authenticate("admin@example.local", "Permanent123!")

    assert second_login.user.must_change_password is False


def test_cannot_reuse_current_password(db_session) -> None:
    service = AccountService(UserRepository(db_session))
    admin = service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    ).user

    with pytest.raises(InvalidPasswordChangeError):
        service.change_own_password(
            user=admin,
            current_password="Temporary123!",
            new_password="Temporary123!",
        )


def test_failed_logins_lock_account(db_session) -> None:
    service = AccountService(UserRepository(db_session))
    service.ensure_admin_password(
        email="admin@example.local",
        name="Admin",
        temporary_password="Temporary123!",
    )

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            service.authenticate("admin@example.local", "wrong-password")

    user = UserRepository(db_session).get_by_email("admin@example.local")
    assert user is not None
    assert user.locked_until is not None

