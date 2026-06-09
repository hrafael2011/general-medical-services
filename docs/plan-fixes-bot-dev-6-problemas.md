# Propuesta de Implementación — Fix de 6 Problemas Críticos
## Módulo Telegram Bot | Rama `bot-dev`

**Autor:** Kimi Code CLI (IA generativa senior)  
**Fecha:** 2026-05-29  
**Estado:** Pendiente de aprobación  
**Rama objetivo:** `bot-dev`  

---

## 1. Resumen Ejecutivo

El pipeline LLM-First del bot conversacional de Telegram tiene 6 fallas estructurales que degradan la calidad de las respuestas, causan follow-ups incorrectos y desperdician tokens de LLM. Este documento detalla el diagnóstico, la propuesta técnica, el plan de pruebas y el orden de ejecución para resolverlos sin romper las interfaces públicas del sistema ni los tests existentes.

**Restricciones globales aplicables:**
- No modificar interfaces públicas de `TelegramOrchestrator` ni `ConversationalAgent.process()`.
- No eliminar el Path Legacy.
- Cada fix debe tener test unitario correspondiente.
- Usar repositorios y servicios existentes.
- Queries adicionales a DB deben ser async y reutilizar la sesión SQLAlchemy del request.
- Validar con `pytest backend/tests/telegram/ -x -q` entre cada problema.

---

## 2. Diagnóstico del Estado Actual

### 2.1 Arquitectura del Pipeline LLM-First

```
Usuario → process(text, telegram_user_id)
    ├─→ MemoryManager.load_history() ──→ historial conversacional
    ├─→ NLUEngine.classify() ──→ NLUResult(tool, params)
    ├─→ _dispatch_tool() ──→ resultado estructurado
    ├─→ _generate_nl_response() ──→ texto natural
    └─→ _remember_result() ──→ SessionStore
```

### 2.2 Componentes Involucrados

| Archivo | Rol | Problemas vinculados |
|---|---|---|
| `memory.py` | Persistencia de historial conversacional | 1 |
| `agent.py` | Orquestación del pipeline | 2, 4, 5, 6 |
| `intent_classifier.py` | Clasificación NLU | 3 |
| `entity_resolver.py` | Normalización de entidades | 2 (referencia) |
| `nl_response.py` | Generación de respuestas en lenguaje natural | 4 |
| `catalogs.py` | Repositorio de catálogos DB | 2, 3 |

---

## 3. Propuesta Detallada por Problema

---

### PROBLEMA 1 — Historial roto en MemoryManager

#### 3.1.1 Síntoma

El método `MemoryManager.load_history()` (línea 167 de `memory.py`) ejecuta:

```python
if tool_name:
    continue
```

Esto descarta **todas** las interacciones donde se invocó una herramienta, eliminando ~90 % del contexto conversacional real que debería ver el LLM. El test existente `test_memory_load_history_filters_formatted_responses` justifica este comportamiento como protección contra "filtrado de summaries internos", pero el efecto es que el LLM opera con amnesia severa.

#### 3.1.2 Propuesta de Fix

**Cambio en `memory.py` — `load_history()`:**

Reemplazar el `continue` agresivo por lógica condicional que genere un resumen conversacional para interacciones con herramienta:

```python
if tool_name:
    # Incluir el turno del usuario original
    history.append({"role": "user", "content": interaction.input_text})
    
    # Generar resumen compacto para el assistant en vez del JSON crudo
    tool_response = interaction.tool_response or {}
    data = tool_response.get("data", {}) if isinstance(tool_response, dict) else {}
    rows = data.get("rows", []) if isinstance(data, dict) else []
    result_count = len(rows)
    
    summary = f"Consulté {tool_name} y encontré {result_count} resultados."
    history.append({"role": "assistant", "content": summary})
    continue
```

**Mantenimiento del límite:** El parámetro `limit=10` sigue aplicándose sobre el número de interacciones (no de mensajes), por lo que el historial resultante tendrá como máximo 20 mensajes (10 pares).

**Manejo de errores:** Si `tool_response` no tiene estructura esperada, fallback a `"Consulté {tool_name}."`.

#### 3.1.3 Tests Nuevos / Actualizados

- **Actualizar:** `test_memory_load_history_filters_formatted_responses`
  - Antes: `assert history == []`
  - Después: verificar que devuelve 2 mensajes con el resumen compacto
  
- **Nuevo:** `test_load_history_includes_tool_interactions_as_summaries`
  - Crear interacción con `tool_name="count_doctors"` y `tool_response={"data": {"rows": [...5...]}}`
  - Verificar que history contiene user + assistant con "encontré 5 resultados"

- **Nuevo:** `test_load_history_skips_error_responses`
  - Mantener el `_skip_prefixes` existente para mensajes de error

#### 3.1.4 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| El resumen genérico no aporta contexto semántico | Es intencional — evita JSON crudo, mantiene la conversación viva |
| Tests existentes fallan por cambio de comportamiento | Se actualiza el test que validaba el skip agresivo |
| Doble conteo de mensajes (user+assistant por tool) | `limit` sigue aplicado a interacciones, no a mensajes; está documentado |

---

### PROBLEMA 2 — EntityResolver bypaseado en Path LLM-First

#### 3.2.1 Síntoma

En `_process_llm_first()` (líneas 688-716 de `agent.py`):

```python
nlu_result = self._nlu_engine.classify(text, conversation_history=history)
# ...sin normalización de params...
tool_result = self._dispatch_tool(nlu_result.tool, nlu_result.params, text)
```

Los parámetros extraídos por el LLM en lenguaje natural (ej: `{"department": "cirugía"}`) se pasan directo al servicio sin validar contra la base de datos. El `EntityResolver` solo se usa en `_process_legacy()` (línea 890).

#### 3.2.2 Propuesta de Fix

**Nuevo método en `ConversationalAgent`:**

```python
def _normalize_params(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normaliza parámetros extraídos por NLU contra catálogos reales de DB."""
    if not self._session:
        return params
    
    normalized = dict(params)
    repo = self._catalog_repo or CatalogRepository(self._session)
    
    # 1. department → ILIKE contra CatalogRepository.list_departments()
    if "department" in normalized:
        dept_input = str(normalized["department"]).strip()
        departments = repo.list_departments()
        match = next(
            (d for d in departments if dept_input.lower() in d.normalized_name.lower()),
            None
        )
        if match:
            normalized["department"] = match.normalized_name
        else:
            logger.warning("Department not found in catalog: %s", dept_input)
    
    # 2. rank → ILIKE contra CatalogRepository.list_ranks()
    if "rank" in normalized:
        rank_input = str(normalized["rank"]).strip()
        ranks = repo.list_ranks()
        match = next(
            (r for r in ranks if rank_input.lower() in r.normalized_name.lower()),
            None
        )
        if match:
            normalized["rank"] = match.normalized_name
        else:
            logger.warning("Rank not found in catalog: %s", rank_input)
    
    # 3. area → ILIKE contra CatalogRepository.list_service_areas()
    if "area" in normalized:
        area_input = str(normalized["area"]).strip()
        areas = repo.list_service_areas()
        match = next(
            (a for a in areas if area_input.lower() in a.display_name.lower()),
            None
        )
        if match:
            normalized["area"] = match.display_name
        else:
            logger.warning("Area not found in catalog: %s", area_input)
    
    # 4. sex → normalización semántica
    if "sex" in normalized:
        sex_val = str(normalized["sex"]).lower().strip()
        female_variants = {"femenino", "femenina", "mujer", "doctora", "f"}
        male_variants = {"masculino", "masculina", "hombre", "doctor", "m"}
        if sex_val in female_variants:
            normalized["sex"] = "F"
        elif sex_val in male_variants:
            normalized["sex"] = "M"
        # Si no coincide, dejar original (el servicio fallará con error claro)
    
    return normalized
```

**Integración en `_process_llm_first()`:**

```python
nlu_result = self._nlu_engine.classify(text, conversation_history=history)
# ...clarification/reply handling...
normalized_params = self._normalize_params(nlu_result.tool, nlu_result.params)
tool_result = self._dispatch_tool(nlu_result.tool, normalized_params, text)
```

**Inyección de dependencia:**

Agregar `catalog_repo=None` en `ConversationalAgent.__init__()` para permitir inyección en producción y facilitar mocking en tests.

#### 3.2.3 Reutilización de EntityResolver

En vez de duplicar la lógica de matching, extraer métodos estáticos de `EntityResolver`:

```python
# En entity_resolver.py
@staticmethod
def _match_department(text: str, departments: list[DepartmentModel]) -> DepartmentModel | None:
    ...

@staticmethod
def _match_rank(text: str, ranks: list[RankModel]) -> RankModel | None:
    ...

@staticmethod
def _match_area(text: str, areas: list[ServiceAreaModel]) -> ServiceAreaModel | None:
    ...

@staticmethod
def normalize_sex(text: str) -> str | None:
    ...
```

Luego `_normalize_params()` llama a estos métodos estáticos. Esto:
- Elimina duplicación
- Mantiene la lógica de matching en un solo lugar
- Facilita testing unitario de la lógica de matching

#### 3.2.4 Tests Nuevos

- `test_normalize_params_department_exact_match`
- `test_normalize_params_rank_partial_match`
- `test_normalize_params_area_by_display_name`
- `test_normalize_params_sex_female_variants` → verifica "doctora" → "F"
- `test_normalize_params_sex_male_variants` → verifica "hombre" → "M"
- `test_normalize_params_unknown_department_logs_warning` → deja original, loggea warning
- `test_normalize_params_no_session_returns_unchanged`

#### 3.2.5 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Queries sincrónicas bloquean el event loop | `CatalogRepository` ya opera sincrónicamente (como `EntityResolver`). Mantener consistencia temporal. Si el proyecto migra a async en el futuro, el cambio es local a `_normalize_params` |
| Falso positivo en substring matching | Usar `in` (substring) en vez de `==` para tolerar "cirugía general" vs "cirugía". Loggear cuando hay ambigüedad |
| Cambio de comportamiento en servicios | Los servicios reciben ahora nombres exactos de DB (mejor) en vez de texto libre |

---

### PROBLEMA 3 — Schema injection faltante en prompt NLU

#### 3.3.1 Síntoma

El `NLU_SYSTEM_PROMPT` (líneas 38-70 de `intent_classifier.py`) solo tiene placeholders para `{tools_section}` y `{conversation_context}`. El LLM no conoce los valores reales de la base de datos, por lo que inventa o malforma nombres de departamentos, rangos y áreas.

#### 3.3.2 Propuesta de Fix

**Extensión del system prompt:**

```python
NLU_SYSTEM_PROMPT = """Eres el motor NLU de un sistema de turnos médicos militares...

{tools_section}

{db_catalog}

CONTEXTO DE CONVERSACIÓN:
{conversation_context}

...resto del prompt..."""
```

**Nueva sección de catálogo:**

```python
_CATALOG_PROMPT_TEMPLATE = """CATÁLOGO DE VALORES VÁLIDOS EN LA BASE DE DATOS:
Departamentos: {departments}
Rangos militares: {ranks}
Áreas de servicio: {areas}

Usa EXACTAMENTE estos nombres cuando extraigas parámetros. Si el usuario dice algo similar pero no idéntico, elige el valor más cercano de la lista."""
```

**Cache en `NLUEngine`:**

```python
class NLUEngine:
    _CACHE_TTL_SECONDS = 1800  # 30 minutos
    
    def __init__(self, llm: LLMProvider, catalog_repo=None):
        self._llm = llm
        self._tools_prompt = build_tools_prompt()
        self._catalog_repo = catalog_repo
        self._catalog_cache: dict | None = None
        self._catalog_cached_at: float = 0.0
    
    def _get_catalog_prompt(self) -> str:
        if not self._catalog_repo:
            return ""
        now = time.time()
        if self._catalog_cache and (now - self._catalog_cached_at) < self._CACHE_TTL_SECONDS:
            return self._build_catalog_prompt(self._catalog_cache)
        
        # Cargar de DB
        departments = [d.normalized_name for d in self._catalog_repo.list_departments()]
        ranks = [r.normalized_name for r in self._catalog_repo.list_ranks()]
        areas = [a.display_name for a in self._catalog_repo.list_service_areas()]
        
        self._catalog_cache = {"departments": departments, "ranks": ranks, "areas": areas}
        self._catalog_cached_at = now
        return self._build_catalog_prompt(self._catalog_cache)
    
    def _build_catalog_prompt(self, cache: dict) -> str:
        return _CATALOG_PROMPT_TEMPLATE.format(
            departments=", ".join(cache["departments"]),
            ranks=", ".join(cache["ranks"]),
            areas=", ".join(cache["areas"]),
        )
```

**Integración en `classify()`:**

```python
system_prompt = NLU_SYSTEM_PROMPT.format(
    tools_section=self._tools_prompt,
    db_catalog=self._get_catalog_prompt(),
    conversation_context=context,
)
```

#### 3.3.3 Tests Nuevos

- `test_nlu_engine_catalog_prompt_included_when_repo_provided`
- `test_nlu_engine_catalog_prompt_empty_when_no_repo`
- `test_nlu_engine_catalog_cache_respects_ttl`
- `test_nlu_engine_catalog_cache_invalidation_after_30_minutes`

#### 3.3.4 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Prompt se vuelve muy largo con muchos catálogos | Limitar a top 50 por categoría o usar los más frecuentes. Documentar en código |
| Cache desactualizada tras cambios en DB | TTL de 30 min es balance entre frescura y performance. Aceptable para catálogos estables |
| NLUEngine.__init__ cambia de firma | Param `catalog_repo` es opcional (`None` por defecto). Tests existentes no se ven afectados |

---

### PROBLEMA 4 — SessionStore y MemoryManager desconectados

#### 3.4.1 Síntoma

El LLM que genera la respuesta natural (`_generate_nl_response()` → `generate_response()` en `nl_response.py`) solo recibe:
1. El system prompt genérico
2. El historial de texto (que puede estar incompleto por Problema 1)
3. La pregunta actual y el resultado de la herramienta

No recibe el estado estructurado de la sesión (`SessionState`), por lo que si el historial tiene gaps, el LLM pierde contexto de filtros, dominio y totales previos.

#### 3.4.2 Propuesta de Fix

**Cambio en `nl_response.py`:**

```python
def generate_response(
    llm: LLMProvider,
    user_message: str,
    tool_name: str,
    tool_result: dict[str, Any] | None,
    conversation_history: list[dict[str, str]] | None = None,
    session_context: dict[str, Any] | None = None,  # ← NUEVO
) -> str:
```

**Inyección del mensaje de sistema de sesión:**

```python
messages: list[dict[str, str]] = [{"role": "system", "content": _NL_SYSTEM_PROMPT}]

if session_context:
    session_msg = (
        f"CONTEXTO DE SESIÓN ACTIVA:\n"
        f"Última consulta: {session_context.get('last_query_type', 'N/A')}\n"
        f"Filtros aplicados: {session_context.get('last_filters', 'Ninguno')}\n"
        f"Total encontrado: {session_context.get('last_total', 'N/A')}\n"
        f"Dominio: {session_context.get('last_domain', 'N/A')}"
    )
    messages.append({"role": "system", "content": session_msg})

if conversation_history:
    messages.extend(conversation_history[-6:])

messages.append({
    "role": "user",
    "content": f"Usuario preguntó: \"{user_message}\"\n\nDatos del sistema:\n{data_context}\n\nGenera una respuesta natural y útil.",
})
```

**Cambio en `_generate_nl_response()` de `agent.py`:**

```python
def _generate_nl_response(self, user_text, nlu_result, tool_result, history):
    session_context = None
    if self._session_store and hasattr(self, '_last_telegram_user_id'):
        state = self._session_store.get(self._last_telegram_user_id)
        if state:
            session_context = {
                "last_query_type": state.last_query_type,
                "last_filters": state.last_filters,
                "last_total": state.last_total,
                "last_domain": state.last_domain,
            }
    
    try:
        return generate_response(
            self._llm, user_text, nlu_result.tool, tool_result,
            history, session_context,
        )
    except TypeError:
        # Fallback si generate_response no acepta session_context (backward compat)
        return generate_response(
            self._llm, user_text, nlu_result.tool, tool_result, history,
        )
```

**Alternativa más limpia (preferida):** En vez de guardar `_last_telegram_user_id`, modificar `_generate_nl_response` para recibir `telegram_user_id` como parámetro opcional. Los call sites en `_process_llm_first` y `_process_legacy` pasan el ID disponible.

#### 3.4.3 Tests Nuevos

- `test_generate_response_includes_session_context`
- `test_generate_response_without_session_context_still_works`
- `test_generate_response_session_context_omitted_when_no_store`

#### 3.4.4 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| `generate_response` cambia de firma | Param opcional `session_context=None`. Fallback `TypeError` para máxima compatibilidad |
| Prompt se alarga con contexto de sesión | Solo 4 líneas de texto plano. Impacto mínimo en tokens |
| Información de sesión desactualizada | Se lee del `SessionStore` justo antes de generar la respuesta, no de cache |

---

### PROBLEMA 5 — _looks_like_followup demasiado agresivo

#### 3.5.1 Síntoma

Los patrones actuales (`_FOLLOWUP_PATTERNS`, líneas 34-45) clasifican como follow-up mensajes que son intenciones completamente nuevas:

- `"lista de doctores"` → match por `"lista"`
- `"dame un pdf"` → match por `"pdf"`
- `"son 15 médicos"` → match por `"son"`

Esto causa que `_merge_followup_context()` inyecte filtros previos incorrectamente.

#### 3.5.2 Propuesta de Fix

**Reescritura completa de `_looks_like_followup()`:**

```python
# Nuevos patrones ANAFÓRICOS explícitos (conectores de referencia)
_ANAPHORIC_CONNECTORS = [
    r"\by de\b",
    r"\by ellos\b",
    r"\by ellas\b",
    r"\bde esos\b",
    r"\bde esas\b",
    r"\bde ellos\b",
    r"\bde ellas\b",
    r"\bcuáles de\b",
    r"\bqué hay de\b",
]

# Sustantivos de dominio que indican NUEVA consulta
_DOMAIN_NOUNS = {
    "medico", "medicos", "doctor", "doctores", "doctora", "doctoras",
    "guardia", "guardias", "mision", "misiones", "calendario", "calendarios",
    "turno", "turnos", "departamento", "departamentos", "area", "areas",
    "servicio", "servicios", "paciente", "pacientes", "hospital",
}

# Patrones de export explícito
_EXPORT_PATTERNS = [
    r"\bexp[oó]rtalo\b",
    r"\bexportalo\b",
    r"\ben pdf\b",
    r"\ben excel\b",
]


def _looks_like_followup(text: str, session_has_results: bool = False) -> bool:
    """Detecta si un mensaje es un follow-up contextual de la consulta anterior.
    
    Un mensaje ES follow-up SOLO si cumple AL MENOS una condición:
    1. Tiene menos de 8 palabras.
    2. Empieza con conector anafórico explícito.
    3. No contiene ningún sustantivo de dominio nuevo.
    
    Las solicitudes de export (pdf/excel) solo son follow-up si hay resultados
    activos en la sesión.
    """
    words = text.lower().split()
    
    # Criterio 1: mensaje corto
    if len(words) < 8:
        return True
    
    # Criterio 2: conector anafórico explícito al inicio
    text_lower = text.lower()
    for pattern in _ANAPHORIC_CONNECTORS:
        if re.search(pattern, text_lower):
            return True
    
    # Detectar solicitudes de export
    is_export_request = any(re.search(p, text_lower) for p in _EXPORT_PATTERNS)
    if is_export_request:
        return session_has_results
    
    # Criterio 3: ausencia de sustantivos de dominio
    text_words = set(re.findall(r"\b\w+\b", text_lower))
    has_domain_noun = bool(text_words & _DOMAIN_NOUNS)
    if not has_domain_noun:
        return True
    
    return False
```

**Integración con `_merge_followup_context()`:**

```python
state = self._session_store.get(telegram_user_id)
session_has_results = bool(state and state.last_results)

if not _looks_like_followup(user_text, session_has_results=session_has_results):
    return resolved_entities, entity_hints, False, None
```

#### 3.5.3 Tests Nuevos

- `test_looks_like_followup_short_message` → `"y de ellos"` (4 palabras) → True
- `test_looks_like_followup_anaphoric_connector` → `"cuáles de esos"` → True
- `test_looks_like_followup_no_domain_noun` → `"muéstrame los primeros"` → True
- `test_looks_like_followup_new_domain_noun` → `"lista de doctores"` → False
- `test_looks_like_followup_pdf_without_session` → `"en pdf"` sin last_results → False
- `test_looks_like_followup_pdf_with_session` → `"en pdf"` con last_results → True
- `test_looks_like_followup_lista_is_false` → `"lista"` ya NO es follow-up

#### 3.5.4 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| Falsos negativos en follow-ups legítimos | El criterio de <8 palabras captura la mayoría. El criterio de dominio es conservador |
| `_DOMAIN_NOUNS` incompleto | Lista extensible. Se documenta como constante configurable |
| Tests legacy de follow-up fallan | Revisar `test_compound_queries.py` y `test_operational_context.py` para actualizar expectativas |

---

### PROBLEMA 6 — SQL Agent sin contexto conversacional

#### 3.6.1 Síntoma

`_fallback_to_query_db()` (línea 236) recibe solo `user_text` y `entity_hints`. Cuando `_dispatch_tool()` lo invoca para `tool_name == "sql_query"`, no pasa el `telegram_user_id`, por lo que el SQL Agent no puede enriquecer la pregunta con contexto de sesión.

#### 3.6.2 Propuesta de Fix

**Cambio de firma:**

```python
def _fallback_to_query_db(
    self,
    user_text: str,
    entity_hints: str = "",
    telegram_user_id: str | None = None,
) -> AgentResult:
```

**Enriquecimiento de la pregunta:**

```python
def _fallback_to_query_db(self, user_text, entity_hints="", telegram_user_id=None):
    if self._query_executor is None:
        return AgentResult(...)
    
    enriched_question = user_text
    if telegram_user_id and self._session_store:
        state = self._session_store.get(telegram_user_id)
        if state and state.last_domain:
            enriched_question = (
                f"Pregunta: {user_text}\n"
                f"Contexto previo: última consulta fue sobre {state.last_domain}, "
                f"filtros: {state.last_filters}"
            )
    
    result = self._query_executor.execute(enriched_question, enriched_question, entity_hints=entity_hints)
    ...
```

**Actualización de call sites:**

En `_dispatch_tool()`:
```python
# Antes:
result = self._fallback_to_query_db(params.get("question", user_text))

# Después:
result = self._fallback_to_query_db(
    params.get("question", user_text),
    telegram_user_id=telegram_user_id,  # necesita recibirlo
)
```

Esto implica que `_dispatch_tool` debe recibir `telegram_user_id` como parámetro. Actualmente su firma es:
```python
def _dispatch_tool(self, tool_name, params, user_text):
```

Se modificará a:
```python
def _dispatch_tool(self, tool_name, params, user_text, telegram_user_id=None):
```

Y el call site en `_process_llm_first` pasará `telegram_user_id`.

#### 3.6.3 Tests Nuevos

- `test_fallback_to_query_db_enriches_question_with_session`
- `test_fallback_to_query_db_passes_raw_question_when_no_session`
- `test_fallback_to_query_db_passes_telegram_user_id_from_dispatch`

#### 3.6.4 Riesgos y Mitigaciones

| Riesgo | Mitigación |
|---|---|
| `_dispatch_tool` cambia de firma | Param opcional al final. No afecta call sites que no pasan el ID |
| Prompt enriquecido confunde al QueryExecutor | QueryExecutor usa NL-to-SQL; texto adicional con contexto mejora la interpretación, no la empeora |
| Información de sesión privada filtrada | Solo se pasan `last_domain` y `last_filters`, no resultados ni datos personales |

---

## 4. Cambios en Interfaces y Dependencias

### 4.1 Firmas modificadas

| Componente | Firma actual | Firma propuesta | Compatibilidad |
|---|---|---|---|
| `ConversationalAgent.__init__` | `..., nlu_engine=None, tool_registry=None` | `..., nlu_engine=None, tool_registry=None, catalog_repo=None` | ✅ Opcional al final |
| `NLUEngine.__init__` | `(self, llm)` | `(self, llm, catalog_repo=None)` | ✅ Opcional al final |
| `_dispatch_tool` | `(self, tool_name, params, user_text)` | `(self, tool_name, params, user_text, telegram_user_id=None)` | ✅ Opcional al final |
| `_fallback_to_query_db` | `(self, user_text, entity_hints="")` | `(self, user_text, entity_hints="", telegram_user_id=None)` | ✅ Opcional al final |
| `generate_response` | `(..., conversation_history=None)` | `(..., conversation_history=None, session_context=None)` | ✅ Opcional al final |

### 4.2 Nuevos métodos

| Método | Clase/Módulo | Visibilidad |
|---|---|---|
| `_normalize_params` | `ConversationalAgent` | Privado |
| `_get_catalog_prompt` | `NLUEngine` | Privado |
| `_build_catalog_prompt` | `NLUEngine` | Privado |
| `_match_department` | `EntityResolver` | Estático, público |
| `_match_rank` | `EntityResolver` | Estático, público |
| `_match_area` | `EntityResolver` | Estático, público |
| `normalize_sex` | `EntityResolver` | Estático, público |

### 4.3 Constantes nuevas

| Constante | Ubicación | Valor |
|---|---|---|
| `_CATALOG_PROMPT_TEMPLATE` | `intent_classifier.py` | Template de catálogo para inyección |
| `_CACHE_TTL_SECONDS` | `NLUEngine` | `1800` |
| `_ANAPHORIC_CONNECTORS` | `agent.py` | Lista de regex de conectores |
| `_DOMAIN_NOUNS` | `agent.py` | Set de sustantivos de dominio |
| `_EXPORT_PATTERNS` | `agent.py` | Lista de regex de export |

---

## 5. Plan de Pruebas

### 5.1 Estrategia General

- **Tests unitarios:** Uno por cada comportamiento nuevo (mínimo 24 tests nuevos).
- **Tests de regresión:** `pytest backend/tests/telegram/ -x -q` entre cada problema.
- **Tests de integración:** Verificar que el pipeline completo LLM-first funciona end-to-end con los 6 fixes aplicados.

### 5.2 Tests por Problema

| Problema | Tests nuevos | Tests actualizados |
|---|---|---|
| 1. Historial | 2 | 1 (`test_memory_load_history_filters_formatted_responses`) |
| 2. Normalización | 7 | 0 |
| 3. Schema injection | 4 | 0 |
| 4. Sesión en NL response | 3 | 0 |
| 5. Follow-up | 7 | Revisar `test_compound_queries.py`, `test_operational_context.py` |
| 6. SQL Agent context | 3 | 0 |
| **Total** | **26** | **1+ por revisar** |

### 5.3 Comandos de Validación

```bash
# Después de CADA problema:
pytest backend/tests/telegram/ -x -q

# Después de TODOS los problemas:
pytest backend/tests/telegram/ -v --tb=short
pytest backend/tests/telegram/test_comprehensive_agent.py -v
```

---

## 6. Orden de Ejecución y Checkpoints

```
┌─────────────────────────────────────────────────────────────┐
│  Paso 1: PROBLEMA 1 — Historial roto                        │
│  → memory.py                                                │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 2: PROBLEMA 5 — Follow-up agresivo                    │
│  → agent.py (_looks_like_followup)                          │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 3: PROBLEMA 2 — EntityResolver en LLM-first           │
│  → agent.py (_normalize_params)                             │
│  → entity_resolver.py (métodos estáticos)                   │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 4: PROBLEMA 3 — Schema injection NLU                  │
│  → intent_classifier.py                                     │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 5: PROBLEMA 4 — SessionStore en NL response           │
│  → agent.py, nl_response.py                                 │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 6: PROBLEMA 6 — SQL Agent con contexto                │
│  → agent.py (_fallback_to_query_db, _dispatch_tool)         │
│  → pytest -x -q ✅                                          │
├─────────────────────────────────────────────────────────────┤
│  Paso 7: Validación completa                                │
│  → pytest backend/tests/telegram/ -v                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. Riesgos Globales y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Tests existentes fallan por cambio de comportamiento en `load_history` | Media | Alto | Actualizar test que validaba skip agresivo; mantener skip de errores |
| Prompt de NLU excede límite de tokens del modelo | Baja | Medio | Catálogo truncado a top 50 valores; monitorear en logs |
| Normalización async vs sync genera inconsistencias | Baja | Medio | Usar sincrónico consistente con `EntityResolver`; documentar |
| Follow-up más restrictivo reduce UX en casos edge | Media | Medio | `_DOMAIN_NOUNS` extensible; monitorear métricas de follow-up |
| Cambio en `_dispatch_tool` firma rompe overrides | Baja | Alto | Param opcional al final; verificar con `grep` que no hay subclasses |

---

## 8. Checklist de Aprobación

Antes de comenzar la implementación, confirmar:

- [ ] Aprobación del orden de ejecución (1→5→2→3→4→6)
- [ ] Aprobación de inyectar `CatalogRepository` en `ConversationalAgent`
- [ ] Aprobación de inyectar `catalog_repo` opcional en `NLUEngine`
- [ ] Aprobación de agregar tests en archivos existentes (no archivo nuevo)
- [ ] Aprobación de modificar `generate_response` con `session_context` opcional
- [ ] Confirmación de que `QueryExecutor.execute()` acepta texto enriquecido sin problemas
- [ ] Confirmación de que no hay subclasses de `ConversationalAgent` que overrideen `_dispatch_tool`

---

## 9. Anexos

### Anexo A: Ubicación de archivos

```
backend/app/application/telegram/
├── memory.py              # Problema 1
├── agent.py               # Problemas 2, 4, 5, 6
├── intent_classifier.py   # Problema 3
├── entity_resolver.py     # Problema 2 (refactor)
├── nl_response.py         # Problema 4
└── tool_registry.py       # Sin cambios

backend/app/infrastructure/repositories/
└── catalogs.py            # Referencia (sin cambios)

backend/tests/telegram/
├── test_memory.py         # Tests Problema 1
├── test_agent.py          # Tests Problemas 2, 5, 6
├── test_intent_classifier.py  # Tests Problema 3
├── test_entity_resolver.py    # Tests Problema 2 (refactor)
└── test_nl_primary_path.py    # Tests Problema 4
```

### Anexo B: Ejemplo de historial antes/después (Problema 1)

**Antes:**
```
Usuario: "¿Cuántos doctores hay en cirugía?"
# → tool_name="count_doctors", response_text="Hay 15 doctores..."
# → load_history() devuelve: []  (¡perdido!)
Usuario: "y de ellos, cuántas mujeres"
# → LLM no tiene contexto de la pregunta anterior
```

**Después:**
```
Usuario: "¿Cuántos doctores hay en cirugía?"
# → tool_name="count_doctors"
# → load_history() devuelve:
#   [{"role":"user","content":"¿Cuántos doctores hay en cirugía?"},
#    {"role":"assistant","content":"Consulté count_doctors y encontré 1 resultados."}]
Usuario: "y de ellos, cuántas mujeres"
# → LLM ve la consulta anterior y puede resolver el anáfora
```

---

*Documento generado para revisión y aprobación antes de la implementación.*
