---
spec: 14
version: 1.0.0
status: draft
created: 2026-05-06
updated: 2026-05-06
---

# Spec 14 — Master Plan: Hybrid Bot + Technical Audit

## Objetivo

Unificar en un solo roadmap:
1. La optimización del bot de Telegram (conversacional híbrido, rápido, auto-aprendido)
2. Los items pendientes de la auditoría técnica (`spect-extra-improve.md`)

Sin duplicar esfuerzo, sin romper lo que funciona.

---

## Lo que YA FUNCIONA y NO se toca

| Componente | Razón |
|-----------|-------|
| Webhook → Orchestrator pipeline | Responde 200, pipeline sólido |
| Deep-link auth (/start <token>) | Vinculación funciona |
| User link management (CRUD) | Admin endpoints funcionales |
| PDF templates con reportlab | Generan PDFs con logo, tabla, footer |
| bot_client.send_message / send_document | Envío funciona |
| ReportService (calendar_excel, doctor_history_excel, etc.) | Lógica de reports existentes probada |
| MemoryManager | Carga historial correctamente |
| Filtros de seguridad (SELECT-only) | QueryExecutor ya bloquea DML |
| Sistema de autenticación JWT | Login, tokens, roles funcionan |
| CRUD de doctores, calendarios, misiones | Endpoints funcionales |
| Catálogos (ranks, departamentos, áreas) | Datos base cargados |
| Migraciones Alembic | Versionadas y aplicadas |

---

## Roadmap general

```
Sprint 1 ─── Fase 0: Quick fixes (bugs activos)
Sprint 1 ─── Fase 1: Router híbrido + auto-aprendizaje
Sprint 2 ─── Fase 2: Exportación genérica de reportes
Sprint 2 ─── Fase 3: Observabilidad del bot
Sprint 3-4 ─ Fase 4: Items de auditoría (CommandValidator, FairnessEngine, etc.)
Sprint 5   ─ Fase 5: Consolidación y cache
```

---

## Fase 0 — Quick Fixes (bugs activos que dan respuestas incorrectas)

**Problema:** QueryExecutor genera SQL con valores incorrectos porque el schema no incluye los valores reales de las columnas.

| Consulta | Respuesta actual | Respuesta correcta |
|----------|-----------------|-------------------|
| "cuántos femeninos" | 0 | 75 |
| "cuántos cabos" | "out of domain" / 0 | 58 |

### Tareas

**0.1 — Incluir valores reales de columnas en schema_summary**
- Leer valores DISTINCT de columnas críticas: `doctors.sex`, `doctors.availability_mode`, `ranks.normalized_name`
- Agregarlos al schema_summary como hint:
  ```
  doctors.sex VARCHAR(10): 'male' | 'female'    NOTA: valores en inglés
  ranks.normalized_name VARCHAR(50): 'cabo', 'sargento', 'pasante', 'contrata', 'sargento mayor'
  ```
- Archivo: `backend/app/application/telegram/query_executor.py:_build_schema_summary()`

**0.2 — Instruir idioma agnóstico en system prompt**
- Agregar al system prompt: "Responde SIEMPRE en el mismo idioma que el usuario."
- Archivo: `backend/app/application/telegram/agent.py:_SYSTEM_PROMPT`

**0.3 — Graceful degradation en webhook**
- Reemplazar `except: pass` silencioso por:
  - Log del error completo
  - Reintento 1 vez
  - Si persiste: responder mensaje legible al usuario
- Archivo: `backend/app/api/routes/telegram.py`

### Criterio de salida
- `curl` simulado de "cuántas médicos femeninos" → 75
- `curl` simulado de "cuántos cabos" → 58
- Si DeepSeek falla → usuario recibe mensaje, no silencio

---

## Fase 1 — Router Híbrido de Intenciones + Auto-aprendizaje

**Problema:** 13 tools fijos + 2 llamadas LLM = lento, caro, y consultas no mapeadas fallan.

### Arquitectura nueva

```
Usuario → 1 llamada LLM (clasifica intención)
  → {"action": "query", "query_type": "doctors_by_rank", "params": {"rank": "cabo"}}
    → IntentRouter busca en QueryRegistry
      ├── Match encontrado → SQL predefinido → BD → respuesta (~1-3s)
      └── Sin match → fallback query_database (LLM genera SQL) → funciona (~4-6s)
          → Se auto-registra en QueryRegistry para próxima vez
```

### Componentes nuevos

**1. IntentRouter** — `backend/app/application/telegram/intent_router.py`
- Recibe `{action, query_type, params, format}` del LLM
- Rutas:
  - `action = "reply"` → responde directo (saludos, fuera de dominio)
  - `action = "query"` → busca query_type en registro, si no hay → fallback a query_database
  - `action = "export"` → igual que query + genera PDF/Excel con DataExporter
  - `action = "ambiguous"` → pide aclaración al usuario

**2. QueryRegistry** — `backend/app/application/telegram/registry.py`
- Tabla en BD:
  ```sql
  query_registry (
    id UUID PK,
    query_type VARCHAR(100) UNIQUE,
    frase_ejemplo VARCHAR(500),
    embedding VECTOR(384),
    sql_template VARCHAR(2000),
    params_schema JSON,
    hits INTEGER DEFAULT 0,
    auto_promoted BOOLEAN DEFAULT false,
    created_at TIMESTAMP,
    last_used_at TIMESTAMP
  )
  ```
- Métodos:
  - `register(query_type, frase, sql_template, params_schema)` — guarda nueva
  - `find_match(user_message)` — similarity por embedding > 85%
  - `increment_hit(query_type)` — contador
  - `get_all(), delete(id)` — admin

**3. ConversationalAgent modificado** — `backend/app/application/telegram/agent.py`
- System prompt reducido (sin tools, sin schema, sin 28 tablas)
- 1 sola llamada LLM (no 2):
  - Prompt: "Dado el mensaje del usuario, extrae la acción y parámetros en JSON"
  - Respuesta: `{"action": "query", "query_type": "...", "params": {...}}`
- Eliminar `_call_tool_and_format()` — ya no se necesita
- AgentResult se simplifica: solo `action, query_type, params, response_text, document_bytes`

**4. Auto-registro de consultas nuevas**
- Cuando query_database (fallback) ejecuta SQL con éxito
- IntentRouter normaliza: extrae sql_template paramétrico + query_type
- sentence-transformers genera embedding de la pregunta (~5ms local)
- Guarda en query_registry con auto_promoted=true

**5. Embeddings locales** — sin API externa
- Librería: `sentence-transformers` (modelo all-MiniLM-L6-v2)
- Vector 384 dimensiones, inferencia ~5ms
- Búsqueda por cosine similarity en PostgreSQL con pgvector

### Dependencias nuevas
- `sentence-transformers>=3.0`
- Extensión PostgreSQL `pgvector` (o simular con cosine distancia en Python)

### Criterio de salida
- 1 sola llamada LLM por mensaje (vs 2 hoy)
- Consultas mapeadas → ~1-3s
- Consultas no mapeadas → fallback funciona → ~4-6s
- Consulta repetida → auto-mapeada → próxima vez rápida
- Cobertura total: cualquier consulta con datos en BD se responde

---

## Fase 2 — Exportación Genérica de Reportes

**Problema:** No hay forma de generar PDF/Excel de datos arbitrarios. Solo existen tools fijos para calendario/historial/resumen/ranking, todos atados a mes/año.

### Componentes nuevos

**1. DataExporter** — `backend/app/application/reports/data_exporter.py`
```
export_pdf(title, headers, rows) → bytes
export_excel(title, headers, rows) → bytes
export_json(title, headers, rows) → dict
```
- Reutiliza estilos de pdf_templates.py (logo, header azul, footer)
- Sin dependencias nuevas (ya usa reportlab + openpyxl)

**2. Integración con IntentRouter**
- Cuando `action = "export"` y `format = "pdf"|"excel"`
- Router ejecuta query, toma rows, llama DataExporter
- Devuelve `response_text + document_bytes + document_filename`
- Mensaje: "Aquí tienes el reporte de {title} en PDF."

### Criterio de salida
- "genera PDF de los cabos" → PDF con 58 médicos
- "exporta a Excel las mujeres" → Excel con 75 médicas
- "genera reporte de los que trabajaron en navidad" → PDF con ese listado
- Cualquier resultado de query puede exportarse

---

## Fase 3 — Observabilidad del Bot

**Problema:** No hay logging de decisiones del LLM, latencia, ni trazabilidad de qué respondió el bot y por qué.

### Tareas

**3.1 — Logging estructurado**
- Cada interacción loguea:
  ```json
  {
    "user_id": "...",
    "action": "query|export|reply|ambiguous",
    "query_type": "doctors_by_rank",
    "match_type": "registry|fallback|direct",
    "latency_ms": 1234,
    "tokens_estimated": 600,
    "sql_generated": "SELECT ..." (solo DEBUG),
    "error": null
  }
  ```

**3.2 — Endpoints admin de monitoreo**
- `GET /api/telegram/query-registry` — listar queries + hits + última vez
- `DELETE /api/telegram/query-registry/{id}` — eliminar query problemática
- `GET /api/telegram/metrics` — tasa de aciertos del registro, latencia promedio

**3.3 — Archivos a modificar**
- `agent.py` — loggear acción + latencia
- `intent_router.py` — loggear match encontrado + SQL ejecutado
- `query_executor.py` — loggear SQL generado (solo DEBUG)
- `orchestrator.py` — loggear interacción completa

---

## Fase 4 — Items de la Auditoría Técnica

**Fuente:** `spect-extra-improve.md` (Bloques 1-12)

**NOTA:** Ninguno de estos items afecta al bot. Son mejoras arquitectónicas internas del core del sistema.

### 4.1 — CommandValidator (Bloque 1, 4)
**Qué:** Validador de ambigüedad antes de ejecutar comandos críticos. Si el input es ambiguo ("asigna a Pérez esta semana"), pide aclaración antes de ejecutar.
**Dónde:** `backend/app/application/validators/command_validator.py`
**Dependencias:** Ninguna nueva.

### 4.2 — FairnessEngine con reglas desacopladas (Bloque 4, 5)
**Qué:** Refactorizar el FairnessEngine actual de función monolítica a clases individuales por regla:
- `RulePreventOverload`
- `RuleAreaRotation`
- `RuleDiasValidos`
- `RuleLimiteMensual`
- `RuleEspaciadoServicios`
- `RuleCoberturaDiaria`
**Dónde:** `backend/app/domain/calendars/rules/`
**Dependencias:** pytest para tests unitarios por regla.

### 4.3 — State machine para asignaciones (Bloque 2, 11)
**Qué:** Control de transiciones de estado. No permitir:
- Confirmar turno cancelado
- Modificar calendario aprobado
- Notificar calendario no aprobado
**Dónde:** `backend/app/domain/calendars/state_machine.py`

### 4.4 — Idempotencia en acciones críticas (Bloque 6)
**Qué:** Las acciones de confirmar turno, asignar, override deben ser idempotentes. Misma request enviada 2 veces → mismo resultado.
**Dónde:** IdempotencyKey en header de requests + tabla `idempotency_keys`

### 4.5 — Override tracking (Bloque 1)
**Qué:** Toda asignación forzada debe registrar:
- Reglas violadas
- Usuario que forzó
- Fecha/hora
- Razón
**Dónde:** Tabla `override_audit_log` + middleware en endpoints de override

### 4.6 — API responses consistentes (Bloque 6)
**Qué:** Wrap de respuestas en estructura uniforme:
```json
{"success": true, "message": "...", "data": {...}}
{"success": false, "message": "...", "error_code": "..."}
```
**Dónde:** Middleware FastAPI + `backend/app/api/responses.py`

### 4.7 — CI/CD pipeline (Bloque 12)
**Qué:** Pipeline automatizado que ejecute tests antes de merge/deploy.
**Dónde:** `.github/workflows/` (ya existe base, fortalecer)

### 4.8 — Testing del FairnessEngine (Bloque 7)
**Qué:** Tests unitarios independientes por regla + tests integrados del engine completo.
**Dónde:** `backend/tests/calendars/test_fairness_rules/`

---

## Fase 5 — Consolidación y Cache (futuro)

### 5.1 — Curaduría del registro de queries
- Endpoint admin para aprobar/rechazar/editar queries auto-promoted
- Fusión de query_types duplicados
- Limpieza de queries con 0 hits en 90 días

### 5.2 — Cache de respuestas frecuentes
- Datos estáticos (catálogos, conteos) → cache 5-30 min
- Cache por query_type + hash de params
- Usar Redis o cache en memoria simple

### 5.3 — Persistencia de historial conversacional
- Opcional: extender MemoryManager para persistir entre reinicios del backend

---

## Resumen de impacto

| Métrica | Hoy | Después Fase 0-1-2 | Después Fase 3-4-5 |
|---------|-----|-------------------|-------------------|
| Latencia consulta simple | 5-8s | 1-3s | 1-3s |
| Latencia con PDF | 8-15s | 2-4s | 2-4s |
| Llamadas LLM por mensaje | 2 | 1 | 1 |
| Tokens por consulta | ~2000 | ~600 | ~600 |
| Cobertura de consultas | 8 intents | 100% | 100% |
| Auto-aprendizaje | No | Sí | Sí |
| Respuestas correctas | No (0 femeninos) | Sí | Sí |
| Exportación genérica | No | Sí | Sí |
| CommandValidator | No | No | Sí |
| FairnessEngine desacoplado | No | No | Sí |
| State machine | No | No | Sí |
| Idempotencia | No | No | Sí |
| CI/CD completo | Parcial | Parcial | Sí |

---

## Lo que NO está en este plan (no tocar)

- CRUD de doctores, calendarios, misiones — funcionan
- Frontend React — no se modifica
- Autenticación JWT — funciona
- Sistema de notificaciones — funciona
- Telegram user link management — funciona
- Migraciones existentes — no se retroceden
- Esquema de BD actual — no se modifican tablas existentes

---

## Dependencias entre fases

```
Fase 0 ─── no depende de nada (arranca ya)
  │
  ▼
Fase 1 ─── necesita Fase 0 (para que query_database dé datos correctos)
  │
  ├──► Fase 2 ─── necesita Fase 1 (el router debe existir)
  │
  ├──► Fase 3 ─── puede ir en paralelo con Fase 1-2
  │
  ▼
Fase 4 ─── independiente de Fase 0-1-2-3 (no toca el bot)
  │
  ▼
Fase 5 ─── necesita Fase 1 (registro de queries maduro)
```

**Nota:** Fase 4 puede ejecutarse en paralelo con Fase 1-2-3 porque son capas distintas del sistema.
