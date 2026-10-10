# Tasks — Mi perfil y mensajes de contraseña

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-mi-perfil-y-politica-contrasena.md](2026-10-09-mi-perfil-y-politica-contrasena.md)

**Goal:** Pantalla **Mi perfil** (nombre editable y auditado, contraseña cambiable en cualquier
momento) accesible desde el avatar, más una política de contraseñas unificada que diga la causa
exacta del rechazo y exija **8** caracteres en vez de 10.

**Architecture:** La política de contraseñas vive en una única función de
`backend/app/core/security.py` —junto a `hash_password`/`verify_password`, que es lo que necesita
para comprobar el historial— y devuelve **la causa** del rechazo (o `None`). Los dos flujos que
hoy la duplican pasan a usarla y traducen la causa a un `detail` con `code` y `message`, forma que
`ApiError` ya sabe leer. El perfil es una ruta nueva protegida por sesión, con un `PATCH /me` que
**solo** acepta el nombre, y el avatar del menú lateral es el punto de entrada. La auditoría pasa
a ser exclusiva del rol administrador.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, React + TanStack Query, React Router, pytest, vitest

**Estado:** ✅ **Implementado** en la rama `feat/whatsapp-pdf-semanal` (2026-10-09).

**Evidencia de verificación (en vivo, contra el backend real):**

| Comprobación | Resultado |
|---|---|
| `PATCH /auth/me` cambia el nombre | `HTTP 200`, nombre actualizado |
| `PATCH /auth/me` ignora correo y rol | enviados `email` y `role=admin` → siguen intactos |
| Cada causa de contraseña | `password_current_incorrect`, `password_too_short`, `password_no_uppercase`, `password_no_lowercase`, `password_no_digit`, `password_no_special`, `password_same_as_current`, `password_reused` — **cada una con su mensaje propio** |
| 8 caracteres válidos | `HTTP 200` |
| 7 caracteres | `400 password_too_short` (antes: un 422 de Pydantic con el prefijo `new_password:`) |
| Auditoría antes → después | `Se actualizó — nombre: de «Rafael Hendrick» a «DRA. ALEXANDRA ACOSTA RAMOS»` |
| Auditoría solo admin | encargado → **403** |
| Limpieza de `view_audit` | 3 usuarios locales actualizados; quedan 0 |
| Tests backend | `pytest backend/tests -q` (ver corrida final) |
| Tests frontend | **123 passed**, 22 archivos (en secuencia) |
| Lint | backend: 13 errores baseline → **12** (cero nuevos) · frontend limpio · `tsc` limpio |

---

## Fase 1 — Una sola política de contraseñas

### Task 1.1 — La función única

**Archivo nuevo:** `backend/app/domain/passwords.py`

- [x] **Definir** `PASSWORD_MIN_LENGTH = 8` como única constante de longitud.
- [x] **Definir** el enum de causas: `too_short`, `no_uppercase`, `no_lowercase`, `no_digit`,
      `no_special`, `same_as_current`, `reused`.
- [x] **Escribir** `check_password_strength(password, *, current_hash=None, recent_hashes=())`
      que devuelva la **primera** causa encontrada o `None` si es válida.
- [x] **Escribir** `describe(problem)` con el mensaje en español de cada causa.
- [x] **Mantener** el conjunto actual de símbolos y el orden de comprobación del flujo de
      invitación, para no cambiar el comportamiento más de lo necesario.

> Es capa `domain`: no importa infraestructura, así que la pueden usar tanto el servicio como
> las rutas.

### Task 1.2 — Usarla en los dos flujos

**Archivos:** `backend/app/application/accounts/service.py`,
`backend/app/api/routes/auth.py`

- [x] **Reemplazar** el bloque duplicado de `change_own_password` (`service.py:201-217`) por la
      función única.
- [x] **Reemplazar** el bloque duplicado de `set_password` (`auth.py:354-380`) por la función
      única.
- [x] **Conservar** la comprobación de contraseña actual y la de historial, pasándolas como
      argumentos.

### Task 1.3 — Bajar el mínimo a 8 en todas partes

- [x] `backend/app/schemas/accounts.py` — las **tres** apariciones de `min_length=10`
      (líneas 44, 50 y 69) pasan a usar `PASSWORD_MIN_LENGTH`.
- [x] `backend/app/api/routes/auth.py:50` — `min_length=10` → `PASSWORD_MIN_LENGTH`.
- [x] `frontend/src/features/auth/SetPasswordPage.tsx` — `minLength={10}`, el texto
      "Mínimo 10 caracteres" y su validación previa.
- [x] `frontend/src/App.tsx:135-136` — la comprobación de longitud del flujo forzado.

> Son **7 sitios**. Si se cambia uno solo, la pantalla dice una cosa y el backend exige otra.

### Task 1.4 — La temporal del admin también valida

**Archivo:** `backend/app/application/accounts/service.py` (`create_encargado`, ≈ línea 85)

- [x] **Validar** la `temporary_password` cuando la escribe un admin, con la misma función.
      Hoy se hashea sin comprobar nada: un admin puede crear un usuario con `"1234567890"`.

---

## Fase 2 — Mensajes con la causa exacta

### Task 2.1 — Código por causa en las respuestas

**Archivo:** `backend/app/api/routes/auth.py`

- [x] `change-password`: mapear la causa a `400 {detail: {code, message}}` en vez del mensaje
      genérico actual.
- [x] `set-password`: mantener el 400 pero con la misma forma `{code, message}`.
- [x] **Mantener** el 422 de Pydantic para el caso en que el cuerpo ni siquiera valide (campo
      ausente, tipo equivocado).

### Task 2.2 — Mostrarlos en el frontend

- [x] En la pantalla de perfil y en la de contraseña forzada, mostrar el `message` tal cual
      llega (`ApiError` ya lo extrae) y **listar las reglas antes de enviar**, para que el error
      sea la excepción.

---

## Fase 3 — El perfil en el backend

### Task 3.1 — Endpoint `PATCH /api/auth/me`

**Archivo:** `backend/app/api/routes/auth.py`

- [x] **Añadir** `PATCH /me` con `UpdateOwnProfileRequest` que contiene **solo** `name`
      (`min_length=1`, `max_length=160`).
- [x] **Delegar** en un método nuevo del servicio (`update_own_profile`) que actualice el nombre
      y registre `AuditService.log_user_updated`.
- [x] **Devolver** `UserRead` para que el frontend refresque el contexto.
- [x] **Confirmar** que un `PATCH` con `email`, `role` o `permissions` **no** los cambia.

### Task 3.2 — Schema

**Archivo:** `backend/app/schemas/accounts.py`

- [x] **Añadir** `UpdateOwnProfileRequest` con el nombre y su validación de longitud.

---

## Fase 4 — El perfil en el frontend

### Task 4.1 — El avatar abre el perfil

**Archivo:** `frontend/src/components/Sidebar.tsx` (bloque de usuario, ≈ líneas 225-244)

- [x] **Convertir** el bloque del avatar en un elemento clicable que navegue a `/profile`.
- [x] **Dejarlo accesible**: que sea un `<button>`, que responda al teclado y tenga
      `aria-label`. El botón de **Cerrar sesión** queda aparte y no debe dispararse al pulsar el
      avatar.

### Task 4.2 — La pantalla

**Archivo nuevo:** `frontend/src/features/profile/ProfilePage.tsx` + ruta en `App.tsx`

- [x] **Añadir** la ruta `/profile` dentro del layout protegido.
- [x] **Sección Mis datos**: nombre editable; correo y rol de solo lectura.
- [x] **Sección Cambiar contraseña**: actual, nueva y confirmación, con las reglas escritas
      debajo del campo.
- [x] **Al guardar el nombre**, llamar a `setCurrentUser` con la respuesta para que el menú se
      actualice sin recargar.
- [x] **Ignorar** cualquier cambio de rol o permisos: la pantalla no los ofrece.

### Task 4.3 — Cliente de API

**Archivo:** `frontend/src/api/auth.ts`

- [x] **Añadir** `updateProfile(name)` contra `PATCH /auth/me`.
- [x] **Reutilizar** `changePassword()` que ya existe.

---

## Fase 5 — Tests

### Task 5.1 — Política (una por regla)

- [x] **Un caso por causa**: corta, sin mayúscula, sin minúscula, sin número, sin símbolo, igual
      a la actual, reusada.
- [x] **Frontera de longitud**: 8 se acepta, 7 se rechaza.
- [x] **Sin regresión**: una contraseña que antes era válida con 10 caracteres sigue siéndolo.

### Task 5.2 — Endpoints

- [x] `PATCH /me` cambia el nombre y lo devuelve.
- [x] `PATCH /me` **ignora** `email`, `role` y `permissions`.
- [x] `PATCH /me` registra el evento de auditoría.
- [x] `change-password` con mayúscula faltante devuelve `password_no_uppercase`, **no** un
      mensaje sobre la contraseña actual (el bug que motiva esta parte).
- [x] La temporal de un admin sin complejidad es rechazada.

### Task 5.3 — Frontend

- [x] El avatar del menú navega a `/profile`.
- [x] Guardar el nombre refresca el nombre del menú.
- [x] El mensaje de error de contraseña se muestra literal.
- [x] El texto de reglas dice **8**, no 10.

---

## Fase 6 — Verificación

### Task 6.1 — En vivo

- [x] **Entrar** con un usuario, abrir el perfil desde el avatar y cambiar el nombre.
- [x] **Confirmar** que el menú lateral se actualiza solo.
- [x] **Cambiar la contraseña** con una válida de 8 caracteres y volver a entrar con ella.
- [x] **Provocar cada error** (sin mayúscula, corta, reusada, actual incorrecta) y confirmar que
      el mensaje dice la causa correcta en cada caso.
- [x] **Confirmar** que el correo y el rol no se pueden modificar desde la pantalla.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 1 | Fase 1 | Política única y mínimo 8 | Medio — toca dos flujos vivos | ✅ hecho |
| 🔴 2 | Fase 2 | Mensajes con causa exacta | Bajo | ✅ hecho |
| 🟠 3 | Fase 3 | Editar el propio nombre | Bajo | ✅ hecho |
| 🟠 4 | Fase 4 | La pantalla y el avatar | Bajo | ✅ hecho |
| 🟡 5 | Fase 5 | Cobertura | Bajo | ✅ hecho |
| 🟡 6 | Fase 6 | Verificación manual | Bajo | ✅ hecho |

## Archivos tocados

| Archivo | Tipo |
|---|---|
| `backend/app/core/security.py` | modificado — **la política única**. Se puso aquí y no en `domain/` porque necesita `verify_password` para el historial |
| `backend/app/application/accounts/service.py` | modificado — usa la política; valida la temporal; audita antes/después |
| `backend/app/application/accounts/errors.py` | modificado — el error lleva la causa |
| `backend/app/application/audit/service.py` | modificado — `log_user_updated` acepta el valor previo |
| `backend/app/application/audit/presenter.py` | modificado — resumen «de X a Y» |
| `backend/app/api/routes/auth.py` | modificado — `PATCH /me`, mensajes con código |
| `backend/app/api/routes/admin_users.py` | modificado — propaga la causa al crear/restablecer |
| `backend/app/api/routes/audit.py` | modificado — `require_admin` |
| `backend/app/domain/accounts.py` | modificado — `VIEW_AUDIT` eliminado |
| `backend/app/schemas/accounts.py` | modificado — schema del perfil; la longitud la valida la política, no Pydantic |
| `scripts/strip_view_audit_permission.py` | **nuevo** — limpieza de datos, con `--dry-run` |
| `frontend/src/components/Sidebar.tsx` | modificado — avatar clicable; Auditoría por rol |
| `frontend/src/features/profile/ProfilePage.tsx` | **nuevo** — la pantalla |
| `frontend/src/App.tsx` | modificado — ruta `/profile` y mínimo 8 |
| `frontend/src/api/auth.ts` | modificado — `updateProfile` + `PASSWORD_MIN_LENGTH` |
| `frontend/src/features/auth/SetPasswordPage.tsx` | modificado — reglas a 8 |
| `frontend/src/features/users/UsersView.tsx` | modificado — `view_audit` fuera de la lista |
| `frontend/src/styles.css` | modificado — el bloque del usuario como botón |
| Tests backend y frontend | añadidos y ajustados |

**Sin migraciones de esquema.**

## Casillas abiertas

1. **Limpieza de datos en producción** — el script
   `scripts/strip_view_audit_permission.py` debe correrse contra Neon junto con el despliegue.
   Si no, guardar a los 2 encargados que tienen `view_audit` fallará con
   `Permisos inválidos: view_audit`. **No se ejecutó contra producción.**
2. **Cuentas dormidas** (`Alexandra`, `Rafael`, `Rafael Hendrick`) — decisión aparte, fuera de
   alcance. La de `Rafael` tiene el correo mal escrito (`hotmailc.om`).
3. **El mínimo de 8 debilita** las contraseñas nuevas frente a 10. Se mantienen las otras cuatro
   reglas y el historial de 5. **No invalida** las existentes.
4. **Efecto secundario en el nombre**: el nombre del usuario se usa en toda la interfaz y también
   es la firma. Si se pone uno largo, aparecerá largo en la lista de usuarios y en la auditoría.
5. **Merge a `master`** — pendiente de autorización.

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas. Decisiones: nombre editable y auditado, correo no, mínimo 8, mensajes con causa exacta en el mismo cambio. |
| 2026-10-09 | Auditoría solo admin | `view_audit` eliminado del enum, del menú y de Usuarios; endpoint con `require_admin`. Se descubrió que **`Equilibrio` también estaba colgado de `view_audit`** aunque su API solo pide sesión: se reasignó a `manage_calendars`. |
| 2026-10-09 | 1.1–1.4 | Política única en `core/security.py`; los dos flujos la usan; la temporal del admin ya valida. |
| 2026-10-09 | 2.1–2.2 | `detail` con `code` + `message`. Se quitó el `min_length` de Pydantic para que la longitud también dé un 400 limpio en vez de un 422 con `new_password:` de prefijo. |
| 2026-10-09 | 3.1–3.2 | `PATCH /auth/me` solo acepta `name`; la auditoría guarda antes y después. |
| 2026-10-09 | 4.1–4.3 | Pantalla **Mi perfil**, avatar clicable, ruta `/profile`. |
| 2026-10-09 | 5.1–5.3 | 13 tests de política, 6 de perfil, 3 de auditoría, 14 de frontend. |
| 2026-10-09 | 6.1 | En vivo: nombre, correo/rol ignorados, las 8 causas de contraseña, auditoría «de X a Y», 403 al encargado. |
| 2026-10-09 | — | Se verificó que **borrar un usuario es lógico** y que un borrado duro choca con la FK de `password_history`; y que la propia tabla de auditoría rechazó un `DELETE` de prueba. |
