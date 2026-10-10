---
spec: mi-perfil-y-politica-contrasena
version: 1.2.0
status: implementado
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Mi perfil y mensajes de contraseña

## Goal

Tres cosas en un solo cambio:

1. Que **cualquier usuario** pueda ver y editar su propia información desde el avatar del menú
   lateral — hoy esa pantalla **no existe**.
2. Que pueda **cambiar su contraseña cuando quiera**, no solo cuando el sistema se lo exige al
   entrar.
3. Que el sistema diga **exactamente por qué** rechaza una contraseña. Hoy da un único mensaje
   para siete causas distintas, y ese mensaje suele ser falso.

Además: la longitud mínima baja de **10 a 8 caracteres** (el resto de la política se mantiene).

**Tareas de implementación:** [2026-10-09-mi-perfil-y-politica-contrasena-tasks.md](2026-10-09-mi-perfil-y-politica-contrasena-tasks.md)

## Contexto

Origen: pedido directo del usuario (2026-10-09), al preguntar *"¿dónde el usuario puede editar su
información?"*. Hoy un usuario no puede editar **nada** propio salvo la contraseña, y solo cuando
el sistema lo obliga al iniciar sesión.

### Lo que ya tenemos (verificado)

| Pieza | Dónde | Estado |
|---|---|---|
| Leer el propio usuario | `GET /api/auth/me` (`auth.py:230`) | ✅ funciona |
| Cambiar la propia contraseña | `POST /api/auth/change-password` (`auth.py:235`) | ✅ con política completa, historial y correo de aviso |
| Función en el cliente web | `changePassword()` (`api/auth.ts:24`) | ✅ existe |
| Contexto con el usuario y su refresco | `AuthContext.setCurrentUser` | ✅ listo |
| Bloque del avatar en el menú | `Sidebar.tsx:225-244` | ✅ existe, hoy **no es clicable** |
| Auditoría de cambios de usuario | `AuditService.log_user_updated` (`audit/service.py:211`) | ✅ existe, sin usar para esto |
| El frontend entiende `detail = {code, message}` | `ApiError` (`client.ts:43-62`) | ✅ ya lo soporta |

### Lo que falta

| # | Qué | Estado |
|---|---|---|
| 1 | Endpoint para editar el propio perfil | **no existe** (solo `GET /me`) |
| 2 | Ruta y pantalla de perfil en el frontend | **no existe** |
| 3 | Que el avatar del menú abra esa pantalla | hoy es texto plano |
| 4 | Mensajes específicos de contraseña | hoy son genéricos |

## Hallazgos de la investigación

**1. La política de contraseñas está duplicada y puede divergir.**
Las mismas 4 reglas de complejidad están escritas dos veces: en
`application/accounts/service.py:202-211` (cambio propio) y en `api/routes/auth.py:354-374`
(flujo de invitación). No comparten código.

**2. El flujo de invitación YA tiene los mensajes buenos — el otro no.**
Comparación directa:

| Flujo | Mensaje cuando falta una mayúscula |
|---|---|
| Invitación (`auth.py:358`) | ✅ *"La contraseña debe contener al menos una mayúscula"* |
| Cambio propio (`service.py`) | ❌ *"No se pudo cambiar la contraseña. Verifica que la contraseña actual sea correcta."* |

O sea: **el patrón correcto ya existe en el propio repositorio**; solo hay que unificarlo y
extenderlo al cambio propio.

**3. El mínimo de 10 vive en 7 lugares distintos.**
`schemas/accounts.py:44,50,69` · `api/routes/auth.py:50` · `service.py:202` ·
`SetPasswordPage.tsx:157` (y su `minLength`) · `App.tsx:135`. Cambiarlo en uno solo deja el
sistema incoherente, con la pantalla diciendo una cosa y el backend exigiendo otra.

**4. Las contraseñas temporales escritas por un admin no validan complejidad.**
`service.py:85-99`: si el admin escribe una `temporary_password`, se hashea tal cual. Solo se le
exige `min_length` de Pydantic. Un admin puede crear un usuario con `"1234567890"` — contraseña
que el propio sistema rechazaría si el usuario intentara ponerla.

**5. El cliente web no necesita cambios para mostrar mensajes específicos.**
`ApiError` ya interpreta `detail` como texto, lista (422 de Pydantic) u objeto con `message`.
Devolver `{"code": ..., "message": ...}` funciona sin tocar `client.ts`.

**6. `view_audit` se usa en 4 sitios y en ningún otro lado.**
`domain/accounts.py:20`, `api/routes/audit.py:19`, `Sidebar.tsx:64,117,128` y
`UsersView.tsx:39`. Cerrar la puerta es cambiar una dependencia: **`require_admin` ya existe**
(`dependencies.py:49`) y rechaza a cualquier que no sea admin.

**7. Estado real de las cuentas (auditoría de producción, 2026-10-09).**
Consulta de solo lectura sobre la base de producción (Neon):

| Nombre | Rol | ¿Tenía `view_audit`? | Último login |
|---|---|---|---|
| Alexandra | encargado | **Sí** | **nunca** |
| Rafael | encargado | No | nunca |
| Rafael Hendrick | encargado | **Sí** | 2026-05-23 |
| Administrador | admin | por rol | 2026-09-11 |
| Dra. Alexandra Acosta | admin | por rol | 2026-10-02 |

Las tres cuentas de encargado están **dormidas**; quienes usan el sistema son los dos
administradores. Por eso retirar el permiso **no le quita visibilidad a nadie activo**.

**8. Borrar un usuario no rompe el historial.**
El borrado es **lógico** (`soft_delete_user`, `admin_users.py:206`), así que la fila permanece y
el presenter de auditoría sigue resolviendo el nombre del actor. Con un borrado físico, las
entradas viejas pasarían a decir *"Usuario del sistema"*.

**9. `view_audit` está en las listas de producción, y eso hay que limpiarlo.**
Si el permiso desaparece del enum **sin limpiar los datos**, guardar cualquiera de esos usuarios
desde la pantalla de Usuarios falla con `Permisos inválidos: view_audit`. La limpieza es un
`UPDATE` sobre `users.permissions` (sin migración de esquema) y **debe correr en producción**
junto con el despliegue.

## Alcance

| Dentro | Fuera |
|---|---|
| Pantalla **Mi perfil** con nombre y contraseña | Editar el correo (decisión: no) |
| Avatar del menú como punto de entrada | Editar rol o permisos |
| Una sola fuente de verdad para la política | WhatsApp del usuario (columna muerta) |
| Mensajes específicos por causa | El correo de aviso al cambiar contraseña (ya existe) |
| Mínimo 10 → 8 en todos los sitios | Recuperación por correo (ya existe y funciona) |
| **Auditoría solo para administradores** (se retira `view_audit`) | Desactivar o borrar cuentas dormidas (decisión aparte) |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | El usuario **sí** puede editar su **nombre** | Lo pidió; se audita porque termina en la firma de un documento oficial |
| 2 | El **correo NO** es editable | Es la identidad de acceso **y** el destino de la recuperación: cambiarlo sin verificar deja al usuario fuera |
| 3 | Rol y permisos **nunca** | Escalada de privilegios |
| 4 | La contraseña se cambia **cuando quiera**, no solo al entrar | Hoy no hay forma de cambiarla estando dentro |
| 5 | **Mínimo 8 caracteres** (era 10) | Pedido explícito; se mantienen mayúscula, minúscula, número y símbolo |
| 6 | **Una sola fuente de verdad** para la política | Hoy está duplicada y puede divergir |
| 7 | El error de contraseña devuelve **código + mensaje exacto** | El usuario debe saber qué corregir |
| 8 | WhatsApp del usuario **fuera** | La columna existe pero ninguna parte del código la lee |
| 9 | La **auditoría es solo para administradores** y `view_audit` desaparece | La traza existe para vigilar a quien tiene poder; un encargado leyéndola ve también lo que hacen los administradores, y la relación de supervisión se invierte |
| 10 | Las **cuentas dormidas** se tratan aparte | Son una decisión de datos con su propio riesgo; mezclarla con el cambio de permisos lo vuelve más difícil de revisar |

## Requisitos

- **R1** — El bloque del avatar en el menú lateral es clicable y abre **Mi perfil**.
- **R2** — La pantalla muestra **nombre**, **correo** y **rol**. El correo y el rol son de solo
  lectura.
- **R3** — El nombre se puede editar y guardar; el cambio se registra en auditoría.
- **R4** — Cambiar el nombre **actualiza el menú lateral** sin recargar la página.
- **R5** — La pantalla permite cambiar la contraseña pidiendo la actual.
- **R6** — La contraseña nueva cumple: **≥ 8 caracteres**, 1 mayúscula, 1 minúscula, 1 número,
  1 símbolo; distinta de la actual y de las últimas 5.
- **R7** — Si la contraseña se rechaza, el mensaje dice **la causa exacta**.
- **R8** — La longitud mínima es **8** en backend y frontend, en todos los sitios.
- **R9** — Un usuario solo puede editar **su propia** cuenta: no hay forma de tocar la de otro.
- **R10** — La contraseña temporal que escribe un admin también valida complejidad.
- **R11** — La pantalla de Auditoría queda **solo para administradores**. Un encargado recibe
  `403` aunque tuviera el permiso.
- **R12** — El permiso `view_audit` **deja de existir**: no se define, no se concede y no
  aparece en la pantalla de Usuarios. Las listas que lo contengan se limpian.

## Criterios de aceptación

**AC1 — Entrar al perfil**
- **Dado** un usuario con sesión abierta,
- **cuando** pulsa su nombre o avatar en el menú,
- **entonces** llega a **Mi perfil** con sus datos.

**AC2 — Cambiar el nombre**
- **Dado** el campo Nombre,
- **cuando** lo cambia y guarda,
- **entonces** el nombre nuevo aparece en el menú lateral y queda registrado en auditoría.

**AC3 — Cambiar la contraseña**
- **Dada** la contraseña actual correcta y una nueva válida,
- **cuando** guarda,
- **entonces** la contraseña cambia y recibe el correo de aviso.

**AC4 — El mensaje dice la verdad**
- **Dada** una contraseña nueva sin mayúscula,
- **entonces** el mensaje es *"debe contener al menos una mayúscula"* — **no** un mensaje sobre
  la contraseña actual.
- Y lo mismo para cada causa: corta, sin minúscula, sin número, sin símbolo, igual a la actual,
  ya usada antes, contraseña actual incorrecta.

**AC5 — Ocho caracteres**
- **Dada** una contraseña de 8 caracteres que cumpla el resto,
- **entonces** se acepta. Con 7, se rechaza indicando la longitud mínima.

**AC6 — Sin fugas de privilegio**
- **Dado** el perfil,
- **entonces** no hay forma de cambiar el correo, el rol ni los permisos, ni de editar a otro
  usuario.

**AC7 — La auditoría es solo del administrador**
- **Dado** un encargado con sesión abierta,
- **cuando** intenta abrir la auditoría (API o menú),
- **entonces** recibe `403` y **no ve la opción** en el menú.
- **Y dado** un administrador, **entonces** sí la ve y la abre con normalidad.

**AC8 — `view_audit` ya no existe**
- **Dada** la pantalla de Usuarios,
- **entonces** `view_audit` no aparece entre los permisos concedibles.
- **Y dado** un usuario cuya lista lo contenía, **entonces** queda limpia y el usuario se puede
  guardar sin errores.

## Contrato

**1. Endpoint nuevo** — el usuario edita su propia cuenta (requiere sesión, sin permiso extra):

```
PATCH /api/auth/me
{ "name": "DRA. ALEXANDRA ACOSTA RAMOS" }
→ 200 UserRead
```

Solo acepta `name`. Cualquier otro campo se ignora por diseño.

**2. Errores de contraseña con causa exacta.** `POST /api/auth/change-password` y
`POST /api/auth/set-password` pasan a devolver:

```json
400 {
  "detail": {
    "code": "password_no_uppercase",
    "message": "La contraseña debe contener al menos una mayúscula."
  }
}
```

Códigos previstos: `password_too_short`, `password_no_uppercase`, `password_no_lowercase`,
`password_no_digit`, `password_no_special`, `password_same_as_current`, `password_reused`,
`password_current_incorrect`.

`ApiError` del frontend ya sabe leer esta forma, así que la pantalla muestra el mensaje sin
tocar el cliente.

## Impacto en tests

| Archivo | Efecto |
|---|---|
| `backend/tests/accounts/test_auth_routes.py` | `test_set_password_weak_password` cambia de motivo (422 → 400 con código); añadir un caso por causa |
| `backend/tests/accounts/test_password_security.py` | Cubre reuso e historial; hay que ajustar los mensajes esperados |
| Nuevos: perfil | `PATCH /me` cambia el nombre, audita, y **rechaza** intentar tocar el correo |
| Nuevos: política | Un test por regla, incluida la de 8 caracteres |
| `frontend/src/features/auth/SetPasswordPage.test.tsx` | El texto "Mínimo 10 caracteres" pasa a 8 |
| Nuevos: frontend | El avatar abre el perfil; guardar nombre refresca el menú; el error de contraseña se muestra literal |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Bajar el mínimo a 8 debilita las contraseñas nuevas | Se mantienen las otras 4 reglas y el historial de 5. **No invalida** las contraseñas existentes |
| Que el usuario se ponga un nombre que no corresponde en la firma | Es un documento oficial; queda **auditado** con `log_user_updated` y el admin puede corregirlo |
| Cambiar la política en un sitio y olvidar otro | Se unifica en una sola función y un test recorre las reglas |
| Que la pantalla de perfil se convierta en puerta a permisos | El endpoint solo acepta `name`; un test lo fija |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Nuevo requerimiento | Se crea la pantalla **Mi perfil** (nombre editable y auditado, correo y rol de solo lectura, cambio de contraseña disponible en cualquier momento) accesible desde el avatar del menú. Se unifica la política de contraseñas —hoy duplicada en dos flujos— y se reemplazan los mensajes genéricos por mensajes con la causa exacta. El mínimo baja de 10 a 8 caracteres. Queda documentado que las contraseñas temporales escritas por un admin hoy no validan complejidad. |
| 1.1.0 | 2026-10-09 | — | Feedback | La **auditoría pasa a ser solo para administradores**: se retira el permiso `view_audit` del enum, del menú y de la pantalla de Usuarios, y el endpoint pasa a `require_admin`. Se documenta el estado real de las cuentas de producción (3 encargados dormidos, 2 con el permiso) y que la limpieza de las listas debe correr junto con el despliegue. Las cuentas dormidas quedan fuera de alcance, como decisión aparte. |
| 1.2.0 | 2026-10-09 | — | Implementación | Estado pasa a `implementado`. La política vive en `core/security.py` y es la única que decide; los dos flujos la consumen y cada causa tiene su mensaje. `PATCH /auth/me` permite cambiar el nombre, que queda auditado **con el valor anterior**. La auditoría guarda antes y después y el presenter lo resume como «de X a Y». La pantalla **Mi perfil** cuelga del avatar del menú. Se quitó el `min_length` de Pydantic para que la longitud también produzca un error limpio con código, y se descubrió y corrigió que el enlace **Equilibrio** estaba colgado de `view_audit` aunque su API solo pide sesión. |
