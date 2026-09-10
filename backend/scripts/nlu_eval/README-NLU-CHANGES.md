# Cambios NLU — desambiguación de colisiones

Rama: `feature/nlu-desambiguacion`

## Resumen ejecutivo

El bot elige la herramienta equivocada cuando dos tools compiten por la misma
frase. La causa: el prompt solo decía **cuándo usar** cada tool, nunca **cuándo
no**. Se agregaron 7 bloques de desambiguación con discriminador explícito, se
agruparon las 22 tools por dominio, y se unificó el parámetro de área.

**Además se corrigió un bug que el plan original no contemplaba** y que habría
roto el filtro por área en silencio (ver «Cambio 2»).

## Resultados medidos

Corrido contra la API real de DeepSeek (2026-09-10):

| Métrica | Resultado |
|---|---|
| Tool accuracy | **35/35 (100%)** |
| Params correctos | **35/35 (100%)** |
| Cobertura por colisión | 5/5 en las 7 |

Dos corridas consecutivas dieron resultados idénticos (temperatura 0).

### Cómo se llegó ahí

1. **Primera corrida: 34/35 (97.1%)** — un fallo real y tres falsos.
2. **Un fallo real (C7-02):** «Genera el PDF del calendario de septiembre» iba a
   `reply/out_of_scope`. Causa: la regla de escritura decía literalmente
   «generar calendario», y la frase contenía «Genera» + «calendario». Se
   desambigüó: generar el calendario (crear turnos) es escritura, pero enviar
   un reporte/PDF es lectura → `generate_report`.
3. **Tres falsos positivos, dos eran bugs de mi harness:** `@current_month` /
   `@current_year` se comparaban contra la *clave* en vez del *valor*, así que el
   centinela nunca se resolvía. El modelo había respondido `9` y `2026`
   correctamente. El tercero (C6-05) pedía `status="open"` cuando la tool ya
   filtra por `open` al omitirlo.

### Advertencias sobre este número

- **Los 35 casos los escribí yo.** Miden que el prompt maneje las colisiones que
  ya conozco, no que sea correcto ante frases que nadie previó. Un 100% aquí no
  es un 100% en producción.
- **El arreglo de C7-02 se hizo después de ver el fallo.** Es una inconsistencia
  real del prompt (no un ajuste cosmético para pasar el test), pero conviene
  saberlo al leer el 100%.
- **Tamaño de muestra:** 35 casos. Un fallo mueve la aguja ~3 puntos.

## Cambios

### 1. `tool_registry.py`

| Qué | Dónde |
|---|---|
| `_SERVICE_AREA_ENUM` / `_SERVICE_AREA_HINT` como contrato único de área | [:75-76](../../app/application/telegram/tool_registry.py#L75-L76) |
| `list_doctors.area` → `service_area` **con enum** (antes no tenía) | [:107](../../app/application/telegram/tool_registry.py#L107) |
| `calendar_assignments.service_area` — se le agregó el enum | [:233](../../app/application/telegram/tool_registry.py#L233) |
| `slot_recommendation` y `slot_explanation` usan la constante compartida | [:271](../../app/application/telegram/tool_registry.py#L271), [:291](../../app/application/telegram/tool_registry.py#L291) |
| `DOMAIN_GROUPS` — 9 dominios; `ALL_TOOLS` se **deriva** de ahí | [:527-542](../../app/application/telegram/tool_registry.py#L527-L542) |
| `build_tools_prompt()` agrupa por dominio en vez de aplanar 22 tools | [:563](../../app/application/telegram/tool_registry.py#L563) |

`ALL_TOOLS` ahora se deriva de `DOMAIN_GROUPS` para que no exista una segunda
lista que se pueda desincronizar. El orden resultante es idéntico al anterior.

### 2. `tool_handlers.py` — el bug silencioso ⚠️

`handle_list_doctors` leía `params["area"]`, pero el catálogo expone
`service_area`. El dispatcher usa `**params` sin validar claves, así que el
`service_area` se **descartaba sin error** y la consulta devolvía TODOS los
médicos en vez de los del área pedida. Corregido en
[:181-182](../../app/application/telegram/tool_handlers.py#L181-L182).

El plan original solo listaba `tool_registry.py` e `intent_classifier.py`: sin
este cambio, renombrar el parámetro rompía el filtro en silencio.

### 3. `intent_classifier.py`

| Qué | Dónde |
|---|---|
| **Fecha de hoy** inyectada al prompt (antes no existía) | [:59](../../app/application/telegram/intent_classifier.py#L59), [:198-199](../../app/application/telegram/intent_classifier.py#L198-L199) |
| Bloque `DESAMBIGUACIÓN DE COLISIONES CONOCIDAS` — 7 colisiones, 62 líneas | [:104](../../app/application/telegram/intent_classifier.py#L104) |
| Regla de params: `area` → `service_area` | [:80](../../app/application/telegram/intent_classifier.py#L80) |

**La fecha de hoy fue una adición no pedida.** Las colisiones 2 y 4 usan «hoy»,
«mañana», «el 5» — y `doctors_available_on` / `slot_recommendation` exigen una
fecha exacta. Sin la fecha en el prompt, el modelo solo podía inventarla, que es
justo lo que el prompt prohíbe.

### 4. Tests nuevos (4)

| Test | Qué protege |
|---|---|
| `test_list_doctors_filters_by_service_area` | El bug del handler: un `service_area` debe filtrar de verdad |
| `test_all_area_params_share_one_contract` | Que las 4 tools de área no vuelvan a divergir |
| `test_prompt_renders_every_tool_under_a_domain_header` | Que agrupar no pierda ni duplique tools |
| `test_system_prompt_includes_today_for_relative_dates` | Que «mañana» siga siendo resoluble |

Los cuatro se vieron fallar antes de implementar (TDD), y se verificó que
`test_all_area_params_share_one_contract` falla con el mensaje correcto contra
el código previo.

## Lo que se descartó del plan original

1. **`"Confianza: 0.95"` hardcodeado** por colisión — habría enseñado al modelo a
   emitir siempre 0.95, destruyendo la señal de `confidence` / `needs_clarification`.
2. **Las cajas ASCII de ~180 líneas** — se hizo una versión compacta de 62 líneas.
   Más reglas no es mejor: diluyen la atención. El prompt completo quedó en 285
   líneas / 15.4 KB por mensaje.
3. **La promesa de 100% de accuracy** — no es medible ni honesta de antemano.
4. **El alcance de 3 archivos** — faltaba `tool_handlers.py`.

## Cómo evaluar

```bash
# Todos los casos
python backend/scripts/nlu_eval/eval_harness.py

# Una colisión (1-7)
python backend/scripts/nlu_eval/eval_harness.py --only 4

# Detalle caso por caso
python backend/scripts/nlu_eval/eval_harness.py --verbose

# Umbral de salida (default 0.95)
python backend/scripts/nlu_eval/eval_harness.py --min-tool-accuracy 0.90
```

Salida: accuracy de tool, accuracy de params, detalle de fallos, matriz de
confusión y cobertura por colisión.

**Requiere `DEEPSEEK_API_KEY` válida.** El harness hace un *preflight*: si la
API rechaza la credencial, sale con código 3 y no mide nada.

### Medir antes vs después

El harness importa el código vivo. Para obtener la baseline:

```bash
git stash push backend/app/application/telegram/tool_registry.py \
                backend/app/application/telegram/intent_classifier.py \
                backend/app/application/telegram/tool_handlers.py
python backend/scripts/nlu_eval/eval_harness.py   # baseline
git stash pop
python backend/scripts/nlu_eval/eval_harness.py   # después
```

Nota: `eval_set.json` declara `service_area` en los params esperados, así que en
la baseline esos casos también fallan por nombre de parámetro — que es
exactamente lo que pasaba en producción.

> **La baseline no se midió en esta sesión** (la key llegó inválida primero y
> después se corrigió). El número de 100% es el estado *después*.

## Mantenimiento

⚠️ **Si se agrega un área en la tabla `service_areas`, hay que sumarla a
`_SERVICE_AREA_ENUM`** ([`tool_registry.py:75`](../../app/application/telegram/tool_registry.py#L75)).
El enum es un contrato estático del JSON Schema: protege contra nombres
inventados como «UCI» (que aparece en consultas reales y no existe), pero no se
auto-actualiza.

`docs/telegram-tools-prompt.md` es autogenerado. Tras tocar `tool_registry.py`:

```bash
python scripts/dump_tools_prompt.py
```

## Verificación

- Suite completa: **1181 passed**, 249 skipped, 1 xfailed — 0 regresiones
  (baseline: 1177 passed; los 4 nuevos son los tests agregados).
- Lint: 34 E501 vs 37 en baseline — 3 errores menos, ninguno nuevo.
- Eval: 35/35 tool + 35/35 params, estable en dos corridas consecutivas.
