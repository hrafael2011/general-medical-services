# Tasks — Generación de vínculos de Telegram por rol

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-27-gestion-vinculos-telegram.md](2026-10-27-gestion-vinculos-telegram.md)

**Goal:** que la pantalla de Telegram genere el enlace correcto para cada persona según su rol, sin
listas vacías y sin los campos del bot asistente.

**Architecture:** la regla vive en el backend (`create_link_token`); la pantalla solo refleja esa
regla y deja de administrar el vínculo del asistente, que no entrega avisos.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, pytest, React + TypeScript, vitest.

**Estado:** ⬜ Propuesto. No implementado.

---

## Fase 1 — Política en el backend

### Task 1.1 — Aplicar la regla de quién puede generar enlaces

**Files:**
- Modify: `backend/app/api/routes/telegram.py`
- Test: `backend/tests/telegram/test_link_token_policy.py`

- [ ] **Step 1: Escribir los tests que fallan**

```python
"""Quién puede generar un enlace de vínculo al bot de avisos.

El listado de admins es solo-superadmin, pero el endpoint aceptaba cualquier
`user_id`: la política existía en la pantalla y no en la API.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture(autouse=True)
def _alerts_bot(monkeypatch):
    """Sin username del bot de avisos el endpoint responde 503 en vez de crear el token."""
    monkeypatch.setattr(
        settings, "telegram_notification_bot_username", "TurnosMedicosNotificaciones_bot"
    )


def _user(session, *, role: str, is_superadmin: bool = False) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name=f"{role} {uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=[],
        is_superadmin=is_superadmin,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def _client(session, actor: UserModel) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app)


def test_an_admin_can_generate_a_link_for_an_encargado(session):
    admin = _user(session, role="admin")
    encargado = _user(session, role="encargado")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": encargado.id}
    )

    assert response.status_code == 201
    assert response.json()["deep_link_url"].startswith("https://t.me/")


def test_an_admin_can_generate_their_own_link(session):
    admin = _user(session, role="admin")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": admin.id}
    )

    assert response.status_code == 201


def test_an_admin_cannot_generate_a_link_for_another_admin(session):
    admin = _user(session, role="admin")
    other = _user(session, role="admin")

    response = _client(session, admin).post(
        "/api/telegram/link-tokens", json={"user_id": other.id}
    )

    assert response.status_code == 403


def test_a_superadmin_can_generate_a_link_for_another_admin(session):
    superadmin = _user(session, role="admin", is_superadmin=True)
    other = _user(session, role="admin")

    response = _client(session, superadmin).post(
        "/api/telegram/link-tokens", json={"user_id": other.id}
    )

    assert response.status_code == 201
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_link_token_policy.py -q
```

Expected: `test_an_admin_cannot_generate_a_link_for_another_admin` falla (hoy devuelve 201).

- [ ] **Step 3: Añadir la comprobación**

En `backend/app/api/routes/telegram.py`, junto a `_get_linkable_user`:

```python
def _ensure_can_link(admin: UserModel, target: UserModel) -> None:
    """Un admin solo reparte enlaces entre encargados y para sí mismo.

    El listado de admins ya era solo-superadmin; sin esta comprobación la regla
    vivía únicamente en la pantalla y el endpoint aceptaba cualquier `user_id`.
    """
    if admin.is_superadmin:
        return
    if target.role == "admin" and target.id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo un superadministrador puede generar enlaces para otros "
                "administradores."
            ),
        )
```

Y en `create_link_token`, sustituir la primera línea del cuerpo:

```python
    target = _get_linkable_user(session, payload.user_id)
    _ensure_can_link(admin, target)
```

- [ ] **Step 4: Ejecutar y ver que pasa**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_link_token_policy.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/routes/telegram.py backend/tests/telegram/test_link_token_policy.py
git commit -m "feat(telegram): only superadmins can generate links for other admins"
```

---

## Fase 2 — Pantalla

### Task 2.1 — Lista de destinatarios correcta

**Files:**
- Modify: `frontend/src/features/telegram/TelegramLinks.tsx`
- Modify: `frontend/src/api/auth.ts`
- Test: `frontend/src/features/telegram/TelegramLinks.test.tsx`

- [ ] **Step 1: Añadir `telegram_chat_id` al tipo del usuario autenticado**

En `frontend/src/api/auth.ts`, dentro de `UserRead`:

```ts
  telegram_chat_id: string | null;
```

`/auth/login` ya devuelve el campo (usa el mismo `UserRead` del backend); solo faltaba en el tipo.

- [ ] **Step 2: Escribir los tests que fallan**

En `TelegramLinks.test.tsx`, añadir la variable y el mock antes de los `describe`:

```tsx
let currentUserMock: { id: string; name: string; role: string; is_superadmin: boolean;
  permissions: string[]; email: string; active: boolean; must_change_password: boolean;
  telegram_chat_id: string | null } | null = null;

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ currentUser: currentUserMock }),
}));
```

Y estos dos tests dentro de `describe("TelegramLinks", ...)`:

```tsx
  it("muestra a los encargados aunque la lista de admins falle", async () => {
    const { adminApi } = await import("../../api/admin");
    const self = { ...ADMIN_LINKED, id: "u-self", name: "Yo Admin", telegram_chat_id: null };
    currentUserMock = self;
    vi.mocked(adminApi.listUsers).mockImplementation(async (role?: string) => {
      if (role === "admin") throw new Error("403");
      return [ENCARGADO_UNLINKED];
    });

    renderComponent();

    expect(await screen.findByText("Encargado Sin Telegram")).toBeInTheDocument();
  });

  it("incluye al propio usuario en la lista de destinatarios", async () => {
    const { adminApi } = await import("../../api/admin");
    const self = { ...ADMIN_LINKED, id: "u-self", name: "Yo Admin", telegram_chat_id: null };
    currentUserMock = self;
    vi.mocked(adminApi.listUsers).mockResolvedValue([]);

    renderComponent();

    const select = await screen.findByLabelText(/usuario del sistema/i);
    expect(within(select).getByText(/Yo Admin/)).toBeInTheDocument();
  });
```

- [ ] **Step 3: Ejecutar y ver que fallan**

```bash
npm --prefix frontend run test -- --run TelegramLinks
```

Expected: los dos fallan (hoy la lista queda vacía y no existe “Yo Admin”).

- [ ] **Step 4: Cambiar la consulta**

En `TelegramLinks.tsx`, añadir el import y leer el usuario:

```tsx
import { useAuth } from "../../context/AuthContext";
```

```tsx
  const { currentUser } = useAuth();
  const isSuperadmin = currentUser?.is_superadmin ?? false;
```

Y sustituir el `useQuery` de usuarios por:

```tsx
  const { data: users } = useQuery({
    queryKey: ["telegram-linkable-users", isSuperadmin],
    queryFn: async () => {
      // `allSettled`: un 403 al listar admins no debe vaciar también los encargados.
      const [admins, encargados] = await Promise.allSettled([
        isSuperadmin ? adminApi.listUsers("admin") : Promise.resolve([] as UserRead[]),
        adminApi.listUsers("encargado"),
      ]);
      const ok = (r: PromiseSettledResult<UserRead[]>) =>
        r.status === "fulfilled" ? r.value : [];

      const list = [...ok(admins), ...ok(encargados)];
      // El propio usuario siempre, porque un admin normal no puede listar admins.
      if (currentUser && !list.some((u) => u.id === currentUser.id)) {
        list.push({ ...currentUser });
      }
      return list.sort((a, b) => a.name.localeCompare(b.name));
    },
  });
```

- [ ] **Step 5: Marcar “Yo” en el desplegable**

En el `<option>` del selector de usuario:

```tsx
            {users?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name} ({u.email}){u.id === currentUser?.id ? " — Yo" : ""}
              </option>
            ))}
```

- [ ] **Step 6: Ejecutar**

```bash
npm --prefix frontend run test -- --run TelegramLinks
```

Expected: todos pasan.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/features/telegram/TelegramLinks.tsx \
  frontend/src/features/telegram/TelegramLinks.test.tsx
git commit -m "fix(telegram): keep the recipient list usable and include the current user"
```

### Task 2.2 — Retirar la administración del vínculo del asistente

**Files:**
- Modify: `frontend/src/features/telegram/TelegramLinks.tsx`
- Test: `frontend/src/features/telegram/TelegramLinks.test.tsx`

- [ ] **Step 1: Quitar el bloque “Vinculación manual”**

Eliminar el `<details>` completo cuyo `<summary>` dice `Vinculacion manual (admin)`, y con él el
estado y el manejador que solo usa ese formulario:

```tsx
  // eliminar
  const [telegramUserId, setTelegramUserId] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [userId, setUserId] = useState("");
  const createMutation = useMutation({ ... });
  function handleSubmit(e: FormEvent<HTMLFormElement>) { ... }
```

- [ ] **Step 2: Quitar la tabla de vínculos del asistente**

Eliminar el `useQuery` de `telegramApi.listLinks`, el `deleteMutation`, el contador `{links && ...}`
de la cabecera, el bloque de estado vacío y la tabla final. El archivo deja de importar
`TelegramUserLinkRead`, `Trash2`, `Check`, `FormEvent` y `CreateTelegramLinkRequest` si quedan sin
uso.

- [ ] **Step 3: Quitar los tests del bloque retirado**

En `TelegramLinks.test.tsx`, eliminar los tres tests que solo cubren la tabla vieja:

```tsx
  it("muestra estado vacío cuando no hay vínculos", ...);
  it("muestra la tabla cuando hay vínculos", ...);
  it("muestra el título de la sección", ...);   // también usa `links`
```

Y quitar del mock de `../../api/telegram` las funciones `listLinks`, `createLink` y `deleteLink` si
ya no se usan.

- [ ] **Step 4: Añadir el test que fija la ausencia**

```tsx
  it("no muestra los campos del vínculo manual del asistente", async () => {
    await setupMocks({ admins: [{ ...ADMIN_LINKED, id: "u-admin-2", name: "Otro Admin" }] });

    renderComponent();

    await screen.findByRole("heading", { name: /telegram/i });
    expect(screen.queryByText(/vinculacion manual/i)).toBeNull();
    expect(screen.queryByText(/telegram user id/i)).toBeNull();
  });
```

- [ ] **Step 5: Ejecutar**

```bash
npm --prefix frontend run test -- --run TelegramLinks
npx --prefix frontend tsc -b
```

Expected: tests en verde y `tsc` sin errores.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/telegram/TelegramLinks.tsx \
  frontend/src/features/telegram/TelegramLinks.test.tsx
git commit -m "refactor(telegram): drop the assistant-link admin from the alerts screen"
```

---

## Fase 3 — Cierre

### Task 3.1 — Suite completa y registro

**Files:**
- Modify: `docs/specs/2026-10-27-gestion-vinculos-telegram.md` (estado y registro)

- [ ] **Step 1: Suite completa**

```bash
./.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend run test -- --run
```

Expected: todo en verde.

- [ ] **Step 2: Actualizar el spec**

Cambiar `status: accepted` por `status: implemented` y añadir al changelog la fecha y el resultado.

- [ ] **Step 3: Commit**

```bash
git add docs/specs/2026-10-27-gestion-vinculos-telegram.md
git commit -m "docs(spec): mark the Telegram link policy as implemented"
```

---

## Orden de ejecución

| Fase | Tasks | Qué resuelve | Depende de |
|---|---|---|---|
| 1 | 1.1 | La regla se aplica en la API | — |
| 2 | 2.1, 2.2 | Lista usable y pantalla sin el vínculo del asistente | Fase 1 |
| 3 | 3.1 | Verificación y cierre | Fases 1–2 |

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-27 | — | Spec y tasks creadas. Sin implementar. |
