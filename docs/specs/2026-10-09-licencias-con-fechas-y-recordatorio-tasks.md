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
**implementadas y con la suite en verde; falta desplegar y ejecutar la conversión en producción**
(pendiente de autorización).

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
- [x] **Elegibilidad**: dentro del rango se rechaza; fuera del rango se permite sin intervención
      (AC2). Cubierto por los tests de elegibilidad existentes (en verde) y comprobado **en vivo**
      en producción: bloqueado el 11 y el 12, libre el 10 y el 13.

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

- [x] **Cargar** las restricciones que **solapen** el mes completo, con un método nuevo
      (`list_restrictions_overlapping`): la pregunta correcta para un contexto que va a evaluar
      muchos días no es "¿qué está activo el día 1?" sino "¿qué toca este rango?".
- [x] **Comprobar** los **dos** sitios (≈129 y ≈322), no solo uno.
- [x] **Test de regresión** (`test_generate_respects_hard_block_that_starts_mid_month`): una
      ausencia del **3 al 6** de febrero → 0 turnos dentro y turnos fuera. **Comprobado por
      mutación**: con el código anterior el médico recibía **4** turnos dentro de la ausencia.
- [x] **Confirmar** que no se degrada el rendimiento: sigue siendo **una consulta por médico**
      (la misma que antes), solo con un `WHERE` más ancho.

> Es lo único de toda la spec que es un **defecto**, no una decisión. Hoy pasa desapercibido porque
> el flag tapa el hueco; con una sola puerta, dejaría de taparlo.

## Fase 8 — Una sola puerta en la interfaz

- [x] **Quitar** el bloque *"Razón para desactivar servicio"* del perfil del médico, y con él las
      mutaciones, el estado y las props que lo sostenían.
- [x] **Quitar** el botón **"Reactivar servicio"**: su equivalente es **levantar la ausencia**.
      *(Comprobado en test: el perfil ya no ofrece "Desactivar para servicio" ni "Reactivar
      servicio", y sí "Registrar ausencia".)*
- [x] **Quitar** la casilla *"¿Hace servicio?"* del formulario y **dejar de mandar
      `service_active`** en el `PATCH`, que era la segunda puerta (y que además fallaba con
      `reason_required` al desmarcarla).
- [x] **Dejar** la sección *No disponible* como **única entrada**, cubriendo **con fechas** e
      **Indefinido**.
- [x] **Revisar los textos**: "Indefinido" ahora dice que el médico queda fuera **hasta que alguien
      levante la ausencia** (en el formulario y en la fila de la lista).

## Fase 9 — El estado derivado

- [x] **Recalcular** `service_active` como valor calculado
      (`application/doctors/service_state.py`): activo = sin ausencia vigente hoy.
- [x] **Hacerlo al escribir**: registrar, editar y levantar una ausencia recalculan ese médico
      desde `AvailabilityService`.
- [x] **Hacerlo al pasar la fecha**: el job del recordatorio recalcula **antes** de cualquier
      salida temprana, así el estado cambia solo el día que la ausencia empieza o termina.
- [x] **Copiar** el motivo y el detalle de la ausencia vigente a `service_inactive_reason_id` y
      `service_inactive_detail`, para que la vista por departamento siga explicando el porqué.
- [x] **Unificar de verdad las dos viejas puertas**: `deactivate_service` ahora **crea una ausencia
      indefinida** y `reactivate_service` la **levanta**; el `PATCH` con `service_active` hace lo
      mismo. Ya no queda ningún camino que mueva el flag a mano.
- [x] **Cubrirlo con tests** (14 nuevos): ausencia vigente lo saca, futura no, terminada lo
      devuelve, levantar lo devuelve, editar recalcula, motivo/detalle copiados, idempotencia,
      auditoría como "Sistema", y que **no se borra** disponibilidad ni áreas (AC13).
- [x] **Decidido por el usuario (2026-10-10)**: la ausencia **sí** quita al médico de los
      calendarios **en borrador** dentro del rango —una asignación en un día que no puede servir es
      inválida, y dejarla crea un hueco que nadie más arregla—. La **disponibilidad y las áreas
      siguen intactas**. Implementado (`delete_assignments_for_doctor_in_range`) con test
      comprobado por mutación, y la pantalla avisa de cuántos turnos quedaron como hueco.

> **Por qué así y no reescribiendo las consultas:** el flag se lee en **83 sitios del backend y 29
> del frontend**, incluido el SQL del asistente. Mantenerlo como valor calculado deja esos sitios
> funcionando **sin tocarlos**; reescribirlos es mucho más caro para el mismo resultado.

## Fase 10 — Convertir las ausencias actuales

- [x] **Script** `scripts/convert_deactivations_to_absences.py`, con `--dry-run`, idempotente y
      auditado como "Sistema": crea una ausencia **Indefinida** por médico fuera de servicio sin
      ausencia, con su motivo y detalle, **empezando en `deactivated_at`** para no inventar
      historia.
- [x] **Verificado en base desechable** con el escenario de producción: convierte los que
      corresponde, deja al médico activo en paz, es idempotente (segunda corrida: 0) y no reactiva
      a nadie.
- [x] **Ejecutado** en producción el 2026-10-10, **antes** de desplegar. Resultado: 29 convertidos,
      **0 fuera de servicio sin ausencia**, **nadie reactivado** (43 activos / 29 fuera, igual que
      antes). Las 29 quedan con fecha de inicio **2026-10-10** porque `deactivated_at` estaba vacío
      en todas: es la fecha del **registro**, no la de la ausencia real, que el sistema nunca
      guardó. Se puede corregir a mano desde la pantalla si la fecha importa.

## Fase 11 — Tests y verificación en vivo

- [x] **Generación**: ausencia de mitad de mes respetada (Fase 7), con test de mutación.
- [x] **Una sola puerta**: el perfil no ofrece desactivar ni reactivar, y el formulario no manda
      `service_active` (test de interfaz).
- [x] **Indefinido**: equivale a la desactivación de antes (AC12).
- [x] **No destruye nada**: disponibilidad, áreas y misiones intactas (AC13).
- [x] **Estado derivado**: con ausencia vigente queda inactivo, y al terminar o al levantar la
      ausencia vuelve solo (AC15).
- [x] **En vivo contra producción** (2026-10-10, con el código local apuntando a la base real):
      una ausencia de mitad de mes la ve la consulta nueva (1) y **no** la vieja (0); una ausencia
      futura no lo saca; una vigente lo saca **y copia el motivo y el detalle**; al levantarla
      vuelve solo y se limpia el motivo.
- [x] **Fallo encontrado y corregido gracias a esa verificación**: el recálculo consultaba **antes**
      de volcar los cambios pendientes, y la sesión de la aplicación trabaja con `autoflush`
      apagado, así que el estado se quedaba **un paso por detrás** (editar o levantar una ausencia
      no surtía efecto hasta la operación siguiente). Lo tapaba el `flush` del evento de auditoría,
      por eso los tests con auditoría pasaban. Arreglado en `sync_service_state` (flush propio) con
      dos tests que usan el servicio **sin** auditoría, comprobados por mutación.
      *El estado que quedó torcido en producción se corrigió con el propio recálculo: 1 médico,
      y volvió a 29 fuera / 43 activos.*
- [x] **En vivo**: con una ausencia de mitad de mes, la consulta del generador la ve (**1**) y la
      consulta anterior **no** (**0**) — que es exactamente el defecto de la Fase 7—; y levantar una
      ausencia devuelve al médico a "activo para servicio" al instante. *No se generó un calendario
      real en producción a propósito: habría creado un calendario de prueba en el sistema de
      trabajo. La integración generador→restricciones está cubierta por el test de la Fase 7,
      comprobado por mutación.*

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
| 2026-10-10 | Extensión v1.3.0 | El usuario decide **unificar las dos funcionalidades en una**: la ausencia es la única puerta y el estado "activo para servicio" se deriva de ella. Acepta que registrar una ausencia no borre disponibilidad/áreas/asignaciones ni toque misiones. Se documenta el **bug de la generación** como bloqueante previo. |
| 2026-10-10 | Fases 7-9 | Implementadas. La generación respeta las ausencias de mitad de mes (test comprobado por mutación: antes le daba 4 turnos). Fuera el bloque de desactivación y la casilla del formulario. El estado se deriva de las ausencias, al escribir y al pasar la fecha, y las dos viejas puertas ahora escriben una ausencia. 14 tests nuevos. Suite: backend 1845, frontend 139. |
| 2026-10-10 | Fase 10 | Script de conversión escrito y verificado en base desechable, y **ejecutado en producción antes de desplegar**: 29 convertidos, 0 sin ausencia, nadie reactivado. |
| 2026-10-10 | Decisión del usuario | La ausencia **sí** quita al médico de los calendarios **en borrador** dentro del rango (una asignación en un día que no puede servir es inválida, y dejarla crea un hueco que nadie arregla). La disponibilidad y las áreas siguen intactas. Implementado con `delete_assignments_for_doctor_in_range`, con aviso en la pantalla de los huecos que quedan. |
| 2026-10-10 | Fase 11 | Verificación en vivo en producción: el generador ve la ausencia de mitad de mes, el estado se deriva al registrar/editar/levantar, y el recálculo se auto-corrige. **Encontró un fallo real** (el estado iba un paso por detrás por el `autoflush` apagado), corregido con dos tests de regresión. |
