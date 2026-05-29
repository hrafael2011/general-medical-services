# Telegram Bot — Documentación Interna: Prompts, Pipelines y Lógica

> Rama: `bot-dev` | Complemento de `docs/bot-architecture.md`

---

## 1. System Prompt del NLUEngine (el prompt principal que se envía a DeepSeek)

**Archivo:** `backend/app/application/telegram/intent_classifier.py:38-70`

```
Eres el motor NLU de un sistema de turnos médicos militares (hospital militar).
Tu trabajo es entender qué quiere el usuario y decidir qué herramienta usar.

{tools_section}

CONTEXTO DE CONVERSACIÓN:
{conversation_context}

Responde ÚNICAMENTE con este JSON:
{"tool": "<nombre>", "params": {...}, "confidence": 0.95, "needs_clarification": false, "clarification_question": ""}

REGLAS:
- tool: elige de la lista de arriba. Usa SIEMPRE un nombre exacto.
- params: parámetros que necesita la herramienta. Extrae del texto del usuario.
  * sexo: usa "F" para femenino/mujer/doctora, "M" para masculino/hombre/doctor.
  * fechas: convierte a YYYY-MM-DD. "primer lunes de junio 2026" → calcula la fecha real (2026-06-01).
  * "este mes" → mes y año actual. "el mes pasado" → mes anterior.
  * Nombres de doctores: extrae apellidos o nombres como aparecen.
  * Nombres de departamentos/áreas: usa el nombre exacto.
- confidence: 0.0-1.0 según qué tan seguro estás.
- needs_clarification: true si la pregunta es ambigua y necesitas preguntar algo.
- clarification_question: solo si needs_clarification=true, pregunta corta al usuario.

IMPORTANTE:
- Si es un saludo ("hola", "buenos días") → tool="reply", params={"response_type":"greeting"}.
- Si es "gracias" o despedida → tool="reply", params={"response_type":"farewell"}.
- Si pregunta "qué puedes hacer" o "ayuda" → tool="reply", params={"response_type":"help"}.
- Preguntas de conteo ("cuántos", "cuántas") → usa count_doctors o doctors_by_sex/rank/department.
- Preguntas de listado ("muéstrame", "dame lista", "quiénes") → usa list_doctors.
- Preguntas sobre guardias/asignaciones → usa calendar_assignments o calendar_assigned_count.
- Si ninguna herramienta específica sirve y es una pregunta de datos → usa sql_query.
- NUNCA inventes datos. Solo extraes parámetros del mensaje del usuario.
- Si el usuario hace follow-up ("y de ellos", "cuáles son mujeres") usa el contexto de la conversación.
```

### Tools Section (generada dinámicamente por `build_tools_prompt()`)

**Archivo:** `backend/app/application/telegram/tool_registry.py:239-254`

Se genera a partir de `ALL_TOOLS` (14 herramientas: 8 de doctores, 3 de calendario, 2 de misiones, 1 sql_query, 1 reply). El texto inyectado en `{tools_section}` se ve así:

```
## Herramientas Disponibles

### list_doctors
Descripción: Lista doctores activos con filtros opcionales. Usar para preguntas como 'qué doctores hay en cirugía', 'muéstrame las doctoras', 'doctores con rango capitán'.
Parámetros:
  - sex: F para femenino, M para masculino
  - rank: Nombre del rango militar (ej: capitán, mayor, teniente coronel)
  - department: Nombre del departamento (ej: cirugía, pediatría, medicina general)
  - service_active: Filtrar solo activos para servicio (default true)

### count_doctors
Descripción: Cuenta doctores con filtros opcionales. Usar para 'cuántos médicos hay', 'cuántas doctoras en cardiología', 'cantidad de capitanes disponibles'.
Parámetros:
  - sex: F para femenino, M para masculino
  - rank: Nombre del rango militar
  - department: Nombre del departamento
  - service_active: Filtrar solo activos para servicio

... (12 herramientas más)
```

### Formato del Contexto de Conversación

**Archivo:** `backend/app/application/telegram/intent_classifier.py:109-117`

```python
def _format_history(self, history: list[dict[str, str]] | None) -> str:
    if not history:
        return "(primera interacción)"
    lines = []
    for msg in history[-6:]:  # Solo últimos 6 mensajes
        role = "Usuario" if msg.get("role") == "user" else "Bot"
        content = msg.get("content", "")[:200]  # Truncado a 200 chars
        lines.append(f"{role}: {content}")
    return "\n".join(lines)
```

---

## 2. Parseo de la Respuesta del LLM

**Archivo:** `backend/app/application/telegram/intent_classifier.py:131-169`

```python
def _parse(self, response: str) -> NLUResult:
    if not response:
        return self._fallback()
    
    parsed = self._extract_json(response)
    if parsed is None:
        return self._fallback()
    
    return NLUResult(
        tool=parsed.get("tool", "reply"),
        params=parsed.get("params", {}),
        confidence=float(parsed.get("confidence", 0.5)),
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        clarification_question=str(parsed.get("clarification_question", "")),
    )

def _extract_json(self, text: str) -> dict | None:
    """Extrae JSON del texto, manejando bloques de código markdown."""
    try:
        return json.loads(text)  # Intenta parseo directo
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)  # Busca primer { ... }
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None

def _fallback(self) -> NLUResult:
    """Fallback conservador — pide clarificación."""
    return NLUResult(
        tool="reply",
        params={"response_type": "unknown"},
        confidence=0.0,
        needs_clarification=True,
        clarification_question="No entendí bien tu consulta. ¿Podrías explicarlo de otra forma?",
    )
```

### Estructura del NLUResult (dataclass de salida)

```python
@dataclass
class NLUResult:
    tool: str                              # Nombre exacto de la herramienta
    params: dict[str, Any] = {}            # Parámetros extraídos
    confidence: float = 1.0                # 0.0 - 1.0
    needs_clarification: bool = False      # ¿Requiere preguntar al usuario?
    clarification_question: str = ""       # Pregunta de clarificación
```

### Llamada al LLM (con retry)

```python
def _call_llm(self, messages: list[dict]) -> str:
    try:
        # Primer intento: json_mode=True
        response = self._llm.chat_complete(messages, temperature=0.0, json_mode=True)
        return response.strip()
    except Exception:
        try:
            # Segundo intento: sin json_mode (fallback)
            response = self._llm.chat_complete(messages, temperature=0.0, json_mode=False)
            return response.strip()
        except Exception:
            return ""
```

---

## 3. Pipeline Dual del Agent — Cómo Decide Qué Path Tomar

**Archivo:** `backend/app/application/telegram/agent.py:645-673`

```python
def process(self, text, telegram_user_id=None, user_info=None, actor_id=None) -> AgentResult:
    # Phase 1: Cargar historial de conversación
    history = []
    if self._memory and telegram_user_id:
        history = self._memory.load_history(telegram_user_id)
    
    # Phase 2: Decisión de pipeline
    if self._nlu_engine is not None:
        return self._process_llm_first(text, telegram_user_id, history, start)  # ← PATH PRIMARIO
    
    return self._process_legacy(text, telegram_user_id, history, start)  # ← PATH LEGACY
```

**La decisión es simple:** si `NLUEngine` está configurado (siempre lo está en producción porque DeepSeek está disponible), se usa el pipeline LLM-First. Si no (tests sin LLM), se usa el legacy con keyword matching.

### PATH 1: LLM-First (`_process_llm_first`)

**Archivo:** `agent.py:679-744`

```
1. NLUEngine.classify(text, conversation_history=history)
   → 1 llamada LLM que produce NLUResult(tool, params, confidence)

2. Si needs_clarification → respuesta de clarificación

3. Si tool == "reply" → _handle_reply() (saludos, ayuda, despedidas)

4. _dispatch_tool(tool, params, text) → ejecución determinística

5. _generate_nl_response(text, nlu_result, tool_result, history)
   → LLM convierte resultado estructurado en español conversacional

6. _remember_result() → guarda contexto para follow-ups
```

### PATH 2: Legacy (`_process_legacy`)

**Archivo:** `agent.py:878-1002`

```
1. EntityResolver.pre_process(text) → extrae entidades (fechas, nombres, áreas)

2. _merge_followup_context() → añade filtros de la consulta anterior si es follow-up

3. _mission_contextual_followup_result() → follow-ups sobre listado de misiones

4. _classify_intent() → keyword matching (fallback sin LLM)

5. if-elif chain de enrutamiento:
   → SemanticLayerResolver (15 métricas SQL predefinidas)
   → DoctorQueryService (consultas determinísticas)
   → CalendarQueryService (consultas de calendario)
   → IntentRouter (30+ SQL templates)
   → QueryExecutor (NL→SQL como último recurso)
```

### Despacho de Herramientas (`_dispatch_tool`)

**Archivo:** `agent.py:746-814`

```python
def _dispatch_tool(self, tool_name, params, user_text):
    # 1. ToolRegistry (nuevo) — handlers registrados
    if self._tool_registry is not None:
        handler = self._tool_registry.get(tool_name)
        if handler is not None:
            return handler(**params)
    
    # 2. Doctor tools → DoctorQueryService
    if tool_name in ("list_doctors", "count_doctors", "doctors_by_sex",
                     "doctors_by_rank", "doctors_by_department"):
        return self._doctor_query_service.execute(user_text, params)
    
    # 3. Doctor métricas → SemanticLayerResolver
    if tool_name in ("doctor_last_service", "doctor_service_load", "unassigned_doctors"):
        return self._semantic_layer_resolver.resolve(...)
    
    # 4. Calendar tools → CalendarQueryService
    if tool_name in ("calendar_assignments", "calendar_assigned_count", "calendar_status"):
        return self._calendar_query_service.execute(tool_name, params)
    
    # 5. IntentRouter (SQL templates registradas)
    entry = self._router.registry.get(tool_name)
    if entry is not None:
        return self._router.handle(action="query", query_type=tool_name, ...)
    
    # 6. SQL Agent (nl→sql como fallback)
    if tool_name == "sql_query":
        return self._fallback_to_query_db(params.get("question", user_text))
    
    # 7. Último recurso: SQL Agent con texto original
    return self._fallback_to_query_db(user_text)
```

---

## 4. EntityResolver — Cómo Resuelve Entidades

**Archivo:** `backend/app/application/telegram/entity_resolver.py`

### 4.1 Fechas (`resolve_date_expression`)

Resuelve expresiones en español a fechas concretas mediante un diccionario de keywords:

| Expresión | Resultado |
|-----------|-----------|
| `hoy` | `{"type": "single_date", "value": "2026-05-29"}` |
| `ayer` | `{"type": "single_date", "value": "2026-05-28"}` |
| `mañana` / `manana` | `{"type": "single_date", "value": "2026-05-30"}` |
| `pasado mañana` | `{"type": "single_date", "value": "2026-05-31"}` |
| `esta semana` | `{"type": "date_range", "start": "2026-05-25", "end": "2026-05-31"}` |
| `la próxima semana` | `{"type": "date_range", "start": "2026-06-01", "end": "2026-06-07"}` |
| `este mes` | `{"type": "date_range", "start": "2026-05-01", "end": "2026-05-31"}` |
| `el mes pasado` | `{"type": "date_range", "start": "2026-04-01", "end": "2026-04-30"}` |
| `enero`, `febrero`, ... | `{"type": "month", "month": 1}` |
| `abril 2026` | `{"type": "month_year", "month": 4, "year": 2026}` |

### 4.2 Médicos (`resolve_doctor`)

- Busca por apellido vía `ILIKE` contra `DoctorRepository.list_service_active()`
- Si 0 matches → `status="not_found"`
- Si 1 match → `status="resolved"`
- Si >1 match → `status="ambiguous"` con lista de candidatos

### 4.3 Áreas de Servicio (`resolve_area`)

- Busca por `display_name` vía `ILIKE` contra `CatalogRepository.list_service_areas()`
- Misma lógica: 0 → not_found, 1 → resolved, >1 → ambiguous

### 4.4 Rangos Militares (`resolve_rank`)

- Busca por `normalized_name` vía `ILIKE` contra `CatalogRepository.list_ranks()`
- Detecta palabras clave como "capitán", "mayor", "teniente coronel"

### 4.5 Sexo/Género

- Match por palabras clave normalizadas (sin acentos):
  - Femenino: `femenino`, `femenina`, `mujer`, `mujeres`, `doctora`
  - Masculino: `masculino`, `hombre`, `hombres`, `varon`, `varones` (+ variantes con errores de tipeo)

### 4.6 Pre-procesamiento (`pre_process`)

Método principal que escanea el mensaje completo y extrae TODAS las entidades detectables:

```python
def pre_process(self, user_message: str) -> dict:
    """
    Returns:
        resolved: dict  → {"date": {...}, "doctor": {...}, "area": {...}, "rank": {...}, "sex": "F"}
        ambiguous: list → [{"field": "doctor", "candidates": [...], "question": "..."}]
        hints: str      → "date=2026-05-29, sex='F', area_id=uuid"
    """
```

El campo `hints` se inyecta en el prompt del LLM para el pipeline legacy.

---

## 5. Memory — Cómo Construye el Historial para el LLM

**Archivo:** `backend/app/application/telegram/memory.py`

### 5.1 MemoryManager.load_history()

```python
def load_history(self, telegram_user_id: str, limit: int = 10) -> list[dict]:
    """
    Carga últimas N interacciones como lista de mensajes para LLM.
    
    Returns:
        [{"role": "user", "content": "..."},
         {"role": "assistant", "content": "..."}, ...]
    """
    interactions = self._telegram_repo.list_interactions(telegram_user_id, limit=limit)
    interactions.reverse()  # Desc → cronológico
    
    history = []
    for interaction in interactions:
        # Omite interacciones que son tool outputs (no texto conversacional)
        if interaction.tool_name:
            continue
        # Omite respuestas de error genéricas
        if interaction.response_text.startswith(("Lo siento, no pude", "Error de", ...)):
            continue
        
        history.append({"role": "user", "content": interaction.input_text})
        history.append({"role": "assistant", "content": interaction.response_text})
    
    return history
```

### 5.2 SessionStore — Contexto de Follow-up

**TTL:** 30 minutos (1800 segundos). **Persistencia:** Opcional en tabla `telegram_sessions`.

```python
@dataclass
class SessionState:
    last_query_type: str | None = None       # Tipo de query anterior
    last_params: dict | None = None          # Parámetros usados
    last_results: list[dict] | None = None   # Últimos resultados (máx 50 filas)
    last_filters: dict | None = None         # Filtros aplicados
    last_tool_name: str | None = None        # Herramienta usada
    last_agent_action: str | None = None     # Acción: query, export, query_db
    last_operation: str | None = None        # Operación: count, list
    last_domain: str | None = None           # Dominio: medicos, calendario, missions
    last_period: dict | None = None          # Período: {month, year}
    last_subject: str | None = None          # Sujeto: assigned_doctors, unassigned_doctors
    last_total: int | None = None            # Total de resultados
    last_document_format: str | None = None  # Formato: pdf, xlsx
    pending_selection: dict | None = None    # Selección pendiente
    pending_clarification: str | None = None # Pregunta de clarificación pendiente
    collected_slots: dict = {}               # Slots recolectados multi-turno
    turn_count: int = 0                      # Contador de turnos
    created_at: float                        # Timestamp de creación
```

### 5.3 Detección de Follow-ups

**Archivo:** `agent.py:34-45`

```python
_FOLLOWUP_PATTERNS = [
    re.compile(r"\b(y|son|ellos|ellas|eso|esa|esos|esas|mismo|misma|"
               r"exp[oó]rtalo|exportalo|esportalo)\b", re.IGNORECASE),
    re.compile(r"\b(femenin[oa]s?|feminios?|femenios?|masculin[oa]s?|pdf|excel|listado|lista)\b",
               re.IGNORECASE),
    re.compile(r"\b\d+\s+o\s+\d+\b", re.IGNORECASE),  # "1 o 2"
]

def _looks_like_followup(text: str) -> bool:
    return any(pattern.search(text) for pattern in _FOLLOWUP_PATTERNS)
```

### 5.4 Merge de Contexto en Follow-ups

**Archivo:** `agent.py:596-634`

```python
def _merge_followup_context(self, telegram_user_id, resolved_entities, entity_hints, user_text):
    """
    Si el mensaje parece follow-up Y no tiene ≥2 dimensiones de filtro explícitas:
    → Recupera los filtros de la consulta anterior (SessionStore)
    → Los mergea con las entidades resueltas del mensaje actual
    → Retorna entidades mergeadas + hints actualizados
    
    Ejemplo:
      Usuario: "cuántos doctores hay en cirugía"
      → last_filters = {"department": "cirugía"}
      Usuario: "y de ellos, cuáles son mujeres"
      → _looks_like_followup("y de ellos...") = True
      → mergea department="cirugía" + sex="F" del mensaje actual
    """
```

---

## 6. Generación de Respuesta en Lenguaje Natural

**Archivo:** `backend/app/application/telegram/nl_response.py`

### System Prompt para Formateo de Respuestas

```
Eres un asistente médico-militar conciso que responde consultas sobre turnos y guardias.

Reglas:
- Usa SOLO los datos proporcionados abajo. NO inventes información.
- Si los datos están vacíos o no existen, explica la causa probable:
  * Sin doctores que coincidan → "No encontré doctores con ese criterio."
  * Sin calendario → "No hay un calendario creado para ese mes. ¿Quieres crear uno?"
  * Sin asignaciones → "Ese calendario existe pero no tiene guardias asignadas todavía."
- Para conteos: responde en una frase. Ej: "Hay 22 doctoras activas en el servicio."
- Para listas (≤10 items): usa viñetas con nombre, rango y departamento.
- Para listas (>10 items): da un resumen numérico y ofrece detallar si el usuario quiere.
- Sé conversacional pero profesional. Si algo es ambiguo, pide clarificación.
- Si el usuario pregunta algo que el sistema no puede responder, sé honesto y sugiere alternativas.
```

### Flujo de `generate_response()`

```
1. Extrae datos significativos del tool_result (_extract_data)
2. Si datos vacíos → _generate_empty_response() con prompt contextual
3. Si hay datos → construye contexto JSON (_build_data_context)
4. Arma mensajes: [system_prompt] + [historial últimos 6] + [datos + pregunta]
5. Llama al LLM con temperature=0.3
6. Si falla → _format_fallback() simple
```

### Construcción del Contexto de Datos

```python
def _build_data_context(tool_name, data):
    if isinstance(data, list):
        if len(data) <= 30:
            return f"Herramienta: {tool_name}\nResultados ({len(data)}):\n" + json.dumps(data, ...)
        else:
            # Trunca a 30 items, indica cuántos más hay
            return f"Herramienta: {tool_name}\nResultados ({len(data)}):\n" + \
                   json.dumps(data[:30], ...) + f"\n... y {len(data) - 30} resultados más."
    return f"Herramienta: {tool_name}\nResultado:\n" + json.dumps(data, ...)
```

---

## 7. Flujo Completo de una Consulta (Ejemplo)

### Usuario escribe: "¿cuántas doctoras hay en cirugía?"

```
1. Telegram → POST /api/telegram/webhook
2. Orchestrator → Agent.process("¿cuántas doctoras hay en cirugía?")
3. MemoryManager.load_history() → [] (primera interacción)
4. NLUEngine.classify():
   
   SYSTEM PROMPT:
   "Eres el motor NLU de un sistema de turnos médicos militares...
   ## Herramientas Disponibles
   ### count_doctors
   Descripción: Cuenta doctores con filtros opcionales...
   Parámetros:
     - sex: F para femenino, M para masculino
     - department: Nombre del departamento
   ...
   CONTEXTO DE CONVERSACIÓN:
   (primera interacción)"
   
   USER: "¿cuántas doctoras hay en cirugía?"
   
   LLM RESPONSE:
   {"tool": "count_doctors", "params": {"sex": "F", "department": "cirugía"}, 
    "confidence": 0.95, "needs_clarification": false, "clarification_question": ""}

5. _dispatch_tool("count_doctors", {"sex": "F", "department": "cirugía"})
   → DoctorQueryService.execute() → {"total": 5, "rows": [...], "columns": [...]}

6. _generate_nl_response():
   SYSTEM: "Eres un asistente médico-militar conciso..."
   USER: "Usuario preguntó: ¿cuántas doctoras hay en cirugía?
          Datos del sistema:
          Herramienta: count_doctors
          Resultados (5): [{...}, {...}, ...]
          Genera una respuesta natural y útil."
   
   LLM RESPONSE: "Hay 5 doctoras activas en el departamento de cirugía."

7. Bot responde en Telegram: "Hay 5 doctoras activas en el departamento de cirugía."

8. _remember_result() guarda:
   last_query_type = "count_doctors"
   last_filters = {"sex": ["F"], "department": "cirugía"}
   last_total = 5
```

### Follow-up: "y de ellas, cuáles son capitanas?"

```
1. _looks_like_followup("y de ellas, cuáles son capitanas?") → True (patrón "y")
2. _merge_followup_context():
   - Recupera last_filters = {"sex": ["F"], "department": "cirugía"}
   - Mensaje actual solo tiene rank="capitán" (1 filtro)
   - Como tiene <2 dimensiones → mergea: sex="F" + department="cirugía" + rank="capitán"
3. NLUEngine.classify() con contexto mergeado:
   → tool="list_doctors", params={"sex": "F", "department": "cirugía", "rank": "capitán"}
4. Respuesta: lista de doctoras capitanas en cirugía
```

---

## 8. Seguridad y Guardrails

### 8.1 SQL Injection Prevention

**Archivo:** `backend/app/application/telegram/sql_agent/validator.py`

- Solo permite `SELECT` statements
- Bloquea: DML (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE)
- Bloquea funciones peligrosas: `pg_read_file()`, `pg_sleep()`, etc.
- Tablas excluidas (`_EXCLUDE_TABLES`): nunca accesibles vía SQL agent
- Validación de longitud máxima de SQL
- Verificación de que todas las tablas referenciadas existen en el schema
- Si no hay LIMIT y la query no tiene agregación → se agrega LIMIT automáticamente

### 8.2 Rate Limiting

**Archivo:** `backend/app/infrastructure/rate_limiter.py`

- 20 requests por minuto por `telegram_user_id`
- Aplicado en el webhook antes de cualquier procesamiento

### 8.3 Webhook Security

- Validación del header `X-Telegram-Bot-Api-Secret-Token` con `secrets.compare_digest()`
- Si no está configurado, se loggea un warning pero se permite (modo desarrollo)

### 8.4 Feature Flag

```python
# Solo se carga el router si FEATURE_TELEGRAM=true
if settings.feature_telegram:
    api_router.include_router(telegram_router)
```

---

## 9. Estructura de Llamadas al LLM (Resumen)

| Propósito | System Prompt | Temperature | JSON Mode | Archivo |
|-----------|--------------|-------------|-----------|---------|
| **NLU (intent + tool)** | NLU_SYSTEM_PROMPT | 0.0 | Sí (1º intento) | `intent_classifier.py` |
| **Formateo NL respuesta** | _NL_SYSTEM_PROMPT | 0.3 | No | `nl_response.py` |
| **Formateo NL (fallback)** | Prompt inline | 0.3 | No | `agent.py:_format_nl_response` |
| **Empty response** | _NL_EMPTY_PROMPT | 0.3 | No | `nl_response.py` |
| **SQL Generation** | Prompt inline CoT | 0.1 | No | `sql_agent/generator.py` |
| **SQL Verification** | Prompt inline | 0.1 | No | `sql_agent/verifier.py` |
| **SQL Refinement** | Prompt inline | 0.1 | No | `sql_agent/refiner.py` |

---

## 10. Comunicación con Telegram Bot API

**Archivo:** `backend/app/application/telegram/bot_client.py`

No se usa `python-telegram-bot`. Toda la comunicación es HTTP directa:

```python
class TelegramBotClient:
    def send_message(self, chat_id: str, text: str) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        response = httpx.post(url, json=payload, timeout=30)
        return response.json()
    
    def send_document(self, chat_id: str, document_bytes: bytes, filename: str) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/sendDocument"
        files = {"document": (filename, document_bytes)}
        data = {"chat_id": chat_id}
        response = httpx.post(url, files=files, data=data, timeout=60)
        return response.json()
```

### FakeBotClient (para desarrollo/tests)

```python
class FakeBotClient:
    def send_message(self, chat_id, text) -> dict:
        return {"ok": True, "result": {"message_id": 1}}
    
    def send_document(self, chat_id, document_bytes, filename) -> dict:
        return {"ok": True, "result": {"message_id": 2}}
```
