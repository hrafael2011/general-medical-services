---
spec: licencias-con-fechas-y-recordatorio
version: 1.3.0
status: accepted
created: 2026-10-09
updated: 2026-10-10
---

# Spec — Licencias con fechas y recordatorio de reintegro

## Goal

Poder registrar **cuándo empieza y cuándo termina** la ausencia de un médico (licencia, embarazo,
préstamo…), con la opción de **tiempo indefinido**, y que **X días antes** del reintegro el
encargado o administrador reciba un aviso: *"a la Dra. X se le acaba la licencia el día N; se
reintegra el día N"*.

**Tareas de implementación:** [2026-10-09-licencias-con-fechas-y-recordatorio-tasks.md](2026-10-09-licencias-con-fechas-y-recordatorio-tasks.md)

> **Estado (2026-10-10).** Las **Fases 0 a 6** están implementadas, desplegadas y verificadas en
> producción (ausencias con fechas, "Indefinido", recordatorio y pantalla). La **extensión v1.3.0**
> —*una sola funcionalidad*, más abajo— está **aceptada por el usuario y pendiente de
> implementar**: unifica la desactivación y la ausencia en una única puerta y deriva de ella el
> estado "activo para servicio".

**Depende de:** [Reparar el canal de avisos por Telegram](2026-10-09-reparar-canal-avisos-telegram.md)
— sin el canal, el aviso no llega a nadie.

## Contexto

Origen: pedido directo del usuario (2026-10-09), ampliado tras descubrir que **"inhabilitado" no
es un solo estado, sino ocho ejes independientes**, y que el pedido inicial (licencias) cubría
solo uno de ellos.

Hoy un médico se desactiva con un motivo y **sin fecha de regreso**: queda fuera indefinidamente
hasta que alguien se acuerde de reactivarlo.

### Los ocho ejes de inhabilitación (verificado)

| # | Eje | Campo | Qué impide | ¿Tiene fechas? | ¿En el alcance? |
|---|---|---|---|---|---|
| 1 | Inactivo **en el sistema** | `doctors.active` | Todo: ni aparece | ❌ | No |
| 2 | **Fuera de servicio** + motivo | `service_active` + `reason_id` | Se le asignen turnos | ❌ **hoy** | ✅ **el objetivo** |
| 3 | **Excluido de misiones** | `participa_misiones` | Misiones | ❌ | No — eje aparte |
| 4 | Fuera del **pool** | `pool_active` | Búsquedas del bot | ❌ | No |
| 5 | **Restricción con fechas** | `doctor_restrictions` | Bloqueo por rango | ✅ **sí** | ✅ **el mecanismo que se reutiliza** |
| 6 | **Sin disponibilidad** reportada | `doctor_availability` | Ese mes / esos días | por período | No — se toca en su propia pantalla |
| 7 | **Área no permitida** | `doctor_allowed_areas` | Solo ciertas áreas | ❌ | No |
| 8 | **Borrado lógico** | `deleted_at` | Todo (recuperable) | ❌ | No |

El motor de asignación evalúa **1, 2, 5, 6 y 7** (`eligibility.py`), y el 3 aparte en misiones.

### Estado real medido en producción (2026-10-09)

```
  médicos totales ...................... 73
  activos en el sistema ................ 73   ← el eje 1 NO se usa
  activos para servicio ................ 44   ← 29 FUERA  (el eje real)
  participan en misiones ............... 41   ← 32 excluidos
  dentro del pool ...................... 73
  borrados lógicos .....................  1
  con disponibilidad cargada ........... 71
  restricciones de área permitida ...... 134
```

**Los ejes son independientes, no una sola cosa:**

```
  5 médicos: activos para servicio PERO fuera de misiones
  2 médicos: fuera de servicio PERO todavía en misiones    ← inconsistencia
  2 médicos: fuera de servicio SIN motivo registrado       ← hueco de datos
```

> **Corrección medida el 2026-10-10: son los MISMOS 2 médicos, no 4 registros.** Cada uno tiene
> los dos problemas a la vez (fuera de servicio, sin motivo y todavía en misiones). La auditoría de
> mayo lo confirma: ambos entraron por la puerta B (`doctor_updated` con `service_active: False`,
> `participa_misiones: True`, `allowed_area_ids: []`) y **el motivo no quedó registrado en ninguna
> parte**, así que no se puede recuperar: se elige. Decisión del usuario: motivo `OTROS` con una
> nota de que fue una desactivación histórica, y fuera de misiones.

### El catálogo real de motivos (producción, no el del código)

El catálogo sembrado en el repositorio **no es el que se usa**. El de producción tiene **ocho**
motivos, y **todos con severidad `hard_block`**:

```
CONCURSO · DIRECCION · GERENCIAS MEDICAS · LICENCIA PRE Y POST NATAL
LICENCIAS MEDICAS · OTROS · PRESTADO BATALLAS DE LAS CARRERAS · VACACIONES
```

> Como **todos** son `hard_block`, la severidad **ya no distingue nada**: el catálogo sembrado
> tenía `warn` para vacaciones, préstamo y traslado, pero producción los igualó. La severidad no
> sirve hoy para decidir nada.

### Qué motivos esperan regreso

| Motivo | Naturaleza | ¿Fecha de regreso? |
|---|---|---|
| LICENCIAS MEDICAS | temporal | ✅ sí |
| LICENCIA PRE Y POST NATAL | temporal (larga) | ✅ sí |
| VACACIONES | temporal | ✅ sí |
| PRESTADO BATALLAS DE LAS CARRERAS | temporal | ✅ probablemente |
| **DIRECCION** | **es un puesto** | ❌ **indefinido** |
| **GERENCIAS MEDICAS** | **es un puesto** | ❌ **indefinido** |
| CONCURSO | incierto | depende |
| OTROS | incierto | depende |

**Consecuencia de diseño:** "indefinido" **no es un caso borde** — cubre dos de los ocho motivos
reales, y son justo los de puesto permanente. Es una opción de primera clase.

> ⚠️ **Esta tabla es un punto de partida, NO una regla.** El catálogo de motivos es **editable**:
> los administradores pueden crear motivos nuevos y modificar los existentes, así que la
> clasificación **no puede vivir en el código**. Va como **atributo de cada motivo**, editable
> desde la pantalla de Catálogos; los ocho de arriba son solo los **valores iniciales** de la
> carga, y un motivo nuevo nace con un valor por defecto que el admin ajusta.
>
> **Prohibido decidir por el `code` del motivo** (`if reason.code == "medical_license"`): se
> rompería el día que alguien añada, renombre o desactive un motivo — que es justo para lo que
> existe el catálogo.

### Los dos defectos encontrados

**1. Hay DOS puertas para desactivar, y hacen cosas distintas.**

| | Puerta A: botón "Desactivar" | Puerta B: editar el médico y desmarcar "presta servicio" |
|---|---|---|
| Guarda el **motivo** | ✅ sí | ❌ **no** |
| Quita de **misiones** | ✅ sí | ❌ **no** |
| Borra disponibilidad y áreas | ❌ no | ✅ sí |
| Borra asignaciones del calendario | ❌ no | ✅ sí |
| Evento de auditoría | `doctor_service_deactivated` | `doctor_updated` |

Esto **explica exactamente** los 2 médicos sin motivo y los 2 que siguen en misiones estando
fuera de servicio: entraron por la puerta B. Es una trampa directa para esta spec —si las
licencias usaran una puerta y el resto la otra, el problema se duplicaría—.

**2. El catálogo no dice qué motivos esperan regreso.** Hoy todos son idénticos, así que la
interfaz no puede saber si debe pedir una fecha.

### Lo que ya existe y se reutiliza

| Pieza | Estado |
|---|---|
| `doctors.service_active` + motivo + detalle | ✅ **se usa a diario** — pero **sin fechas** |
| `doctor_restrictions` con `starts_at` / `ends_at` / motivo / severidad | ✅ existe — **0 filas, sin pantalla** |
| El motor de asignación respeta el rango | ✅ **ya funciona** (`eligibility.py:79`) |
| API de restricciones | ✅ `POST /doctors/{id}/restrictions`, `/lift`, `GET` |
| Aviso a encargados por Telegram | ⚠️ el código existe, **el canal está roto** (spec aparte) |
| Campana de alertas en la app | ✅ funciona y no depende de Telegram |
| Botones en Telegram | ✅ `with_telegram_buttons` ya existe |

> **El hallazgo que gobierna el diseño:** el mecanismo con fechas **ya está construido, ya bloquea
> asignaciones y ya expira solo**. No hay que inventar nada: hay que **darle pantalla**.

### Por qué no se reutiliza `service_active` para las fechas

`service_active = false` saca al médico **de inmediato y para siempre**. Una licencia que empieza
el 1 de marzo y hoy es 20 de febrero debe dejar al médico **trabajando hasta el 1 de marzo**.
Eso solo lo hace bien el mecanismo con fechas.

**Consecuencia:** conviven dos representaciones para el mismo eje, y la interfaz las unifica.

## Alcance

| Dentro | Fuera |
|---|---|
| Ausencias con o sin fecha sobre el **eje 2** (fuera de servicio) | El canal de Telegram (spec aparte) |
| Opción **"indefinido"** entre las opciones de fecha | Los **29 desactivados actuales**: se quedan como están |
| Recordatorio X días antes del reintegro | Auto-reactivar a nadie |
| Aviso por **Telegram + campana** | **Ejes 1, 3, 4, 6, 7 y 8** (sistema, misiones, pool, disponibilidad, áreas, borrado) |
| Editar la fecha y **re-armar** el aviso | Reglas de elegibilidad (ya funcionan) |
| **Unificar las dos puertas** de desactivación | El catálogo de motivos **más allá** de marcar si esperan regreso |

> **El alcance se acota al eje 2 a propósito.** Los otros siete ejes siguen funcionando como hoy.
> Lo único que se toca de ellos es que la pantalla **los muestre juntos** (decisión 6) y que las
> dos puertas del eje 2 dejen de comportarse distinto (decisión 10).

## Decisiones tomadas

| # | Decisión | Razón |
|---|---|---|
| 1 | **Fuera solo en ese rango** | Fuera del rango vuelve a ser asignable **sin que nadie haga nada**: la restricción expira sola |
| 2 | Aviso por **Telegram y campana** | La campana funciona hoy; Telegram cuando el canal esté arreglado |
| 3 | **"Indefinido" es de primera clase**, no un caso borde | Cubre **2 de los 8 motivos reales** (DIRECCION, GERENCIAS MEDICAS), que son puestos, no ausencias |
| 4 | Editar la fecha **re-arma** el aviso | Si se extiende la licencia, hay que volver a avisar |
| 5 | **Nunca reactivar automáticamente** | Con la decisión 1 no hace falta: la restricción deja de aplicar y listo |
| 6 | **Una sola pantalla** que unifica las representaciones del eje 2 | El encargado ve *"no disponible"* con motivo y fechas, sin saber de tablas |
| 7 | Días de aviso: **2 por defecto**, configurables **a nivel global** | `doctor_restrictions` no tiene dónde guardar un número por registro; un valor global es editable y no necesita migración |
| 8 | **Sin migración** para las fechas | `doctor_restrictions` ya tiene todo; el re-armado usa la clave única de `notification_events` |
| 9 | Los desactivados actuales **no se tocan** en su estado ✅ confirmado | Decisión explícita del usuario. **Pero sí se corrigen los 4 datos inconsistentes** (2 sin motivo, 2 en misiones fuera de servicio), también confirmado |
| 10 | **Unificar las dos puertas** de desactivación | Hoy dejan datos distintos (motivo, misiones, auditoría); si no se unifican, esta spec duplicaría el problema |
| 11 | **El motivo indica si espera regreso**, y es **editable en el catálogo**. ✅ **Migración autorizada** | La pantalla acierta sola: DIRECCION ⇒ indefinido sin preguntar fecha. **Nunca por `code`**: el catálogo es editable y un motivo nuevo debe funcionar sin tocar código. Requiere migración (una columna) **y** un campo en la pantalla de Catálogos |
| 12 | **Solo el eje 2** entra al recordatorio | Las misiones (eje 3) son otro eje y se gestionan aparte |

> **Nota sobre el punto 7:** si más adelante hace falta un plazo distinto por caso, eso sí
> requeriría una columna nueva en `doctor_restrictions` y su migración. Queda fuera a propósito.
>
> **Nota sobre el punto 11:** es la única parte de esta spec que **rompe la regla de "sin
> migración"**. Se puede recortar (que el encargado elija siempre) si prefieres no migrar; pierde
> comodidad pero no funcionalidad.

### Extensión v1.3.0 — Una sola funcionalidad (ACEPTADA, pendiente de implementar)

> **Se lee junto con la decisión 10, no en su contra.** La decisión 10 unificó el *efecto* de las
> dos puertas (mismo motivo, mismas misiones, misma auditoría). La decisión 13 va un paso más allá y
> **elimina una de las dos puertas**: mantener dos controles distintos para el mismo eje fue
> justamente lo que produjo las inconsistencias.

**Decidido por el usuario (2026-10-10):** no debe haber **dos formas** de decir "este médico no
está disponible". La **ausencia** —con fechas o Indefinida— es la **única puerta**, y el estado
"activo para servicio" se **deduce** de ella.

| # | Decisión | Razón |
|---|---|---|
| 13 | La **ausencia es la única puerta**. Desaparecen el bloque *"Razón para desactivar servicio"* y la casilla *"¿Hace servicio?"* del formulario | Tener dos puertas para lo mismo es lo que produjo los datos inconsistentes de producción; con una sola, el estado no puede divergir |
| 14 | Registrar una ausencia **no** borra disponibilidad, ni áreas, ni asignaciones, y **no** saca de misiones | Lo que se borra hay que volver a cargarlo, y las misiones son el eje 3, que esta spec no toca. *(Aceptado por el usuario)* |
| 15 | `service_active` **deja de ponerse a mano** y se **deriva**: "activo para servicio" = **sin ausencia vigente hoy** | Si nada apaga el flag, el tablero, el asistente y los reportes seguirían diciendo "activo" de un médico de licencia |
| 16 | **Primero** se arregla la carga de restricciones de la generación automática | No es una decisión de diseño: es un **bug** que hoy tapa el flag y que con una sola puerta pasa a ser crítico |

#### El defecto que obliga a arreglar la generación antes

`generation_service.py` carga las restricciones **una sola vez, con la fecha del día 1** del mes
(`list_active_restrictions_for_doctor(d.id, on_date=first_day)`, dos sitios: ≈línea 126 y ≈línea
319), y esa consulta descarta lo que empiece **después** de esa fecha. Una licencia del **3 al 10**
nunca entra en el contexto, así que `CalendarEngine._has_hard_block` no la ve y **el generador
reparte turnos a un médico de licencia**.

Las otras tres rutas de asignación (`_run_eligibility`, `_run_eligibility_with_force`,
`get_eligible_doctors_for_slot`) sí consultan por la **fecha del turno**, y por eso **no** tienen el
fallo: la asignación manual ya respeta la ausencia. El generador es el único que no.

#### Cómo queda

- Una sola entrada: **Registrar ausencia**, con **desde/hasta** o **Indefinido**.
- **Con fecha**: fuera solo en el rango, vuelve solo, con aviso X días antes.
- **Indefinido**: fuera desde la fecha **hasta que alguien levante la ausencia**, sin aviso. Es
  exactamente lo que hoy hace "Desactivar para servicio".
- **El motivo** sale del mismo catálogo (con `expects_return` proponiendo cuál corresponde).
- **`service_active` se deriva**: deja de ser un botón y pasa a ser un cálculo.
- Los **29** médicos que hoy están fuera por el flag pasan a ser ausencias **Indefinidas** con su
  motivo, así que tampoco necesitan el botón "Reactivar": se levanta la ausencia.

#### Cómo se deriva el estado (propuesta a confirmar al autorizar)

El flag se mantiene como **valor calculado**, no manual:

1. **Al escribir**: registrar, editar o levantar una ausencia recalcula el estado de ese médico.
2. **Al pasar la fecha**: un job (el del recordatorio, que ya corre cada 30 minutos) recalcula los
   médicos cuya ausencia empieza o termina ese día.

Así los **83 sitios del backend y 29 del frontend** que hoy leen `service_active` siguen
funcionando **sin tocarlos**, y dejan de mentir. La alternativa —reescribir cada consulta— toca
también el SQL del asistente (22 consultas) y es mucho más cara para el mismo resultado.

#### Consecuencias que hay que asumir (y una que conviene confirmar aparte)

- Las asignaciones **ya existentes** en calendarios en **borrador** que caigan dentro del rango
  **no se quitan solas** (decisión 14). Quedan visibles como hueco para que el encargado las
  reemplace; el generador ya no las producirá. Es la contrapartida de no borrar nada
  automáticamente y **conviene confirmarla explícitamente**.
- Los contadores pasan a decir **"disponible ahora"**: al entrar en licencia el número de médicos
  "activos para servicio" baja, y **sube solo** al cumplirse la fecha.

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
- **R6** — **X días antes** de la fecha de regreso —**2 por defecto**, ajustable en la
  configuración del sistema— se avisa por **Telegram** a los encargados/administradores con ese
  permiso y se crea una alerta en la **campana**.
- **R7** — El aviso se envía **una sola vez** por fecha de regreso. **Editar la fecha vuelve a
  armarlo.**
- **R8** — El aviso dice **el nombre del médico, el motivo y la fecha de reintegro**.
- **R9** — La alerta de la campana se puede **resolver** y queda registrado quién y cuándo.
- **R10** — Nada de esto cambia el comportamiento de los médicos que hoy están desactivados sin
  fecha.
- **R11** — Las **dos puertas** de desactivación (el botón dedicado y editar el médico) producen
  **el mismo resultado**: mismo motivo, mismas misiones, mismo evento de auditoría.
- **R12** — El catálogo de motivos indica, por motivo, **si espera fecha de regreso**; la pantalla
  lo usa como valor inicial y no pregunta una fecha cuando no corresponde.
- **R12b** — Ese atributo es **editable desde la pantalla de Catálogos**, como el resto del
  catálogo: crear un motivo nuevo no debe requerir tocar código. **Ninguna regla puede depender
  del `code` del motivo.**
- **R13** — La pantalla muestra **solo el eje 2** (fuera de servicio). No ofrece tocar misiones,
  pool, disponibilidad, áreas ni borrado.
- **R14** — El recordatorio **no** se dispara por cambios en el eje 3 (misiones): son ejes
  independientes.
- **R15** — Se corrige el **hueco de datos** detectado: hoy hay médicos fuera de servicio sin
  motivo registrado porque la puerta B no lo pedía.
- **R16** — Existe **una sola** forma de registrar que un médico no está disponible: la
  **ausencia** (con fechas o Indefinida). No queda ningún otro control que desactive el servicio.
- **R17** — La ausencia **Indefinida** cubre el caso que hoy representa el flag: el médico queda
  fuera desde la fecha indicada hasta que alguien levante la ausencia, y no genera recordatorio.
- **R18** — Registrar una ausencia **no** borra la disponibilidad del médico, ni sus áreas
  permitidas, ni sus asignaciones existentes, y **no** cambia su participación en misiones.
- **R19** — "Activo para servicio" **se deriva**: un médico está activo para servicio si **no tiene
  una ausencia vigente hoy**. Deja de ser un valor que se pone a mano.
- **R20** — La **generación automática de calendario** respeta las ausencias **por la fecha del
  turno**, igual que la asignación manual: una ausencia que empiece después del día 1 del mes
  bloquea los días de su rango.
- **R21** — Los médicos que hoy están fuera por el flag (29 en producción) quedan representados
  como ausencias **Indefinidas** con su motivo y detalle, sin pérdida de información y auditado.

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
- **Dada** una licencia que termina el 15 de marzo y un aviso configurado a 2 días,
- **cuando** llega el 13 de marzo, **entonces** el encargado **recibe** el aviso por Telegram y ve
  la alerta en la campana, con nombre, motivo y fecha.

**AC5 — No se repite**
- **Dado** un aviso ya enviado, **cuando** corre el job otra vez, **entonces** no se vuelve a
  enviar.

**AC6 — Editar re-arma**
- **Dada** una licencia avisada, **cuando** se cambia la fecha de regreso, **entonces** se vuelve a
  avisar cuando corresponda a la nueva fecha.

**AC7 — Nada se rompe**
- **Dados** los 29 médicos desactivados sin fecha, **entonces** siguen exactamente igual, y el flujo
  actual de desactivación sigue funcionando.

**AC8 — Las dos puertas dan el mismo resultado**
- **Dado** un mismo médico desactivado por el botón dedicado y por la edición del médico,
- **entonces** en ambos casos queda **con motivo, fuera de misiones** y con el evento de auditoría
  correspondiente. No hay dos estados distintos para lo mismo.

**AC9 — El motivo propone, no impone**
- **Dado** el motivo **DIRECCION**, **cuando** se elige, **entonces** la pantalla propone
  **Indefinido** y no exige una fecha.
- **Dado** el motivo **LICENCIAS MEDICAS**, **entonces** propone pedir las fechas.
- **Y en ambos casos** el encargado puede cambiarlo a mano.

**AC10 — Los ejes no se pisan**
- **Dado** un médico al que solo se le cambia la participación en misiones,
- **entonces** **no** se dispara ningún aviso de reintegro de servicio.

**AC11 — Una sola puerta**
- **Dado** un médico activo, **entonces** la única forma de dejarlo sin servicio es registrar una
  ausencia: no existe ningún otro control que lo desactive.

**AC12 — Indefinido equivale a la desactivación de antes**
- **Dado** un médico con una ausencia Indefinida, **entonces** queda fuera desde esa fecha, **no**
  vuelve solo y **no** genera aviso, hasta que alguien levante la ausencia.

**AC13 — Registrar una ausencia no destruye nada**
- **Dado** un médico con disponibilidad, áreas y asignaciones, **cuando** se le registra una
  ausencia, **entonces** conserva su disponibilidad, sus áreas y sus asignaciones, y su
  participación en misiones no cambia.

**AC14 — El generador respeta la ausencia de mitad de mes**
- **Dado** un médico con una ausencia del 20 al 25, **cuando** se genera el calendario de ese mes,
- **entonces** no se le asigna ningún turno dentro de ese rango, y sí puede recibir fuera de él.

**AC15 — "Activo para servicio" dice la verdad**
- **Dado** un médico con una ausencia vigente, **entonces** el tablero, el listado y las respuestas
  del asistente lo cuentan como **no** activo para servicio, y vuelve a contarse como activo **solo**
  al cumplirse la fecha o al levantar la ausencia.

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
| **Puertas unificadas** | Test nuevo: desactivar por A y por B deja **el mismo** estado (motivo, misiones, auditoría) |
| **Catálogo** | Test nuevo: un motivo que no espera regreso no pide fecha |
| **Ejes independientes** | Test: cambiar misiones **no** dispara el recordatorio de servicio |
| No regresión | Los 29 desactivados no cambian de estado; los 8 motivos siguen funcionando |

## Riesgos

| Riesgo | Mitigación |
|---|---|
| **Dos mecanismos** para el eje 2 (flag y restricción) confunden al usuario | Decisión 6: una sola pantalla que los unifica; el usuario no ve la diferencia |
| **Dos puertas** que dejan datos distintos | Decisión 10 / R11: se unifican antes de construir encima |
| El aviso no llega porque el canal sigue roto | Es una **dependencia declarada**: el spec del canal va primero |
| Cambiar la fecha varias veces genera varios avisos | La clave incluye la fecha: cada fecha distinta avisa **una** vez; volver a la anterior no re-avisa |
| Un médico con licencia **y** desactivado a la vez | La pantalla lo muestra junto; el bloqueo es la unión de ambos |
| **El catálogo manda y no siempre acierta**: un motivo marcado "indefinido" que sí vuelve | El encargado puede cambiarlo a mano; el motivo solo propone |
| **Confundir el eje 2 con el 3**: creer que una licencia también saca de misiones | Se unifican las puertas (R11) para que el efecto sea el mismo y predecible |
| **Escribir reglas por el `code` del motivo** | El catálogo es editable: cualquier regla fija se rompe al añadir o renombrar un motivo. Todo se decide por el **atributo editable**, nunca por el código |
| Un motivo nuevo sin clasificar | Nace con un valor por defecto; el admin lo ajusta y la pantalla siempre permite cambiarlo a mano |
| **La generación ignoraba las ausencias de mitad de mes** | Fase 7, **antes que nada**: es el bug que hacía parecer imprescindible el flag |
| Convertir 29 médicos a ausencias Indefinidas | Script con `--dry-run`, idempotente y auditado; se compara antes y después contra producción |
| Las asignaciones ya hechas dentro del rango no se quitan solas | Decisión 14: quedan como hueco visible para reemplazar. **Confirmar aparte** |
| Derivar el estado cambia lo que cuentan 83 lecturas del backend y 29 del frontend | Se mantiene como valor calculado en un solo sitio (no se reescriben las consultas) y se cubren con tests los consumidores visibles: tablero, asistente, reportes y vista por departamento |

## Changelog

| Version | Date | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-10-09 | — | Nuevo requerimiento | Se añade fecha de inicio y de regreso (o **indefinido**) a la ausencia de un médico, reutilizando el mecanismo de restricciones que ya existe y ya bloquea asignaciones por rango, sin migración. Se programa un recordatorio X días antes del reintegro por Telegram y campana, con re-armado al editar la fecha. Depende de reparar el canal de avisos. |
| 1.3.0 | 2026-10-10 | — | Decisión del usuario | **Una sola funcionalidad.** El usuario decide que no haya dos formas de decir "no está disponible": la **ausencia** (con fechas o Indefinida) es la única puerta, y "activo para servicio" se **deriva** de ella (sin ausencia vigente). Se acepta que registrar una ausencia no borre disponibilidad, áreas ni asignaciones, y que no toque misiones. Se documenta el **bug que obliga a arreglar la generación primero**: carga las restricciones con la fecha del día 1 del mes, así que una ausencia que empiece después no bloquea nada en la generación automática —el flag lo tapaba, y con una sola puerta pasa a ser crítico—. Se añaden R16-R21 y AC11-AC15. **Aceptada, pendiente de autorización para implementar.** |
| 1.2.0 | 2026-10-10 | — | Implementación | Se implementan las Fases 0 a 5. **Las dos puertas de desactivación quedan unificadas**: desactivar exige motivo (validado contra el catálogo y contra el sexo del médico), saca de misiones, registra el mismo evento de auditoría y crea las mismas alertas, se entre por donde se entre. Se añade `expects_return` al catálogo de motivos (migración `a2446a0123b3`, verificada en base desechable con los 8 códigos reales) y se hace editable en la pantalla de Catálogos, para que la pantalla sepa proponer "Indefinido" sin que ninguna regla dependa del `code`. Se añade `PATCH /restrictions/{id}` —**el plan asumía que editar ya era posible y no lo era**— para poder editar la fecha, que es lo que re-arma el aviso. El recordatorio es el quinto job del worker, con alerta en la campana y aviso por Telegram, idempotente por restricción + fecha + destinatario. La pantalla "No disponible" unifica las dos representaciones del eje 2. Detalle en el archivo de tareas. |
| 1.1.0 | 2026-10-09 | — | Investigación | Se descubre que **"inhabilitado" son ocho ejes independientes**, no uno, y se documenta el estado real de producción (73 médicos, 29 fuera de servicio, 32 fuera de misiones, catálogo real de 8 motivos todos `hard_block`). Se acota el alcance al eje 2 y se añaden dos correcciones de fondo: **unificar las dos puertas** de desactivación —que hoy dejan motivo, misiones y auditoría distintos, y que explican los datos inconsistentes— y que **el motivo indique si espera regreso**, para que "indefinido" deje de ser un caso borde. "Indefinido" pasa a ser de primera clase: cubre 2 de los 8 motivos reales. |
