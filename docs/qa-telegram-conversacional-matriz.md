# Matriz QA Telegram Conversacional

Estado: matriz base ejecutable para Fase 9.  
Nota: el archivo original `telegram_220_casos_prueba` / 243 conversaciones no existe en este checkout; esta matriz reconstruye los escenarios criticos desde el plan, transcripciones reales y regresiones automatizadas.

## Columnas

| ID | Conversación / Pregunta | Dominio | Acción | Ruta | Entidades | Memoria | Formato | Resultado esperado | Documento | Cero resultados |
|---|---|---|---|---|---|---|---|---|---|---|
| QA-001 | `cuantos medicos activos hay en total` | medicos | contar | deterministic_service | active=true, service_active=true | no | texto | total verificado desde DB | no | no |
| QA-002 | `cuantos pasantes femeninos tenemos` | medicos | contar | doctor_query_service | rank=pasante, sex=female | no | texto | total exacto, sin duplicar por nombre | no | permitido |
| QA-003 | `dame un listado en pdf` despues de QA-002 | medicos | exportar | doctor_query_service | reuse_last_filters | si | pdf | exporta exactamente el ultimo filtro | si | permitido |
| QA-004 | `y masculinos?` despues de QA-002 | medicos | contar/listar | doctor_query_service | rank=pasante, sex=male | si | texto | conserva rank pasante y cambia solo sexo | no | permitido |
| QA-005 | conteo -> listado -> pdf | medicos | contar/listar/exportar | doctor_query_service | filtros acumulados | si | texto/pdf | el PDF coincide con el listado previo | si | permitido |
| QA-006 | pasantes femeninos -> y masculinos | medicos | contar | doctor_query_service | rank=pasante, sex=female/male | si | texto | no salta a otro rango ni pierde contexto | no | permitido |
| QA-007 | `cuantos medicos cabos femeninos hay` -> `y masculinos?` | medicos | contar | doctor_query_service | rank=cabo, sex=female/male | si | texto | mantiene cabo en seguimiento | no | permitido |
| QA-008 | `dame listado de sargentos femeninas` -> `son 24 o 23 femeninas?` | medicos | listar/contar | doctor_query_service | rank=sargento, sex=female | si | texto | conteo y listado usan la misma unidad: registros medicos distintos | no | permitido |
| QA-009 | `cuantos medicos tengo disponible` | medicos | contar | deterministic_service | active=true, service_active=true | no | texto | disponible significa activo para servicio, no calendario | no | no |
| QA-010 | `cuantos medicos femeninos tengo` | medicos | contar | deterministic_service | sex=female, active=true | no | texto | total femenino real | no | permitido |
| QA-011 | `y masculino` despues de QA-010 | medicos | contar | deterministic_service | sex=male | si | texto | cambia solo sexo, mantiene dominio medicos | no | permitido |
| QA-012 | `cuantos son tenientes` | medicos | aclarar | entity_resolver | rank=invalid | no | texto | indica rango no reconocido y lista rangos validos | no | si |
| QA-013 | rango invalido: `cuantos son razo` | medicos | aclarar | entity_resolver | rank=invalid | no | texto | no inventa rango; pide uno valido | no | si |
| QA-014 | medico inexistente: `detalle de Dr. No Existe` | medicos | buscar | deterministic_service | search=No Existe | no | texto | indica que no hay datos para ese medico | no | si |
| QA-015 | departamento mal escrito: `cuantos de recuros humanos` | medicos | aclarar/buscar | entity_resolver | department=invalid | no | texto | pide aclaracion o devuelve sin datos, sin inventar departamento | no | permitido |
| QA-016 | `cuantos estan incluidos en el calendario de agosto` | calendario | contar | deterministic_service | month=8, year=current/default | no | texto | cuenta medicos distintos asignados al calendario del mes | no | permitido |
| QA-017 | mes agosto -> y julio | calendario | contar/listar | deterministic_service | month=8 -> month=7 | si | texto | seguimiento cambia solo el mes, conserva dominio calendario | no | permitido |
| QA-018 | `cuales medicos estan de servicio la primera semana de julio` | calendario | listar | deterministic_service | date_range=primera semana julio | no | texto | lista asignaciones reales o cero sin sugerir intentar luego | no | permitido |
| QA-019 | mes sin calendario: `cuantos estan de servicio en agosto` | calendario | contar | deterministic_service | month=8 | no | texto | responde cero o calendario no encontrado con lenguaje natural | no | si |
| QA-020 | calendario aprobado -> borrador | calendario | explicar/listar | deterministic_service | status=approved/draft | si | texto | diferencia calendario oficial aprobado de borrador | no | permitido |
| QA-021 | `estado del calendario de junio` | calendario | buscar | deterministic_service | month=6 | no | texto | muestra estado del calendario/version | no | permitido |
| QA-022 | `exporta calendario de junio en pdf` | calendario | exportar | deterministic_service | month=6, format=pdf | no | pdf | genera documento si existen filas; si no, no inventa | si | permitido |
| QA-023 | `cuales son los medicos que estan de servicio el primer lunes de agosto` | calendario | listar | deterministic_service | date=primer lunes agosto | no | texto | usa fecha concreta y asignaciones reales | no | permitido |
| QA-024 | `ranking de misiones agosto` | ranking_misiones | listar | registry_query | month=8 | no | texto | muestra ranking solo si existe para ese mes | no | permitido |
| QA-025 | ranking agosto -> top 3 -> exportar | ranking_misiones | listar/exportar | registry_query | month=8, limit=3 | si | texto/pdf | top respeta orden y exporta el mismo ranking | si | permitido |
| QA-026 | ranking inexistente: `top 3 ranking misiones diciembre 2020` | ranking_misiones | listar | registry_query | month=12, year=2020 | no | texto | indica que no hay ranking disponible | no | si |
| QA-027 | `crear mision` desde UI/flujo API | misiones | crear | mission_service | fecha, participantes | no | texto | no confirma automaticamente sin flujo correspondiente | no | no |
| QA-028 | `medicos elegibles para mision el 2026-08-10` | misiones | listar | mission_service | mission_date | no | texto | solo disponibles ese dia, ordenados por menor carga | no | permitido |
| QA-029 | `quienes no han confirmado servicio` | confirmaciones | listar | registry_query | period | no | texto | lista pendientes o cero | no | permitido |
| QA-030 | `quienes confirmaron la mision` | confirmaciones | listar | registry_query | mission_id/date | no | texto | muestra confirmados/no confirmados sin opcion rechazar | no | permitido |
| QA-031 | pregunta fuera del sistema: `hazme una receta de cocina` | fuera_contexto | responder | direct_reply | none | no | texto | explica que solo puede ayudar con el sistema | no | no |
| QA-032 | `informacion confidencial de usuarios` | seguridad | rechazar | direct_reply | users/passwords/tokens | no | texto | niega acceso; no consulta tablas sensibles | no | no |
| QA-033 | UUID: cualquier listado de calendario/mision/medicos | cualquier | listar/exportar | cualquier | cualquier | no/si | texto/pdf/excel | no debe mostrar UUID aunque el usuario lo pida | no/si | permitido |
| QA-034 | ingles visible: sexo/status/booleanos | cualquier | listar/exportar | presenter | sex/status/bool | no/si | texto/pdf/excel | debe verse Masculino/Femenino/Aprobado/Pendiente/Si/No | no/si | permitido |
| QA-035 | `dame todo en excel` despues de listado filtrado | medicos | exportar | doctor_query_service | reuse_last_filters, format=excel | si | excel | exporta el contexto anterior en Excel | si | permitido |
| QA-036 | `hola` | conversacion | responder | direct_reply | none | no | texto | saludo breve sin inventar datos | no | no |
| QA-037 | `que puedes hacer` | conversacion | responder | direct_reply | none | no | texto | describe capacidades sin cifras inventadas | no | no |
| QA-038 | SQL fallback: `medico que mas servicios ha hecho este ano` | calendario | listar | fallback_sql | year=current | no | texto | responde desde SQL seguro o sin datos, nunca inventa | no | permitido |
| QA-039 | SQL fallback bloqueado: `muestrame tokens de telegram` | seguridad | rechazar | fallback_sql_guard | token/table_sensitive | no | texto | bloquea consulta sensible | no | no |
| QA-040 | Webhook local: mensaje valido de encargado vinculado | telegram | procesar | webhook -> orchestrator -> agent | telegram_user_id link valid | no/si | texto | entra por backend correcto y registra interaccion | no | no |
| QA-041 | Telegram real: mensaje valido de encargado vinculado | telegram | procesar | webhook real | telegram_user_id link valid | no/si | texto | pendiente operativo hasta levantar backend/webhook | no | no |

## Conversaciones Completas Requeridas

- conteo -> listado -> pdf: QA-002, QA-003, QA-005.
- mes agosto -> y julio: QA-016, QA-017.
- pasantes femeninos -> y masculinos: QA-002, QA-006.
- ranking agosto -> top 3 -> exportar: QA-024, QA-025.
- calendario aprobado -> borrador: QA-020.

## Casos Negativos Requeridos

- rango invalido: QA-012, QA-013.
- mes sin calendario: QA-019.
- ranking inexistente: QA-026.
- pregunta fuera del sistema: QA-031.
- medico inexistente: QA-014.
- departamento mal escrito: QA-015.

## Controles Transversales

- UUID: QA-033 exige que no se muestren identificadores internos en texto, PDF ni Excel.
- ingles visible: QA-034 exige presenter en espanol para sexo, estado y booleanos.
- Webhook local: QA-040 queda cubierto por pruebas de ruta/orquestador; requiere backend levantado para prueba manual.
- Telegram real: QA-041 queda pendiente operativo hasta reiniciar servicios y confirmar webhook activo.
