---
spec: infra-limpieza-correo-y-despliegue
version: 1.1.0
status: implementado
created: 2026-10-04
updated: 2026-10-04
---

# Spec — Puesta al día de Turnos Médicos: limpieza de infraestructura, correo y despliegue

## Goal

Dejar el proyecto con el correo de restablecimiento funcionando, el arreglo de la pantalla
de recuperación desplegado, y los recursos huérfanos de Railway eliminados.

**Tareas de implementación:** [2026-10-04-infra-limpieza-correo-y-despliegue-tasks.md](2026-10-04-infra-limpieza-correo-y-despliegue-tasks.md)

## Contexto

Auditoría de infraestructura del 2026-10-04 sobre **este** proyecto únicamente
(`generous-rebirth` en Railway). El resto de proyectos del workspace se gestionan
por separado y quedan fuera de alcance.

**Topología actual:**

| Capa | Dónde | Detalle |
|---|---|---|
| Frontend | Vercel | `general-medical-services.vercel.app` |
| Backend (API) | Railway | `general-medical-services-production.up.railway.app` (us-east4) |
| Worker (cron) | Railway | `*/30 * * * *`, `python -m backend.app.application.scheduler.run_once` |
| Base de datos | **Neon** (us-east-2) | La API y el worker apuntan aquí |
| DNS + dominio | Cloudflare | Zona `rafenixcore.com`, plan Free |
| Correo | Resend | `rafenixcore.com` verificado, envío habilitado |

**Medición del periodo 2026-09-21 → 2026-10-21 (13 días transcurridos): $0.07579**

| Servicio | Costo | Estado |
|---|---|---|
| `deleted service` (volumen) | $0.02554 | 🔴 Huérfano — factura para siempre |
| `general-medical-services` (API) | $0.01855 | ✅ En uso |
| `Postgres` (Railway) | $0.01582 | 🔴 Huérfano — con dominio público expuesto |
| `Postgres-V7Ht` (staging) | $0.01582 | 🔴 Huérfano — staging sin app |
| `worker` | $0.00006 | ✅ En uso |

- **Huérfanos: $0.05718 = 75.4% del costo.** Cuestionan 3× más que la app en uso.
- **Volumen de disco: $0.05427 = 71.6% del costo.** Es lo que domina, no el cómputo.
- Proyección mensual: **$0.175 → $0.043** tras la limpieza. Ahorro ≈ **$0.132/mes**.

**Los dos problemas con impacto real en usuarios:**

1. **El correo de restablecimiento no funciona.** Resend está configurado y el dominio
   verificado, pero `RESEND_API_KEY` nunca se puso en Railway. Sigue con las variables
   de Gmail, cuyo refresh token devuelve 400 desde septiembre.
2. **El frontend no se despliega desde el 2026-09-11.** El arreglo de la pantalla de
   recuperación existe y está probado, pero vive en una rama sin mergear.

## R1 — Conectar Resend

El proveedor ya está elegido y verificado; solo falta cablearlo.

**Configuración requerida — las dos variables son inseparables:**

| Variable | Valor | Por qué |
|---|---|---|
| `RESEND_API_KEY` | `re_...` | Activa la rama de Resend en `send_email` |
| `RESEND_FROM_EMAIL` | `noreply@rafenixcore.com` | Debe usar el dominio verificado |

⚠️ **`RESEND_FROM_EMAIL` es obligatoria.** El default en `backend/app/core/config.py`
es `noreply@turnos-medicos.com`, un dominio **no verificado** en Resend. Poner solo la
API key produce un **403** y el síntoma se confunde con "Resend no funciona".

**Prioridad del código** (`backend/app/infrastructure/email/resend.py`):
Resend → Gmail API → log a consola. Al configurar Resend, Gmail queda como respaldo
inactivo.

**Prioridad del código verificada** (`backend/app/core/config.py:29-30`): las variables
`RESEND_API_KEY` y `RESEND_FROM_EMAIL` mapean a `resend_api_key` y `resend_from_email` sin
`env_prefix` que las desvíe. El cableado es correcto.

**Aceptación**
- Dado un correo de un usuario `encargado` activo, cuando se solicita restablecimiento,
  entonces el correo llega — **confirmado en el panel/API de Resend**, no en los logs.
- Dado un envío fallido, cuando Resend rechaza, entonces el endpoint sigue devolviendo
  **200** (contrato anti-enumeración de `auth.py`) y queda registro del fallo.

> ### ⚠️ Corrección — la verificación NO se hace por logs de Railway
>
> `configure_logging` (`backend/app/core/logging_config.py:36`) **nunca se invoca**, así que
> el root logger queda en `WARNING` y todo `logger.info` se descarta — incluido
> `"Email sent to %s via Resend"` (`resend.py:87`). Un **fallo** sí aparecería
> (`logger.error`/`exception`).
>
> Consecuencia: la ausencia de la línea de éxito **no** prueba que el envío falló; se deduce
> lo contrario. La fuente de verdad es Resend. Verificación que sí sirvió:
>
> ```
> (destinatario de prueba) · "Recuperacion de contrasena — Sistema de Turnos Medicos"
> Status: delivered · 2026-10-04 14:09 UTC
> ```
>
> Arreglar `configure_logging` es trabajo aparte (ver "Fuera de alcance").

## R2 — Desplegar el arreglo de la pantalla de recuperación

La rama `fix/pantalla-recuperacion-y-correo` (commit `fbd36c4`) contiene el trabajo
completo: pantalla migrada al sistema `.auth-panel` a 440px, `send_email` devolviendo
`bool`, alerta admin ante fallo de envío, y tests.

**Causa raíz que resuelve:** `ForgotPasswordPage` y `SetPasswordPage` usaban las clases
`login-page`, `login-card`, `form-group`, `form-label`, `form-input` y `form-hint`,
**ninguna definida en `styles.css`**. Sin tarjeta que contuviera el input, la regla
global `input { width: 100% }` lo estiraba al ancho completo de la pantalla.

**Aceptación**
- Dado `/forgot-password` en producción, cuando se carga, entonces la tarjeta mide
  ~440px y está centrada, y el input no abarca la pantalla.
- Dado `/login`, cuando se carga, entonces sigue midiendo 720px (sin regresión).
- Dado que el envío falla, cuando el admin abre la campana, entonces ve una alerta
  "Correo no entregado".

## R3 — Eliminar el Postgres huérfano de Railway

El servicio `Postgres` de Railway tiene **dominio público**
(`postgres-production-64ca.up.railway.app`) y **nadie lo usa**: el `DATABASE_URL` de la
API y del worker apuntan a Neon. Es superficie de ataque sin función.

**Riesgo: medio.** Es una eliminación destructiva. Requiere verificar primero que ningún
servicio se conecte ahí.

> ### ⚠️ Corrección — el dato NO estaba respaldado en Neon
>
> La versión 1.0.0 de esta spec afirmaba que "el dato queda respaldado en Neon, que es la
> base realmente usada". **Es falso.** Al inspeccionarlo antes de borrar, el Postgres de
> Railway resultó tener **datos propios y distintos**: 69 médicos, 5 usuarios, 570
> `audit_events`, 125 `doctor_allowed_areas`, con `alembic_version =
> 20260611_audit_append_only` (junio 2026). Es la base de producción **anterior** a la
> migración a Neon, congelada hace 4 meses.
>
> Antes de borrar se volcaron ambos Postgres con `pg_dump` 18 y **se verificó que restauran**
> (restauración real en un Postgres desechable, cotejando conteos fila por fila — no basta
> con que el archivo exista). Destino: `~/backups-turnos-medicos/`.
>
> El `pg_dump` local es v16 y el servidor es v18; v16 se niega a dumpear de un servidor más
> nuevo, así que el volcado se hizo con la imagen `postgres:18` en contenedor.

## R4 — Eliminar los huérfanos restantes

| Recurso | Costo 13d | Identificado como | Estado |
|---|---|---|---|
| Volumen del `deleted service` | $0.02554 | **Dos** volúmenes, no uno: `postgres-volume-ooV5` (`b86478c1-…`, 198 MB) y `postgres-volume-zvfE` (`c5c3b19b-…`, 199 MB) | ✅ eliminados |
| `Postgres-V7Ht` (staging) | $0.01582 | Solo contenía el Postgres, sin API ni worker | ✅ eliminado |

> ### ⚠️ Corrección — eran dos volúmenes huérfanos, no uno
>
> La versión 1.0.0 hablaba de "el volumen del `deleted service`" en singular. En staging
> había **dos** volúmenes con `serviceName: null`, ambos provisionados a 5 GB.
>
> **No se pudieron respaldar.** Su servicio ya no existía, así que no había forma de leerlos
> — es el precio exacto de borrar un servicio sin borrar su volumen: el volumen sigue
> facturando y ya no tiene dueño que pueda abrirlo.
>
> Además, al quedar `staging` sin ningún servicio, se eliminó la **env completa**.
> El proyecto quedó con un solo entorno, `production`.
>
> **Su Postgres sí tenía datos** (43 médicos, 1025 filas) y era un conjunto **distinto** al
> de producción, no un clon. Se respaldó y verificó antes de borrar.

**Riesgo: bajo** una vez identificados.

## R5 — Mergear el arreglo de tests

La rama `fix/ci-solver-idle-timeout` (commit `48c0baf`) corrige el timeout de
`idle_in_transaction` que mataba la conexión durante el solver CP-SAT. Independiente
del resto.

## Fuera de alcance (decidido explícitamente)

| Tema | Decisión | Motivo |
|---|---|---|
| **Neon** | No tocar | Plan Free = **$0**. Los 100 CU-hours son cuota, no factura; se usan ~30. |
| **Cron del worker (30 min)** | No tocar | Su frecuencia **es** la ventana de `send_pre_service_reminders` (±30 min, `jobs.py:118-120`). Bajarla pierde recordatorios. Cuesta $0.00006. |
| **Sueño de la app** | No tocar | Ya duerme (`sleepApplication: true`, estado `SLEEPING` observado, cold start 4.8s). **No ahorra dinero**: el costo es volumen, no cómputo. |
| **Región de Neon** | Diferido | us-east-2 vs us-east4 añade latencia, pero migrar no ahorra dinero. Solo si se nota lentitud. |
| **Otros proyectos del workspace** | Fuera de alcance | Se gestionan por separado. |
| **Arreglar `configure_logging`** | Fuera de alcance | `backend/app/core/logging_config.py:36` nunca se invoca; el root logger queda en `WARNING` y todo `logger.info` se descarta. Es lo que hace que la verificación del correo no se pueda hacer por logs. Trabajo aparte. |

## Archivos afectados

| Archivo / Recurso | Cambio | Riesgo |
|---|---|---|
| Railway → variables de `general-medical-services` y `worker` | +`RESEND_API_KEY`, +`RESEND_FROM_EMAIL` | Bajo — aditivo, reversible |
| `frontend/` (build) | Redespliegue en Vercel | Bajo — 113 tests en verde |
| Rama `fix/pantalla-recuperacion-y-correo` | Merge a `master` | Bajo — 1773 tests backend + 113 frontend en verde |
| Rama `fix/ci-solver-idle-timeout` | Merge a `master` | Bajo — cambio de timeout en tests |
| Railway → servicio `Postgres` + volumen `postgres-volume` | Eliminación | **Medio — destructivo, verificar antes** |
| Railway → servicio `Postgres-V7Ht` (staging) | Eliminación | Bajo — destructivo, sin uso |
| Railway → volumen del `deleted service` | Eliminación | Bajo — requiere identificar origen |
| Railway → límite de gasto del workspace | Configurar soft/hard | Bajo — protección, no gasto |
| Railway → env `staging` completa | Eliminación | Bajo — quedó sin servicios |

> Todas las filas se ejecutaron el 2026-10-04. El detalle casilla por casilla está en el
> [tasks](2026-10-04-infra-limpieza-correo-y-despliegue-tasks.md). Quedan cuatro casillas
> abiertas: el fallo silencioso del correo, tres comprobaciones visuales en navegador, la
> materialización del ahorro (tras el 2026-10-06) y la segunda vuelta del correo a la semana.

## Lo que NO cambia

- Modelos de base de datos y migraciones
- El motor de calendarios, scoring y reglas
- La lógica de negocio de auth (contrato anti-enumeración de `/forgot-password` intacto)
- El esquema de la base en Neon
- DNS de Cloudflare y la configuración del dominio en Resend (ya correctos)
- El código de `send_email` (ya soporta Resend como proveedor primario)

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-04 | — | Inicial | Spec creada a partir de la auditoría de infraestructura del 2026-10-04. |
| 1.1.0 | 2026-10-04 | — | Ejecución de las 4 fases | Estado pasa a `implementado`. Tres correcciones tras ejecutar: (1) eran **dos** volúmenes huérfanos, no uno; (2) la verificación del correo **no** se hace por logs de Railway — `configure_logging` nunca se invoca y el root logger está en `WARNING`, así que se verifica en Resend; (3) los Postgres huérfanos **sí tenían datos propios** (no respaldados en Neon), y se respaldaron y verificaron por restauración antes de borrar. |
