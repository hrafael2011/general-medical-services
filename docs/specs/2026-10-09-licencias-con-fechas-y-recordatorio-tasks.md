# Tasks — Licencias con fechas y recordatorio de reintegro

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-09-licencias-con-fechas-y-recordatorio.md](2026-10-09-licencias-con-fechas-y-recordatorio.md)

**Goal:** Registrar la ausencia de un médico —**eje 2, "fuera de servicio"**— con fecha de inicio
y de regreso (o **indefinido**), y avisar por Telegram y campana **X días antes** del reintegro.

> **"Inhabilitado" son ocho ejes independientes** (sistema, servicio, misiones, pool,
> restricciones, disponibilidad, áreas, borrado). Esta spec trabaja **solo el eje 2**; los otros
> siguen igual. La Fase 0 corrige los dos defectos que la investigación destapó.

**Architecture:** Se reutiliza `doctor_restrictions`, que ya tiene `starts_at` / `ends_at` y que el
motor de asignación **ya respeta** — así el médico queda fuera **solo en ese rango** y vuelve solo.
Una pantalla nueva en la ficha del médico unifica las dos representaciones de "no disponible"
(la restricción con fechas y el flag `service_active` sin fecha) para que el encargado no tenga que
saber que son dos cosas. El recordatorio es un job más del scheduler, con la idempotencia que ya
existe en `notification_events`: la clave incluye la fecha de regreso, así que **editar la fecha
re-arma el aviso sin columna nueva**.

**Tech Stack:** FastAPI, SQLAlchemy, React + TanStack Query, scheduler del proyecto, pytest, vitest

**Estado:** Las **Fases 0 a 6** están hechas, desplegadas y verificadas en producción
(2026-10-10). Las **Fases 7 a 11** son la **extensión v1.3.0** —*una sola funcionalidad*—:
**aceptadas por el usuario y pendientes de autorización para implementar**.

---

## Fase 0 — Correcciones previas (antes de construir encima)

> Estas dos correcciones salieron de investigar **los ocho ejes** de inhabilitación. Sin ellas, la
> función nueva se apoyaría en una base que ya está inconsistente.

### Task 0.1 — Unificar las dos puertas de desactivación

**Archivos:** `backend/app/application/doctors/service.py` (`deactivate_service` ≈ línea 491 y
`update` ≈ línea 296)

Hoy hay **dos caminos** para lo mismo y dejan resultados distintos:

| | Botón "Desactivar" | Editar el médico |
|---|---|---|
| Motivo | ✅ | ❌ |
| Quita de misiones | ✅ | ❌ |
| Auditoría | `doctor_service_deactivated` | `doctor_updated` |

Eso explica los datos reales de producción: **2 médicos sin motivo** y **2 fuera de servicio pero
todavía en misiones**.

- [x] **Decidir** cuál es el comportamiento correcto. **Decidido:** el de la puerta A, más el aseo
      que ya hacía la puerta B (disponibilidad, áreas y asignaciones de borrador). Desactivar deja
      **motivo + fuera de misiones + auditoría + alertas de misiones**, venga de donde venga.
- [x] **Hacer que `update`**, cuando recibe `service_active=False`, exija y guarde motivo y
      sincronice misiones. El motivo es obligatorio (`reason_required`) y se valida contra el
      catálogo **y contra el sexo del médico**, con el mismo validador que usa el botón dedicado.
      Reactivar limpia el motivo; `participa_misiones` solo se toca si el cliente no lo pidió.
- [x] **Unificar el evento de auditoría**: desactivar emite `doctor_service_deactivated` y
      reactivar `doctor_service_reactivated`, se entre por donde se entre. Los demás campos
      cambiados se siguen registrando como `doctor_updated`.
- [x] **Corregir los datos existentes** ✅ confirmado por el usuario (2026-10-10): motivo
      **OTROS** con una nota de que fue una desactivación histórica sin motivo registrado, y
      fuera de misiones. **Corrección al spec: no son 4 registros, son 2 médicos** (cada uno
      tenía los dos problemas a la vez; la auditoría de mayo muestra que ambos entraron por la
      puerta B con `service_active: False`, `participa_misiones: True`). Script:
      `scripts/fix_absence_inconsistencies.py`, con `--dry-run`, idempotente.

### Task 0.2 — Que el motivo diga si espera regreso

**Archivos:** `backend/app/infrastructure/db/models/catalogs.py` (o `doctors.py`),
migración nueva, `backend/app/domain/catalogs.py`

- [x] **Añadir** al catálogo de motivos un campo del tipo `expects_return` (booleano), con
      valor por defecto `True` (avisar de más es más barato que no avisar).
- [x] **Migración** `a2446a0123b3` que lo agrega y **clasifica los 8 motivos de producción**:
      *sin regreso* → `direccion`, `gerencias_medicas` (y `no_service` del catálogo sembrado);
      *con regreso* → el resto, incluidos CONCURSO y OTROS, que quedaron "a decidir" y se cargan
      con el valor conservador. **Verificada de verdad**, no solo revisada: en una base desechable
      se subió hasta la revisión anterior, se sembraron los 8 códigos reales más uno inventado,
      se corrió el `upgrade` (los dos puestos quedan en `false`, el inventado en `true`), el
      `downgrade` (la columna desaparece) y el `upgrade` otra vez.
- [x] **Exponerlo** en la API del catálogo (`DeactivationReasonRead`, crear y actualizar).
- [x] **Añadirlo a la pantalla de Catálogos**: columna "¿Espera regreso?" y casilla al crear y al
      editar. 6 tests, uno de ellos específico de la columna nueva.

> ⚠️ Es la **única migración** de esta spec, y **está autorizada por el usuario** (2026-10-09).

### Task 0.3 — Carga inicial de la clasificación

- [x] **Cargar** los valores iniciales de los 8 motivos existentes (en la migración, que es donde
      corresponde: es un dato, no una regla).
- [x] **Confirmar** con el usuario los dos que quedan a decidir. **Sin respuesta todavía**, así que
      se aplicó el criterio previsto: CONCURSO y OTROS se cargan **con regreso** (más conservador)
      y el administrador lo cambia en un clic desde la pantalla de Catálogos.

---

## Fase 1 — Fechas en la ausencia (backend)

### Task 1.1 — Confirmar la API existente

**Archivo:** `backend/app/api/routes/availability.py` (líneas 133-183)

- [x] **Revisar** los contratos actuales. `ends_at` ya admite nulo y `severity` acepta
      `hard_block`; el tipo es `license|restriction`. Lo que **no** existía es forma de **editar**
      una ausencia ya registrada, y AC6 la necesita: se añadió
      `PATCH /availability/restrictions/{id}` con su evento de auditoría `restriction_updated`.
      **El plan decía "se reutilizan los endpoints existentes" y eso era falso**: sin este
      endpoint, editar la fecha no era posible y el re-armado del aviso no tenía por dónde entrar.
- [x] **Verificar** que `ends_at` nulo bloquea desde `starts_at` sin fecha de fin
      (`list_active_restrictions_for_doctor`: `r.ends_at is None or r.ends_at >= on_date`) y que el
      recordatorio **no** lo toca (el job filtra `ends_at IS NOT NULL`).
- [x] **Comprobar** que `restriction_type="license"` y `severity="hard_block"` se ajustan a una
      ausencia, que es como los usa la pantalla.

> El endpoint **ya existe**: esta tarea es de reconocimiento, no de construcción. Si el contrato
> ya sirve, no se toca la ruta.

### Task 1.2 — Que el motivo sea el del catálogo

- [x] **Confirmar** que la restricción usa `reason_id` → **el mismo** catálogo de motivos que la
      desactivación (FK a `deactivation_reasons`), es decir el de 8 motivos de producción.
- [x] **Rechazar** motivos que no apliquen al sexo del médico: se añadió el mismo validador que usa
      `deactivate_service`, más la comprobación de que el motivo exista (`reason_not_found`) y de
      que la fecha de regreso no sea anterior a la de inicio (`invalid_date_range`).

### Task 1.3 — Indefinido

- [x] **Definir** "indefinido" como `ends_at = NULL`, documentado en el esquema
      (`RestrictionPayload.ends_at: string | null` con el comentario) y en la pantalla, que lo
      explica en el propio formulario.
- [x] **Comprobar** las dos cosas: bloquea desde `starts_at` sin fin, y **no** entra en el
      recordatorio. Cubierto por el test `test_indefinido_no_genera_nada`.

---

## Fase 2 — Los días de aviso (configuración)

### Task 2.1 — Clave en `system_settings`

- [x] **Sembrar** `notifications.license_reminder_days` con valor **2** en
      `seed_initial_catalogs`, con `GET` y fallback al valor por defecto (si lo guardado no es un
      entero positivo, se usa 2: un dato mal escrito no puede tumbar el job que avisa).
- [x] **Exponerlo** en una pestaña nueva de Catálogos, **"Avisos"**, editable sin tocar la base
      (`GET`/`PUT /catalogs/notification-settings`).

> **Sin migración**: es una fila de `system_settings`, no una columna nueva. El valor por registro
> queda fuera a propósito (ver la nota del spec).

---

## Fase 3 — El recordatorio (backend)

### Task 3.1 — El job

**Archivo:** `backend/app/application/scheduler/jobs.py` (añadir un quinto job)

- [x] **Buscar** restricciones con `ends_at` no nulo, no levantadas, con la fecha de regreso en la
      ventana `hoy .. hoy + N`. La ventana es **abierta por abajo** a propósito: así una ausencia
      registrada cuando ya estaba dentro del plazo también avisa.
- [x] **No** incluir las indefinidas (`ends_at IS NULL`) ni las ya vencidas.
- [x] **Crear la alerta en la campana** con nombre, motivo y fecha, `action_url` a la ficha del
      médico, y una sola alerta abierta por ausencia. Si la fecha se edita y la alerta seguía
      abierta, **se reescribe**: no puede quedarse mostrando una fecha de reintegro vieja.
- [x] **Encolar el aviso por Telegram** a los usuarios con `telegram_chat_id` y el permiso
      `receive_escalation_alerts`, con el mismo patrón que `check_unconfirmed_escalamiento`.
      **El mensaje dice quién, por qué y cuándo vuelve** (R8). Sin destinatarios vinculados el
      aviso no sale, pero la campana se crea igual.

### Task 3.2 — Idempotencia y re-armado

- [x] **Usar** una clave de idempotencia que incluye el id de la restricción, la fecha de regreso
      **y el destinatario**: `license_expiring:{restriction_id}:{ends_at}:{user_id}`.
- [x] **Verificar** los tres escenarios, con tests que los comprueban de verdad (y comprobados por
      mutación: quitar la fecha de la clave hace fallar el test del re-armado, y quitar el límite
      inferior de la ventana hace fallar el de la ausencia vencida).

> Es el punto delicado del spec (AC5 y AC6). La clave única de `notification_events` ya lo
> resuelve, pero hay que probarlo en los tres escenarios.

### Task 3.3 — Registrar el job

- [x] **Añadirlo** a `_TASKS` en `run_once.py` como quinto job, así que el worker lo ejecuta en su
      cron de cada 30 minutos.
- [x] **Comprobar** que es idempotente: correrlo dos veces seguidas no duplica nada (test).

---

## Fase 4 — La pantalla (frontend)

### Task 4.1 — Sección "No disponible" en la ficha del médico

**Archivo:** `frontend/src/features/doctors/` (lista y ficha del médico)

- [x] **Listar** lo vigente y lo programado, unificando las dos fuentes, en la sección
      **"No disponible"** de la ficha del médico (`AbsenceSection.tsx`):
      ausencia con fechas → *"LICENCIAS MEDICAS · 01/03/2026 → se reintegra el 15/03/2026"*;
      ausencia sin fecha (el flag) → *"Sin fecha de regreso (hasta reactivarlo)"*, en rojo.
- [x] **Distinguir visualmente** vigente (rojo), programada (azul) y anteriores (plegadas, en gris).
- [x] **Mostrar** la fecha de reintegro destacada, con la frase "se reintegra el …".

### Task 4.2 — El formulario

- [x] **Pedir**: motivo (catálogo), desde, hasta y la opción **Indefinido**.
- [x] **Deshabilitar** "hasta" cuando se marca Indefinido y explicar que en ese caso no habrá
      recordatorio. Además, **el motivo propone**: si no espera regreso (DIRECCION), se marca
      Indefinido solo, y el encargado puede cambiarlo a mano (AC9).
- [x] **Permitir editar** una ausencia existente (`PATCH`) y **levantarla** (`/lift`).
- [x] **Validar** desde ≤ hasta antes de enviar, y mostrar el error sin llamar a la API.

### Task 4.3 — Cliente de API

**Archivo:** `frontend/src/api/doctors.ts`

- [x] **Añadir** las funciones de listar, crear, editar y levantar restricciones en
      `frontend/src/api/doctors.ts` (`availabilityApi`).

---

## Fase 5 — Tests

- [x] **Indefinido**: bloquea desde la fecha y **nunca** genera aviso (AC3).
- [x] **Ventana**: avisa dentro de los N días, no antes ni después (AC4).
- [x] **Idempotencia**: dos corridas del job, un solo aviso (AC5).
- [x] **Re-armado**: cambiar la fecha vuelve a avisar, y volver a la anterior no (AC6).
- [x] **Configuración**: la ventana sale del ajuste, no de un número escrito en el código.
- [x] **Sin destinatarios**: la campana se crea igual y no se encola nada.
- [x] **No regresión**: los médicos desactivados sin fecha siguen igual, y las dos puertas de
      desactivación dejan el mismo estado (suite completa de `doctors`, `availability` y `audit`).
- [x] **Frontend**: 8 tests de la sección nueva —lista la ausencia con fechas, lista la que no
      tiene fecha, distingue programada de vigente, propone Indefinido según el motivo, valida el
      rango, guarda `ends_at: null`, levanta y edita sin crear otra. Comprobados por mutación.
- [ ] **Elegibilidad**: dentro del rango se rechaza; fuera del rango se permite sin intervención
      (AC2). **Ya estaba cubierto** por los tests de elegibilidad existentes, que siguen en verde.

---

## Fase 6 — Verificación en vivo ✅ HECHA (2026-10-10, en producción)

Se hizo con **un médico real** (ANGIE VEGA QUITERIO) y una ausencia real de 2 días
(2026-10-11 → 2026-10-12), que se **levantó al terminar** y cuya alerta de prueba se descartó, para
no dejar ruido en la campana. El bloqueo se comprobó llamando al **mismo método del motor de
calendario** que decide en producción (`CalendarEngine._has_hard_block`), alimentado por la misma
consulta que usa (`list_active_restrictions_for_doctor`): nada de lógica paralela.

| # | Qué se comprobó | Resultado |
|---|---|---|
| 1 | Antes de la fecha de inicio el médico sigue asignable | ✅ sin bloqueo el 10, 11, 12 y 13 antes de crear la ausencia |
| 2 | Dentro del rango se rechaza | ✅ bloqueado el 11 y el 12 |
| 3 | Fuera del rango vuelve solo, sin reactivar nada | ✅ sin bloqueo el 10 (antes) y el 13 (después) |
| 4 | El aviso aparece en la campana con quién, por qué y cuándo | ✅ alerta abierta: *"…se le acaba la ausencia el 2026-10-12. Motivo: LICENCIAS MEDICAS. Se reintegra en 2 días."* |
| 5 | No se repite al correrlo otra vez | ✅ 2ª corrida: `alerts_created: 0`, una sola alerta |
| 6 | Editar la fecha re-arma | ✅ la alerta se reescribió con la fecha nueva |
| 7 | Una ausencia Indefinida no genera nada | ✅ `{'reminders': 0}` |
| 8 | Levantarla la quita de en medio | ✅ sin bloqueo en ninguna de las 4 fechas |

- [x] **Registrar** una licencia que empiece en el futuro y comprobar que el médico sigue asignable
      antes de esa fecha (fila 1).
- [x] **Intentar asignarlo** dentro del rango y comprobar el rechazo (fila 2, y fila 3 al salir).
- [ ] ⚠️ **Provocar un aviso y confirmar que LLEGA por Telegram**: **no se pudo comprobar el envío**,
      porque **sigue sin haber nadie con Telegram vinculado** (0 de 5 usuarios). Lo que sí está
      comprobado es que el job **encola** el aviso cuando hay destinatario (tests con destinatario
      real en base de datos) y que en producción quedó `0 encolados` justamente porque no hay
      ninguno. **Este es el único punto del spec que queda abierto**, y no depende del código.
- [x] **Editar** la fecha y confirmar que vuelve a avisar (fila 6).
- [x] **Confirmar** que una ausencia Indefinida no genera nada (fila 7).

> El cron del worker (18:30 UTC) ejecutó los **cinco** jobs, incluido
> `send_license_return_reminders -> {'reminders': 0, 'alerts_created': 0}`, sin errores: el job
> nuevo corre en producción.

---

## Extensión v1.3.0 — Una sola funcionalidad

> **Decidido por el usuario (2026-10-10).** Hoy hay **dos** formas de decir "este médico no está
> disponible" y dejan estados distintos: es lo que produjo los datos inconsistentes. Se unifican en
> una sola: la **ausencia**. El estado "activo para servicio" deja de ponerse a mano y se **deriva**
> de ella. **Nada de esta extensión está implementado todavía.**

## Fase 7 — Arreglar la generación (BLOQUEANTE, va primero)

**El bug:** `generation_service.py` carga las restricciones **una sola vez con la fecha del día 1**
(`list_active_restrictions_for_doctor(d.id, on_date=first_day)`, en los dos sitios: ≈126 y ≈319).
Esa consulta descarta lo que empiece después de esa fecha, así que una licencia del **3 al 10** no
entra en el contexto, `CalendarEngine._has_hard_block` no la ve, y **el generador asigna turnos a un
médico de licencia**. La asignación manual no tiene el fallo porque consulta por la fecha del turno.

- [ ] **Cargar** las restricciones de forma que cubran **todo el mes** que se va a generar (o
      consultar por día, como hacen `_run_eligibility`, `_run_eligibility_with_force` y
      `get_eligible_doctors_for_slot`).
- [ ] **Comprobar** los **dos** sitios, no solo uno.
- [ ] **Test de regresión**: una ausencia del **20 al 25** → el generador **no** asigna dentro de
      ese rango y **sí** puede asignar fuera. Comprobado por mutación (que falle sin el arreglo).
- [ ] **Confirmar** que no se degrada el rendimiento de la generación (una consulta por médico, no
      una por médico y día, si se puede evitar).

> Es lo único de toda la spec que es un **defecto**, no una decisión. Hoy pasa desapercibido porque
> el flag tapa el hueco; con una sola puerta, dejaría de taparlo.

## Fase 8 — Una sola puerta en la interfaz

- [ ] **Quitar** el bloque *"Razón para desactivar servicio"* del perfil del médico (el desplegable
      de motivo y el botón "Desactivar para servicio").
- [ ] **Quitar** el botón **"Reactivar servicio"**: su equivalente pasa a ser **levantar la
      ausencia**, que ya existe en la sección *No disponible*.
- [ ] **Quitar** la casilla *"¿Hace servicio?"* del formulario de edición y **dejar de mandar
      `service_active`** en el `PATCH`. *(Hoy además está rota: al desmarcarla el backend responde
      `reason_required` porque exige motivo y el formulario no lo manda.)*
- [ ] **Dejar** la sección *No disponible* como **única entrada**, con su formulario cubriendo los
      dos casos: **con fechas** y **Indefinido**.
- [ ] **Revisar los textos** de la pantalla para que "Indefinido" explique que el médico queda fuera
      hasta que se levante la ausencia (no que "no avisa" a secas).

## Fase 9 — El estado derivado

- [ ] **Recalcular** `service_active` como **valor calculado**: activo = **sin ausencia vigente
      hoy** (no levantada, `starts_at <= hoy` y `ends_at` nulo o `>= hoy`).
- [ ] **Hacerlo al escribir**: registrar, editar o levantar una ausencia recalcula ese médico.
- [ ] **Hacerlo al pasar la fecha**: el job del recordatorio (que ya corre cada 30 minutos)
      recalcula los médicos cuya ausencia **empieza o termina** ese día. Sin esto, el estado solo
      cambiaría cuando alguien tocara la ficha.
- [ ] **Copiar** el motivo y el detalle de la ausencia vigente a `service_inactive_reason_id` y
      `service_inactive_detail`, para que la vista **por departamento** siga explicando por qué ese
      médico no está (hoy esos campos solo los llena la desactivación manual).
- [ ] **Revisar los consumidores visibles** y cubrirlos con tests: KPI del tablero, listado de
      médicos, asistente de Telegram (22 consultas), resumen de reportes y vista por departamento.
- [ ] **Decidir** qué pasa con las **asignaciones ya existentes** en calendarios en borrador dentro
      del rango: **no se quitan solas** (decisión 14). Confirmar que se acepta que queden como hueco
      visible para reemplazar.

> **Por qué así y no reescribiendo las consultas:** el flag se lee en **83 sitios del backend y 29
> del frontend**, incluido el SQL del asistente. Mantenerlo como valor calculado deja esos sitios
> funcionando **sin tocarlos**; reescribirlos es mucho más caro para el mismo resultado.

## Fase 10 — Convertir las ausencias actuales

- [ ] **Script** con `--dry-run`, idempotente y auditado (como
      `scripts/fix_absence_inconsistencies.py`): por cada médico fuera de servicio **sin ausencia
      registrada** (hoy 29), crear una ausencia **Indefinida** con su motivo y detalle actuales
      (`ends_at = None`), y dejarlo registrado en la auditoría como "Sistema".
- [ ] **Verificar en simulación** contra producción: cuántos son, con qué motivo y detalle, y qué
      quedaría después.
- [ ] **Ejecutar** en producción y comprobar que **ningún** médico queda "fuera de servicio sin
      ausencia" y que los 29 siguen fuera (no se reactiva a nadie por accidente).

## Fase 11 — Tests y verificación en vivo

- [ ] **Generación**: ausencia de mitad de mes respetada (Fase 7), con test de mutación.
- [ ] **Una sola puerta**: no queda ningún control que ponga `service_active` a mano (test de
      interfaz: el perfil no ofrece desactivar, y el formulario no manda el campo).
- [ ] **Indefinido**: equivale a la desactivación de antes (AC12).
- [ ] **No destruye nada**: disponibilidad, áreas, asignaciones y misiones intactas (AC13).
- [ ] **Estado derivado**: con ausencia vigente, el tablero y el listado lo cuentan como no activo;
      al cumplirse la fecha, vuelve solo (AC15).
- [ ] **En vivo**: registrar una ausencia que empiece **el 20** de un mes y generar ese mes para
      comprobar que no aparece; levantar una Indefinida y ver que vuelve a contar como activo.

---

## Orden de ejecución resumido

| Prioridad | Fase | Qué resuelve | Riesgo | Estado |
|---|---|---|---|---|
| 🔴 0 | Fase 0 | Unificar puertas + motivo con regreso | **Medio** — toca datos y trae la única migración | ✅ hecho (falta correr la corrección en producción) |
| 🔴 1 | Fase 1 | Fechas e indefinido en la API | Bajo — el mecanismo ya existía | ✅ hecho (+ `PATCH` para editar, que no existía) |
| 🟠 2 | Fase 2 | Los días de aviso | Bajo | ✅ hecho |
| 🟠 3 | Fase 3 | El recordatorio | **Medio** — idempotencia y re-armado | ✅ hecho |
| 🟠 4 | Fase 4 | La pantalla | Medio — unifica dos representaciones | ✅ hecho |
| 🟡 5 | Fase 5 | Cobertura | Bajo | ✅ hecho |
| 🟡 6 | Fase 6 | Verificación en vivo | Bajo | ✅ hecha (salvo el envío real por Telegram: no hay nadie vinculado) |
| 🔴 7 | Fase 7 | **La generación respeta la ausencia** | **Alto si se omite** — es un defecto en producción | ⬜ pendiente (bloqueante) |
| 🔴 8 | Fase 8 | Una sola puerta en la interfaz | Bajo | ⬜ pendiente |
| 🟠 9 | Fase 9 | El estado se deriva de la ausencia | Medio — cambia lo que cuentan los contadores | ⬜ pendiente |
| 🟠 10 | Fase 10 | Convertir las 29 ausencias actuales | Medio — toca datos | ⬜ pendiente |
| 🟡 11 | Fase 11 | Tests y verificación en vivo | Bajo | ⬜ pendiente |

## Archivos a tocar

| Archivo | Tipo |
|---|---|
| `backend/app/application/doctors/service.py` | corregir — unificar las dos puertas |
| `backend/app/infrastructure/db/models/catalogs.py` | añadir — `expects_return` en el motivo |
| `backend/app/api/routes/availability.py` | añadir — `PATCH /restrictions/{id}` (editar la ausencia) |
| `scripts/fix_absence_inconsistencies.py` | **nuevo** — cierra el hueco de datos, con `--dry-run` |
| `frontend/src/features/doctors/AbsenceSection.tsx` | **nuevo** — sección "No disponible" |
| `backend/app/application/calendars/generation_service.py` | **corregir** — el bug de la Fase 7 (dos sitios) |
| `frontend/src/features/doctors/DoctorList.tsx` | quitar — bloque "Razón para desactivar servicio" y botón reactivar |
| `frontend/src/features/doctors/DoctorForm.tsx` | quitar — casilla "¿Hace servicio?" y el `service_active` del `PATCH` |
| `backend/app/application/doctors/service.py` | añadir — recalcular el estado desde las ausencias |
| `backend/app/application/scheduler/jobs.py` | añadir — recalcular al empezar/terminar una ausencia |
| `scripts/convert_deactivations_to_absences.py` | **nuevo** — convierte las 29, con `--dry-run` |
| `migrations/versions/` | **nueva** — la única migración de esta spec |
| `backend/app/api/routes/availability.py` | revisar — probablemente sin cambios |
| `backend/app/application/availability/service.py` | revisar/ajustar — `add_restriction` |
| `backend/app/application/scheduler/jobs.py` | añadir — el job de recordatorio |
| `backend/app/application/scheduler/run_once.py` | añadir — registrarlo |
| `backend/app/application/notifications/templates.py` | añadir — plantilla del aviso |
| `backend/app/application/notifications/triggers.py` | añadir — encolar a encargados |
| `backend/app/application/catalogs/service.py` | añadir — la clave de configuración |
| `frontend/src/features/doctors/` | añadir — sección y formulario |
| `frontend/src/api/doctors.ts` | añadir — funciones de restricciones |
| Tests backend y frontend | añadir |

**Sin migraciones de esquema.**

## Casillas abiertas

1. **Depende del canal de Telegram** — si el canal sigue roto, la campana funciona pero el aviso
   por Telegram no llega.
2. **Los días de aviso son globales**, no por registro (decisión 7). Si necesitas plazos distintos
   por caso, es una columna nueva + migración, en otro cambio.
3. **Los desactivados actuales** se quedan como están (decisión 9), pero la Fase 0 propone revisar
   los 2 sin motivo y los 2 que siguen en misiones fuera de servicio.
4. **CONCURSO y OTROS** quedan a decidir en la carga inicial; si no hay respuesta se cargan como
   "con regreso" (avisa de más, no de menos) y el admin lo ajusta desde la pantalla.
5. **La migración** del campo `expects_return` está **autorizada**.
4. **Nada implementado todavía.**

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-09 | — | Spec y tasks creadas. Decisiones confirmadas: fuera solo en el rango, aviso por ambos canales, indefinido entre las opciones, editar re-arma, los desactivados no se tocan, solo Telegram, **2 días de aviso por defecto**. |
| 2026-10-09 | Investigación | Se descubren **8 ejes** de inhabilitación, el catálogo real de 8 motivos (todos `hard_block`) y el estado de los 73 médicos. Se añaden la Fase 0 (unificar puertas + `expects_return`) y los requisitos R11-R15. |
| 2026-10-10 | Fase 0 | Puertas unificadas (motivo obligatorio, validado contra el catálogo y el sexo, misiones sincronizadas, auditoría y alertas iguales). Migración `a2446a0123b3` con `expects_return`, verificada en base desechable con los códigos reales. `expects_return` editable en Catálogos. **Corrección al spec: los "4 registros" inconsistentes son 2 médicos**, no 4. |
| 2026-10-10 | Fases 1-2 | `PATCH /restrictions/{id}` (editar la ausencia, que no existía) con validación de fechas, motivo y sexo. Ajuste `notifications.license_reminder_days` (2 por defecto, con fallback) y pestaña "Avisos". |
| 2026-10-10 | Fase 3 | Job `send_license_return_reminders` como quinto job del worker: alerta en la campana + aviso por Telegram, idempotente por `license_expiring:{restriccion}:{fecha}:{usuario}`. 9 tests; comprobados por mutación. |
| 2026-10-10 | Fase 4 | Sección "No disponible" en la ficha del médico (`AbsenceSection.tsx`): lista las dos representaciones del eje 2, con formulario de alta/edición/levante y "Indefinido". 8 tests. |
| 2026-10-10 | Despliegue | `2592305` a producción: API y worker en verde, `/api/health` 200, migración `a2446a0123b3` aplicada (el propio despliegue la corre) y DIRECCION + GERENCIAS MEDICAS clasificados como "sin regreso". Frontend desplegado (bundle con la pantalla nueva). |
| 2026-10-10 | Datos | Corregidos los **2** médicos inconsistentes en producción: ahora hay **0** fuera de servicio sin motivo y **0** fuera de servicio en misiones; los 29 desactivados siguen intactos. |
| 2026-10-10 | Fase 6 | Verificación en vivo en producción con un médico real: solo bloquea dentro del rango, avisa 2 días antes en la campana, no se repite, re-arma al editar la fecha, Indefinido no genera nada, y se levantó todo al terminar. |
| 2026-10-10 | Extensión v1.3.0 | El usuario decide **unificar las dos funcionalidades en una**: la ausencia es la única puerta y el estado "activo para servicio" se deriva de ella. Acepta que registrar una ausencia no borre disponibilidad/áreas/asignaciones ni toque misiones. Se documenta el **bug de la generación** como bloqueante previo. **Pendiente de autorización.** |
