# Tasks — Puesta al día de Turnos Médicos: limpieza de infraestructura, correo y despliegue

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-04-infra-limpieza-correo-y-despliegue.md](2026-10-04-infra-limpieza-correo-y-despliegue.md)

**Goal:** Dejar el proyecto de Turnos Médicos con el correo de restablecimiento funcionando, el arreglo de la pantalla desplegado, y los recursos huérfanos de Railway eliminados.

**Architecture:** El orden va por impacto real al usuario, no por ahorro. Las fases 1 y 2 arreglan lo que el usuario final ve (correo roto, pantalla rota); la fase 3 es limpieza destructiva y va al final, con puertas de verificación antes de cada borrado. Toda la fase 3 usa `railway` CLI contra el proyecto `generous-rebirth`.

**Tech Stack:** Railway CLI 5.63.1, Vercel (frontend), Resend (correo), Neon (DB), Git

**Proyecto Railway:** `generous-rebirth`
**Env producción:** `production`
**Servicios (tras la limpieza):** la API (`general-medical-services`) y el worker (`worker`)

> Los UUIDs de infraestructura (proyecto, entorno, servicios, volúmenes) se omiten a
> propósito: **este repositorio es público**. Se obtienen con `railway status --json` o
> `railway service list`.

**Contexto y justificación completa:** [2026-10-04-infra-limpieza-correo-y-despliegue.md](2026-10-04-infra-limpieza-correo-y-despliegue.md)

---

## Estado de ejecución (2026-10-04)

Las cuatro fases se ejecutaron el mismo día. Quedan **dos casillas** abiertas, ambas
marcadas abajo como `PENDIENTE`, y **tres correcciones** a lo que decía el plan original:

| # | El plan decía | La realidad |
|---|---|---|
| 1 | Un volumen huérfano | **Dos** (`ooV5` y `zvfE`), más el de `Postgres-V7Ht` |
| 2 | Verificar el envío leyendo logs de Railway | **No funciona** — ver Task 1.3 |
| 3 | Los Postgres huérfanos no tenían datos | **Sí tenían**: 69 médicos / 5 usuarios el de producción, 43 médicos el de staging |

---

## Evidencia del baseline (medido 2026-10-04)

| Medición | Comando | Resultado |
|---|---|---|
| Costo del proyecto, 13 días | `railway usage projects --project <id>` | $0.07579 |
| Huérfanos vs en uso | ídem, por servicio | $0.05718 (75.4%) vs $0.01861 |
| Estado de la API | `railway service list` | `SLEEPING` (duerme correctamente) |
| Cold start medido | `curl /api/health` tras dormir | 4.81s |
| CORS | `curl -X OPTIONS` con Origin de Vercel | 200, origen permitido |
| Assets del frontend | `curl https://general-medical-services.vercel.app` | `index-CTh1GDl6.js` + `index-o_83VCg3.css` — sin cambios desde 2026-09-11 |
| `RESEND_API_KEY` en API y worker | `railway variable list` | AUSENTE (en ambos) |

---

## Fase 1 — Correo (R1)

**Impacto:** alto — hoy un encargado que olvida su contraseña queda bloqueado.

### Task 1.1 — Obtener la API key de Resend

- [x] **Verificar el dominio**: `rafenixcore.com` en `verified` con `Sending: enabled`
- [x] **Crear la API key**: `turnos-medicos-railway-produccion`, permiso *sending_access*
      restringido al dominio `rafenixcore.com`

> El permiso mínimo se comprueba: `GET /domains` con esa key devuelve **401** con
> `{"name":"restricted_api_key","message":"This API key is restricted to only send emails"}`.
> Eso es la restricción funcionando, no un fallo.

### Task 1.2 — Setear las dos variables en Railway

⚠️ **Las dos juntas.** Solo con `RESEND_API_KEY`, el remitente por defecto del código
(`noreply@turnos-medicos.com`) hace que Resend responda **403**, y el síntoma se
confunde con una falla del proveedor.

- [x] **API**: `RESEND_API_KEY` + `RESEND_FROM_EMAIL=noreply@rafenixcore.com`
- [x] **Worker**: ídem (el worker también envía: `process_notification_queue`)
- [x] **Read-back**: ambas variables confirmadas por igual en los dos servicios

### Task 1.3 — Redesplegar y verificar end-to-end

⚠️ Railway **no** recarga variables en caliente: sin redesplegar, el cambio no aplica.

- [x] **Redesplegar** API y worker (`railway redeploy`, ambos `SUCCESS`)
- [x] **Disparar** un `/forgot-password` real con un correo de una usuaria `encargado` activa
- [x] **Verificar en Resend** que el correo salió y llegó
- [ ] **PENDIENTE — Verificar el fallo silencioso**: forzar un error y confirmar que el
      endpoint sigue devolviendo **200** y que aparece la alerta en la campana

> ### ⚠️ Corrección: la verificación NO se hace por logs de Railway
>
> El plan original decía "verificar en los logs: `Email sent to … via Resend`". **Eso no
> puede funcionar.** `configure_logging` (`backend/app/core/logging_config.py:36`) nunca se
> invoca, así que el root logger queda en `WARNING` y todo `logger.info` se descarta — el
> mensaje de éxito incluido. Un **fallo** sí aparecería (`logger.error`/`exception`).
>
> Consecuencia práctica: la ausencia de la línea de éxito **no** significa que el envío
> falló. Se deduce lo contrario. La fuente de verdad es el panel/API de Resend.
>
> Verificación que sí sirvió:
> ```
> (destinatario de prueba)
> "Recuperacion de contrasena — Sistema de Turnos Medicos"
> Status: delivered · 2026-10-04 14:09 UTC
> ```
> (Arreglar `configure_logging` es trabajo aparte; ver "Fuera de alcance" del spec.)

---

## Fase 2 — Despliegue del arreglo (R2, R5)

**Impacto:** alto — el bug de la pantalla reportado originalmente sigue vivo en producción.

> **Método:** para no tocar `master` antes de validar, los dos merges se hicieron en una
> rama de integración desechable `integration/limpieza-infra` creada desde `master`. Solo
> cuando la suite entera pasó se hizo fast-forward de `master` a esa rama. La rama de
> integración se borró después.

### Task 2.1 — Mergear el arreglo de la pantalla

- [x] **Revisar el diff**: 11 archivos, 785 inserciones (+156 borrados) — coincide
- [x] **Correr los tests antes del merge**: **1773 passed** backend (35 deselected,
      1 xfailed) · **113 passed** frontend · `npm run build` limpio
- [x] **Mergear** `fix/pantalla-recuperacion-y-correo` (`fbd36c4`) a `master`
- [x] **Verificar** que las clases muertas no vuelven: cero en código fuente. Solo
      sobreviven dentro de los propios tests, como aserciones de regresión

### Task 2.2 — Mergear el arreglo de tests (R5)

- [x] **Revisar**: 1 commit, `48c0baf`
- [x] **Mergear** `fix/ci-solver-idle-timeout` a `master`

### Task 2.3 — Desplegar

- [x] **Backend**: push a `master` (`315bb29..f35404c`) → Railway redespliega
- [x] **Frontend**: mismo push → Vercel redespliega
- [x] **Verificar el deploy**: los assets cambiaron a `index-DsyyoK4a.js` + `index-DufsZIAM.css`

### Task 2.4 — Verificar el arreglo en producción

- [x] **Verificar el CSS servido** (no solo el build local):
      `.auth-panel--narrow{width:min(100%,440px)}` — presente en el bundle de producción,
      y cero ocurrencias de `login-card`/`form-hint`
- [x] **Verificar el JS servido**: referencia `auth-panel--narrow`, ninguna clase muerta
- [x] **`/forgot-password` responde** 200
- [ ] **PENDIENTE — Medir la tarjeta** en un navegador: ~440px, centrada
- [ ] **PENDIENTE — Probar móvil** a 400px: sin scroll horizontal
- [ ] **PENDIENTE — Recorrer las ramas**: `/set-password?token=basura` → "Enlace inválido"

> Las tres pendientes son comprobaciones **visuales en navegador**; no se hicieron. Lo
> verificado es que la regla CSS correcta se sirve en producción, que es lo que delató el
> bug la primera vez.

---

## Fase 3 — Limpieza de huérfanos (R3, R4)

**Impacto:** ahorro ~$0.132/mes + elimina superficie de ataque.
**Esta fase es destructiva.** Cada borrado lleva puerta de verificación previa.

### Task 3.0 — Respaldo previo (añadida sobre el plan)

- [x] **Volcar** los dos Postgres legibles con `pg_dump` 18 (vía contenedor: el servidor es
      v18 y el `pg_dump` local es v16, que se niega a dumpear de un servidor más nuevo).
      Destino: `~/backups-turnos-medicos/` — 4 archivos, ~1.2 MB
- [x] **Verificar restaurando**, no solo comprobando que el archivo existe: cada dump se
      restauró en un Postgres 18 desechable y se cotejaron los conteos fila por fila
      (producción 21 tablas; staging 1025 filas)

### Task 3.1 — Verificar que nada usa el Postgres de Railway (PUERTA)

- [x] **Confirmar el apuntado**: `DATABASE_URL` de API y worker apunta a un host
      `*.neon.tech` (**Neon**), no a `railway.internal` ni a `postgres-production`
- [x] **Confirmar sin otro consumidor**: producción solo tenía API, worker y Postgres
- [x] **Confirmar el volumen**: `postgres-volume`, 223 MB usados de 5 GB, `/var/lib/postgresql/data`
- [x] **Decisión**: nada apuntaba ahí → proceder

### Task 3.2 — Eliminar el Postgres de Railway (R3)

- [x] **Anotar** los ids del servicio y del volumen antes de borrar
- [x] **Eliminar** el servicio `Postgres`
- [x] **Eliminar** el volumen `postgres-volume`
- [x] **Verificar** que el dominio deja de usarse (la baja es diferida, ver Task 3.5)

### Task 3.3 — Identificar y eliminar los volúmenes del `deleted service` (R4)

- [x] **Identificar**: **dos** volúmenes sin servicio — `postgres-volume-ooV5`
      (`b86478c1-…`, 198 MB) y `postgres-volume-zvfE` (`c5c3b19b-…`, 199 MB)
- [x] **Confirmar** que ninguno está montado en un servicio vivo (`serviceName: null`)
- [x] **Eliminar** ambos
- [x] **Anotar**: ⚠️ **no se pudieron respaldar**. Su servicio ya no existía, así que no
      había forma de leerlos. Es el precio de borrar un servicio sin borrar su volumen:
      el volumen queda facturando y ya sin dueño que lo pueda abrir

### Task 3.4 — Eliminar el staging huérfano (R4)

- [x] **Confirmar** que `staging` solo contenía `Postgres-V7Ht`, sin API ni worker
- [x] **Respaldo** del Postgres de staging (43 médicos, 1025 filas — **conjunto distinto**
      al de producción, no un clon) y verificación por restauración
- [x] **Decisión**: eliminar la env `staging` completa, no solo el servicio
- [x] **Eliminar** `Postgres-V7Ht`, su volumen `postgres-volume-AJXF`, y la env `staging`

### Task 3.5 — Verificar el ahorro

- [x] **Leer el costo** post-limpieza
- [x] **Comparar** contra el baseline de $0.07579 / 13 días
- [ ] **PENDIENTE — Confirmar que el total bajó a ~$0.019** (solo API + worker)

> ⚠️ **Railway difiere las eliminaciones de volumen 2 días.** Los cuatro volúmenes quedaron
> en `isPendingDeletion: true` con `deletedAt` **2026-10-06**. El costo **todavía no bajó**:
> seguía en $0.0784 con tres entradas `deleted service`. La baja se materializa después de
> esa fecha. No dar el ahorro por confirmado antes.

---

## Fase 4 — Cierre

### Task 4.1 — Poner límite de gasto en el workspace

Hoy `usageLimit: null` — no hay ninguna protección contra un gasto descontrolado.

- [x] **Leer el estado actual**: límite de workspace en `null`; el de *agente* sí existía
      (hard $5, usados $2.42)
- [x] **Definir montos**: **soft $8 / hard $15** (gasto proyectado del workspace ~$6.60/mes)
- [x] **Setear** y verificar: `usageLimit: {softLimit: 8, hardLimit: 15}`

### Task 4.2 — Verificación final y no-ops documentados

- [ ] **PENDIENTE — Confirmar que el correo funciona end-to-end por segunda vez** (una
      semana después, para descartar fallos intermitentes). Se verifica en **Resend**, no
      en los logs — ver Task 1.3
- [x] **Confirmar** que el worker sigue corriendo: cron `*/30 * * * *`, deploy `SUCCESS`,
      próxima corrida programada
- [x] **Confirmar** que la app sigue durmiendo: `SLEEPING` observado, cold start ~5s
- [x] **Documentar los no-ops** para que nadie los "optimice" por error:
      - Neon Free = $0 → no hay nada que ahorrar
      - El cron de 30 min **es** la ventana de `send_pre_service_reminders` (±30 min) → no bajar
      - El sueño ya funciona → no ahorra dinero porque el costo es volumen, no cómputo
      - La región de Neon (us-east-2 vs us-east4) solo afecta latencia, no costo

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué arregla | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 1 | Fase 1 | Correo roto → usuarios desbloqueados | Bajo | ✅ hecho |
| 🔴 2 | Fase 2 | Pantalla rota en producción | Bajo | ✅ desplegado |
| 🟠 3 | Fase 3 | $0.132/mes + Postgres público expuesto | **Medio — destructivo** | ✅ hecho (baja diferida a 2026-10-06) |
| 🟡 4 | Fase 4 | Protección de gasto + cierre | Bajo | 🔶 límite puesto |

## Casillas abiertas

1. **Fallo silencioso del correo** (Task 1.3) — forzar un error y ver la alerta en la campana.
2. **Verificación visual** en navegador (Task 2.4) — 440px, móvil, ramas de `/set-password`.
3. **Ahorro materializado** (Task 3.5) — reconfirmar el costo después del 2026-10-06.
4. **Correo, segunda vuelta** (Task 4.2) — una semana después, vía Resend.
