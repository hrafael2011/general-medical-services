# Plan Definitivo Del Bot Conversacional

Fecha: 2026-05-16

## Objetivo

Convertir el bot de Telegram en un asistente operacional confiable del sistema de turnos medicos.

El bot debe poder interpretar preguntas dentro del contexto del sistema y la base de datos, consultar informacion real, mantener continuidad conversacional solo cuando corresponda, generar reportes correctos y evitar respuestas inventadas.

Si la informacion existe en la base de datos y pertenece al contexto del sistema, debe responder. Si no existe o no puede consultarla con seguridad, debe decirlo de forma clara y natural.

## Principios De Implementacion

- No usar LangChain por ahora.
- No reescribir toda la arquitectura.
- No permitir que el LLM sea la fuente de verdad.
- La verdad debe salir de servicios deterministas, SQL validado o consultas seguras.
- El LLM puede ayudar a interpretar lenguaje y redactar, pero no inventar datos.
- Las preguntas frecuentes deben resolverse por rutas deterministicas.
- El fallback NL-to-SQL debe ser seguro, limitado y semantico.
- La memoria no debe contaminar preguntas nuevas.
- Ninguna respuesta debe mostrar UUID aunque el usuario lo pida.
- Cada fase debe terminar con pruebas y un resumen corto antes de continuar.

## Estado Actual Diagnosticado

### Lo Que Esta Bien

- Existe separacion entre agente, router, registry, resolvedor de entidades y servicios.
- Hay protecciones iniciales contra alucinacion.
- El SQL de fallback esta limitado a consultas `SELECT`.
- Hay rutas deterministicas para varios casos de medicos y calendario.
- Hay persistencia de memoria conversacional.
- Hay auditoria de interacciones de Telegram.
- Ya existen pruebas conversacionales y casos documentados.

### Lo Que Esta Mal

- La memoria actual puede contaminar preguntas nuevas con filtros viejos.
- El ruteo de intencion puede mandar preguntas al dominio equivocado.
- Algunas consultas de ranking caen como calendario.
- Algunas consultas de calendario caen como medicos/departamento.
- El fallback NL-to-SQL no conoce suficientemente las reglas de negocio.
- Algunas pruebas validan que el bot responda, pero no necesariamente que responda lo correcto.
- Puede haber desalineacion entre codigo implementado y backend activo si no se reinician servicios.

### Lo Que Hace Falta

Una capa de planificacion conversacional semantica que decida, antes de consultar:

- dominio
- accion
- entidades
- periodo
- formato
- si es pregunta nueva o seguimiento
- ruta segura de ejecucion
- nivel de confianza

## Flujo Objetivo

```text
mensaje del usuario
  -> normalizador
  -> resolvedor de entidades
  -> planner conversacional semantico
  -> memoria por dominio
  -> router seguro
  -> servicio deterministico | registry SQL | fallback NL-to-SQL seguro
  -> presenter en espanol
  -> respuesta Telegram o documento
  -> auditoria/observabilidad
```

## Checklist General

- [ ] El bot distingue pregunta nueva vs seguimiento.
- [ ] El bot separa memoria por dominio.
- [ ] El bot no arrastra filtros incompatibles.
- [ ] Ranking de misiones no cae en calendario.
- [ ] Calendario no cae en medicos por departamento.
- [ ] Exportaciones usan exactamente el ultimo resultado valido o filtros explicitos.
- [ ] Conteo y PDF devuelven cantidades consistentes.
- [ ] El fallback SQL respeta reglas de negocio.
- [ ] Las respuestas estan en espanol natural.
- [ ] No se muestran UUID.
- [ ] Telegram prueba el mismo codigo que esta en el repositorio.

## Fase 1: Contrato Semantico Del Sistema

### Objetivo

Centralizar el significado oficial de los terminos del negocio para que todas las capas interpreten igual.

### Tareas

- [x] Definir dominios oficiales:
  - `medicos`
  - `calendario`
  - `misiones`
  - `ranking_misiones`
  - `confirmaciones`
  - `reportes`
  - `auditoria`
- [x] Definir acciones oficiales:
  - `contar`
  - `listar`
  - `exportar`
  - `resumir`
  - `buscar`
  - `comparar`
  - `explicar`
- [x] Definir significados de negocio:
  - "disponibles" = medicos con `active = true` y `service_active = true`.
  - "activos para servicio" = medicos con `active = true` y `service_active = true`.
  - "inactivos para servicio" = medicos activos en sistema con `service_active = false`.
  - "incluidos en calendario" = medicos distintos con asignaciones en calendario del periodo.
  - "de servicio" = asignaciones reales en `calendar_assignments`.
  - "servicios del mes" = asignaciones del calendario del mes.
  - "calendario oficial" = calendario aprobado.
  - "calendario aprobado" = calendario y version aprobada.
  - "borrador" = calendario o version no aprobada.
  - "ranking de misiones" = ranking calculado para mes/ano.
  - "elegibles para mision" = medicos disponibles para esa fecha y sin conflicto activo.
- [x] Alinear el contrato semantico con prompts, rutas deterministicas y tests.
- [x] Documentar terminos ambiguos y su regla de prioridad.

### Criterio De Exito

Ninguna capa interpreta distinto terminos como "disponible", "servicio", "calendario", "ranking", "oficial" o "borrador".

### Resumen Al Cerrar Fase

Registrar en dos lineas que conceptos quedaron centralizados y que pruebas se ejecutaron.

## Fase 2: Normalizador Y Resolvedor De Entidades

### Objetivo

Extraer entidades confiables del mensaje antes de decidir la ruta.

### Tareas

- [x] Normalizar errores comunes:
  - `masuclino`
  - `masuculino`
  - `massulino`
  - `feminio`
  - `femenio`
  - `servico`
  - `serviicio`
  - `caledario`
  - `cauantos`
  - `cuanos`
  - `ensenansa`
- [x] Resolver sexo:
  - masculino
  - femenino
  - hombres
  - mujeres
  - ambos sexos cuando aplique.
- [x] Resolver rangos:
  - cabo
  - pasante
  - sargento
  - sargento mayor
  - contrata
- [x] Resolver departamentos sin falsos positivos.
- [x] Resolver areas de servicio.
- [x] Resolver meses, anos, semanas y fechas exactas.
- [x] Resolver formatos:
  - texto
  - PDF
  - Excel
- [x] Evitar que "primera semana" sea interpretado como departamento.
- [x] Validar entidades contra base de datos antes de usarlas.
- [ ] Si una entidad no existe, responder con opciones validas.

### Criterio De Exito

El bot extrae filtros correctos y no aplica entidades que el usuario no pidio.

### Resumen Al Cerrar Fase

Registrar en dos lineas las entidades reforzadas y los falsos positivos corregidos.

## Fase 3: Planner Conversacional Unico

### Objetivo

Crear una decision estructurada unica antes de ejecutar cualquier consulta.

### Estructura Objetivo

```text
ConversationPlan:
  domain
  action
  entities
  period
  output_format
  is_followup
  memory_policy
  route
  confidence
  clarification_question
```

### Tareas

- [x] Crear salida estructurada del planner.
- [x] Clasificar dominio antes de usar memoria.
- [x] Clasificar accion antes de ejecutar SQL.
- [x] Detectar si es pregunta nueva o seguimiento.
- [x] Definir politica de memoria:
  - `none`
  - `same_domain_only`
  - `reuse_last_filters`
  - `reuse_last_period`
  - `reuse_last_result_for_export`
- [x] Definir rutas:
  - `deterministic_service`
  - `registry_query`
  - `semantic_sql_fallback`
  - `direct_reply`
  - `clarification`
- [x] Aplicar prioridad:
  - ranking de misiones antes que calendario.
  - calendario antes que medicos cuando se habla de servicio/turnos/asignaciones.
  - medicos cuando se habla de rango, sexo, departamento o disponibilidad.
  - confirmaciones cuando se habla de recibido, pendientes o confirmacion.
  - auditoria cuando se habla de quien aprobo, cambios o historial.
- [x] Si la confianza es baja, pedir aclaracion.
- [x] Registrar el plan en auditoria de interaccion.

### Criterio De Exito

La pregunta cae en el dominio correcto antes de consultar datos.

### Resumen Al Cerrar Fase

Registrar en dos lineas que el planner decide dominio/accion/ruta y que casos criticos pasan.

## Fase 4: Memoria Por Dominio

### Objetivo

Mantener contexto util sin contaminar preguntas nuevas.

### Tareas

- [x] Separar memoria por dominio:
  - `last_medicos_context`
  - `last_calendario_context`
  - `last_misiones_context`
  - `last_ranking_context`
  - `last_reporte_context`
- [x] Guardar filtros de medicos solo dentro de dominio medicos.
- [x] Guardar periodo de calendario solo dentro de dominio calendario.
- [x] Guardar periodo de ranking solo dentro de dominio ranking.
- [x] Guardar ultimo resultado exportable con su dominio y filtros.
- [x] Usar memoria solo en follow-ups reales:
  - "y masculinos?"
  - "y femeninos?"
  - "y julio?"
  - "exportalo en PDF"
  - "dame el listado"
  - "ahora en Excel"
- [x] No usar memoria cuando el mensaje trae una pregunta completa nueva.
- [x] No mezclar filtros entre dominios.
- [x] Limpiar filtros incompatibles al cambiar de dominio.
- [x] Agregar TTL y razon de expiracion si aplica.

### Criterio De Exito

Un filtro viejo de departamento, sexo, rango o periodo no afecta una consulta nueva.

### Resumen Al Cerrar Fase

Registrar en dos lineas que la memoria queda aislada por dominio y que exportaciones contextuales funcionan.

## Fase 5: Rutas Deterministicas Criticas

### Objetivo

Resolver lo frecuente sin depender del LLM ni de SQL libre.

### Tareas Medicos

- [x] Contar medicos activos para servicio.
- [x] Contar medicos inactivos para servicio.
- [x] Listar medicos activos.
- [x] Listar medicos inactivos.
- [x] Contar por sexo.
- [x] Listar por sexo.
- [x] Contar por rango.
- [x] Listar por rango.
- [x] Contar por rango + sexo.
- [x] Listar por rango + sexo.
- [x] Contar por departamento.
- [x] Listar por departamento.
- [x] Exportar en PDF/Excel con los mismos filtros.

### Tareas Calendario

- [x] Contar medicos incluidos en calendario de un mes.
- [x] Listar medicos incluidos en calendario de un mes.
- [x] Consultar servicios por fecha exacta.
- [x] Consultar servicios por semana.
- [x] Consultar servicios por mes.
- [x] Consultar medico con mas servicios en un periodo.
- [x] Consultar carga por medico en un periodo.
- [x] Distinguir calendario aprobado de borrador.
- [x] Si solo hay borrador, decirlo sin mezclarlo con oficial.

### Tareas Misiones Y Ranking

- [x] Consultar ranking de misiones por mes.
- [x] Consultar top N del ranking.
- [ ] Consultar elegibles por fecha de mision.
- [ ] Excluir medicos con servicios activos en la fecha.
- [ ] Listar misiones por mes.
- [ ] Listar participantes de una mision.
- [x] Consultar pendientes de confirmacion.

### Tareas Transversales

- [x] Quitar UUID de todas las respuestas.
- [x] Traducir valores tecnicos a espanol.
- [x] Unificar conteo/listado/exportacion.
- [x] Si el listado tiene N, el PDF debe tener N.

### Criterio De Exito

Las preguntas frecuentes y operativas se resuelven por servicios controlados y devuelven resultados consistentes.

### Resumen Al Cerrar Fase

Registrar en dos lineas que rutas criticas estan cubiertas y que conteo/listado/exportacion coinciden.

## Fase 6: Fallback SQL Seguro Y Semantico

### Objetivo

Responder preguntas no previstas sin romper seguridad ni reglas de negocio.

### Tareas

- [x] Mantener fallback NL-to-SQL solo como respaldo.
- [x] Crear capa semantica permitida para el LLM.
- [x] Exponer al fallback solo conceptos seguros:
  - medicos visibles
  - calendarios oficiales
  - asignaciones oficiales
  - ranking de misiones
  - misiones
  - confirmaciones operativas
  - auditoria permitida
- [x] No exponer:
  - usuarios
  - passwords
  - tokens
  - vinculos Telegram
  - tablas internas sensibles
- [x] Obligar `SELECT`.
- [x] Bloquear DML/DDL.
- [x] Aplicar `LIMIT`.
- [x] Bloquear columnas UUID en salida.
- [x] Aplicar reglas obligatorias:
  - medicos visibles usan `active = true`.
  - disponibles usan `active = true` y `service_active = true`.
  - calendario oficial usa aprobado.
  - soft delete debe respetarse.
- [x] Si el SQL falla, responder sin inventar.
- [x] Si el SQL devuelve cero, responder cero con lenguaje natural.

### Criterio De Exito

El fallback puede responder preguntas nuevas, pero siempre dentro del contrato del sistema.

### Resumen Al Cerrar Fase

Registrar en dos lineas que el fallback queda limitado por contrato semantico y seguridad.

## Fase 7: Respuestas Naturales Controladas

### Objetivo

Responder como asistente, pero con datos verificados.

### Tareas

- [x] Separar datos de redaccion.
- [x] Usar servicios/SQL como fuente de verdad.
- [ ] Usar LLM solo para convertir resultados en lenguaje natural.
- [x] Crear presenter en espanol para valores:
  - `male` -> `Masculino`
  - `female` -> `Femenino`
  - `draft` -> `Borrador`
  - `approved` -> `Aprobado`
  - `pending` -> `Pendiente`
  - `confirmed` -> `Confirmado`
  - `true` -> `Si`
  - `false` -> `No`
- [x] Crear respuestas naturales para cero resultados.
- [ ] Crear respuestas naturales para calendario no aprobado.
- [ ] Crear respuestas naturales para datos inexistentes.
- [x] Evitar respuestas largas innecesarias.
- [ ] Evitar pedir al usuario que intente luego cuando el problema es dato inexistente.
- [x] Mantener tono profesional y claro.

### Criterio De Exito

El usuario recibe respuestas naturales, breves, verificadas y sin informacion inventada.

### Resumen Al Cerrar Fase

Registrar en dos lineas que las respuestas quedaron en espanol natural y basadas en datos.

## Fase 8: Seguridad Y Telegram

### Objetivo

Asegurar que Telegram use el codigo correcto y respete roles/seguridad.

### Tareas

- [x] Verificar que solo `admin` y `encargado` puedan vincularse al asistente interno.
- [x] Revisar vinculos antiguos con roles invalidos.
- [x] Definir conducta para vinculos antiguos invalidos.
- [x] Separar flujo interno de encargado/admin del flujo de confirmacion de medicos.
- [x] Verificar webhook activo a nivel de ruta y pruebas.
- [ ] Verificar backend activo.
- [ ] Verificar que backend activo tenga el codigo actualizado.
- [x] Revisar rate limit para no perder mensajes silenciosamente.
- [x] Registrar mensajes descartados por rate limit.
- [x] Verificar envio de documentos PDF/Excel.

### Criterio De Exito

Las pruebas reales por Telegram pasan por el backend correcto y respetan seguridad.

### Resumen Al Cerrar Fase

Registrar en dos lineas que Telegram queda alineado con roles, webhook y backend activo.

## Fase 9: QA Conversacional

### Objetivo

Validar conversaciones reales, no solo preguntas aisladas.

### Tareas

- [x] Convertir los 243 casos en matriz de QA.
- [x] Para cada caso definir:
  - dominio esperado
  - accion esperada
  - ruta esperada
  - entidades esperadas
  - memoria esperada si/no
  - formato esperado
  - resultado esperado cuando sea determinista
  - si debe generar documento
  - si debe devolver cero resultados
- [x] Agregar conversaciones completas:
  - conteo -> listado -> PDF
  - mes agosto -> y julio
  - pasantes femeninos -> y masculinos
  - ranking agosto -> top 3 -> exportar
  - calendario aprobado -> borrador
- [x] Probar casos negativos:
  - rango invalido
  - mes sin calendario
  - ranking inexistente
  - pregunta fuera del sistema
  - medico inexistente
  - departamento mal escrito
- [x] Verificar que no haya UUID.
- [x] Verificar que no haya ingles en respuestas visibles.
- [x] Probar por webhook local a nivel de ruta/orquestador automatizado.
- [ ] Probar por Telegram real.

### Criterio De Exito

El bot pasa regresion conversacional antes de considerarse listo.

### Resumen Al Cerrar Fase

Registrar en dos lineas cantidad de casos probados, pasados, fallidos y riesgos.

## Fase 10: Observabilidad Y Cierre

### Objetivo

Poder explicar por que el bot respondio cada cosa.

### Tareas

- [x] Registrar por cada mensaje:
  - dominio detectado
  - accion detectada
  - ruta usada
  - entidades
  - periodo
  - si uso memoria
  - politica de memoria
  - query_type
  - herramienta usada
  - cantidad de resultados
  - si genero documento
  - razon de fallback
- [x] Registrar fallos de LLM.
- [x] Registrar fallos de SQL.
- [x] Registrar fallos de validacion.
- [x] Crear resumen QA final.
- [x] Listar deudas tecnicas restantes.
- [ ] Reiniciar servicios.
- [ ] Probar Telegram real.
- [ ] Confirmar que frontend no fue afectado.

### Criterio De Exito

Si una respuesta falla, se puede saber exactamente si fallo por intencion, entidad, memoria, ruta, SQL, datos o despliegue.

### Resumen Al Cerrar Fase

Registrar en dos lineas el estado final y las deudas tecnicas restantes.

## Orden Recomendado De Implementacion

1. Fase 1: Contrato Semantico Del Sistema
2. Fase 2: Normalizador Y Resolvedor De Entidades
3. Fase 3: Planner Conversacional Unico
4. Fase 4: Memoria Por Dominio
5. Fase 5: Rutas Deterministicas Criticas
6. Fase 7: Respuestas Naturales Controladas
7. Fase 6: Fallback SQL Seguro Y Semantico
8. Fase 8: Seguridad Y Telegram
9. Fase 9: QA Conversacional
10. Fase 10: Observabilidad Y Cierre

## Control De Avance

### Fase 1

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 2

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 3

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 4

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 5

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 6

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 7

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 8

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 9

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

### Fase 10

- [ ] Pendiente
- [ ] En progreso
- [x] Completada

## Deudas Tecnicas A Vigilar Durante La Implementacion

- [ ] Memoria persistida con estructura antigua puede contaminar pruebas reales.
- [x] Vinculos antiguos de Telegram con roles no permitidos pueden seguir activos.
- [x] El backend activo puede quedar desalineado si no se reinicia despues de cambios.
- [ ] Algunas consultas del registry pueden no respetar estado aprobado o soft delete.
- [ ] El fallback NL-to-SQL necesita contrato semantico para evitar consultas conceptualmente incorrectas.
- [ ] Las pruebas de 243 casos deben validar resultado correcto, no solo respuesta sin error.
- [ ] Los presenters deben evitar ingles y columnas tecnicas.
- [ ] Exportaciones deben compartir exactamente la misma fuente que respuestas en texto.

## Regla Para El Implementador

No avanzar a la siguiente fase sin:

- ejecutar pruebas relevantes,
- dar resumen corto de la fase,
- registrar deudas tecnicas encontradas,
- recibir autorizacion del usuario.
