from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings

# Register every model before anything queries. SQLAlchemy resolves relationships by
# table name, so a model nobody imported is missing from the metadata and any foreign
# key pointing at it raises NoReferencedTableError. The API process was fine because
# importing the routes pulls everything in; the scheduler does not import routes, so
# its jobs imported models one by one and crashed on the first foreign key that pointed
# elsewhere — silently, reporting zeros. Importing the package here makes "can talk to
# the database" and "knows every table" the same thing.
from backend.app.infrastructure.db import models as _models  # noqa: F401

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

