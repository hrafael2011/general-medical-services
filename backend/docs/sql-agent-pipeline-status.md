# Estado del Pipeline SQL Agent — Fase 5

**Rama:** `bot-dev` | **Fecha:** 2026-05-27

---

## Pipeline Completo

```
Usuario → Telegram Webhook
   ↓
ConversationalAgent.process(text, user_info)
   ↓
1. SemanticLayerResolver (determinista, ~100% para comunes)
   ├── Si encaja: responde directamente (latencia <1s)
   └── Si no encaja: continúa
   ↓
2. IntentRouter legacy (29 queries predefinidas)
   ├── Si encaja: ejecuta query registry (latencia <1s)
   └── Si no encaja: continúa
   ↓
3. SQL Agent Multi-Turno (fallback ad-hoc)
   ├── SchemaLinker → reduce schema por keywords
   ├── PromptBuilder → inyecta 3-5 ejemplos few-shot (sqlite-vec)
   ├── QueryGenerator (CoT) → genera SQL
   ├── SQLValidator → 8 reglas de seguridad (antes de BD)
   ├── SafeSQLExecutor → ejecuta con timeout 10s
   ├── SQLVerifier → LLM critic verifica semántica
   └── QueryRefiner → corrige errores (max 3 iteraciones)
   └── Responde (latencia target <8s)
   ↓
4. Exportación (PDF/Excel) si se solicita
```

---

## Métricas de Tests

| Suite | Tests | Estado |
|-------|-------|--------|
| `test_semantic_layer.py` | 25 | ✅ Todos pasan |
| `test_sql_agent.py` | 28 | ✅ Todos pasan |
| `test_validator.py` | 23 | ✅ Todos pasan |
| `test_query_executor.py` | 14 | ✅ Todos pasan |
| **Nuestros tests (Fases 1-4)** | **90** | **✅ Todos pasan** |
| Tests originales preexistentes | ~293 | 7 fallos conocidos (SQLite schema vs PostgreSQL) |
| `test_comprehensive_agent.py` | 52 | ❌ 51 errors preexistentes (SQLite schema mismatch) |

> **Nota:** Los fallos en `test_comprehensive_agent.py`, `test_agent.py`, `test_agent_integration.py`, e `test_intent_router.py` son **preexistentes** y relacionados con discrepancias de schema SQLite (`whatsapp_phone` NOT NULL, `participa_misiones`, etc.). No fueron introducidos por el Semantic Layer ni el SQL Agent.

---

## Archivos Nuevos/Modificados

### Nuevos (Fases 1-4)
```
backend/app/application/telegram/semantic_layer/
    ├── __init__.py
    ├── models.py
    ├── definitions.py
    ├── engine.py
    ├── registry.py
    └── resolver.py

backend/app/application/telegram/sql_agent/
    ├── __init__.py
    ├── schema_linker.py
    ├── generator.py
    ├── executor.py
    ├── verifier.py
    ├── refiner.py
    ├── orchestrator.py
    ├── security.py
    ├── validator.py
    ├── example_store.py
    └── prompt_builder.py

backend/tests/telegram/test_semantic_layer.py
backend/tests/telegram/test_sql_agent.py
backend/tests/telegram/test_validator.py
backend/scripts/seed_sql_agent_examples.py
```

### Modificados
```
backend/app/application/telegram/agent.py          (integra SemanticLayerResolver)
backend/app/application/telegram/query_executor.py  (wrapper → SQLAgentOrchestrator)
requirements.txt                                    (+sqlite-vec, numpy, scikit-learn)
```

---

## Seguridad

| Capa | Protección |
|------|------------|
| SQLValidator (programático) | SELECT-only, no DML/DDL, funciones prohibidas, patrones peligrosos, tablas excluidas, LIMIT obligatorio |
| SafeSQLExecutor | Timeout 10s, solo SELECT, row limit 100, sanitiza UUIDs |
| validate_sql (security.py) | Bloquea INSERT/UPDATE/DELETE/DROP, tablas excluidas |
| Semantic Layer | Zero LLM calls para consultas comunes |

---

## Dependencias Nuevas

- `sqlite-vec>=0.1.0` — vector store local
- `numpy>=2.0.0` — vectores TF-IDF
- `scikit-learn>=1.5.0` — TfidfVectorizer

---

## Próximos Pasos (fuera de scope actual)

1. **Fix schema SQLite:** Alinear constraints SQLite con PostgreSQL para tests existentes
2. **Benchmark de 243 casos QA:** Validar ≥95% pass rate en escenarios conversacionales
3. **Benchmark de latencia:** Medir Semantic Layer <1s, SQL Agent <8s en producción
