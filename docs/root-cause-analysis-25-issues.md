# Análisis de Causa Raíz — 25 Issues del Bot de Telegram

**Fecha:** 2026-05-15
**Rama:** `before-dev`
**Objetivo:** Diagnóstico quirúrgico de cada issue, impacto real en el sistema, y soluciones concretas.

---

## Resumen Ejecutivo

Los 25 issues se agrupan en **6 patrones de causa raíz**:

| Grupo | Issues | Causa raíz | Severidad sistémica |
|-------|--------|-----------|---------------------|
| G1: EntityResolver greedy | I1 | Resolución de rango "sargento mayor" → "sargento" por `break` prematuro | **Alta** — datos incorrectos |
| G2: Contexto multi-turno | I2, I3, I8, I11, I21 | SessionStore no se consulta para operaciones de export; filtros no se heredan | **Alta** — rompe flujo conversacional |
| G3: UUIDs expuestos | I14, I16, I22 | `format_rows()` trunca a 3 columnas sin priorizar columnas informativas; columnas con UUIDs no siempre filtradas | **Media** — experiencia de usuario |
| G4: QueryExecutor sin entity hints | I10, I12, I13, I15, I17, I18, I24, I25 | `_fallback_to_query_db()` no recibe entity_hints; QueryExecutor genera SQL sin conocer IDs reales | **Alta** — 8 issues con fallos en consultas |
| G5: Registry gaps | I5, I6, I7, I9, I24, I25 | Faltan query_types para filtros compuestos, auditoría, duplicados, notificaciones | **Media** — funcionalidad ausente |
| G6: Diseño de respuestas | I4, I19, I20, I23 | `format_rows()` mecánico — 3 columnas máx, sin priorización, sin lenguaje natural | **Media** — respuestas pobres |

---

## G1: EntityResolver — Resolución Greedy de Rangos

### Issue: I1

**Síntoma:** "Sargento mayor" muestra sargentos regulares (casos #28, #29, #47, #48, #60).

### Causa raíz

`entity_resolver.py:387-401` — la detección de rangos:

```python
for rank in ranks:
    rank_words = _normalize_text(rank.normalized_name).split()
    if any(word in msg_normalized for word in rank_words if len(word) >= 3):
        resolved["rank"] = {...}
        hints_parts.append(f"rank_id={rank.id}, rank_name='{rank.normalized_name}'")
        break  # ← SALE en el primer match
```

El mensaje "cuantos sargentos mayores tengo" contiene la palabra "sargento". Al iterar los ranks, "sargento" hace match primero (está antes en la DB que "sargento mayor"). El `break` impide que se considere "sargento mayor".

Adicionalmente, el match usa `any(word in msg_normalized for word in rank_words)` — si `rank_words` es `["sargento", "mayor"]`, la palabra "sargento" está en el mensaje, y el match es True para el rank "sargento".

### Impacto

- **Datos incorrectos:** El usuario pregunta por sargentos mayores y recibe datos de sargentos regulares. Es **información errónea**, no solo falta de datos.
- **Efecto cascada:** Exportaciones PDF/Excel también contienen datos equivocados (#60).

### Solución

Dos cambios en `entity_resolver.py`:

**1. Buscar el match más largo, no el primero:**

```python
# En lugar de break en el primer match, recolectar todos los matches
# y quedarse con el de mayor longitud de nombre
best_match = None
best_len = 0
for rank in ranks:
    rank_words = _normalize_text(rank.normalized_name).split()
    if any(word in msg_normalized for word in rank_words if len(word) >= 3):
        name_len = len(rank.normalized_name)
        if name_len > best_len:
            best_match = rank
            best_len = name_len
if best_match:
    resolved["rank"] = {...}
```

**2. Adicionalmente en `resolve_rank()`: usar match exacto primero:**

```python
def resolve_rank(self, name: str) -> ResolveResult:
    name_lower = name.lower().strip()
    # Primero buscar match exacto
    exact = [r for r in all_ranks if r.normalized_name.lower() == name_lower]
    if exact:
        matches = exact
    else:
        matches = [r for r in all_ranks if name_lower in r.normalized_name.lower()]
```

---

## G2: Contexto Multi-Turno — Pérdida de Filtros

### Issues: I2, I3, I8, I11, I21

**Síntomas:**
- I2: "De esos, exportalo en PDF" → exporta datos sin filtro previo
- I3: "Ahora dame solo los masculinos" → no retiene filtro de rango
- I8: "Ese medico" → devuelve todos los médicos
- I11: "Y el de agosto?" → no retiene tema de calendario
- I21: "Si el primero no puede, quien sigue?" → no retiene ranking

### Causa raíz

El sistema tiene DOS mecanismos de contexto, ambos insuficientes:

**A. `_merge_followup_context()` (agent.py:649-683):**
- Solo se activa cuando `_count_filter_dims(entity_hints) < 2`
- Solo mergea filtros de la sesión anterior como entity_hints para el LLM
- Pero si el LLM no usa esos hints (o la query no llega al LLM porque toma ruta determinística sin los filtros), se pierden

**B. `_remember_result()` (agent.py:468-519):**
- Guarda `last_results`, `last_filters`, `last_query_type`, `last_params`
- Pero **nunca se reutilizan** en exportaciones ni en queries subsecuentes
- `last_results` se guarda pero ningún código las lee para responder follow-ups

**C. El problema específico de exportaciones:**
- "De esos, exportalo en PDF" → el LLM recibe el mensaje. EntityResolver no encuentra entidades → `entity_hints=""`. 
- `_merge_followup_context()` agrega filtros de la sesión a entity_hints (si `_count_filter_dims < 2`), pero export NO es una operación que el DoctorQueryService maneje automáticamente con filtros merged.
- El LLM selecciona `action=export, query_type=doctors_by_rank` con `params={}` (sin el rank), y el router ejecuta la query sin filtro → devuelve todos los médicos.

### Impacto

- **Funcionalidad rota:** El usuario no puede tener una conversación natural con follow-ups. Cada pregunta debe ser autocontenida.
- Esto **rompe el modelo conversacional** que es el propósito central del bot.

### Solución

**1. Hacer que `_merge_followup_context()` funcione para exportaciones:**

En `_fallback_to_query_db()` y en el path de export, cuando `entity_hints` está vacío y la sesión tiene `last_filters`, inyectar los filtros:

```python
def _fallback_to_query_db(self, user_text: str, entity_hints: str = "") -> AgentResult:
    if self._query_executor is None:
        return AgentResult(...)
    
    # Inyectar entity_hints de la sesión si no hay nuevos
    if not entity_hints and self._session_store:
        state = self._session_store.get(telegram_user_id)
        if state and state.last_filters:
            hints_parts = []
            for k, v in state.last_filters.items():
                hints_parts.append(f"{k}={v}")
            entity_hints = ", ".join(hints_parts)
    
    result = self._query_executor.execute(user_text, user_text, entity_hints=entity_hints)
```

**2. Para referencias anafóricas ("ese medico", "el primero"):**

El `EntityResolver.resolve_reference()` (line 261-291) ya existe pero **nunca se llama desde `process()`**. Agregar la llamada:

```python
# En process(), después de entity pre-processing:
ref_idx = self._entity_resolver.resolve_reference(text, session_state)
if ref_idx is not None and session_state.get("last_results"):
    ref_data = session_state["last_results"][ref_idx]
    # Inyectar como entidad resuelta
    resolved_entities["doctor"] = ref_data
    entity_hints += f", doctor_id={ref_data.get('id')}"
```

**3. Para "Y el de agosto?":**

`_calendar_followup_query_intent()` (agent.py:585-630) solo aplica cuando el dominio anterior es `calendar_assignments`. Ampliar para otros dominios (calendar_status, mission_ranking).

---

## G3: UUIDs Expuestos al Usuario

### Issues: I14, I16, I22

**Síntomas:**
- I14: UUIDs como "7ea6f5f4-23c5-4cdf-80a6-e9468407c6e7" en respuestas de calendarios
- I16: UUIDs en respuestas de carga de trabajo
- I22: UUIDs en respuestas de misiones

### Causa raíz

El filtrado de columnas internas ocurre en 3 lugares distintos:

1. `sanitize.py:_public_columns()` — filtra `id` y `*_id`
2. `intent_router.py:_public_columns()` — idéntica, filtra `id` y `*_id`
3. `query_executor.py:_strip_internal_identifier_columns()` — idéntica, filtra `id` y `*_id`

El problema NO es que el filtro falle en columnas `_id`. El problema es más sutil:

**A. Resultados vía QueryExecutor (NL-to-SQL):** El LLM genera SQL con `SELECT *` o selecciona columnas que incluyen claves foráneas. Si la query es `SELECT d.id, d.name, d.department_id FROM doctors...`, el `department_id` se filtra (termina en `_id`), pero `d.id` también se filtra. Sin embargo, si el LLM genera `SELECT d.id AS doctor_identifier`, el alias NO termina en `_id` → el UUID pasa.

**B. `format_rows()` trunca a 3 columnas pero no hay control de CUÁLES 3:** Las columnas se toman en orden SQL. Si el orden es `id, name, sex`, se muestran `name, sex` (id se filtra). Pero si el orden es `year, month, id, name`, se muestran `year, month` (id se filtra, name queda fuera).

**C. Posible fuente real de UUIDs:** Cuando el LLM genera SQL que incluye `doctor_id` de una tabla JOIN, y la columna se llama `doctor_id` en el resultado, el filtro `_id` SÍ la elimina. Pero si el LLM la renombra (ej. `AS medico_id_interno` o algo que no termina en `_id`), pasa el filtro.

### Impacto

- **Experiencia de usuario degradada:** UUIDs no son legibles para humanos
- **No es fuga de datos sensible:** Los UUIDs son identificadores internos, no datos protegidos
- **Media severidad** porque no rompe funcionalidad pero hace las respuestas incomprensibles

### Solución

**1. Agregar filtro por patrón UUID en el valor mismo:**

```python
import re
_UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    re.IGNORECASE
)

def _is_uuid_column(rows: list[dict], column: str) -> bool:
    """Check if a column contains only UUID values."""
    if not rows:
        return False
    samples = [row.get(column) for row in rows[:5] if row.get(column) is not None]
    if not samples:
        return False
    return all(isinstance(v, str) and _UUID_PATTERN.match(v) for v in samples)
```

**2. En `_public_columns()`, agregar detección de UUIDs:**

```python
def _public_columns(columns: list[str], rows: list[dict] | None = None) -> list[str]:
    cols = [c for c in columns if c.lower() != "id" and not c.lower().endswith("_id")]
    if rows:
        cols = [c for c in cols if not _is_uuid_column(rows, c)]
    return cols
```

**3. Priorizar columnas informativas en `format_rows()`:**

En lugar de `cols[:3]`, seleccionar las 3 columnas más informativas (excluyendo año/mes que son contexto implícito).

---

## G4: QueryExecutor sin Entity Hints

### Issues: I10, I12, I13, I15, I17, I18, I24, I25

**Síntomas:**
- I10: Consultas de estado de calendario fallan vía NL fallback
- I12: Consultas por fecha específica ("primer lunes", "4 de julio") no encuentran datos
- I13: "Cuantos servicios hay en julio?" devuelve 0
- I15: Consultas por área (Emergencia, Pista, UCI) sin datos
- I17: Consultas complejas (distribución, metas) devuelven ambiguous
- I18: Misiones de agosto fallan (sin datos)
- I24: "Quien aprobo el calendario?" — único ❌ total
- I25: Notificaciones/confirmaciones/auditoría sin query_types

### Causa raíz

**El problema central:** `_fallback_to_query_db()` en agent.py:428 no recibe `entity_hints`:

```python
result = self._query_executor.execute(user_text, user_text)
#                                       ^^^^^^^^^  ^^^^^^^^^
#                                       nl_query   user_text (sin hints!)
```

Y `QueryExecutor.execute()` en query_executor.py:162-166 no acepta `entity_hints`:

```python
def execute(self, nl_query: str, user_text: str = "") -> dict:
    sql = self._generate_sql(nl_query, user_text)
```

El resultado: cuando una consulta cae al fallback NL-to-SQL, el LLM que genera SQL **no recibe los valores reales de las entidades** (IDs de doctores, áreas, departamentos, meses/años resueltos). Tiene que adivinar basándose solo en el texto del usuario y el esquema.

### Desglose por sub-issue

**I10 (estado calendario):** El LLM del agente principal detecta `calendar_status_month`, el router lo ejecuta, pero si no hay datos → fallback. El QueryExecutor regenera SQL sin saber el mes/año resuelto → SQL incorrecto.

**I12 (fechas específicas):** "Primer lunes de agosto" requiere cómputo de fecha. Ni EntityResolver ni calendar_query_service lo resuelven. El QueryExecutor recibe el texto crudo y el LLM no puede calcular "primer lunes" en SQL portable.

**I13 (servicios totales):** `_calendar_assignment_query_intent()` mapea "cuantos" + mes → `count_assigned_doctors_by_month`. Pero esta query cuenta **doctores distintos**, no servicios totales. La query correcta sería `COUNT(*) FROM calendar_assignments`.

**I15 (áreas):** EntityResolver resuelve el área, genera hints con `area_id=X`. Pero la ruta determinística de calendario (`_calendar_week_query_intent` / `_calendar_assignment_query_intent`) NO usa áreas → va al router con una query sin filtro de área → fallback. El fallback no recibe `area_id` → SQL sin filtro de área.

**I24 (aprobador del calendario):** `audit_logs` está en `_EXCLUDE_TABLES` (query_executor.py:40) → el QueryExecutor **no puede** generar SQL contra esa tabla. No hay query_type registrado. Es un **bloqueo total por diseño**.

**I25 (notificaciones/confirmaciones):** No hay query_types para:
- `notifications` (medicos que no confirmaron)
- Auditoría de cambios
- Confirmaciones de servicio/misión

### Impacto

- **8 issues, todos de severidad Alta o Media**
- **I24 es bloqueante total** — el usuario NUNCA recibirá respuesta sobre quién aprobó
- Las consultas por área/fecha son preguntas operacionales FRECUENTES
- Es el grupo más grande de issues

### Solución

**1. Pasar entity_hints a QueryExecutor (crítico):**

```python
# query_executor.py
def execute(self, nl_query: str, user_text: str = "", entity_hints: str = "") -> dict:
    sql = self._generate_sql(nl_query, user_text, entity_hints=entity_hints)

def _generate_sql(self, nl_query: str, user_text: str = "", entity_hints: str = "") -> str:
    entity_section = ""
    if entity_hints:
        entity_section = (
            f"\n\nENTIDADES DETECTADAS (usa estos valores exactos en los predicados SQL):\n"
            f"{entity_hints}\n"
        )
    # ... incluir entity_section en el prompt

# agent.py
def _fallback_to_query_db(self, user_text: str, entity_hints: str = "") -> AgentResult:
    result = self._query_executor.execute(user_text, user_text, entity_hints=entity_hints)
```

Y actualizar las 3 llamadas en `process()` (líneas 878, 984, 1059) para pasar `entity_hints`.

**2. Registrar query_type seguro para auditoría (I24):**

```python
{
    "query_type": "calendar_approval_info",
    "sql_template": (
        "SELECT a.action, a.created_at, u.full_name AS actor "
        "FROM audit_logs a "
        "JOIN users u ON a.actor_id = u.id "
        "WHERE a.resource_type = 'calendar' "
        "AND a.resource_id = ("
        "  SELECT c.id FROM calendars c "
        "  WHERE c.year = :year AND c.month = :month "
        "  ORDER BY c.created_at DESC LIMIT 1"
        ") "
        "ORDER BY a.created_at DESC LIMIT 5"
    ),
    "params_schema": {"year": "int", "month": "int"},
    "description": "Informacion de aprobacion y cambios de un calendario.",
}
```

**3. Agregar query_types para notificaciones/confirmaciones (I25):**

```python
{
    "query_type": "pending_service_confirmation",
    "sql_template": (
        "SELECT d.name, ca.service_date, sa.display_name AS area "
        "FROM calendar_assignments ca "
        "JOIN doctors d ON ca.doctor_id = d.id "
        "JOIN service_areas sa ON ca.service_area_id = sa.id "
        "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
        "JOIN calendars c ON cv.calendar_id = c.id "
        "WHERE c.year = :year AND c.month = :month "
        "AND ca.confirmed = FALSE "
        "ORDER BY ca.service_date, d.name"
    ),
    "params_schema": {"year": "int", "month": "int"},
    "description": "Medicos que no han confirmado servicio en un mes.",
}
```

**4. Corregir `count_assigned_doctors_by_month` vs "servicios totales" (I13):**

Agregar nuevo query_type:

```python
{
    "query_type": "total_services_by_month",
    "sql_template": (
        "SELECT COUNT(*) AS total "
        "FROM calendar_assignments ca "
        "JOIN calendar_versions cv ON ca.calendar_version_id = cv.id "
        "JOIN calendars c ON cv.calendar_id = c.id "
        "WHERE c.year = :year AND c.month = :month"
    ),
    "params_schema": {"year": "int", "month": "int"},
    "description": "Total de servicios en un mes (suma todos los turnos).",
}
```

Y ajustar `_calendar_assignment_query_intent()` para distinguir "cuantos servicios" vs "cuantos medicos".

---

## G5: Registry Gaps — Query Types Faltantes

### Issues: I5, I6, I7, I9

**Síntomas:**
- I5: "Recurso Humanos" devuelve resumen en vez del conteo específico (#76)
- I6: Filtros compuestos no aplican: "cabos en Recursos Humanos" ignora departamento (#84, #88, #89)
- I7: Preguntas específicas sobre Acosta Ramos (rango/sexo/departamento) no responden directamente (#95, #96, #97)
- I9: No entiende "médicos duplicados" (#108, #109, #110)

### Causa raíz

**I5:** El EntityResolver detecta "Recurso Humanos" como departamento y genera `department_id=X`. Pero `_calendar_assignment_query_intent()` tiene prioridad sobre el query determinístico de doctor. La frase "Cuantos medicos hay en Recurso Humanos" NO contiene palabras de calendario → pasa a la ruta de doctor_query_service. Sin embargo, `DoctorQueryService._operation_from_text()` detecta "cuantos" + sin filtro de sexo → `count`, no `list`. La respuesta es un conteo, pero:

El problema real es que `entity_resolver.py` busca departamentos por `normalized_name`. Si el nombre normalizado de "Recursos Humanos" es "recursos humanos", y el usuario escribe "Recurso Humanos" (singular), el match `dept_name in msg_normalized` falla porque "recursos humanos" no está contenido en "recurso humanos" (plural vs singular).

**I6:** No hay query_type para filtros compuestos. El sistema depende del DoctorQueryService para queries determinísticas con hasta 3 filtros, pero la prioridad de ruta (`_calendar_assignment_query_intent` primero, luego doctor_query_service) a veces deriva la query por un camino sin los filtros completos.

Cuando los filtros son compuestos (rank + department, sex + department, etc.), `_count_filter_dims() >= 2` → a partir de línea 874, va directo a `_fallback_to_query_db()` sin pasar por DoctorQueryService. El QueryExecutor no recibe entity_hints (ver G4).

**I7:** `doctor_detail` query_type solo selecciona `name, sex, availability_mode, active, service_active` de la tabla doctors. No hace JOIN con ranks ni departments. Para responder "cual es el rango de Acosta Ramos?", se necesita:

```sql
SELECT d.name, d.sex, r.name AS rank, dep.name AS department
FROM doctors d
JOIN ranks r ON d.rank_id = r.id
JOIN departments dep ON d.department_id = dep.id
WHERE d.name LIKE '%' || :search || '%'
```

**I9:** DoctorQueryService tiene `_possible_duplicate_names()` (línea 34-44) que encuentra nombres duplicados. Pero:
1. Los duplicados solo se guardan en `tool_result.metadata`, no en `response_text`
2. "Medicos duplicados" no activa la ruta determinística de doctor (no contiene filtros de entidad reconocibles)
3. No hay query_type para duplicados

### Impacto

- **Media severidad** — funcionalidad esperada ausente pero el sistema no responde con datos incorrectos (simplemente no responde bien)
- Los filtros compuestos son preguntas operacionales comunes

### Solución

**I5:** En `entity_resolver.py`, normalizar la búsqueda de departamento para manejar variaciones singular/plural:

```python
# Usar stem/aproximación en vez de match exacto de substring
msg_words = set(msg_normalized.split())
for department in departments:
    dept_words = set(_normalize_text(department.normalized_name).split())
    # Si al menos una palabra significativa coincide
    if dept_words & msg_words:
        # match
```

**I6:** La solución de G4 (pasar entity_hints a QueryExecutor) resuelve la mayoría. Adicionalmente, no desviar queries con 2+ filtros directamente a fallback — probar DoctorQueryService primero:

```python
# En vez de:
if _count_filter_dims(entity_hints) >= 2 and self._query_executor is not None:
    result = self._fallback_to_query_db(text)  # sin entity_hints

# Hacer:
if _count_filter_dims(entity_hints) >= 2 and self._doctor_query_service is not None:
    result = self._doctor_query_service.execute(text, resolved_entities)
    if result is not None:
        return result
# Solo entonces fallback con entity_hints
if _count_filter_dims(entity_hints) >= 2 and self._query_executor is not None:
    result = self._fallback_to_query_db(text, entity_hints=entity_hints)
```

**I7:** Actualizar `doctor_detail` SQL template para incluir JOINs:

```python
{
    "query_type": "doctor_detail",
    "sql_template": (
        "SELECT d.name, d.sex, r.name AS rank, dep.name AS department, "
        "d.availability_mode, d.active, d.service_active "
        "FROM doctors d "
        "LEFT JOIN ranks r ON d.rank_id = r.id "
        "LEFT JOIN departments dep ON d.department_id = dep.id "
        "WHERE d.name LIKE '%' || :search || '%' OR d.id = :search_id"
    ),
    "params_schema": {"search": "str", "search_id": "str"},
    "description": "Detalle completo de un medico por nombre o ID.",
}
```

**I9:** Agregar query_type para duplicados, o mejor: hacer que `format_rows()` incluya la info de `possible_duplicate_names` del tool_result cuando existe.

---

## G6: Diseño de Respuestas — Formato Mecánico

### Issues: I4, I19, I20, I23

**Síntomas:**
- I4: "Son 24 o 23 sargentos femeninos?" → solo lista resultados, no confirma
- I19: Ranking muestra año/mes/posición sin nombres de médicos
- I20: "No elegibles" expone datos de usuarios del sistema
- I23: Resumen de misiones devuelve datos crudos

### Causa raíz

**I19 — La más reveladora:** `format_rows()` en sanitize.py:102:

```python
lines = [
    f"{i+1}. " + " | ".join(
        display_value(c, r.get(c, "")) for c in cols[:3]
    )
    ...
]
```

El ranking de misiones tiene columnas: `year, month, ranking_position, doctor_name, total_load_score, eligible`. Las primeras 3 son `year, month, ranking_position`. `doctor_name` (la más importante) es la 4ta columna → **nunca se muestra**.

La función `_public_columns()` filtra `id` y `*_id`, pero `year` y `month` pasan el filtro (no son IDs). Son columnas "públicas" pero **no informativas** en un contexto donde el usuario ya sabe el período.

**I4:** `format_rows()` no puede responder preguntas de sí/no. Es puramente mecánico. Si el resultado es `total: 26`, el usuario preguntó "son 24 o 23?" — el bot muestra `total: 26` sin decir "no, son 26".

**I20:** La query NL-to-SQL para "no elegibles" generó SQL que incluyó la tabla `users`. Esto es un error del LLM generando SQL incorrecto. El `_EXCLUDE_TABLES` solo bloquea queries que mencionan explícitamente la tabla — si el LLM genera un JOIN incorrecto que trae datos de users, el validador no lo detecta.

### Impacto

- **Media severidad** — las respuestas son técnicamente correctas pero pobremente comunicadas
- I19 es particularmente grave porque la información más importante (nombre del médico) está ausente

### Solución

**1. Corregir `format_rows()` para priorizar columnas informativas:**

```python
def _informative_columns(columns: list[str], rows: list[dict]) -> list[str]:
    """Ordena columnas: las informativas primero, metadatos (año/mes) al final."""
    METADATA_PATTERNS = {'year', 'month', 'period_year', 'period_month', 
                         'ranking_position', 'id', 'created_at', 'updated_at'}
    info_cols = [c for c in columns if c.lower() not in METADATA_PATTERNS]
    meta_cols = [c for c in columns if c.lower() in METADATA_PATTERNS]
    return info_cols + meta_cols
```

**2. Aumentar el límite de columnas mostradas:** De 3 a 5 en modo lista.

**3. Para I4 (preguntas sí/no):** El plan ya incluye `_format_nl_response()` que usa LLM para convertir resultados en lenguaje natural. Eso resolvería I4, I20, I23.

**4. Formato especial para rankings:** Cuando el query_type es `mission_ranking`, formatear como lista numerada con nombres primero.

---

## Priorización de Correcciones

### Bloque 1: Críticas (rompen funcionalidad — arreglar primero)

| # | Issue(s) | Cambio | Archivos | Esfuerzo |
|---|----------|--------|----------|----------|
| 1 | I1 | Arreglar EntityResolver rank greedy | `entity_resolver.py:387-401` | 30 min |
| 2 | I6, I10, I12, I15, I17 | Pasar entity_hints a QueryExecutor | `agent.py:428`, `query_executor.py:144,183` | 1 hr |
| 3 | I2, I3, I8, I11, I21 | Mergear filtros de sesión en exportaciones y fallback | `agent.py:420-466, 649-683` | 2 hr |
| 4 | I24 | Agregar query_type de auditoría segura | `registry.py:280+` | 30 min |

### Bloque 2: Importantes (degradan experiencia)

| # | Issue(s) | Cambio | Archivos | Esfuerzo |
|---|----------|--------|----------|----------|
| 5 | I19 | Corregir `format_rows()` priorización de columnas | `sanitize.py:77-111` | 45 min |
| 6 | I14, I16, I22 | Filtro de UUID por patrón en valores | `sanitize.py:69-74`, `intent_router.py:38-40`, `query_executor.py:67-82` | 1 hr |
| 7 | I13 | Nuevo query_type `total_services_by_month` | `registry.py`, `agent.py:167-192` | 30 min |
| 8 | I7 | Actualizar `doctor_detail` con JOINs | `registry.py:135-139` | 15 min |
| 9 | I5 | Mejorar detección de departamentos (singular/plural) | `entity_resolver.py:403-420` | 30 min |
| 10 | I25 | Agregar query_types notificaciones/confirmaciones | `registry.py:280+` | 1 hr |

### Bloque 3: Mejoras (refinan experiencia)

| # | Issue(s) | Cambio | Archivos | Esfuerzo |
|---|----------|--------|----------|----------|
| 11 | I4, I20, I23 | `_format_nl_response()` con LLM | `agent.py` (nuevo método) | 1.5 hr |
| 12 | I9 | Exponer `possible_duplicate_names` en respuesta | `doctor_query_service.py:77`, `agent.py` | 30 min |
| 13 | I18 | Verificar si hay datos de misión para agosto (posiblemente no es bug) | Investigación | 30 min |

---

## Archivos Modificados

| Archivo | Issues que resuelve |
|---------|-------------------|
| `entity_resolver.py` | I1, I5 |
| `agent.py` | I2, I3, I4, I8, I11, I17, I21, I23 |
| `query_executor.py` | I6, I10, I12, I15, I17, I18 |
| `registry.py` | I6, I7, I13, I24, I25 |
| `sanitize.py` | I14, I16, I19, I22 |
| `doctor_query_service.py` | I6, I9 |

---

## Verificación

Para cada fix, el test correspondiente del archivo `docs/telegram_220_casos_prueba.md` debe pasar. Los casos específicos están documentados en la tabla de issues.

El plan de implementación detallado (con pasos TDD) está en `docs/superpowers/plans/2026-05-15-telegram-25-issues-fix.md`.
