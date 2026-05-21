# Doctor Delete UX + User Edit & Soft Delete — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move doctor delete button to the profile modal using ConfirmDialog, and add inline editing + soft delete for users.

**Architecture:** Follows existing patterns — `ConfirmDialog` for deletions (same as calendars), soft delete via `_not_deleted()` repo filter (same as doctors), audit events per action. Backend: route → service → repo → flush → route commit. Frontend: React Query mutations + ConfirmDialog + inline row expansion.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 sync, React + TypeScript, React Query, ConfirmDialog component

---

### Task 1: Remove delete button from DoctorForm

**Files:**
- Modify: `frontend/src/features/doctors/DoctorForm.tsx`

- [ ] **Step 1: Remove delete mutation and button from DoctorForm**

Remove these sections from `DoctorForm.tsx`:

1. The `deleteDoctor` mutation (lines currently around 93-99):
```tsx
  const deleteDoctor = useMutation({
    mutationFn: () => doctorsApi.delete(doctor!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doctors"] });
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });
```

2. The delete button in the footer (currently around lines 344-357):
```tsx
            {isEdit && (
              <button
                type="button"
                className="btn-ghost btn-danger"
                disabled={deleteDoctor.isPending}
                onClick={() => {
                  if (window.confirm("¿Eliminar este médico permanentemente?")) {
                    deleteDoctor.mutate();
                  }
                }}
              >
                {deleteDoctor.isPending ? "Eliminando…" : "Eliminar médico"}
              </button>
            )}
```

- [ ] **Step 2: Verify the form renders without errors**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: no build errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/doctors/DoctorForm.tsx
git commit -m "refactor: remove delete button from DoctorForm"
```

---

### Task 2: Add delete to DoctorProfileModal with ConfirmDialog

**Files:**
- Modify: `frontend/src/features/doctors/DoctorList.tsx`

- [ ] **Step 1: Add imports**

Add at the top of `DoctorList.tsx`:
```tsx
import { ConfirmDialog } from "../../components/ConfirmDialog";
```

Also add `Trash2` to the lucide-react import (check if already imported, if not add it):
```tsx
import { Ban, CheckCircle2, Edit, PlusCircle, RefreshCw, Search, Trash2, Users, X, XCircle } from "lucide-react";
```

- [ ] **Step 2: Add delete state and mutation inside DoctorList**

Add these inside the `DoctorList` function, before the `return` statement:

```tsx
  const [deleteTarget, setDeleteTarget] = useState<DoctorRead | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => doctorsApi.delete(id),
    onSuccess: () => {
      setDeleteTarget(null);
      setSelectedDoctor(null);
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (err: Error) => setActionError(err.message),
  });
```

- [ ] **Step 3: Pass delete props to DoctorProfileModal**

Update the `DoctorProfileModal` JSX call to include the new props. Add before the `onClose` prop:
```tsx
          onDelete={() => setDeleteTarget(selectedDoctor)}
```

- [ ] **Step 4: Add onDelete prop to DoctorProfileModal interface**

Add to `DoctorProfileModalProps`:
```tsx
  onDelete: () => void;
```

- [ ] **Step 5: Destructure onDelete in DoctorProfileModal**

Add `onDelete` to the destructuring:
```tsx
function DoctorProfileModal({
  doctor,
  ...
  onReactivate,
  onDelete,
}: DoctorProfileModalProps) {
```

- [ ] **Step 6: Add delete button in the Acciones section**

After the "Editar médico" button in the profile-actions div, add:
```tsx
            <button className="btn-ghost btn-danger" onClick={onDelete}>
              <Trash2 size={16} />
              Eliminar médico
            </button>
```

- [ ] **Step 7: Add ConfirmDialog render**

Add right before the closing `</>` of the `selectedDoctor && (...)` block (before the final `)}`):
```tsx
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Eliminar médico"
        message={`¿Estás seguro de eliminar a ${deleteTarget?.name}?`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
```

- [ ] **Step 8: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: no build errors

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/doctors/DoctorList.tsx
git commit -m "refactor: move doctor delete to profile modal with ConfirmDialog"
```

---

### Task 3: Add deleted_at to UserModel + migration

**Files:**
- Create: `migrations/versions/20260521_0030_add_users_deleted_at.py`
- Modify: `backend/app/infrastructure/db/models/user.py`

- [ ] **Step 1: Add deleted_at to UserModel**

In `user.py`, after the `deactivated_by` line (line 31), add:
```python
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

- [ ] **Step 2: Create migration**

Run: `.venv/bin/alembic revision -m "Add deleted_at to users"` — creates a revision file.

Then replace the content of the new migration file with:
```python
"""Add deleted_at to users

Revision ID: <auto-generated>
Revises: 20260521_0029
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "<use-generated>"
down_revision: str | None = "20260521_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE users ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;")
```

**Important:** Replace `<use-generated>` with the actual revision ID from the file and ensure `down_revision` is `"20260521_0029"`.

- [ ] **Step 3: Apply migration locally**

Run: `.venv/bin/alembic upgrade head`
Expected: `INFO [alembic.runtime.migration] Running upgrade 20260521_0029 -> 20260521_0030, Add deleted_at to users`

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `.venv/bin/python -m pytest backend/tests/accounts/ -v`
Expected: all existing tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/infrastructure/db/models/user.py migrations/versions/20260521_0030_add_users_deleted_at.py
git commit -m "feat: add deleted_at column to users table"
```

---

### Task 4: Add soft_delete + update to UserRepository with _not_deleted() filter

**Files:**
- Modify: `backend/app/infrastructure/repositories/users.py`

- [ ] **Step 1: Rewrite UserRepository with soft delete support**

Replace the entire file content with:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.user import PasswordHistoryModel, UserModel

PASSWORD_HISTORY_DEPTH = 5


def _not_deleted() -> tuple:
    return (UserModel.deleted_at.is_(None),)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, user: UserModel) -> UserModel:
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_id(self, user_id: str) -> UserModel | None:
        stmt = select(UserModel).where(
            UserModel.id == user_id, *_not_deleted()
        )
        return self.session.scalars(stmt).first()

    def get_by_email(self, email: str) -> UserModel | None:
        normalized_email = email.strip().lower()
        statement = select(UserModel).where(
            UserModel.email == normalized_email, *_not_deleted()
        )
        return self.session.scalar(statement)

    def list_by_role(self, role: str) -> list[UserModel]:
        statement = (
            select(UserModel)
            .where(UserModel.role == role, *_not_deleted())
            .order_by(UserModel.name)
        )
        return list(self.session.scalars(statement))

    def list_all(self) -> list[UserModel]:
        statement = (
            select(UserModel)
            .where(*_not_deleted())
            .order_by(UserModel.name)
        )
        return list(self.session.scalars(statement))

    def soft_delete(self, user_id: str) -> None:
        now = datetime.now(UTC)
        self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(deleted_at=now, updated_at=now)
        )
        self.session.flush()

    def update(self, user_id: str, **fields: object) -> None:
        now = datetime.now(UTC)
        values = {**fields, "updated_at": now}
        self.session.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(**values)
        )
        self.session.flush()

    # --- Password History ---

    def list_recent_password_hashes(self, user_id: str) -> list[str]:
        """Return the last PASSWORD_HISTORY_DEPTH password hashes for a user."""
        stmt = (
            select(PasswordHistoryModel.password_hash)
            .where(PasswordHistoryModel.user_id == user_id)
            .order_by(PasswordHistoryModel.created_at.desc())
            .limit(PASSWORD_HISTORY_DEPTH)
        )
        return list(self.session.scalars(stmt))

    def add_password_history(self, user_id: str, password_hash: str) -> None:
        entry = PasswordHistoryModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            password_hash=password_hash,
            created_at=datetime.now(UTC),
        )
        self.session.add(entry)
```

- [ ] **Step 2: Run account tests to verify**

Run: `.venv/bin/python -m pytest backend/tests/accounts/ -v`
Expected: all existing tests pass with `_not_deleted()` filter

- [ ] **Step 3: Commit**

```bash
git add backend/app/infrastructure/repositories/users.py
git commit -m "feat: add soft_delete, update, and _not_deleted filter to UserRepository"
```

---

### Task 5: Add log_user_deleted + log_user_updated to AuditService

**Files:**
- Modify: `backend/app/application/audit/service.py`

- [ ] **Step 1: Add user audit methods**

In `audit/service.py`, after the `log_login_failed` method (after line 184), add:

```python
    def log_user_updated(self, *, actor_id: str, user, changed_fields: dict) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="user_updated",
            entity_type="user",
            entity_id=user.id,
            after=changed_fields,
        )

    def log_user_deleted(self, *, actor_id: str, user) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="user_deleted",
            entity_type="user",
            entity_id=user.id,
            before={"name": user.name, "email": user.email, "role": user.role},
        )
```

- [ ] **Step 2: Run audit tests**

Run: `.venv/bin/python -m pytest backend/tests/audit/ -v`
Expected: all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/application/audit/service.py
git commit -m "feat: add log_user_updated and log_user_deleted audit events"
```

---

### Task 6: Add soft_delete_user + update_user to AccountService

**Files:**
- Modify: `backend/app/application/accounts/service.py`

- [ ] **Step 1: Add soft_delete_user method**

Add after the `_require_admin` method (at end of class):

```python
    def soft_delete_user(self, *, actor: UserModel, user_id: str) -> None:
        self._require_admin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role not in (UserRole.ENCARGADO.value, UserRole.ADMIN.value):
            raise PermissionDeniedError
        self.users.soft_delete(user_id)
        if self.audit is not None:
            self.audit.log_user_deleted(actor_id=actor.id, user=user)

    def update_user(
        self,
        *,
        actor: UserModel,
        user_id: str,
        name: str | None = None,
        role: str | None = None,
        active: bool | None = None,
    ) -> UserModel:
        self._require_admin(actor)
        user = self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError
        if user.role not in (UserRole.ENCARGADO.value, UserRole.ADMIN.value):
            raise PermissionDeniedError

        changed: dict[str, object] = {}
        if name is not None:
            user.name = name.strip()
            changed["name"] = user.name
        if role is not None:
            user.role = role
            changed["role"] = role
        if active is not None:
            user.active = active
            changed["active"] = active

        if not changed:
            return user

        self.users.update(user_id, **changed)
        if self.audit is not None:
            self.audit.log_user_updated(actor_id=actor.id, user=user, changed_fields=changed)
        return user
```

- [ ] **Step 2: Run tests to verify no regressions**

Run: `.venv/bin/python -m pytest backend/tests/accounts/ -v`
Expected: all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add backend/app/application/accounts/service.py
git commit -m "feat: add soft_delete_user and update_user to AccountService"
```

---

### Task 7: Add DELETE + PATCH routes to admin_users.py

**Files:**
- Create: `backend/app/schemas/accounts.py` (add UpdateUserRequest schema)
- Modify: `backend/app/api/routes/admin_users.py`

- [ ] **Step 1: Add UpdateUserRequest schema**

In `backend/app/schemas/accounts.py`, after the `ResetPasswordRequest` class, add:

```python
class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, pattern=r"^(admin|encargado)$")
    active: bool | None = None
```

- [ ] **Step 2: Add DELETE and PATCH endpoints**

In `admin_users.py`, add import for `UpdateUserRequest`:
```python
from backend.app.schemas.accounts import (
    CreateEncargadoRequest,
    ResetPasswordRequest,
    TemporaryPasswordResponse,
    UpdateUserRequest,
    UserRead,
)
```

Then add at the end of the file (before any module-level code):

```python
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    try:
        service.soft_delete_user(actor=admin, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User not found"},
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "Cannot delete this user"},
        ) from exc
    session.commit()


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    admin: Annotated[UserModel, Depends(require_admin)],
    service: Annotated[AccountService, Depends(get_account_service)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRead:
    try:
        updated = service.update_user(
            actor=admin,
            user_id=user_id,
            name=payload.name,
            role=payload.role,
            active=payload.active,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User not found"},
        ) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "permission_denied", "message": "Cannot update this user"},
        ) from exc
    session.commit()
    return UserRead.model_validate(updated)
```

- [ ] **Step 3: Run admin users tests**

Run: `.venv/bin/python -m pytest backend/tests/accounts/test_admin_users_routes.py -v`
Expected: all existing tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/admin_users.py backend/app/schemas/accounts.py
git commit -m "feat: add DELETE and PATCH endpoints for users"
```

---

### Task 8: Write backend tests for user soft delete and update

**Files:**
- Modify: `backend/tests/accounts/test_admin_users_routes.py`
- Modify: `backend/tests/accounts/test_account_service.py`

- [ ] **Step 1: Add route tests for DELETE and PATCH users**

Add to `test_admin_users_routes.py`:

```python
def test_delete_user_returns_204(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.delete(f"/api/admin/users/{user.id}")
    assert response.status_code == 204

    # Verify user is hidden from list
    list_resp = client.get("/api/admin/users")
    assert list_resp.status_code == 200
    user_ids = [u["id"] for u in list_resp.json()]
    assert user.id not in user_ids


def test_delete_nonexistent_user_returns_404(client):
    response = client.delete("/api/admin/users/nonexistent-uuid")
    assert response.status_code == 404


def test_update_user_name_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"name": "Nuevo Nombre"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Nuevo Nombre"


def test_update_user_role_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_update_user_active_returns_200(client, session):
    user = _create_user(session, role="encargado")
    session.commit()

    response = client.patch(
        f"/api/admin/users/{user.id}",
        json={"active": False},
    )
    assert response.status_code == 200
    assert response.json()["active"] is False


def test_update_nonexistent_user_returns_404(client):
    response = client.patch(
        "/api/admin/users/nonexistent-uuid",
        json={"name": "Ghost"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Add service test for soft_delete_user**

Add to `test_account_service.py`:

```python
from backend.app.application.accounts.errors import UserNotFoundError


def test_soft_delete_user_hides_from_queries(db_session) -> None:
    from backend.app.infrastructure.repositories.users import UserRepository

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
        name="ToDelete",
        email="todelete@example.local",
        temporary_password="TempEnc123!",
    ).user
    db_session.commit()

    service.soft_delete_user(actor=admin, user_id=encargado.id)
    db_session.commit()

    repo = UserRepository(db_session)
    assert repo.get_by_id(encargado.id) is None
    users = repo.list_by_role("encargado")
    assert encargado.id not in [u.id for u in users]


def test_soft_delete_nonexistent_user_raises(db_session) -> None:
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
    db_session.commit()

    with pytest.raises(UserNotFoundError):
        service.soft_delete_user(actor=admin, user_id="nonexistent")


def test_update_user_changes_fields(db_session) -> None:
    from backend.app.infrastructure.repositories.users import UserRepository

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
        name="Original",
        email="original@example.local",
        temporary_password="TempEnc123!",
    ).user
    db_session.commit()

    updated = service.update_user(
        actor=admin,
        user_id=encargado.id,
        name="Updated Name",
        role="admin",
        active=False,
    )

    assert updated.name == "Updated Name"
    assert updated.role == "admin"
    assert updated.active is False


def test_update_nonexistent_user_raises(db_session) -> None:
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
    db_session.commit()

    with pytest.raises(UserNotFoundError):
        service.update_user(actor=admin, user_id="nonexistent", name="Ghost")
```

- [ ] **Step 3: Run all new tests**

Run: `.venv/bin/python -m pytest backend/tests/accounts/test_admin_users_routes.py backend/tests/accounts/test_account_service.py -v`
Expected: all new and existing tests pass

- [ ] **Step 4: Commit**

```bash
git add backend/tests/accounts/test_admin_users_routes.py backend/tests/accounts/test_account_service.py
git commit -m "test: add tests for user soft delete and update"
```

---

### Task 9: Add deleteUser + updateUser to admin API client

**Files:**
- Modify: `frontend/src/api/admin.ts`

- [ ] **Step 1: Add deleteUser and updateUser methods**

Add to the `adminApi` object in `admin.ts`, before the closing `};`:

```ts
  deleteUser(id: string) {
    return apiFetch<void>(`/admin/users/${id}`, { method: "DELETE" });
  },

  updateUser(id: string, payload: { name?: string; role?: string; active?: boolean }) {
    return apiFetch<UserRead>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: no build errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/admin.ts
git commit -m "feat: add deleteUser and updateUser to admin API client"
```

---

### Task 10: Add inline edit + delete to UsersView

**Files:**
- Modify: `frontend/src/features/users/UsersView.tsx`

- [ ] **Step 1: Rewrite UsersView with inline edit + delete**

Replace the entire file with:

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserPlus, KeyRound, Pencil, Trash2, Check, X } from "lucide-react";
import { useToast } from "../../components/Toast";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { adminApi, UserRead } from "../../api/admin";

const ROLES = ["encargado", "admin"] as const;

export function UsersView() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editRole, setEditRole] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<UserRead | null>(null);

  const { data: users, isLoading } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => adminApi.listUsers("encargado"),
  });

  const createMutation = useMutation({
    mutationFn: () => adminApi.createEncargado(newName, newEmail),
    onSuccess: (res) => {
      adminApi.inviteUser(res.user.id).catch(() => {});
      addToast("success", `Usuario creado. Se ha enviado una invitación a ${newEmail}.`);
      setShowCreate(false);
      setNewName("");
      setNewEmail("");
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al crear usuario."),
  });

  const resetMutation = useMutation({
    mutationFn: (userId: string) => adminApi.sendReset(userId),
    onSuccess: () => addToast("success", "Correo de restablecimiento enviado."),
    onError: () => addToast("error", "Error al enviar correo de restablecimiento."),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { name?: string; role?: string; active?: boolean } }) =>
      adminApi.updateUser(id, payload),
    onSuccess: () => {
      addToast("success", "Usuario actualizado.");
      setEditingId(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al actualizar usuario."),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => adminApi.deleteUser(id),
    onSuccess: () => {
      addToast("success", "Usuario eliminado.");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => addToast("error", "Error al eliminar usuario."),
  });

  function startEditing(user: UserRead) {
    setEditingId(user.id);
    setEditName(user.name);
    setEditRole(user.role);
    setEditActive(user.active);
  }

  function cancelEditing() {
    setEditingId(null);
  }

  function saveEditing(userId: string) {
    updateMutation.mutate({
      id: userId,
      payload: { name: editName, role: editRole, active: editActive },
    });
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <ShieldCheck size={20} />
          <h2>Usuarios</h2>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <UserPlus size={15} />
          {showCreate ? "Cancelar" : "Nuevo Usuario"}
        </button>
      </div>

      {showCreate && (
        <div style={{ background: "#f9fafb", padding: "16px", borderRadius: "8px", marginBottom: "20px" }}>
          <h4 style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>Crear Encargado</h4>
          <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label>Nombre <input type="text" value={newName} onChange={e => setNewName(e.target.value)} /></label>
            <label>Email <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)} /></label>
            <button className="btn-primary" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creando…" : "Crear"}
            </button>
          </div>
        </div>
      )}

      {isLoading && <p className="loading-text">Cargando usuarios…</p>}

      {users && (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr><th>Nombre</th><th>Email</th><th>Rol</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {users.map(u => (
                editingId === u.id ? (
                  <tr key={u.id} className="edit-row">
                    <td>
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      />
                    </td>
                    <td>{u.email}</td>
                    <td>
                      <select value={editRole} onChange={e => setEditRole(e.target.value)}>
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </td>
                    <td>
                      <label className="toggle-label" style={{ margin: 0 }}>
                        <input
                          type="checkbox"
                          checked={editActive}
                          onChange={e => setEditActive(e.target.checked)}
                        />
                        {editActive ? "Activo" : "Inactivo"}
                      </label>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-primary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => saveEditing(u.id)}
                          disabled={updateMutation.isPending}
                        >
                          <Check size={14} /> Guardar
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={cancelEditing}
                        >
                          <X size={14} /> Cancelar
                        </button>
                        <button
                          className="btn-ghost"
                          style={{ padding: "4px 10px", fontSize: "0.8rem" }}
                          onClick={() => resetMutation.mutate(u.id)}
                        >
                          <KeyRound size={14} /> Resetear
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                    <td>
                      {!u.active ? "No" : u.must_change_password ? "Pendiente" : "Activo"}
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: "6px" }}>
                        <button
                          className="btn-ghost"
                          style={{ padding: "3px 8px" }}
                          onClick={() => startEditing(u)}
                          title="Editar usuario"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="btn-ghost btn-danger"
                          style={{ padding: "3px 8px" }}
                          onClick={() => setDeleteTarget(u)}
                          title="Eliminar usuario"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Eliminar usuario"
        message={`¿Estás seguro de eliminar a ${deleteTarget?.name}?`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: no build errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/users/UsersView.tsx
git commit -m "feat: add inline edit and delete to UsersView"
```

---

### Task 11: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `.venv/bin/python -m pytest backend/tests/accounts/ backend/tests/audit/ backend/tests/doctors/ -v`
Expected: all tests pass (existing + new)

- [ ] **Step 2: Verify migration is clean**

Run: `.venv/bin/alembic upgrade head`
Expected: no errors

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: no errors

- [ ] **Step 4: Final commit (if needed)**

```bash
git add -A
git commit -m "chore: final verification after doctor delete UX and user management"
```
