---
spec: licencias-con-fechas-y-recordatorio
version: 1.0.0
status: draft
created: 2026-10-09
updated: 2026-10-09
---

# Spec — Licencias con fechas y recordatorio de reintegro

## Goal

Poder registrar **cuándo empieza y cuándo termina** la ausencia de un médico (licencia, embarazo,
préstamo…), con la opción de **tiempo indefinido**, y que **X días antes** del reintegro el
encargado o administrador reciba un aviso: *"a la Dra. X se le acaba la licencia el día N; se
reintegra el día N"*.

**Tareas de implementación:** [2026-10-09-licencias-con-fechas-y-recordatorio-tasks.md](2026-10-09-licencias-con-fechas-y-recordatorio-tasks.md)

**Depende de:** [Reparar el canal de avisos por Telegram](2026-10-09-reparar-canal-avisos-telegram.md)
— sin el canal, el aviso no llega a nadie.

## Contexto

Origen: pedido directo del usuario (2026-10-09).

Hoy un médico se desactiva con un motivo y **sin fecha de regreso**: queda fuera
indefinidamente hasta que alguien se acuerde de reactivarlo. En producción hay **27 médicos
desactivados sin fecha**, incluidos 5 con *Licencias médicas* y 1 con *Licencia pre y post
natal* — exactamente los casos de este pedido.

### Lo que ya existe (verificado)

| Pieza | Estado |
|---|---|
| `doctors.service_active` + motivo + detalle | ✅ **se usa a diario** — pero **sin fechas** |
| `doctor_restrictions` con `starts_at` / `ends_at` / motivo / severidad | ✅ existe — **0 filas, sin pantalla** |
| El motor de asignación respeta el rango | ✅ **ya funciona** (`eligibility.py:79`: una restricción `hard_block` bloquea esas fechas) |
| API de restricciones | ✅ `POST /doctors/{id}/restrictions`, `POST /restrictions/{id}/lift`, `GET` |
| Aviso a encargados por Telegram | ⚠️ existe el código, **el canal está roto** (spec aparte) |
| Campana de alertas en la app | ✅ funciona y no depende de Telegram |
| Plantillas y botones en Telegram | ✅ `with_telegram_buttons` ya existe |

> **El hallazgo que gobierna el diseño:** el mecanismo con fechas **ya está construido, ya bloquea
> asignaciones y ya expira solo**. No hay que inventar nada: hay que **darle pantalla**. Cero
> migraciones.

### Por qué no se reutiliza `service_active` para esto

`service_active = false` saca al médico **de inmediato y para siempre**. Una licencia que empieza
el 1 de marzo y hoy es 20 de febrero debe dejar al médico **trabajando hasta el 1 de marzo**.
Eso solo lo hace bien el mecanismo con fechas.

**Consecuencia:** conviven dos representaciones, y la interfaz las unifica (ver Decisiones).

## Alcance

| Dentro | Fuera |
|---|---|
| Pantalla para registrar ausencias con o sin fecha | El canal de Telegram (spec aparte) |
| Opción **"indefinido"** entre las opciones de fecha | Los **27 desactivados actuales**: se quedan como están |
| Recordatorio X días antes del reintegro | Auto-reactivar a nadie |
| Aviso por **Telegram + campana** | Reglas de elegibilidad (ya funcionan) |
| Editar la fecha y **re-armar** el aviso | Disponibilidad mensual/semanal (otra cosa) |

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | **Fuera solo en ese rango** | Fuera del rango vuelve a ser asignable **sin que nadie haga nada**: la restricción expira sola |
| 2 | Aviso por **Telegram y campana** | La campana funciona hoy; Telegram cuando el canal esté arreglado |
| 3 | **"Indefinido"** entre las opciones de fecha | Sin fecha de regreso **no hay nada que recordar** ⇒ ese caso no genera aviso |
| 4 | Editar la fecha **re-arma** el aviso | Si se extiende la licencia, hay que volver a avisar |
| 5 | **Nunca reactivar automáticamente** | Con la decisión 1 no hace falta: la restricción deja de aplicar y listo. No hay riesgo de devolver al servicio a quien no volvió |
| 6 | **Una sola pantalla** que unifica las dos representaciones | El encargado ve *"no disponible"* con su motivo y fechas, sin saber de tablas |
| 7 | Días de aviso: **5 por defecto**, configurables **a nivel global** (no por registro) | `doctor_restrictions` no tiene dónde guardar un número por registro; un valor global en `system_settings` es editable, no necesita migración y cubre el caso real |
| 8 | **Sin migración** | `doctor_restrictions` ya tiene todo lo necesario; el re-armado usa la clave única de `notification_events`, y los días de aviso viven en `system_settings` |
| 9 | Los 27 actuales **no se tocan** | Decisión explícita del usuario |

> **Nota sobre el punto 7:** si más adelante hace falta un plazo distinto por caso (una licencia
> larga que quiera avisar con 15 días y otra con 3), eso sí requeriría una columna nueva en
> `doctor_restrictions` y su migración. Queda fuera de este spec a propósito.

## Requisitos

- **R1** — En la ficha del médico hay una sección **No disponible** que lista lo vigente y lo
  programado, con motivo y fechas.
- **R2** — El formulario pide: **motivo**, **desde**, **hasta** y **días de aviso**. "Hasta" admite
  la opción **Indefinido**.
- **R3** — Con **desde** y **hasta**, el médico queda fuera **solo en ese rango** y vuelve a ser
  asignable al pasar la fecha, sin intervención.
- **R4** — El motor de asignación **rechaza** asignarlo dentro del rango (ya funciona; hay que
  conservarlo).
- **R5** — Con **Indefinido**, el médico queda fuera desde la fecha indicada y **no** se genera
  recordatorio.
- **R6** — **X días antes** de la fecha de regreso —**5 por defecto**, ajustable en la
  configuración del sistema— se avisa por **Telegram** a los encargados/administradores con ese
  permiso y se crea una alerta en la **campana**.
- **R7** — El aviso se envía **una sola vez** por fecha de regreso. **Editar la fecha vuelve a
  armarlo.**
- **R8** — El aviso dice **el nombre del médico, el motivo y la fecha de reintegro**.
- **R9** — La alerta de la campana se puede **resolver** y queda registrado quién y cuándo.
- **R10** — Nada de esto cambia el comportamiento de los médicos que hoy están desactivados sin
  fecha.

## Criterios de aceptación

**AC1 — Registrar una licencia con fechas**
- **Dado** un médico activo, **cuando** se registra una licencia del 1 al 15 de marzo,
- **entonces** aparece en su sección **No disponible** con motivo y fechas, y **sigue siendo
  asignable antes del 1 de marzo**.

**AC2 — Solo fuera en el rango**
- **Dado** esa licencia, **cuando** se intenta asignarlo dentro del rango, **entonces** el sistema
  lo rechaza; y **cuando** pasa el 15 de marzo, **entonces** vuelve a poder asignarse sin que
  nadie lo reactive.

**AC3 — Indefinido**
- **Dado** un médico con ausencia **Indefinida**, **entonces** queda fuera desde la fecha
  indicada y **no** se programa ningún aviso.

**AC4 — El aviso llega antes**
- **Dada** una licencia que termina el 15 de marzo y un aviso configurado a 5 días,
- **cuando** llega el 10 de marzo, **entonces** el encargado **recibe** el aviso por Telegram y ve
  la alerta en la campana, con nombre, motivo y fecha.

**AC5 — No se repite**
- **Dado** un aviso ya enviado, **cuando** corre el job otra vez, **entonces** no se vuelve a
  enviar.

**AC6 — Editar re-arma**
- **Dada** una licencia avisada, **cuando** se cambia la fecha de regreso, **entonces** se vuelve a
  avisar cuando corresponda a la nueva fecha.

**AC7 — Nada se rompe**
- **Dados** los 27 médicos desactivados sin fecha, **entonces** siguen exactamente igual, y el flujo
  actual de desactivación sigue funcionando.

## Contrato

Se reutilizan los endpoints existentes de restricciones (`POST /doctors/{id}/restrictions`,
`POST /restrictions/{id}/lift`, `GET /doctors/{id}/restrictions`) y se amplía el cuerpo para
aceptar `ends_at` nulo (indefinido) y los días de aviso.

**Aviso a interesados:** los destinatarios del recordatorio son usuarios con Telegram vinculado y
el permiso correspondiente — el mismo mecanismo que ya usa la escalación de confirmaciones.

> **El re-armado (R7/AC6) no necesita columna nueva:** la clave única de `notification_events`
> incluye la fecha de regreso, así que al cambiarla la clave cambia y el aviso vuelve a estar
> permitido. Si la fecha no cambia, la clave se repite y el envío se bloquea solo.

## Impacto en tests

| Área | Efecto |
|---|---|
| Restricciones | Ya hay tests de disponibilidad; se añaden los de fecha nula y de aviso |
| Recordatorio | Test nuevo: envía dentro de la ventana, no envía fuera, no repite, re-arma al cambiar la fecha |
| Indefinido | Test nuevo: nunca genera aviso |
| Elegibilidad | Verificar que el rango se sigue respetando (AC2) |
| No regresión | Los 27 desactivados no cambian de estado |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **Dos mecanismos** para "no disponible" (flag y restricción) confunden al usuario | Decisión 6: una sola pantalla que los unifica; el usuario no ve la diferencia |
| El aviso no llega porque el canal sigue roto | Es una **dependencia declarada**: el spec del canal va primero |
| Cambiar la fecha varias veces genera varios avisos | La clave incluye la fecha: cada fecha distinta avisa **una** vez; volver a la anterior no re-avisa |
| Un médico con licencia **y** desactivado a la vez | La pantalla lo muestra junto; el bloqueo es la unión de ambos |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Nuevo requerimiento | Se añade fecha de inicio y de regreso (o **indefinido**) a la ausencia de un médico, reutilizando el mecanismo de restricciones que ya existe y ya bloquea asignaciones por rango, sin migración. Se programa un recordatorio X días antes del reintegro por Telegram y campana, con re-armado al editar la fecha. Depende de reparar el canal de avisos. |
