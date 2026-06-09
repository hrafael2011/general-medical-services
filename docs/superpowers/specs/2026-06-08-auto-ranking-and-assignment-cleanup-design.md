# Design: Auto-Ranking Generation & Assignment Cleanup on Doctor Availability Change

## Context

Two bugs identified in staging:

1. **Doctor days persist after availability mode change.** When a doctor's `availability_mode` is changed (e.g., from "weekly_fixed" to "monthly_variable") or their `service_active` is set to `False`, existing calendar assignments are not cleaned up. The old assignments remain in draft/partial calendars.

2. **Mission ranking is not generated until weeks are approved.** `MissionRankingService.generate_ranking()` is only called from `approve_week()` and `approve_calendar()`. Users working in draft mode (assigning doctors manually without approving weeks) never see a ranking. Additionally, `GET /rankings/{year}/{month}` requires an approved/partial calendar version — draft-only calendars are rejected with HTTP 409.

## Goal

- **Bug #1:** Automatically remove all calendar assignments for a doctor in draft/partial calendars when their `availability_mode` changes or `service_active` is disabled. Notify the frontend so the user can choose to auto-fill or manually fill the resulting gaps.
- **Bug #2:** Generate mission ranking automatically on every assignment change (with debounce for manual mode, immediate for batch generation) and on calendar creation. Make the ranking visible in any calendar status (draft, partial, approved).

## Approach

**Enfoque 1 — Minimal fixes in existing services.** Chosen for low risk, respect for current architecture, and minimal new abstractions.

---

## Design — Bug #1: Assignment Cleanup

### Files modified
- `backend/app/application/doctors/service.py` — `update_doctor()`
- `backend/app/infrastructure/repositories/calendars.py` — new query method

### Changes

**1. New method on `CalendarRepository`**

```python
def delete_assignments_for_doctor_in_active_calendars(self, doctor_id: str) -> int:
    """Delete all assignments for a doctor in draft/partial calendars. Returns count."""
    from sqlalchemy import delete as sql_delete
    stmt = (
        sql_delete(CalendarAssignmentModel)
        .where(CalendarAssignmentModel.doctor_id == doctor_id)
        .where(
            CalendarAssignmentModel.calendar_version_id.in_(
                select(CalendarVersionModel.id)
                .join(CalendarModel)
                .where(CalendarModel.status.in_(["draft", "partial"]))
                .where(CalendarModel.deleted_at.is_(None))
            )
        )
    )
    result = self.session.execute(stmt)
    return result.rowcount
```

**2. New helper on `DoctorService`**

```python
def _cleanup_calendar_assignments(self, doctor_id: str) -> int:
    from backend.app.infrastructure.repositories.calendars import CalendarRepository
    repo = CalendarRepository(self.doctors.session)
    return repo.delete_assignments_for_doctor_in_active_calendars(doctor_id)
```

**3. Two call sites in `update_doctor()`**

- After `availability_mode` change (line ~264): if the mode actually changed, call `_cleanup_calendar_assignments(doctor_id)`.
- After `service_active = False` (line ~270): existing code already deletes availability records and allowed areas; add cleanup of calendar assignments.

**4. Frontend contract**

The `update_doctor` response already includes the updated doctor. The frontend will additionally receive the count of removed assignments. If count > 0, the UI prompts:

> "Se eliminaron X asignaciones del Dr. Y. ¿Desea rellenar los huecos automáticamente o manualmente?"

- **Auto-fill:** call existing `POST /calendars/{id}/generate` for the affected slots via `UnresolvedGapModel`.
- **Manual:** the user fills slots from the grid as usual.

No new backend endpoints are needed; the existing generation service handles auto-fill.

---

## Design — Bug #2: Auto-Ranking

### Files modified
- `backend/app/application/calendars/service.py` — `create_calendar()` adds immediate ranking generation
- `backend/app/application/calendars/assignment_service.py` — `assign_doctor()`, `replace_assignment()`, `remove_assignment()` schedule debounced ranking refresh
- `backend/app/application/calendars/generation_service.py` — batch generation ends with immediate ranking generation
- `backend/app/api/routes/calendars.py` — dependency factories wire `MissionRankingService` into `AssignmentService` and `GenerationService`
- `backend/app/api/routes/missions.py` — `_approved_version_or_409` relaxed to accept any version (draft/partial/approved); `get_ranking` returns ranking for any status
- `backend/app/infrastructure/repositories/calendars.py` — `get_approved_version_by_period` extended or replaced with `get_latest_version_by_period`

### Ranking generation triggers

| Trigger | Debounce? | Where |
|---|---|---|
| `create_calendar()` | No — immediate | `CalendarService.create_calendar()` |
| `assign_doctor()` | Yes — 5s | `AssignmentService._schedule_ranking_refresh()` |
| `replace_assignment()` | Yes — 5s | `AssignmentService._schedule_ranking_refresh()` |
| `remove_assignment()` | Yes — 5s | `AssignmentService._schedule_ranking_refresh()` |
| Generation batch | No — immediate | `GenerationService.generate_assignments()` |

### Debounce mechanism

A `threading.Timer` dictionary keyed by `(year, month)` stored on `AssignmentService`. Each assignment change cancels the previous timer and starts a new 5-second one. When the timer fires, it calls `MissionRankingService.generate_ranking()`.

```python
# In AssignmentService.__init__
self._ranking_timers: dict[str, threading.Timer] = {}

def _schedule_ranking_refresh(self, calendar_version_id, year, month, actor_id):
    key = f"{year}-{month}"
    if key in self._ranking_timers:
        self._ranking_timers[key].cancel()
    timer = threading.Timer(5.0, self._do_refresh_ranking, args=[...])
    timer.daemon = True
    self._ranking_timers[key] = timer
    timer.start()
```

**Why threading.Timer?** The `AssignmentService` is instantiated per-request in FastAPI. The timer is lightweight and daemon=true ensures no thread leak. If the process restarts before the timer fires, the ranking regenerates on the next trigger anyway. Simpler than adding APScheduler tasks or a message queue for this scope.

### Dependency injection

`AssignmentService` and `GenerationService` gain an optional `mission_ranking_service` parameter:

```python
class AssignmentService:
    def __init__(self, ..., mission_ranking_service=None):
        self._mission_ranking_service = mission_ranking_service
```

Wired in `get_assignment_service()` factory in `calendars.py` routes. Existing callers that don't pass the parameter are unaffected (it's optional).

### Relax `get_ranking` visibility

**Current:** `_approved_version_or_409()` looks for calendar `status IN ["approved", "partial"]` and version `status IN ["approved", "draft"]` → 409 if not found.

**New:** `_latest_version_or_404()` returns the latest version regardless of status (draft/partial/approved). If no version exists at all → 404.

```python
def _latest_version_or_404(session, year, month):
    version = CalendarRepository(session).get_latest_version_by_period(year, month)
    if version is None:
        raise HTTPException(404, ...)
    return version
```

New repository method:

```python
def get_latest_version_by_period(self, year, month) -> CalendarVersionModel | None:
    return self.session.scalar(
        select(CalendarVersionModel)
        .join(CalendarModel)
        .where(CalendarModel.year == year, CalendarModel.month == month)
        .where(CalendarModel.deleted_at.is_(None))
        .where(CalendarVersionModel.deleted_at.is_(None))
        .order_by(CalendarVersionModel.version_number.desc())
        .limit(1)
    )
```

### Edge cases

| Case | Behavior |
|---|---|
| No assignments exist → ranking is empty | `generate_ranking()` produces zero entries — returns normally |
| Calendar deleted | Soft-deleted calendars excluded via `deleted_at.is_(None)` |
| Concurrent timers for different months | Separate keys `(year, month)` — independent debounce |
| Service instance dies before timer fires | No-op; next request creates fresh timer |
| `mission_ranking_service` is None | All debounce code paths guard with `if self._mission_ranking_service is not None` |

---

## Files Summary

| File | Change |
|---|---|
| `backend/app/application/doctors/service.py` | Add `_cleanup_calendar_assignments()`, call on availability_mode change and service_active=False |
| `backend/app/infrastructure/repositories/calendars.py` | Add `delete_assignments_for_doctor_in_active_calendars()`, add `get_latest_version_by_period()` |
| `backend/app/application/calendars/service.py` | Call `generate_ranking()` in `create_calendar()` |
| `backend/app/application/calendars/assignment_service.py` | Add `mission_ranking_service` param, debounce timer, call in assign/replace/remove |
| `backend/app/application/calendars/generation_service.py` | Add `mission_ranking_service` param, call after batch generation |
| `backend/app/api/routes/calendars.py` | Wire `MissionRankingService` into factory dependencies |
| `backend/app/api/routes/missions.py` | Replace `_approved_version_or_409` with `_latest_version_or_404` |

## Verification

1. **Unit tests:** Add tests for `_cleanup_calendar_assignments()` — verify assignments removed only from draft/partial, not approved
2. **Unit tests:** Add tests for debounce timer — verify timer cancel/reset, verify `generate_ranking()` called after 5s
3. **Integration test:** Create calendar → assign doctor → wait 5s → assert ranking exists
4. **Integration test:** Change doctor availability_mode → assert assignments removed from draft calendar
5. **Manual:** Create calendar, assign doctors, check ranking visible in draft state
6. **Manual:** Change doctor mode, verify old assignments removed and gaps appear
