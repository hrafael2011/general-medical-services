import argparse
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from sqlalchemy import create_engine

from backend.app.application.accounts.service import AccountService
from backend.app.application.catalogs.service import CatalogService
from backend.app.core.config import settings
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.session import SessionLocal
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.users import UserRepository


def _hash_token(raw: str) -> str:
    return sha256(raw.encode()).hexdigest()


def reset_admin_password(args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        service = AccountService(UserRepository(session))
        result = service.ensure_admin_password(
            email=args.email,
            name=args.name,
            temporary_password=args.password,
        )
        session.commit()
        print(f"Admin account ready: {result.user.email}")
        if args.password is None:
            print(f"Temporary password: {result.temporary_password}")
        print("Password change is required on next login.")


def create_set_password_tokens_table(args: argparse.Namespace) -> None:
    """Drop and recreate the set_password_tokens table."""
    engine = create_engine(settings.database_url)
    SetPasswordTokenModel.__table__.drop(engine, checkfirst=True)
    Base.metadata.create_all(bind=engine, tables=[SetPasswordTokenModel.__table__])
    engine.dispose()
    print("Table `set_password_tokens` created successfully.")


def reset_user_password(args: argparse.Namespace) -> None:
    """Generate a reset token for a user by email and print the URL."""
    with SessionLocal() as session:
        repo = UserRepository(session)
        user = repo.get_by_email(args.email)
        if user is None:
            print(f"Error: User with email '{args.email}' not found.")
            return

        raw_token = token_urlsafe(48)
        now = datetime.now(UTC)
        token_record = SetPasswordTokenModel(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=_hash_token(raw_token),
            email=user.email,
            expires_at=now + timedelta(hours=48),
            used_at=None,
            created_by=user.id,
            created_at=now,
        )
        session.add(token_record)
        session.commit()

        link = f"{settings.frontend_origin}/set-password?token={raw_token}"
        print(f"Reset URL for {user.email}: {link}")
        print("This link expires in 48 hours.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medical-shifts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reset_admin = subparsers.add_parser("reset-admin-password")
    reset_admin.add_argument("--email", required=True)
    reset_admin.add_argument("--name", default="Administrador")
    reset_admin.add_argument("--password", default=None)
    reset_admin.set_defaults(func=reset_admin_password)

    seed_catalogs = subparsers.add_parser("seed-catalogs")
    seed_catalogs.set_defaults(func=seed_initial_catalogs)

    db_parser = subparsers.add_parser("db")
    db_sub = db_parser.add_subparsers(dest="db_command", required=True)
    create_tokens = db_sub.add_parser("create-set-password-tokens")
    create_tokens.set_defaults(func=create_set_password_tokens_table)

    users_parser = subparsers.add_parser("users")
    users_sub = users_parser.add_subparsers(dest="users_command", required=True)
    reset_parser = users_sub.add_parser("reset-password")
    reset_parser.add_argument("email", help="Email of the user to reset")
    reset_parser.set_defaults(func=reset_user_password)

    return parser


def seed_initial_catalogs(_args: argparse.Namespace) -> None:
    with SessionLocal() as session:
        CatalogService(CatalogRepository(session)).seed_initial_catalogs()
        session.commit()
        print("Initial catalogs seeded.")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
