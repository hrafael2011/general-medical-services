import argparse

from backend.app.application.accounts.service import AccountService
from backend.app.application.catalogs.service import CatalogService
from backend.app.infrastructure.db.session import SessionLocal
from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.users import UserRepository


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
