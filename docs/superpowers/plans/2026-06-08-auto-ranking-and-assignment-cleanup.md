# Auto-Ranking Generation & Assignment Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate mission ranking on every assignment change and calendar creation, and clean up calendar assignments when a doctor's availability mode changes or service is deactivated.

**Architecture:** Minimal changes to existing services. `CalendarRepository` gains two query methods. `DoctorService` cleans up assignments on mode/service changes. `AssignmentService` and `GenerationService` gain an optional `mission_ranking_service` dependency and trigger ranking refresh (debounced for manual mode, immediate for batch/creation). The ranking visibility guard is relaxed from "approved version required" to "any version".

**Tech Stack:** Python 3.13, SQLAlchemy 2.0, FastAPI, threading.Timer

---

## File Map

| File | Change |
|---|---|
| `backend/app/infrastructure/repositories/calendars.py` | Add `delete_assignments_for_doctor_in_active_calendars()` and `get_latest_version_by_period()` |
| `backend/app/application/doctors/service.py` | Add `_cleanup_calendar_assignments()`, call on availability_mode change + service_active=False |
| `backend/app/application/calendars/assignment_service.py` | Add `mission_ranking_service` param, debounce timer, scheduling calls in assign/replace/remove |
| `backend/app/application/calendars/generation_service.py` | Add `mission_ranking_service` param, call after batch generation |
| `backend/app/application/calendars/service.py` | Call `generate_ranking()` in `create_calendar()` |
| `backend/app/api/routes/calendars.py` | Wire `MissionRankingService` into `AssignmentService` and `GenerationService` factories |
| `backend/app/api/routes/missions.py` | Replace `_approved_version_or_409` with `_latest_version_or_404` |

---

### Task 1: Add query methods to CalendarRepository

**Files:**
- Modify: `backend/app/infrastructure/repositories/calendars.py`

- [ ] **Step 1: Add `get_latest_version_by_period()` method**

Add after the existing `get_approved_version_by_period()` method (after line 187):

```python
def get_latest_version_by_period(
    self,
    year: int,
    month: int,
) -> CalendarVersionModel | None:
    """Return the latest version for the given period regardless of status."""
    stmt = (
        select(CalendarVersionModel)
        .join(CalendarModel, CalendarVersionModel.calendar_id == CalendarModel.id)
        .where(
            CalendarModel.year == year,
            CalendarModel.month == month,
            *_not_deleted(),
            *_version_not_deleted(),
        )
        .order_by(CalendarVersionModel.version_number.desc())
        .limit(1)
    )
    return self.session.scalar(stmt)
```

- [ ] **Step 2: Add `delete_assignments_for_doctor_in_active_calendars()` method**

Add after the new `get_latest_version_by_period()` method:

```python
def delete_assignments_for_doctor_in_active_calendars(
    self,
    doctor_id: str,
) -> int:
    """Delete all assignments for a doctor in draft/partial calendars.

    Returns the number of deleted rows.
    """
    from sqlalchemy import delete as sql_delete

    active_calendar_ids = (
        select(CalendarModel.id)
        .where(
            CalendarModel.status.in_(["draft", "partial"]),
            CalendarModel.deleted_at.is_(None),
        )
    )

    active_version_ids = (
        select(CalendarVersionModel.id)
        .where(
            CalendarVersionModel.calendar_id.in_(active_calendar_ids),
            CalendarVersionModel.deleted_at.is_(None),
        )
    )

    stmt = (
        sql_delete(CalendarAssignmentModel)
        .where(
            CalendarAssignmentModel.doctor_id == doctor_id,
            CalendarAssignmentModel.calendar_version_id.in_(active_version_ids),
        )
    )
    result = self.session.execute(stmt)
    return result.rowcount
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/infrastructure/repositories/calendars.py
git commit -m "feat: add get_latest_version_by_period and delete_assignments_for_doctor_in_active_calendars to CalendarRepository"
```

---

### Task 2: Clean up assignments on doctor availability mode change

**Files:**
- Modify: `backend/app/application/doctors/service.py`

- [ ] **Step 1: Add `_cleanup_calendar_assignments()` helper**

Add this method to `DoctorService` class, after `update_doctor()`:

```python
def _cleanup_calendar_assignments(self, doctor_id: str) -> int:
    """Remove all assignments for a doctor in draft/partial calendars.

    Returns the count of removed assignments.
    """
    from backend.app.infrastructure.repositories.calendars import CalendarRepository

    repo = CalendarRepository(self.doctors.session)
    return repo.delete_assignments_for_doctor_in_active_calendars(doctor_id)
```

- [ ] **Step 2: Capture old availability_mode before update**

In `update_doctor()`, before the `if availability_mode is not None:` block (before line 262), capture the old value:

```python
# Capture old mode before updating (for assignment cleanup)
old_availability_mode = doctor.availability_mode
```

- [ ] **Step 3: Call cleanup when availability_mode changes**

After line 264 (`changed_fields["availability_mode"] = availability_mode`), add:

```python
if old_availability_mode != availability_mode:
    removed_count = self._cleanup_calendar_assignments(doctor_id)
    if removed_count > 0:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(
            "Cleaned up %d calendar assignments for doctor %s due to availability_mode change (%s → %s)",
            removed_count, doctor_id, old_availability_mode, availability_mode,
        )
```

- [ ] **Step 4: Call cleanup when service_active is set to False**

After line 272 (`changed_fields["allowed_area_ids"] = []`) inside the `if not service_active:` block, add:

```python
removed_count = self._cleanup_calendar_assignments(doctor_id)
if removed_count > 0:
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info(
        "Cleaned up %d calendar assignments for deactivated doctor %s",
        removed_count, doctor_id,
    )
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/doctors/service.py
git commit -m "fix: clean up calendar assignments when doctor availability_mode changes or service deactivated"
```

---

### Task 3: Auto-rank on calendar creation

**Files:**
- Modify: `backend/app/application/calendars/service.py`

- [ ] **Step 1: Add ranking generation call at end of `create_calendar()`**

After the audit block (after line 97, before `return calendar`), add:

```python
# Generate empty initial ranking (no assignments yet, but ranking record exists)
if self.mission_ranking_service is not None:
    self.mission_ranking_service.generate_ranking(
        actor_id=actor_id,
        year=year,
        month=month,
        calendar_version_id=version.id,
    )
```

The full `create_calendar()` tail should look like:

```python
        if self.audit is not None:
            self.audit.log_calendar_created(actor_id=actor_id, calendar=calendar)

        # Generate empty initial ranking
        if self.mission_ranking_service is not None:
            self.mission_ranking_service.generate_ranking(
                actor_id=actor_id,
                year=year,
                month=month,
                calendar_version_id=version.id,
            )

        return calendar
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/application/calendars/service.py
git commit -m "feat: generate initial mission ranking on calendar creation"
```

---

### Task 4: Debounced auto-rank on manual assignment changes

**Files:**
- Modify: `backend/app/application/calendars/assignment_service.py`

- [ ] **Step 1: Add `mission_ranking_service` to constructor**

Update `__init__` signature (line 41-48) to accept the optional parameter:

```python
def __init__(
    self,
    calendar_repo: CalendarRepository,
    doctor_repo: DoctorRepository,
    availability_repo: AvailabilityRepository,
    audit: AuditService | None = None,
    triggers: NotificationTriggers | None = None,
    mission_ranking_service=None,
) -> None:
    self.calendar_repo = calendar_repo
    self.doctor_repo = doctor_repo
    self.availability_repo = availability_repo
    self.audit = audit
    self.triggers = triggers
    self._mission_ranking_service = mission_ranking_service
    self._ranking_timers: dict[str, threading.Timer] = {}
```

Add `import threading` at the top of the file (after other imports).

- [ ] **Step 2: Add debounce scheduler and refresh methods**

Add these two methods to `AssignmentService` class, after `__init__`:

```python
def _schedule_ranking_refresh(
    self,
    calendar_version_id: str,
    year: int,
    month: int,
    actor_id: str,
) -> None:
    """Schedule a debounced ranking refresh (5s delay, resets on each call)."""
    if self._mission_ranking_service is None:
        return

    key = f"{year}-{month}"
    if key in self._ranking_timers:
        self._ranking_timers[key].cancel()

    timer = threading.Timer(
        5.0,
        self._do_ranking_refresh,
        args=[calendar_version_id, year, month, actor_id],
    )
    timer.daemon = True
    self._ranking_timers[key] = timer
    timer.start()


def _do_ranking_refresh(
    self,
    calendar_version_id: str,
    year: int,
    month: int,
    actor_id: str,
) -> None:
    """Execute the ranking refresh (called by the timer)."""
    try:
        self._mission_ranking_service.generate_ranking(
            actor_id=actor_id,
            year=year,
            month=month,
            calendar_version_id=calendar_version_id,
        )
    except Exception:
        import logging
        _logger = logging.getLogger(__name__)
        _logger.exception(
            "Failed to auto-refresh ranking for %d/%02d", year, month
        )
    finally:
        self._ranking_timers.pop(f"{year}-{month}", None)
```

- [ ] **Step 3: Schedule ranking refresh in `assign_doctor()`**

At the end of `assign_doctor()`, after line 762 (`return assignment`), but before the return, add:

```python
        # Schedule debounced ranking refresh
        if self._mission_ranking_service is not None:
            version = self.calendar_repo.get_version_by_id(version_id)
            if version is not None:
                calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
                if calendar is not None:
                    self._schedule_ranking_refresh(
                        calendar_version_id=version_id,
                        year=calendar.year,
                        month=calendar.month,
                        actor_id=actor_id,
                    )
```

Insert this right before the `return assignment` statement (after line 761).

- [ ] **Step 4: Schedule ranking refresh in `replace_assignment()`**

At the end of `replace_assignment()`, before line 923 (`return assignment`), add the same scheduling block:

```python
        # Schedule debounced ranking refresh
        if self._mission_ranking_service is not None:
            version = self.calendar_repo.get_version_by_id(assignment.calendar_version_id)
            if version is not None:
                calendar = self.calendar_repo.get_calendar_by_id(version.calendar_id)
                if calendar is not None:
                    self._schedule_ranking_refresh(
                        calendar_version_id=assignment.calendar_version_id,
                        year=calendar.year,
                        month=calendar.month,
                        actor_id=actor_id,
                    )
```

- [ ] **Step 5: Schedule ranking refresh in `remove_assignment()`**

In `remove_assignment()`, before line 796 (`self.calendar_repo.delete_assignment(assignment_id)`), capture the version and calendar info, then after the deletion, schedule:

Replace the existing block starting at "should_notify" through the deletion:

```python
        service_area_name = self._service_area_name(assignment.service_area_id)
        should_notify = self._is_unlocked_approved_version(version)
        version_id = assignment.calendar_version_id

        # Capture calendar info for ranking refresh before deletion
        _calendar_id = None
        _year = None
        _month = None
        if self._mission_ranking_service is not None and version is not None:
            cal = self.calendar_repo.get_calendar_by_id(version.calendar_id)
            if cal is not None:
                _calendar_id = cal.id
                _year = cal.year
                _month = cal.month

        self.calendar_repo.delete_assignment(assignment_id)

        if self.audit is not None:
            self.audit.log_assignment_removed(actor_id=actor_id, assignment_id=assignment_id)

        if should_notify and self.triggers is not None:
            self.triggers.on_calendar_assignment_removed_after_approval(
                actor_id=actor_id,
                assignment=assignment,
                service_area_name=service_area_name,
            )

        # Schedule debounced ranking refresh
        if self._mission_ranking_service is not None and _year is not None:
            self._schedule_ranking_refresh(
                calendar_version_id=version_id,
                year=_year,
                month=_month,
                actor_id=actor_id,
            )
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/calendars/assignment_service.py
git commit -m "feat: auto-refresh mission ranking on manual assignment changes (debounced)"
```

---

### Task 5: Auto-rank after batch generation

**Files:**
- Modify: `backend/app/application/calendars/generation_service.py`

- [ ] **Step 1: Add `mission_ranking_service` to constructor**

Update `__init__` (lines 51-65):

```python
def __init__(
    self,
    calendar_repo: CalendarRepository,
    doctor_repo: DoctorRepository,
    availability_repo: AvailabilityRepository,
    mission_repo: MissionRepository,
    catalog_repo: CatalogRepository,
    audit: AuditService | None = None,
    mission_ranking_service=None,
) -> None:
    self.calendar_repo = calendar_repo
    self.doctor_repo = doctor_repo
    self.availability_repo = availability_repo
    self.mission_repo = mission_repo
    self.catalog_repo = catalog_repo
    self.audit = audit
    self.mission_ranking_service = mission_ranking_service
```

- [ ] **Step 2: Call ranking generation at end of `generate()`**

Before `return summary_raw` (line 246), add:

```python
        # Generate ranking immediately after batch assignment (no debounce needed)
        if self.mission_ranking_service is not None:
            self.mission_ranking_service.generate_ranking(
                actor_id=actor_id,
                year=calendar.year,
                month=calendar.month,
                calendar_version_id=version.id,
            )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/application/calendars/generation_service.py
git commit -m "feat: generate mission ranking after batch calendar generation"
```

---

### Task 6: Wire MissionRankingService into dependency factories

**Files:**
- Modify: `backend/app/api/routes/calendars.py`

- [ ] **Step 1: Wire into `get_assignment_service()` factory**

In `get_assignment_service()` (line 152-191), add `MissionRankingService` instantiation and pass it to `AssignmentService`. The factory already imports `MissionRankingService` in `get_calendar_service()`. Add the import inline (it already exists in the file at line 85).

Add before the `return AssignmentService(...)`:

```python
    # Build mission ranking service for auto-refresh on assignment changes
    mission_ranking_service = MissionRankingService(
        MissionRepository(session),
        doctor_repo,
        CalendarRepository(session),
        CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
    )

    return AssignmentService(
        CalendarRepository(session),
        doctor_repo,
        AvailabilityRepository(session),
        audit=AuditService(AuditRepository(session)),
        triggers=triggers,
        mission_ranking_service=mission_ranking_service,
    )
```

- [ ] **Step 2: Wire into `get_generation_service()` factory**

In `get_generation_service()` (line 132-149), add `MissionRankingService` and pass it. Update the return block:

```python
    from backend.app.application.missions.ranking_service import MissionRankingService

    return GenerationService(
        CalendarRepository(session),
        DoctorRepository(session),
        AvailabilityRepository(session),
        MissionRepository(session),
        CatalogRepository(session),
        audit=AuditService(AuditRepository(session)),
        mission_ranking_service=MissionRankingService(
            MissionRepository(session),
            DoctorRepository(session),
            CalendarRepository(session),
            CatalogRepository(session),
            audit=AuditService(AuditRepository(session)),
        ),
    )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes/calendars.py
git commit -m "feat: wire MissionRankingService into AssignmentService and GenerationService factories"
```

---

### Task 7: Relax ranking visibility guard (any calendar status)

**Files:**
- Modify: `backend/app/api/routes/missions.py`

- [ ] **Step 1: Add `_latest_version_or_404()` helper**

Add after `_approved_version_or_409()` (after line 276):

```python
def _latest_version_or_404(
    session: Session,
    *,
    year: int,
    month: int,
) -> CalendarVersionModel:
    """Return the latest calendar version for the period regardless of status.

    Raises HTTP 404 if no calendar/version exists at all.
    """
    version = CalendarRepository(session).get_latest_version_by_period(year, month)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "calendar_not_found",
                "message": (
                    f"No hay calendario para {year}/{month:02d}. "
                    "Cree un calendario primero."
                ),
            },
        )
    return version
```

- [ ] **Step 2: Replace guard in `get_ranking` endpoint**

In `get_ranking()` (line 310-329), replace line 317:

```python
# Old:
    approved_version = _approved_version_or_409(session, year=year, month=month)

# New:
    version = _latest_version_or_404(session, year=year, month=month)
```

And update the rest of the method to use `version` instead of `approved_version`:

```python
    ranking = service.get_ranking(
        year=year,
        month=month,
        calendar_version_id=version.id,
    )
    if ranking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ranking_not_found",
                "message": f"No ranking found for calendar {year}/{month:02d}. Generate it first.",
            },
        )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes/missions.py
git commit -m "feat: allow ranking visibility in any calendar status (draft, partial, approved)"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run existing tests to verify no regressions**

```bash
cd backend && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -30
```

- [ ] **Step 2: Verify import chain**

```bash
cd backend && python -c "
from backend.app.infrastructure.repositories.calendars import CalendarRepository
from backend.app.application.doctors.service import DoctorService
from backend.app.application.calendars.assignment_service import AssignmentService
from backend.app.application.calendars.generation_service import GenerationService
from backend.app.application.calendars.service import CalendarService
print('All imports OK')
"
```

- [ ] **Step 3: Manual verification checklist**

- [ ] Crear calendario → verificar que `GET /rankings/{year}/{month}` devuelve ranking vacío (no 409)
- [ ] Asignar médico manualmente → esperar 5s → ranking se actualiza
- [ ] Reemplazar médico → esperar 5s → ranking se actualiza
- [ ] Quitar asignación → esperar 5s → ranking se actualiza
- [ ] Cambiar `availability_mode` de un médico → sus asignaciones en draft desaparecen
- [ ] Desactivar `service_active` de un médico → sus asignaciones en draft desaparecen
- [ ] Generación automática → ranking se genera inmediatamente
- [ ] Aprobar semana → ranking se genera (comportamiento existente preservado)

- [ ] **Step 4: Commit remaining changes and push**

```bash
git status
git push origin fix/auto-ranking-assignment-cleanup
```
