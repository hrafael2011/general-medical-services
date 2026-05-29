# Telegram Bot — Asistente Conversacional para Sistema de Turnos Médicos

> **Rama:** `bot-dev` | **Fecha:** 2026-05-29 | **Feature Flag:** `FEATURE_TELEGRAM`

---

## 1. Resumen Ejecutivo

El bot de Telegram es un **asistente conversacional con IA** integrado al sistema de turnos médicos. Permite a administradores y encargados consultar información de médicos, calendarios, misiones y reportes operativos mediante lenguaje natural en español, directamente desde Telegram.

Utiliza **DeepSeek** como motor LLM para entender las preguntas del usuario y generar respuestas conversacionales, pero todo el acceso a datos se hace mediante consultas SQL determinísticas predefinidas — **el LLM nunca accede directamente a la base de datos**.

---

## 2. Stack Tecnológico

| Categoría | Tecnología | Versión | Propósito |
|-----------|-----------|---------|-----------|
| **Lenguaje** | Python | 3.12 | Backend |
| **Framework Web** | FastAPI | 0.115.6 | API + Webhook |
| **ASGI Server** | Uvicorn | 0.34.0 | Servidor |
| **ORM** | SQLAlchemy | 2.0.36 | Acceso a datos |
| **DB Driver** | psycopg[binary] | 3.2.3 | PostgreSQL |
| **Base de Datos** | PostgreSQL | — | Principal |
| **LLM** | DeepSeek (`deepseek-chat`) | — | NLU + NLG + SQL Agent |
| **SDK LLM** | openai (compatibilidad) | ≥1.0.0 | Cliente OpenAI-compatible |
| **HTTP Client** | httpx | ≥0.27.0 | Telegram Bot API |
| **Validación** | Pydantic v2 | — | Schemas + Settings |
| **PDF** | WeasyPrint + ReportLab | ≥68.0 / ≥4.2 | Exportación reportes |
| **Excel** | openpyxl | 3.1.5 | Exportación reportes |
| **Vector Store** | sqlite-vec + scikit-learn | ≥0.1.0 / ≥1.5.0 | RAG few-shot SQL |
| **Scheduler** | APScheduler | ≥3.10.0 | Jobs en background |
| **Testing** | pytest | — | Tests unitarios e integración |

**Nota importante:** No se usa `python-telegram-bot`. La comunicación con Telegram es directa vía HTTP a `https://api.telegram.org/bot<TOKEN>/sendMessage` y `/sendDocument`.

---

## 3. Arquitectura General

```
┌──────────────────────────────────────────────────────────────┐
│                     TELEGRAM BOT API                         │
│              https://api.telegram.org/bot<TOKEN>             │
└──────────────────────┬───────────────────────────────────────┘
                       │ POST (webhook)
                       ▼
┌──────────────────────────────────────────────────────────────┐
│              POST /api/telegram/webhook                       │
│              backend/app/api/routes/telegram.py               │
│                                                              │
│  • Valida X-Telegram-Bot-Api-Secret-Token                    │
│  • Rate limit: 20 req/min por telegram_user_id               │
│  • 1 retry automático en caso de fallo                       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│         TelegramOrchestrator.handle_message()                 │
│         backend/app/application/telegram/orchestrator.py      │
│                                                              │
│  1. /start <token> → deep-link auth (link Telegram↔Usuario)  │
│  2. Resuelve TelegramUserLink → usuario del sistema          │
│  3. Verifica cuenta activa, must_change_password             │
│  4. /recibido, /confirmar → comandos de confirmación         │
│  5. Delega al ConversationalAgent                            │
│  6. Envía respuesta (texto + documento opcional)             │
│  7. Loggea interacción en telegram_interactions              │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│           ConversationalAgent.process()                       │
│           backend/app/application/telegram/agent.py           │
│                                                              │
│  Pipeline dual:                                              │
│                                                              │
│  ┌─ PATH 1 (PRIMARIO): LLM-First ──────────────────────┐    │
│  │  NLUEngine.classify() → 1 llamada LLM                │    │
│  │  → Tool + Parámetros                                 │    │
│  │  → _dispatch_tool() → manejador determinístico       │    │
│  │  → generate_response() → respuesta en español        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ PATH 2 (LEGACY): EntityResolver + IntentClassifier ─┐   │
│  │  EntityResolver.pre_process() → entidades DB          │   │
│  │  IntentClassifier.classify() → intención              │   │
│  │  → if-elif chain → servicio correspondiente           │   │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  • MemoryManager: historial de conversación                  │
│  • SessionStore: contexto de follow-up (30 min TTL)          │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│              CAPA DE EJECUCIÓN (en orden de prioridad)       │
│                                                              │
│  1. ToolRegistry         → handlers registrados              │
│  2. DoctorQueryService   → queries determinísticas (ORM)     │
│  3. CalendarQueryService → queries de calendario (ORM)       │
│  4. SemanticLayer        → 15 métricas SQL predefinidas      │
│  5. IntentRouter         → 30+ queries SQL parametrizadas    │
│  6. SQL Agent            → NL→SQL multi-turn (fallback)      │
│     ├─ SchemaLinker (reduce schema)                          │
│     ├─ QueryGenerator (Chain-of-Thought → SQL)               │
│     ├─ SafeSQLExecutor (validación + ejecución)              │
│     ├─ SQLVerifier (LLM verifica respuesta)                  │
│     ├─ QueryRefiner (corrige errores, máx 3 iteraciones)     │
│     └─ ExampleStore (RAG few-shot con sqlite-vec + TF-IDF)   │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Componentes del Bot

### 4.1 Archivos Core (15 archivos)

| Archivo | Responsabilidad |
|---------|----------------|
| `orchestrator.py` | Punto de entrada. Maneja links, autenticación, comandos, delegación al agente |
| `agent.py` | Cerebro conversacional. Pipeline dual LLM-First / Legacy, merge de contexto, follow-ups |
| `bot_client.py` | Envío de mensajes y documentos a Telegram vía HTTP (httpx) + FakeBotClient para tests |
| `types.py` | Dataclass `AgentResult`: response_text, document_bytes, tool_name, tool_entities |
| `llm.py` | DeepSeekProvider vía OpenAI SDK + FakeLLMProvider para desarrollo |
| `memory.py` | SessionStore (30 min TTL, persistencia DB) + MemoryManager (historial de chat) |
| `nl_response.py` | Generación de respuestas en español conversacional desde resultados estructurados |
| `sanitize.py` | Sanitización HTML/XML + mapeo de valores DB a español (sexo, estado, etc.) |
| `schemas.py` | Pydantic: IntentOutput (salida validada del LLM), ResolveResult |
| `registry.py` | QueryRegistry con 30+ tipos de queries SQL parametrizadas + estadísticas de uso |
| `intent_classifier.py` | NLUEngine (LLM-first) + IntentClassifier (wrapper legacy) |
| `entity_resolver.py` | Resuelve lenguaje natural → entidades DB (fechas, médicos, áreas, rangos) |
| `tool_registry.py` | ToolRegistry con 12 herramientas y sus JSON schemas para el LLM |
| `tools.py` | ToolGateway — mapa legacy de handlers (8 herramientas pre-LLM) |
| `intent_router.py` | Router de intenciones clasificadas → ejecución SQL + export PDF/Excel |

### 4.2 Doctor Query Service

**Archivo:** `doctor_query_service.py`

Servicio determinístico para consultas de médicos. Soporta:
- `count` — contar médicos con filtros (sexo, rango, departamento, área)
- `list` — listar médicos con filtros
- `count_by_sex` — distribución por sexo
- Detección de nombres duplicados
- Validación de que todos los filtros solicitados fueron aplicados
- Exportación a PDF/Excel

### 4.3 Calendar Query Service

**Archivo:** `calendar_query_service.py`

Consultas determinísticas de asignaciones de calendario. Status-aware: prefiere versiones aprobadas, fallback a draft.

### 4.4 Semantic Layer (Capa Semántica)

**Directorio:** `semantic_layer/` (5 archivos)

Métricas de negocio con SQL escrito a mano. **Cero LLM en generación SQL.** 100% determinístico.

| Métrica | Descripción |
|---------|-------------|
| `total_doctors` | Total de médicos |
| `doctors_by_sex` | Médicos por sexo |
| `doctors_by_rank` | Médicos por rango |
| `doctors_by_department` | Médicos por departamento |
| `duplicate_doctor_names` | Nombres duplicados |
| `active_missions` | Misiones activas |
| `mission_ranking` | Ranking de candidatos para misión |
| `total_services` | Total de servicios |
| `assigned_doctors_count` | Médicos asignados |
| `unassigned_doctors` | Médicos sin asignar |
| `doctor_service_load` | Carga de servicio por médico |
| `unresolved_gaps` | Huecos sin resolver |
| `operational_summary` | Resumen operacional (múltiples métricas) |
| `pending_confirmations` | Confirmaciones pendientes |
| `last_service_by_doctor` | Último servicio de cada médico |
| `calendar_status` | Estado del calendario (draft/aprobado) |

### 4.5 SQL Agent (Agente NL→SQL)

**Directorio:** `sql_agent/` (10 archivos)

Sistema multi-turno para convertir lenguaje natural a SQL con autocorrección. Solo se usa como **fallback** cuando las queries predefinidas no cubren la pregunta.

**Pipeline (máx 3 iteraciones):**

```
SchemaLinker → QueryGenerator → SafeSQLExecutor → SQLVerifier → QueryRefiner
     │               │                │                │              │
     │         CoT prompt        Valida SQL       LLM verifica    Re-genera
     │         con contexto      (SELECT-only,    que responde    SQL si hay
     │         de la BD          sin DML, etc.)   la pregunta     error
     │                                                              │
     └──────────────────────────────────────────────────────────────┘
                          Hasta 3 iteraciones
```

**ExampleStore (RAG):** Base de datos sqlite-vec con TF-IDF para recuperar ejemplos few-shot de preguntas similares y mejorar la generación SQL.

### 4.6 Base de Datos del Bot (4 tablas)

| Modelo | Tabla | Propósito |
|--------|-------|-----------|
| `TelegramUserLinkModel` | `telegram_user_links` | Vincula telegram_user_id ↔ user_id del sistema |
| `TelegramLinkTokenModel` | `telegram_link_tokens` | Tokens de un solo uso para deep-link /start |
| `TelegramInteractionModel` | `telegram_interactions` | Bitácora completa de cada interacción |
| `TelegramSessionModel` | `telegram_sessions` | Persistencia de sesión (sobrevive reinicios) |

---

## 5. Flujo de Autenticación (Deep-Link)

1. Admin genera un token desde el panel web (`POST /api/telegram/link-tokens`)
2. El token se comparte con el usuario como: `https://t.me/MedicalSchedule_bot?start=<token>`
3. Usuario inicia el bot con `/start <token>`
4. El Orchestrator valida el token (no expirado, no usado)
5. Crea `TelegramUserLink` (telegram_user_id ↔ user_id)
6. El bot responde con mensaje de bienvenida

---

## 6. Herramientas Disponibles (12 tools)

Definidas en `tool_registry.py` con JSON schemas para el LLM:

| Tool | Descripción |
|------|-------------|
| `list_doctors` | Listar médicos con filtros |
| `count_doctors` | Contar médicos |
| `doctors_by_sex` | Distribución por sexo |
| `doctors_by_rank` | Distribución por rango |
| `doctors_by_department` | Distribución por departamento |
| `doctor_last_service` | Último servicio de un médico |
| `doctor_service_load` | Carga de servicio |
| `unassigned_doctors` | Médicos sin asignar |
| `calendar_assignments` | Asignaciones del calendario |
| `calendar_assigned_count` | Conteo de asignados por mes |
| `calendar_status` | Estado del calendario |
| `mission_list` | Listar misiones |
| `mission_status` | Estado de misión |
| `sql_query` | Consulta SQL genérica (fallback) |
| `reply` | Respuesta conversacional simple |

---

## 7. Flujo Conversacional (Follow-ups)

El bot mantiene contexto entre mensajes mediante `SessionStore`:

- **TTL de sesión:** 30 minutos
- **Persistencia:** Opcional en tabla `telegram_sessions` (sobrevive reinicios)
- **Merge de contexto:** El método `_merge_followup_context()` en `agent.py` detecta:
  - Textos cortos ("y ellos?", "son", "cuantos", "eso")
  - Referencias anafóricas ("y de esos", "cuales son mujeres")
  - Reutiliza filtros y resultados de la consulta anterior

---

## 8. Seguridad

- **Webhook:** Validación via `X-Telegram-Bot-Api-Secret-Token` con `secrets.compare_digest()`
- **Rate Limiting:** 20 req/min por `telegram_user_id` (en `infrastructure/rate_limiter.py`)
- **SQL Injection:** `SQLValidator` bloquea DML, funciones peligrosas, tablas sensibles. Solo SELECT permitido. Tablas excluidas (`_EXCLUDE_TABLES`).
- **Autenticación:** Solo usuarios linkeados pueden consultar. Verificación de cuenta activa y `must_change_password`.
- **API Admin:** Endpoints de links/interacciones protegidos con `require_admin`.

---

## 9. Configuración

### Variables de Entorno

```bash
# Feature flag — sin esto, el módulo telegram no se carga
FEATURE_TELEGRAM=true

# Telegram Bot API (desde BotFather)
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_BOT_USERNAME=MedicalSchedule_bot
TELEGRAM_WEBHOOK_SECRET=<secret-opcional>

# DeepSeek LLM
DEEPSEEK_API_KEY=<api-key>
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### Modo Desarrollo (sin credenciales)

Si `TELEGRAM_BOT_TOKEN` o `DEEPSEEK_API_KEY` no están configurados, el sistema usa fakes:
- `FakeBotClient`: mensajes en memoria, sin llamadas reales a Telegram
- `FakeLLMProvider`: respuestas predefinidas, sin llamadas reales a DeepSeek

---

## 10. Endpoints de la API

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/api/telegram/webhook` | X-Telegram-Bot-Api-Secret-Token | Recibe updates de Telegram |
| `GET` | `/api/telegram/links` | Admin | Lista usuarios linkeados |
| `POST` | `/api/telegram/links` | Admin | Crea link usuario↔Telegram |
| `DELETE` | `/api/telegram/links/{id}` | Admin | Desactiva un link |
| `POST` | `/api/telegram/link-tokens` | Admin | Genera token deep-link |
| `GET` | `/api/telegram/link-tokens` | Admin | Lista tokens |
| `GET` | `/api/telegram/interactions` | Admin | Bitácora de interacciones |

---

## 11. Frontend de Administración

**Archivo:** `frontend/src/features/telegram/TelegramLinks.tsx`

Panel en la interfaz web para:
- Ver usuarios linkeados a Telegram
- Crear nuevos links
- Desactivar links existentes
- Gestionar tokens de deep-link

---

## 12. Tests

**Directorio:** `backend/tests/telegram/` — **40+ archivos de test**

| Categoría | Archivos |
|-----------|---------|
| Agente | `test_agent.py`, `test_agent_integration.py`, `test_comprehensive_agent.py` |
| Orchestrator | `test_orchestrator.py` |
| NLU | `test_intent_classifier.py`, `test_nl_primary_path.py` |
| Entidades | `test_entity_resolver.py`, `test_entity_resolver_integration.py` |
| Queries | `test_doctor_query_service.py`, `test_calendar_query_service.py` |
| SQL Agent | `test_sql_agent.py`, `test_validator.py` |
| Semantic Layer | `test_semantic_layer.py` |
| Router | `test_intent_router.py` |
| Seguridad | `test_webhook_secret_validation.py`, `test_webhook_security.py` |
| Rate Limiting | `test_rate_limiter.py` |
| Sesiones | `test_memory.py`, `test_session_persistence.py` |
| Conversación | `test_qa_conversational_matrix.py`, `test_compound_queries.py` |
| Integración | `test_bot_client_integration.py` (requiere TELEGRAM_BOT_TOKEN) |

---

## 13. Historial de Desarrollo (commits representativos en `bot-dev`)

| Fase | Commits | Descripción |
|------|---------|-------------|
| **FASE 1** | Semantic Layer Core | 15 métricas SQL predefinidas, engine, resolver |
| **FASE 2** | SQL Agent Multi-Turn | Pipeline SchemaLinker→Generator→Executor→Verifier→Refiner |
| **FASE 3** | RAG Few-Shot | ExampleStore con sqlite-vec + TF-IDF |
| **FASE 4** | Two-Phase Execution | Validación programática post-generación SQL |
| **FASE 5** | Pipeline Integration | Integración del Semantic Layer y SQL Agent en el agente |
| **Refactor** | LLM-First NLU | NLUEngine reemplaza keyword routing, IntentClassifier reemplaza ConversationPlanner |
| **Reciente** | Polishing | Fix mapeo sexo F/M, wire intent classifier en orchestrator, limpieza de código legacy |

---

## 14. Diferencias con WhatsApp

El sistema tiene **dos canales separados** sin enrutamiento híbrido:

| Aspecto | Telegram Bot | WhatsApp |
|---------|-------------|----------|
| **Propósito** | Consultas conversacionales | Confirmaciones de turno |
| **Usuarios** | Admins y encargados | Médicos |
| **Interacción** | Chat bidireccional con IA | Respuesta "1" para confirmar |
| **Tecnología** | HTTP directo a Telegram API | PyWa + Meta Cloud API v22.0 |
| **Webhook** | `POST /api/telegram/webhook` | `POST /api/webhooks/whatsapp` |
| **IA** | DeepSeek para NLU + NLG | Sin IA (solo match de teléfono) |

---

## 15. Diagrama de Directorios

```
backend/app/
├── api/routes/
│   └── telegram.py                    # Webhook + CRUD admin
├── application/telegram/
│   ├── __init__.py
│   ├── agent.py                       # Cerebro conversacional
│   ├── orchestrator.py                # Punto de entrada
│   ├── bot_client.py                  # Cliente HTTP Telegram
│   ├── types.py                       # AgentResult
│   ├── llm.py                         # DeepSeekProvider
│   ├── memory.py                      # Sesiones + historial
│   ├── nl_response.py                 # Respuestas NL
│   ├── sanitize.py                    # Sanitización
│   ├── schemas.py                     # IntentOutput, ResolveResult
│   ├── registry.py                    # 30+ SQL templates
│   ├── intent_classifier.py           # NLUEngine + IntentClassifier
│   ├── entity_resolver.py             # NL → entidades DB
│   ├── tool_registry.py               # 12 herramientas + schemas
│   ├── tools.py                       # ToolGateway legacy
│   ├── intent_router.py               # Router → SQL + PDF/Excel
│   ├── doctor_query_service.py        # Queries determinísticas
│   ├── calendar_query_service.py      # Queries de calendario
│   ├── query_executor.py              # Wrapper SQL Agent
│   ├── semantic_layer/                # Capa semántica determinística
│   │   ├── __init__.py
│   │   ├── models.py                  # Dataclasses core
│   │   ├── definitions.py             # 15 métricas SQL
│   │   ├── engine.py                  # Validador + ejecutor
│   │   ├── resolver.py                # Bridge agente↔semántica
│   │   └── registry.py                # Catálogo para prompts LLM
│   └── sql_agent/                     # NL→SQL multi-turn (fallback)
│       ├── __init__.py
│       ├── orchestrator.py            # Pipeline iterativo
│       ├── generator.py               # CoT → SQL
│       ├── executor.py                # SafeSQLExecutor
│       ├── refiner.py                 # Corrección
│       ├── verifier.py                # Verificación LLM
│       ├── validator.py               # Guardrails SQL
│       ├── schema_linker.py           # Reductor de schema
│       ├── security.py                # Validación + ejecución segura
│       ├── prompt_builder.py          # Formateo few-shot
│       └── example_store.py           # RAG sqlite-vec + TF-IDF
├── infrastructure/db/models/
│   ├── telegram.py                    # UserLink, LinkToken, Interaction
│   └── telegram_session.py           # SessionModel
├── infrastructure/repositories/
│   └── telegram.py                    # TelegramRepository
├── schemas/
│   └── telegram.py                    # Pydantic API schemas
└── core/
    └── config.py                      # Settings (Telegram + DeepSeek)

frontend/src/
├── api/
│   └── notifications.ts               # (comparte tipos con notificaciones)
└── features/
    └── telegram/
        └── TelegramLinks.tsx           # Panel admin de links

backend/tests/telegram/                 # 40+ archivos de test
├── test_agent.py
├── test_agent_integration.py
├── test_intent_classifier.py
├── test_sql_agent.py
├── test_semantic_layer.py
├── test_bot_client_integration.py
├── ... (40+ archivos)
```
