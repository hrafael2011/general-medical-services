# Tools del bot — lo que el modelo lee

> **Generado automáticamente** desde `backend/app/application/telegram/tool_registry.py` — no editar a mano.
> Regenerar con: `python scripts/dump_tools_prompt.py`

El modelo **no ve el código**: para elegir una tool solo lee el bloque de
abajo (nombre + pregunta típica + aclaración + parámetros) y las reglas del
system prompt. Mejorar una descripción es cambiar ese texto en el registro
y regenerar este documento.

---

## 1. Bloque literal que entra al prompt

Salida exacta de `build_tools_prompt()`:

```text
HERRAMIENTAS DISPONIBLES:

## MÉDICOS

1. list_doctors
   Pregunta típica: «¿Cuántos/cuáles médicos hay con estas características?». Lista o cuenta médicos con los filtros indicados. Usa `count: true` cuando el usuario solo quiere el número. Usa `group_by` cuando pide conteos agrupados (por sexo, rango o departamento).
   Parámetros:
   - sex: string (M/F) (opcional) — M (masculino) o F (femenino)
   - rank: string (opcional) — Rango militar exacto (ej: Capitán, Mayor)
   - department: string (opcional) — Departamento (ej: cirugía, pediatría)
   - service_area: string (Emergencia/Pista/Disponible) (opcional) — Área de servicio (valor exacto): Emergencia, Pista o Disponible
   - service_active: boolean (opcional) — Solo médicos con servicio activo (default true)
   - pool_active: boolean (opcional) — Solo médicos activos en el pool de turnos (default true)
   - participa_misiones: boolean (opcional) — Filtrar por participación en misiones
   - group_by: string (sex/rank/department) (opcional) — Agrupar conteo por este criterio
   - count: boolean (opcional) — true → devolver solo el número total
   - no_assignments_in: object (opcional) — Médicos sin guardias asignadas en ese mes/año

2. doctor_info
   Pregunta típica: «Ficha completa de un médico específico». Devuelve rango, departamento, áreas permitidas, límites mensuales, estado y motivo de inactividad si aplica.
   Parámetros:
   - doctor_name: string (requerido) — Nombre o apellido del médico

3. doctor_availability
   Pregunta típica: «¿Qué días está disponible este médico?». Días del mes, patrón semanal, día preferido y si reportó disponibilidad.
   Parámetros:
   - doctor_name: string (requerido) — Nombre o apellido del médico
   - month: integer (opcional) — Mes (1-12); default: mes actual
   - year: integer (opcional) — Año (ej: 2026); default: año actual

4. doctor_restrictions
   Pregunta típica: «¿Qué licencias o restricciones tiene este médico o hay activas?». Sin doctor_name devuelve todas las restricciones activas del período.
   Parámetros:
   - doctor_name: string (opcional) — Nombre o apellido del médico (opcional: todas las activas)
   - month: integer (opcional) — Mes (1-12)
   - year: integer (opcional) — Año (ej: 2026)

5. doctor_service_history
   Pregunta típica: «¿Cuántas guardias lleva este médico o cuándo fue su última?». Total del período, última guardia y áreas cubiertas.
   Parámetros:
   - doctor_name: string (requerido) — Nombre o apellido del médico
   - month: integer (opcional) — Mes (1-12)
   - year: integer (opcional) — Año (ej: 2026)

6. workload_ranking
   Pregunta típica: «¿Quién lleva más o menos carga, o va corto de su meta mensual?». Ranking de carga mensual: `load` = servicios asignados; `target_gap` = faltante vs meta.
   Parámetros:
   - month: integer (requerido) — Mes (1-12)
   - year: integer (requerido) — Año (ej: 2026)
   - criterion: string (load/target_gap) (opcional) — load = más servicios; target_gap = más corto de su meta

## CALENDARIO Y TURNOS

1. calendar_assignments
   Pregunta típica: «¿Qué guardias hay en estas fechas?». Rango de fechas YYYY-MM-DD. Para un solo día usa la misma fecha en start y end.
   Parámetros:
   - start_date: string (requerido) — Fecha inicio YYYY-MM-DD
   - end_date: string (requerido) — Fecha fin YYYY-MM-DD (igual a start para un día)
   - service_area: string (Emergencia/Pista/Disponible) (opcional) — Área de servicio (valor exacto): Emergencia, Pista o Disponible
   - doctor_name: string (opcional) — Filtrar por médico
   - source: string (manual/generated) (opcional) — Origen de la asignación

2. calendar_status
   Pregunta típica: «¿Cómo va el calendario del mes?». Estado, semanas aprobadas/en borrador, asignaciones por área y huecos sin cubrir.
   Parámetros:
   - month: integer (requerido) — Mes (1-12)
   - year: integer (requerido) — Año (ej: 2026)

3. slot_recommendation
   Pregunta típica: «¿Quién puede cubrir este día y área?». Candidatos con razón y advertencias usando la evaluación del backend.
   Parámetros:
   - date: string (requerido) — Fecha YYYY-MM-DD
   - service_area: string (Emergencia/Pista/Disponible) (requerido) — Área de servicio (valor exacto): Emergencia, Pista o Disponible

4. slot_explanation
   Pregunta típica: «¿Por qué este médico está o no está asignado a este día y área?». Si está asignado usa el rationale guardado; si no, bloqueos y advertencias de su evaluación.
   Parámetros:
   - date: string (requerido) — Fecha YYYY-MM-DD
   - service_area: string (Emergencia/Pista/Disponible) (requerido) — Área de servicio (valor exacto): Emergencia, Pista o Disponible
   - doctor_name: string (requerido) — Nombre o apellido del médico

## DISPONIBILIDAD REPORTADA

1. doctors_available_on
   Pregunta típica: «¿Quiénes reportaron disponibilidad para este día?». Listado crudo de quienes reportaron disponibilidad, sin evaluar reglas de calendario.
   Parámetros:
   - date: string (requerido) — Fecha YYYY-MM-DD

2. availability_report_status
   Pregunta típica: «¿Quiénes ya reportaron disponibilidad este mes y quiénes no?». Médicos que ya enviaron su disponibilidad mensual y los que faltan.
   Parámetros:
   - month: integer (requerido) — Mes (1-12)
   - year: integer (requerido) — Año (ej: 2026)

## MISIONES

1. mission_list
   Pregunta típica: «¿Qué misiones hay?».
   Parámetros:
   - status: string (draft/active/completed/cancelled) (opcional) — Estado de la misión
   - month: integer (opcional) — Mes (1-12)
   - year: integer (opcional) — Año (ej: 2026)
   - include_participants: boolean (opcional) — Incluir participantes en el listado

2. mission_status
   Pregunta típica: «¿Cómo va esta misión?». Participantes, ranking, score y confirmaciones de la misión.
   Parámetros:
   - mission_name: string (requerido) — Nombre o parte del nombre de la misión

3. mission_candidates
   Pregunta típica: «¿Quiénes son candidatos para una misión?». Usa el ranking mensual guardado y filtra por la fecha de la misión.
   Parámetros:
   - mission_date: string (requerido) — Fecha de la misión YYYY-MM-DD
   - count: integer (opcional) — Cantidad de candidatos pedida (default 3)

## CONFIRMACIONES

1. confirmation_status
   Pregunta típica: «¿Quiénes confirmaron o faltan por confirmar?». Solicitudes de confirmación con su estado (pendiente, confirmada, declinada, expirada).
   Parámetros:
   - doctor_name: string (opcional) — Filtrar por médico
   - month: integer (opcional) — Mes (1-12)
   - year: integer (opcional) — Año (ej: 2026)

## NOTIFICACIONES Y ALERTAS

1. notification_status
   Pregunta típica: «¿Cómo van los envíos de notificaciones?». Incluye fallidas con su error y programadas. Sin `status`, resume todas.
   Parámetros:
   - status: string (pending/sent/failed) (opcional) — Estado de las notificaciones
   - doctor_name: string (opcional) — Filtrar por médico destinatario
   - month: integer (opcional) — Mes (1-12); default: mes actual
   - year: integer (opcional) — Año (ej: 2026); default: año actual

2. action_alerts
   Pregunta típica: «¿Qué tengo pendiente por atender?». Alertas de acción del sistema (confirmaciones vencidas, notificaciones fallidas, etc.).
   Parámetros:
   - status: string (open/resolved) (opcional) — Solo abiertas o ya resueltas (default open)
   - severity: string (warning/critical) (opcional) — Filtrar por severidad
   - section: string (opcional) — Sección del sistema (ej: confirmations, notifications)

## AUDITORÍA Y CONFIGURACIÓN

1. audit_history
   Pregunta típica: «¿Quién cambió qué y cuándo?». Eventos de auditoría: actor, acción y cuándo.
   Parámetros:
   - doctor_name: string (opcional) — Filtrar por médico afectado
   - action_type: string (opcional) — Tipo de acción (ej: assignment_added, calendar_approved)
   - start_date: string (opcional) — Fecha inicio YYYY-MM-DD
   - end_date: string (opcional) — Fecha fin YYYY-MM-DD

2. system_config
   Pregunta típica: «¿Qué reglas, áreas con pesos y límites están activos?». Devuelve áreas de servicio con su peso, reglas activas y límites por defecto.

## REPORTES

1. generate_report
   Pregunta típica: «Envíame el reporte del mes o de la semana». Genera y envía el PDF del calendario mensual o de la lista semanal.
   Parámetros:
   - type: string (monthly/weekly) (requerido) — monthly = calendario completo; weekly = lista semanal
   - month: integer (requerido) — Mes (1-12)
   - year: integer (requerido) — Año (ej: 2026)
   - week: string (opcional) — Para type=weekly: rango o semana (ej: '2026-05-04' o número)

## CONVERSACIONAL

1. reply
   Pregunta típica: «Hola, gracias, no entiendo o petición fuera de alcance». Responder directamente SIN consultar datos: saludos, gracias, despedida, ayuda, petición que no se entiende o fuera de alcance. clarify = no entendí la petición; out_of_scope = petición fuera del sistema (ej. escribir, aprobar o modificar algo — eso se hace en el panel web).
   Parámetros:
   - response_type: string (greeting/help/farewell/clarify/out_of_scope) (opcional) — Tipo de respuesta conversacional
```

---

## 2. Las 22 tools, una por una

| # | tool | pregunta típica |
|---|---|---|
| 1 | `list_doctors` | ¿Cuántos/cuáles médicos hay con estas características? |
| 2 | `doctor_info` | Ficha completa de un médico específico |
| 3 | `doctor_availability` | ¿Qué días está disponible este médico? |
| 4 | `doctor_restrictions` | ¿Qué licencias o restricciones tiene este médico o hay activas? |
| 5 | `doctor_service_history` | ¿Cuántas guardias lleva este médico o cuándo fue su última? |
| 6 | `workload_ranking` | ¿Quién lleva más o menos carga, o va corto de su meta mensual? |
| 7 | `calendar_assignments` | ¿Qué guardias hay en estas fechas? |
| 8 | `calendar_status` | ¿Cómo va el calendario del mes? |
| 9 | `slot_recommendation` | ¿Quién puede cubrir este día y área? |
| 10 | `slot_explanation` | ¿Por qué este médico está o no está asignado a este día y área? |
| 11 | `doctors_available_on` | ¿Quiénes reportaron disponibilidad para este día? |
| 12 | `availability_report_status` | ¿Quiénes ya reportaron disponibilidad este mes y quiénes no? |
| 13 | `mission_list` | ¿Qué misiones hay? |
| 14 | `mission_status` | ¿Cómo va esta misión? |
| 15 | `mission_candidates` | ¿Quiénes son candidatos para una misión? |
| 16 | `confirmation_status` | ¿Quiénes confirmaron o faltan por confirmar? |
| 17 | `notification_status` | ¿Cómo van los envíos de notificaciones? |
| 18 | `action_alerts` | ¿Qué tengo pendiente por atender? |
| 19 | `audit_history` | ¿Quién cambió qué y cuándo? |
| 20 | `system_config` | ¿Qué reglas, áreas con pesos y límites están activos? |
| 21 | `generate_report` | Envíame el reporte del mes o de la semana |
| 22 | `reply` | Hola, gracias, no entiendo o petición fuera de alcance |

---

### 1. `list_doctors`

**Pregunta típica:** «¿Cuántos/cuáles médicos hay con estas características?»

**Aclaración que el modelo lee:** Lista o cuenta médicos con los filtros indicados. Usa `count: true` cuando el usuario solo quiere el número. Usa `group_by` cuando pide conteos agrupados (por sexo, rango o departamento).

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `sex` | string | no | M/F | M (masculino) o F (femenino) |
| `rank` | string | no | — | Rango militar exacto (ej: Capitán, Mayor) |
| `department` | string | no | — | Departamento (ej: cirugía, pediatría) |
| `service_area` | string | no | Emergencia/Pista/Disponible | Área de servicio (valor exacto): Emergencia, Pista o Disponible |
| `service_active` | boolean | no | — | Solo médicos con servicio activo (default true) |
| `pool_active` | boolean | no | — | Solo médicos activos en el pool de turnos (default true) |
| `participa_misiones` | boolean | no | — | Filtrar por participación en misiones |
| `group_by` | string | no | sex/rank/department | Agrupar conteo por este criterio |
| `count` | boolean | no | — | true → devolver solo el número total |
| `no_assignments_in` | object | no | — | Médicos sin guardias asignadas en ese mes/año |

### 2. `doctor_info`

**Pregunta típica:** «Ficha completa de un médico específico»

**Aclaración que el modelo lee:** Devuelve rango, departamento, áreas permitidas, límites mensuales, estado y motivo de inactividad si aplica.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | sí | — | Nombre o apellido del médico |

### 3. `doctor_availability`

**Pregunta típica:** «¿Qué días está disponible este médico?»

**Aclaración que el modelo lee:** Días del mes, patrón semanal, día preferido y si reportó disponibilidad.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | sí | — | Nombre o apellido del médico |
| `month` | integer | no | — | Mes (1-12); default: mes actual |
| `year` | integer | no | — | Año (ej: 2026); default: año actual |

### 4. `doctor_restrictions`

**Pregunta típica:** «¿Qué licencias o restricciones tiene este médico o hay activas?»

**Aclaración que el modelo lee:** Sin doctor_name devuelve todas las restricciones activas del período.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | no | — | Nombre o apellido del médico (opcional: todas las activas) |
| `month` | integer | no | — | Mes (1-12) |
| `year` | integer | no | — | Año (ej: 2026) |

### 5. `doctor_service_history`

**Pregunta típica:** «¿Cuántas guardias lleva este médico o cuándo fue su última?»

**Aclaración que el modelo lee:** Total del período, última guardia y áreas cubiertas.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | sí | — | Nombre o apellido del médico |
| `month` | integer | no | — | Mes (1-12) |
| `year` | integer | no | — | Año (ej: 2026) |

### 6. `workload_ranking`

**Pregunta típica:** «¿Quién lleva más o menos carga, o va corto de su meta mensual?»

**Aclaración que el modelo lee:** Ranking de carga mensual: `load` = servicios asignados; `target_gap` = faltante vs meta.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `month` | integer | sí | — | Mes (1-12) |
| `year` | integer | sí | — | Año (ej: 2026) |
| `criterion` | string | no | load/target_gap | load = más servicios; target_gap = más corto de su meta |

### 7. `calendar_assignments`

**Pregunta típica:** «¿Qué guardias hay en estas fechas?»

**Aclaración que el modelo lee:** Rango de fechas YYYY-MM-DD. Para un solo día usa la misma fecha en start y end.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `start_date` | string | sí | — | Fecha inicio YYYY-MM-DD |
| `end_date` | string | sí | — | Fecha fin YYYY-MM-DD (igual a start para un día) |
| `service_area` | string | no | Emergencia/Pista/Disponible | Área de servicio (valor exacto): Emergencia, Pista o Disponible |
| `doctor_name` | string | no | — | Filtrar por médico |
| `source` | string | no | manual/generated | Origen de la asignación |

### 8. `calendar_status`

**Pregunta típica:** «¿Cómo va el calendario del mes?»

**Aclaración que el modelo lee:** Estado, semanas aprobadas/en borrador, asignaciones por área y huecos sin cubrir.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `month` | integer | sí | — | Mes (1-12) |
| `year` | integer | sí | — | Año (ej: 2026) |

### 9. `slot_recommendation`

**Pregunta típica:** «¿Quién puede cubrir este día y área?»

**Aclaración que el modelo lee:** Candidatos con razón y advertencias usando la evaluación del backend.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `date` | string | sí | — | Fecha YYYY-MM-DD |
| `service_area` | string | sí | Emergencia/Pista/Disponible | Área de servicio (valor exacto): Emergencia, Pista o Disponible |

### 10. `slot_explanation`

**Pregunta típica:** «¿Por qué este médico está o no está asignado a este día y área?»

**Aclaración que el modelo lee:** Si está asignado usa el rationale guardado; si no, bloqueos y advertencias de su evaluación.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `date` | string | sí | — | Fecha YYYY-MM-DD |
| `service_area` | string | sí | Emergencia/Pista/Disponible | Área de servicio (valor exacto): Emergencia, Pista o Disponible |
| `doctor_name` | string | sí | — | Nombre o apellido del médico |

### 11. `doctors_available_on`

**Pregunta típica:** «¿Quiénes reportaron disponibilidad para este día?»

**Aclaración que el modelo lee:** Listado crudo de quienes reportaron disponibilidad, sin evaluar reglas de calendario.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `date` | string | sí | — | Fecha YYYY-MM-DD |

### 12. `availability_report_status`

**Pregunta típica:** «¿Quiénes ya reportaron disponibilidad este mes y quiénes no?»

**Aclaración que el modelo lee:** Médicos que ya enviaron su disponibilidad mensual y los que faltan.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `month` | integer | sí | — | Mes (1-12) |
| `year` | integer | sí | — | Año (ej: 2026) |

### 13. `mission_list`

**Pregunta típica:** «¿Qué misiones hay?»

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `status` | string | no | draft/active/completed/cancelled | Estado de la misión |
| `month` | integer | no | — | Mes (1-12) |
| `year` | integer | no | — | Año (ej: 2026) |
| `include_participants` | boolean | no | — | Incluir participantes en el listado |

### 14. `mission_status`

**Pregunta típica:** «¿Cómo va esta misión?»

**Aclaración que el modelo lee:** Participantes, ranking, score y confirmaciones de la misión.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `mission_name` | string | sí | — | Nombre o parte del nombre de la misión |

### 15. `mission_candidates`

**Pregunta típica:** «¿Quiénes son candidatos para una misión?»

**Aclaración que el modelo lee:** Usa el ranking mensual guardado y filtra por la fecha de la misión.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `mission_date` | string | sí | — | Fecha de la misión YYYY-MM-DD |
| `count` | integer | no | — | Cantidad de candidatos pedida (default 3) |

### 16. `confirmation_status`

**Pregunta típica:** «¿Quiénes confirmaron o faltan por confirmar?»

**Aclaración que el modelo lee:** Solicitudes de confirmación con su estado (pendiente, confirmada, declinada, expirada).

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | no | — | Filtrar por médico |
| `month` | integer | no | — | Mes (1-12) |
| `year` | integer | no | — | Año (ej: 2026) |

### 17. `notification_status`

**Pregunta típica:** «¿Cómo van los envíos de notificaciones?»

**Aclaración que el modelo lee:** Incluye fallidas con su error y programadas. Sin `status`, resume todas.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `status` | string | no | pending/sent/failed | Estado de las notificaciones |
| `doctor_name` | string | no | — | Filtrar por médico destinatario |
| `month` | integer | no | — | Mes (1-12); default: mes actual |
| `year` | integer | no | — | Año (ej: 2026); default: año actual |

### 18. `action_alerts`

**Pregunta típica:** «¿Qué tengo pendiente por atender?»

**Aclaración que el modelo lee:** Alertas de acción del sistema (confirmaciones vencidas, notificaciones fallidas, etc.).

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `status` | string | no | open/resolved | Solo abiertas o ya resueltas (default open) |
| `severity` | string | no | warning/critical | Filtrar por severidad |
| `section` | string | no | — | Sección del sistema (ej: confirmations, notifications) |

### 19. `audit_history`

**Pregunta típica:** «¿Quién cambió qué y cuándo?»

**Aclaración que el modelo lee:** Eventos de auditoría: actor, acción y cuándo.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `doctor_name` | string | no | — | Filtrar por médico afectado |
| `action_type` | string | no | — | Tipo de acción (ej: assignment_added, calendar_approved) |
| `start_date` | string | no | — | Fecha inicio YYYY-MM-DD |
| `end_date` | string | no | — | Fecha fin YYYY-MM-DD |

### 20. `system_config`

**Pregunta típica:** «¿Qué reglas, áreas con pesos y límites están activos?»

**Aclaración que el modelo lee:** Devuelve áreas de servicio con su peso, reglas activas y límites por defecto.

**Parámetros:** ninguno.

### 21. `generate_report`

**Pregunta típica:** «Envíame el reporte del mes o de la semana»

**Aclaración que el modelo lee:** Genera y envía el PDF del calendario mensual o de la lista semanal.

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `type` | string | sí | monthly/weekly | monthly = calendario completo; weekly = lista semanal |
| `month` | integer | sí | — | Mes (1-12) |
| `year` | integer | sí | — | Año (ej: 2026) |
| `week` | string | no | — | Para type=weekly: rango o semana (ej: '2026-05-04' o número) |

### 22. `reply`

**Pregunta típica:** «Hola, gracias, no entiendo o petición fuera de alcance»

**Aclaración que el modelo lee:** Responder directamente SIN consultar datos: saludos, gracias, despedida, ayuda, petición que no se entiende o fuera de alcance. clarify = no entendí la petición; out_of_scope = petición fuera del sistema (ej. escribir, aprobar o modificar algo — eso se hace en el panel web).

**Parámetros:**

| parámetro | tipo | obligatorio | enum | qué dice la descripción |
|---|---|---|---|---|
| `response_type` | string | no | greeting/help/farewell/clarify/out_of_scope | Tipo de respuesta conversacional |

---

## 3. Dónde se pisan las descripciones

Revisión manual de los choques que explican elecciones equivocadas de tool:

- **`calendar_assignments` vs `list_doctors` vs `doctor_service_history`** — «qué médicos hicieron servicio el 3 de agosto»
  - Ninguna pregunta canónica cubre «médicos que trabajaron en una fecha»: `calendar_assignments` habla de *guardias* (no de médicos), `list_doctors` habla de *médicos* (sin fechas) y `doctor_service_history` exige un médico concreto. Con fecha + médicos en la misma frase el modelo cae a `list_doctors`.
- **`list_doctors` vs `doctors_available_on` vs `availability_report_status`** — «quién está disponible»
  - `list_doctors` filtra por `service_active`/`pool_active` (estado del sistema), `doctors_available_on` es disponibilidad *reportada para un día* y `availability_report_status` es *quién reportó el mes*. Las tres usan la palabra «disponible» con sentidos distintos.
- **`calendar_assignments` vs `calendar_status`** — «el calendario de agosto»
  - `calendar_status` (mes/año) y `calendar_assignments` (rango de fechas) se solapan en el caso «mes completo»; nada dice cuál gana cuando no se pide estado ni huecos.
- **`doctors_available_on` vs `slot_recommendation` vs `slot_explanation`** — «quién puede cubrir el 3 de agosto en Emergencia»
  - `doctors_available_on` es listado crudo sin evaluar reglas; `slot_recommendation` sí evalúa. La diferencia «reportó» vs «puede cubrir» no está explícita en la descripción.
- **`workload_ranking` vs `doctor_service_history` vs `mission_candidates`** — «cómo va la carga»
  - `workload_ranking` es ranking de *servicio* mensual y `mission_candidates` usa el ranking guardado de *misiones*; `doctor_service_history` es el mismo dato pero de un médico. Tres «rankings» con fuentes distintas.
- **`confirmation_status` vs `notification_status` vs `action_alerts`** — «qué está pendiente»
  - Las tres devuelven cosas «pendientes»: confirmaciones, envíos y alertas de acción. Sin la palabra clave de cada dominio el modelo puede elegir cualquiera.
- **`generate_report` vs `calendar_status` / `list_doctors`** — «mándame el reporte de agosto»
  - `generate_report` produce un *documento* (PDF) y las otras devuelven datos en el chat. La palabra «reporte» aparece en varios sitios.

---

## 4. Dónde se ajusta cada cosa

- Descripciones y parámetros de las tools: `backend/app/application/telegram/tool_registry.py`
- Reglas de elección y contrato de comportamiento: `backend/app/application/telegram/intent_classifier.py` (`NLU_SYSTEM_PROMPT`)
- Contexto de BD que acompaña al prompt (catálogos, reglas activas): `backend/app/application/telegram/system_context.py`
- Plantillas SQL que ejecuta cada tool (no las ve el modelo): `backend/app/application/telegram/registry.py`

