# OR-Tools CP-SAT Migration Design

**Status:** Draft (pending review)
**Created:** 2026-07-07
**Spec:** Supercedes greedy-only approach in spec 02; implements Phase 4.2 of spec 14

## Goal

Reemplazar el algoritmo greedy de asignación de turnos (`CalendarEngine` + `compute_candidate_score`) por un modelo de optimización global con OR-Tools CP-SAT, manteniendo exactamente la misma interfaz hacia el service layer y cero cambios en API/DB/frontend.

## Estrategia: Dos Fases

### Fase 1 — Reglas desacopladas (refactor sin cambio de comportamiento)

Extraer la lógica actual de fairness de `scoring.py` (función monolítica) a clases individuales por regla bajo `rules/`. Cada regla implementa una interfaz común `Rule`.

**Estructura:**

```
backend/app/domain/calendars/
├── rules/
│   ├── __init__.py              ← Fábrica: construye pipeline de reglas desde config
│   ├── interface.py             ← Clase base abstracta Rule
│   ├── rule_active_status.py    ← Médico activo y service_active (HARD)
│   ├── rule_area_allowed.py     ← Área permitida (HARD)
│   ├── rule_hard_block.py       ← Restricciones tipo hard_block (HARD)
│   ├── rule_availability.py     ← Disponibilidad del médico (HARD)
│   ├── rule_monthly_limit.py    ← Límite mensual de servicios (HARD → warn-only)
│   ├── rule_spacing.py          ← Espaciado entre servicios (SOFT)
│   ├── rule_load_balancing.py   ← Balance de carga ponderada (SOFT)
│   ├── rule_area_rotation.py    ← Rotación de áreas (SOFT)
│   ├── rule_mission_priority.py ← Prioridad post-misión (SOFT)
│   └── rule_coverage.py         ← Cobertura diaria mínima (HARD)
├── engine.py                    ← Sin cambios en Fase 1
├── scoring.py                   ← Se convierte en wrapper que delega en RulePipeline
├── types.py                     ← Sin cambios
└── weeks.py                     ← Sin cambios
```

**Interfaz `Rule`:**

```python
class Rule(ABC):
    name: str
    is_hard: bool
    weight: float
    config: dict

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        """Evalúa regla para un doctor+slot. Usado por greedy (Fase 1) y
        por evaluación manual (AssignmentService)."""
        ...

    @abstractmethod
    def add_to_cp_model(self, model: CpModel, ctx: CpModelContext) -> list:
        """Traduce la regla a constraints del modelo CP-SAT.
        Solo implementado en Fase 2."""
        ...
```

**Verificación Fase 1:** Los tests existentes `test_scoring.py` (7 tests) y `test_engine.py` (5 tests) deben pasar sin cambios. El output de `compute_candidate_score` debe ser idéntico.

### Fase 2 — Reemplazo del engine greedy por CP-SAT

**Nuevo archivo:** `backend/app/domain/calendars/cp_model.py`

```python
class OrToolsEngine:
    def solve(self, ctx: GenerationContext) -> GenerationSummary:
        # 1. Construir modelo CP-SAT
        # 2. Por cada regla: llamar add_to_cp_model()
        # 3. Definir objetivo: minimizar suma ponderada de violaciones soft
        # 4. solver.Solve()
        # 5. Extraer asignaciones del solver
        # 6. Construir GenerationSummary (misma estructura que hoy)
```

**Variables del modelo:**
- `x[doctor, day, area]` → booleana: 1 si el doctor ocupa ese slot

**Hard constraints (obligatorias):**
1. Cada slot (día + área) tiene exactamente 1 doctor o queda como gap
2. Un médico no puede estar en dos slots el mismo día
3. Médico inactivo o service_active=False → no se asigna
4. Área no permitida → no se asigna
5. Hard block activo → no se asigna
6. Sin disponibilidad → no se asigna
7. Límite mensual máximo respetado

**Soft constraints (objetivo a minimizar):**
1. Espaciado entre servicios (penalidad si <14d fuerte, <7d disponible)
2. Balance de carga mensual (minimizar varianza)
3. Rotación de áreas (favorecer cambio de área)
4. Target mensual (favorecer alcanzar target)
5. Prioridad post-misión

**Función objetivo:**
```
min ∑ (peso_regla × violación_regla_soft)
```

## Archivos afectados (cambio real)

| Archivo | Fase 1 | Fase 2 |
|---|---|---|
| `rules/` (8-10 nuevos) | ✅ Crear | Sin cambios |
| `scoring.py` | ✅ Refactor a wrapper | Sin cambios |
| `engine.py` | Sin cambios | ✅ Reemplazar por OrToolsEngine |
| `cp_model.py` (nuevo) | — | ✅ Crear |
| `generation_service.py` | Sin cambios | ✅ 1 línea: cambiar clase importada |
| `assignment_service.py` | Sin cambios | Sin cambios |
| `types.py` | Sin cambios | Posibles tipos nuevos |
| `pyproject.toml` | ✅ Añadir `ortools` | Sin cambios |

## Archivos que NO cambian (nunca)

```
API routes (calendars.py), Schemas, Frontend (React),
DB models, Migrations, Repository layer,
weeks.py, availability_rules.py, eligibility.py, catalogs.py
```

## Tests

### Fase 1 (deben seguir pasando)
- `test_scoring.py` — 7 tests (misma fórmula) ✅
- `test_engine.py` — 5 tests (engine no cambia) ✅
- **Requisito previo:** Arreglar JSONB en tests de integración para que `test_generation_service.py` y `test_assignment_service.py` puedan ejecutarse

### Fase 2 (nuevos + existentes)
- `test_cp_model.py` — Tests unitarios del solver CP-SAT
- `test_engine.py` — 5 tests se migran a la nueva interfaz (mismos escenarios)
- `test_generation_service.py` — Debe pasar igual (la interfaz no cambia)
- Tests de integración completos

## Dependencia

```
ortools>=9.10  # pip install ortools — librería Python, sin servidor
```

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| CP-SAT no encuentra solución factible | Penalizar gaps con peso altísimo en objetivo. Si aún así no hay solución, reportar gaps como hoy. |
| Performance en meses grandes (~90 slots, 50 médicos) | CP-SAT escala a miles de vars. Benchmark con datos reales. Timeout configurable. |
| Regresión en comportamiento existente | Fase 1 = refactor sin cambio. Fase 2 se valida contra los mismos tests. |
| Complejidad de modelar todas las reglas | Las reglas ya están desacopladas en Fase 1. Cada una implementa `add_to_cp_model()` independientemente. |

## Criterios de aceptación

1. Misma salida que el greedy para casos triviales (1 doctor, sin restricciones)
2. Mejor distribución de carga que greedy en escenarios multi-doctor
3. Sin violaciones de espaciado cuando hay candidatos alternativos
4. Todos los tests existentes pasan
5. Tiempo de solución < 30s para un mes completo con 50 médicos
