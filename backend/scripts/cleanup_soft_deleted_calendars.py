"""One-shot script: permanently delete all soft-deleted calendars and their related data.

Run from the project root:
    python backend/scripts/cleanup_soft_deleted_calendars.py
"""

import sys
sys.path.insert(0, "backend")

from backend.app.core.config import settings
from backend.app.infrastructure.db.models.calendars import CalendarModel
from backend.app.infrastructure.db.session import SessionLocal
from backend.app.infrastructure.repositories.calendars import CalendarRepository


def main():
    session = SessionLocal()
    try:
        repo = CalendarRepository(session)

        deleted = repo.list_deleted_calendars()
        print(f"Found {len(deleted)} soft-deleted calendar(s):")

        for cal in deleted:
            print(f"  - {cal.id[:8]}... {cal.year}/{cal.month:02d} (deleted: {cal.deleted_at})")

        if not deleted:
            print("Nothing to clean up.")
            return

        for cal in deleted:
            print(f"Hard-deleting {cal.id} ({cal.year}/{cal.month:02d})...")
            repo.hard_delete_calendar(cal.id)

        session.commit()
        print(f"Done. {len(deleted)} calendar(s) permanently deleted.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
