# Doctor Delete UX + User Edit & Soft Delete

**Date:** 2026-05-21
**Status:** approved

## Context

Two related improvements to admin panels:

1. **Doctor delete button** is currently buried inside `DoctorForm` (the edit modal), using the bland native `window.confirm()`. The calendar module already has a polished `ConfirmDialog` component with danger styling and "Esta acción no se puede deshacer" warning. The delete action should be at the same level as the edit action — in the profile modal, not inside the form.

2. **Users** have no edit capability and no delete. The `UsersView` table only has a "Resetear" button per row. Users need inline editing (name, role, active) and soft delete, following the same pattern as doctors and calendars.

## Design

### Part 1: Doctor Delete — Move to Profile Modal

**`frontend/src/features/doctors/DoctorList.tsx` — `DoctorProfileModal`**

- Add "Eliminar médico" button (icon + danger-ghost style) next to "Editar médico" in the "Acciones" section
- Add `showDeleteDialog` boolean state
- Add `deleteDoctor` mutation using `doctorsApi.delete(doctor.id)`
- On success: close profile modal, invalidate `["doctors"]` query, show success toast
- On error: show error toast
- Render `ConfirmDialog` with:
  - `title`: "Eliminar médico"
  - `message`: `¿Estás seguro de eliminar a ${doctor.name}?`
  - `confirmLabel`: "Sí, eliminar"
  - `variant`: "danger"
  - Already includes "Esta acción no se puede deshacer"

**`frontend/src/features/doctors/DoctorForm.tsx`**

- Remove delete button and `deleteDoctor` mutation (no longer needed here)

### Part 2: User Edit + Soft Delete

#### Backend

**Migration**: `ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE`

**`backend/app/infrastructure/db/models/user.py`** — `UserModel`:
- Add `deleted_at: Mapped[datetime | None]` column

**`backend/app/infrastructure/repositories/users.py`** — `UserRepository`:
- Add `_not_deleted()` helper: `(UserModel.deleted_at.is_(None),)`
- Filter `get_by_id`, `get_by_email`, `list_by_role` with `_not_deleted()`
- Add `soft_delete(user_id)` — sets `deleted_at=now`, `updated_at=now`
- Add `update(user_id, **fields)` — applies fields dict + `updated_at=now`

**`backend/app/application/accounts/service.py`** — `AccountService`:
- `soft_delete_user(user_id, actor_id)` — validate exists, call repo, audit
- `update_user(user_id, actor_id, name, role, active)` — validate, apply, audit
- Validation: only admins, only encargado targets (like existing methods)

**`backend/app/api/routes/admin_users.py`**:
- `DELETE /admin/users/{user_id}` → `service.soft_delete_user()`
- `PATCH /admin/users/{user_id}` → `service.update_user()` (body: name, role, active)

**`backend/app/application/audit/service.py`** — `AuditService`:
- `log_user_deleted(actor_id, user)` — action_type: "user_deleted"
- `log_user_updated(actor_id, user, before, after)` — action_type: "user_updated"

#### Frontend

**`frontend/src/api/admin.ts`**:
- `deleteUser(id)` → `DELETE /admin/users/${id}`
- `updateUser(id, payload)` → `PATCH /admin/users/${id}` with `{name, role, active}`

**`frontend/src/features/users/UsersView.tsx`**:
- Change actions column: ✏️ edit icon + 🗑 delete icon per row (replace "Resetear" column)
- **Inline edit**: clicking ✏️ expands the row with inline form fields:
  - Name (text input)
  - Role (select: encargado / admin)
  - Active (checkbox)
  - Buttons: Guardar, Cancelar, Resetear (moves here from column)
- **Delete**: clicking 🗑 opens `ConfirmDialog`:
  - `title`: "Eliminar usuario"
  - `message`: `¿Estás seguro de eliminar a ${user.name}?`
  - Uses same `ConfirmDialog` component

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/features/doctors/DoctorList.tsx` | Add delete to `DoctorProfileModal` |
| `frontend/src/features/doctors/DoctorForm.tsx` | Remove delete button + mutation |
| `migrations/versions/20260521_0030_add_users_deleted_at.py` | New migration |
| `backend/app/infrastructure/db/models/user.py` | Add `deleted_at` column |
| `backend/app/infrastructure/repositories/users.py` | Add `_not_deleted`, `soft_delete`, `update` |
| `backend/app/application/accounts/service.py` | Add `soft_delete_user`, `update_user` |
| `backend/app/api/routes/admin_users.py` | Add `DELETE` and `PATCH` endpoints |
| `backend/app/application/audit/service.py` | Add `log_user_deleted`, `log_user_updated` |
| `frontend/src/api/admin.ts` | Add `deleteUser`, `updateUser` |
| `frontend/src/features/users/UsersView.tsx` | Inline edit + delete per row |

## Verification

1. **Backend tests**: Run `pytest backend/tests/audit/ backend/tests/doctors/` — all existing tests pass, new tests for user soft delete + update
2. **Migration**: Run `alembic upgrade head` — no errors, column exists in `users` table
3. **Doctor delete**: Open doctor list → click row → profile modal shows "Eliminar médico" next to "Editar médico" → click → ConfirmDialog opens → confirm → doctor disappears from list
4. **User edit**: Open Users tab → click ✏️ on a row → inline form expands → change name/role/active → save → row updates
5. **User delete**: Click 🗑 → ConfirmDialog opens → confirm → user disappears from list
6. **Soft delete verification**: Deleted users/doctors still exist in DB with `deleted_at` set but don't appear in list queries
