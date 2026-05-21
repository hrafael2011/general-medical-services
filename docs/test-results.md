# Resultados de pruebas conversacionales en Telegram

**Rama:** `before-dev`
**Bot:** @? (encargado)
**Fecha inicio:** 2026-05-15

---

## Issues detectados

| # | Caso | Problema | Severidad |
|---|------|----------|-----------|
| I1 | #28, #29, #47, #48, #60 | "Sargento mayor" no filtra correctamente — muestra sargentos regulares en lugar de sargentos mayores. El resumen por rango (#40) sí distingue: Sargento Mayor | 4 vs Sargento | 21 | Alta |
| I2 | #67 | Pérdida de contexto multi-turno: "De esos, exportalo en PDF" devuelve datos irrelevantes (68 registros con UUIDs del sistema) en lugar de exportar los sargentos femeninos del turno anterior | Alta |
| I3 | #68 | Pérdida de contexto: "Ahora dame solo los masculinos" no retiene el filtro de rango del historial | Media |
| I4 | #65 | No responde la pregunta "Son 24 o 23 sargentos femeninos?" — solo lista resultados sin confirmar/negar el número | Baja |
| I5 | #76 | "Recurso Humanos" devuelve resumen de departamentos en vez del conteo específico | Media |
| I6 | #84, #88, #89 | Filtros compuestos no se aplican: "cabos en Recursos Humanos" ignora el departamento; "resumen por sexo/rango" no desglosa | Alta |
| I7 | #95, #96, #97 | No responden la pregunta específica (rango, sexo, departamento de Acosta Ramos) — solo listan las personas con datos fijos | Media |
| I8 | #98, #100, #106 | Pérdida de contexto: "Ese medico" no retiene a quién se refería, devuelve todos los médicos (80 registros) | Alta |
| I9 | #108, #109, #110 | No entiende "medicos duplicados / que se llamen igual": #109 devuelve conteo total (79) en vez de identificar duplicados | Media |
| I10 | #114, #115, #116, #117, #118, #119, #120, #121 | "Cual es el estado" / "Hay borrador" / "Cuantos calendarios" fallan via NL fallback — el router tiene datos (#111-113 devuelven bien) pero query_db no | Alta |
| I11 | #142, #143 | Contexto multi-turno perdido en calendarios: "Y el de agosto?" y "Y el de julio?" no retienen el tema anterior | Alta |
| I12 | #144, #145, #146, #147, #148 | Consultas por fecha específica ("primer lunes", "4 de julio") no encuentran datos vía query_db, mientras semana completa sí funciona (#137-141) | Alta |
| I13 | #151, #152 | "Cuantos servicios hay en julio/agosto?" devuelve 0, contradictorio con #135-136 que muestran asignaciones | Media |
| I14 | #122, #123 | Respuestas exponen UUIDs internos al usuario (ej: "7ea6f5f4-23c5-4cdf-80a6-e9468407c6e7") | Media |
| I15 | #161, #162, #163, #164, #165, #166, #167, #168, #169 | Consultas por área específica (Emergencia, Pista, UCI) y médicos con más/menos servicios en un mes no encuentran datos vía query_db | Alta |
| I16 | #175 | Expone UUIDs internos al mostrar "Quienes tienen menos de 3 servicios en julio?" | Media |
| I17 | #176, #177, #178, #179, #180 | Consultas complejas (distribución por área+rango/sexo, metas mensuales) no cubiertas — todas devuelven ambiguous sin datos | Alta |
| I18 | #182, #184, #185, #187, #188, #190, #191 | Consultas de misiones de agosto fallan vía query_db (sin datos) | Media |
| I19 | #181, #183, #189 | Ranking de misiones de julio muestra año/mes/posición sin nombres de médicos | Media |
| I20 | #192 | "No elegibles para misión" devuelve usuarios del sistema (Rafael cedano, Hendrick) y UUIDs | Alta |
| I21 | #195 | Pérdida de contexto: "Si el primero no puede, quien sigue?" no retiene el ranking anterior | Alta |
| I22 | #198 | Misiones expone UUIDs internos | Media |
| I23 | #210 | Resumen de misiones por mes devuelve datos crudos sin formato | Baja |
| I24 | #218 | "Quien aprobo el calendario de julio?" — único ❌ de toda la suite, fallback también falla | Alta |
| I25 | #213, #215, #216, #217 | Notificaciones/confirmaciones/auditoría no tienen query_types — devuelven ambiguous o listas genéricas | Media |

---

## Bloque 1: Médicos básicos + Errores de escritura (casos 1-20, 221-224)

| # | Consulta | ¿Pasó? | Respuesta del bot | Notas |
|---|----------|--------|-------------------|-------|
| 1 | Cuantos medicos tengo en total? | | | |
| 2 | Cuantos medicos tengo disponibles? | | | |
| 3 | Cuantos medicos estan activos para servicio? | | | |
| 4 | Cuantos medicos no estan activos para servicio? | | | |
| 5 | Dame la lista de medicos activos para servicio. | | | |
| 6 | Dame la lista de medicos inactivos para servicio. | | | |
| 7 | Exporta en PDF los medicos activos para servicio. | | | |
| 8 | Exporta en Excel los medicos activos para servicio. | | | |
| 9 | Cuantos medicos masculinos tengo? | | | |
| 10 | Cuantos medicos femeninos tengo? | | | |
| 11 | Dame la lista de medicos masculinos. | | | |
| 12 | Dame la lista de medicos femeninos. | | | |
| 13 | Exporta en PDF los medicos femeninos. | | | |
| 14 | Exporta en Excel los medicos masculinos. | | | |
| 15 | Cuantos hombres tengo disponibles? | | | |
| 16 | Cuantas mujeres tengo disponibles? | | | |
| 17 | Y masculinos? | | | |
| 18 | Y femeninos? | | | |
| 19 | Dame un resumen de medicos por sexo. | | | |
| 20 | Exporta el resumen de medicos por sexo en PDF. | | | |
| 221 | Busca al medico Acostta. | | | |
| 222 | Dame los medicos de Licencias Medicass. | | | |
| 223 | Cuantos medicos hay en Ensenansa? | | | |
| 224 | Cuantos sargento mayores femeninos tengo? | | | |

**Resultados:** ✅ / ❌ / ⚠️

---
## Bloque 1

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #1 | Cuantos medicos tengo en total? | ✅ | Resultado: total: 79 | query | 3588ms |
| #2 | Cuantos medicos tengo disponibles? | ✅ | Resultado: total: 79 | query | 1133ms |
| #3 | Cuantos medicos estan activos para servicio? | ✅ | Resultado: total: 79 | query | 1517ms |
| #4 | Cuantos medicos no estan activos para servicio? | ✅ | Resultado: total: 79 | query | 1690ms |
| #5 | Dame la lista de medicos activos para servicio. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina  | query | 1484ms |
| #6 | Dame la lista de medicos inactivos para servicio. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina  | query | 1741ms |
| #7 | Exporta en PDF los medicos activos para servicio. | ✅ | Aquí tienes el reporte solicitado. (79 registros, PDF). | export | 1958ms |
| #8 | Exporta en Excel los medicos activos para servicio. | ✅ | Aquí tienes el reporte solicitado. (79 registros, Excel). | export | 1624ms |
| #9 | Cuantos medicos masculinos tengo? | ✅ | Resultado: total: 53 | query | 19ms |
| #10 | Cuantos medicos femeninos tengo? | ✅ | Resultado: total: 26 | query | 12ms |
| #11 | Dame la lista de medicos masculinos. | ✅ | Se encontraron 53 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Alvarez Monegro Raym | query | 12ms |
| #12 | Dame la lista de medicos femeninos. | ✅ | Se encontraron 26 resultados. Los primeros: 1. Acosta Ramos, Miguelina Alexandra | Femenino | Sargento 2. Balbuena Reyes | query | 12ms |
| #13 | Exporta en PDF los medicos femeninos. | ✅ | Aquí tienes el reporte solicitado. (26 registros, PDF). | export | 65ms |
| #14 | Exporta en Excel los medicos masculinos. | ✅ | Aquí tienes el reporte solicitado. (53 registros, EXCEL). | export | 24ms |
| #15 | Cuantos hombres tengo disponibles? | ✅ | Resultado: total: 53 | query | 12ms |
| #16 | Cuantas mujeres tengo disponibles? | ✅ | Resultado: total: 26 | query | 9ms |
| #17 | Y masculinos? | ✅ | Se encontraron 53 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Alvarez Monegro Raym | query | 13ms |
| #18 | Y femeninos? | ✅ | Se encontraron 26 resultados. Los primeros: 1. Acosta Ramos, Miguelina Alexandra | Femenino | Sargento 2. Balbuena Reyes | query | 12ms |
| #19 | Dame un resumen de medicos por sexo. | ✅ | Se encontraron 2 resultados: 1. Femenino | 26 2. Masculino | 53 | query | 1552ms |
| #20 | Exporta el resumen de medicos por sexo en PDF. | ✅ | Aquí tienes el reporte solicitado. (2 registros, PDF). | export | 1349ms |
| #221 | Busca al medico Acostta. | ✅ | No se encontraron resultados. | query_db | 4083ms |
| #222 | Dame los medicos de Licencias Medicass. | ✅ | Resultado: name: Cuevas Cuevas Katherine | sex: Femenino | rank: Sargento | query | 15ms |
| #223 | Cuantos medicos hay en Ensenansa? | ✅ | Se encontraron 3 resultados: 1. Evaluaciones Médicas | 2 2. Enseñanza | 2 3. Licencias Médicas | 1 | query | 1416ms |
| #224 | Cuantos sargento mayores femeninos tengo? | ✅ | Resultado: total: 7 | query | 11ms |

## Bloque 2

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #21 | Cuantos pasantes tengo? | ✅ | Resultado: total: 15 | query | 56ms |
| #22 | Cuantos cabos tengo? | ✅ | Resultado: total: 22 | query | 7ms |
| #23 | Cuantos sargentos tengo? | ✅ | Resultado: total: 21 | query | 10ms |
| #24 | Cuantos sargentos mayores tengo? | ✅ | Resultado: total: 21 | query | 8ms |
| #25 | Cuantos contrata tengo? | ✅ | Resultado: total: 5 | query | 8ms |
| #26 | Dame la lista de pasantes. | ✅ | Se encontraron 15 resultados. Los primeros: 1. Amador Burgos, Cynhtia I. | Masculino | Pasante 2. Ana Suero Grano De Oro | query | 13ms |
| #27 | Dame la lista de cabos. | ✅ | Se encontraron 22 resultados. Los primeros: 1. Batistta Muñoz Lia Marie | Masculino | Cabo 2. Cabo Sheen De La Rosa Kair | query | 9ms |
| #28 | Dame la lista de sargentos. | ✅ | Se encontraron 21 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Acosta Ramos, Miguel | query | 9ms |
| #29 | Dame la lista de sargentos mayores. | ✅ | Se encontraron 21 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Acosta Ramos, Miguel | query | 8ms |
| #30 | Dame la lista de contrata. | ✅ | Se encontraron 5 resultados: 1. Amador Burgos, Cynhtia Isabel. | Masculino | Contrata 2. Galva Florentino, Adrihanny. |  | query | 7ms |
| #31 | Exporta en PDF los pasantes. | ✅ | Aquí tienes el reporte solicitado. (15 registros, PDF). | export | 202ms |
| #32 | Exporta en PDF los cabos. | ✅ | Aquí tienes el reporte solicitado. (22 registros, PDF). | export | 46ms |
| #33 | Exporta en PDF los sargentos. | ✅ | Aquí tienes el reporte solicitado. (21 registros, PDF). | export | 46ms |
| #34 | Exporta en Excel los sargentos mayores. | ✅ | Aquí tienes el reporte solicitado. (21 registros, EXCEL). | export | 134ms |
| #35 | Exporta en Excel los contrata. | ✅ | Aquí tienes el reporte solicitado. (5 registros, EXCEL). | export | 16ms |
| #36 | Cuantos medicos son cabo? | ✅ | Resultado: total: 22 | query | 7ms |
| #37 | Cuantos medicos son sargento? | ✅ | Resultado: total: 21 | query | 9ms |
| #38 | Cuantos medicos son pasante? | ✅ | Resultado: total: 15 | query | 8ms |
| #39 | Cuantos medicos son sargento mayor? | ✅ | Resultado: total: 21 | query | 8ms |
| #40 | Dame un resumen por rango. | ✅ | Se encontraron 5 resultados: 1. Cabo | 22 2. Sargento | 21 3. Pasante | 15 4. Contrata | 5 5. Sargento Mayor | 4 | query | 2366ms |

## Bloque 3

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #41 | Cuantos pasantes femeninos tengo? | ✅ | Resultado: total: 5 | query | 71ms |
| #42 | Cuantos pasantes masculinos tengo? | ✅ | Resultado: total: 10 | query | 12ms |
| #43 | Cuantos cabos femeninos tengo? | ✅ | Resultado: total: 9 | query | 17ms |
| #44 | Cuantos cabos masculinos tengo? | ✅ | Resultado: total: 13 | query | 20ms |
| #45 | Cuantos sargentos femeninos tengo? | ✅ | Resultado: total: 7 | query | 16ms |
| #46 | Cuantos sargentos masculinos tengo? | ✅ | Resultado: total: 14 | query | 17ms |
| #47 | Cuantos sargentos mayores femeninos tengo? | ✅ | Resultado: total: 7 | query | 10ms |
| #48 | Cuantos sargentos mayores masculinos tengo? | ✅ | Resultado: total: 14 | query | 15ms |
| #49 | Cuantos contrata femeninos tengo? | ✅ | Resultado: total: 0 | query | 10ms |
| #50 | Cuantos contrata masculinos tengo? | ✅ | Resultado: total: 5 | query | 12ms |
| #51 | Dame la lista de pasantes femeninos. | ✅ | Se encontraron 5 resultados: 1. Bido Ruiz Paola | Femenino | Pasante 2. Castillo Noelia | Femenino | Pasante 3. Contrera | query | 16ms |
| #52 | Dame la lista de pasantes masculinos. | ✅ | Se encontraron 10 resultados. Los primeros: 1. Amador Burgos, Cynhtia I. | Masculino | Pasante 2. Ana Suero Grano De Oro | query | 18ms |
| #53 | Dame la lista de cabos femeninos. | ✅ | Se encontraron 9 resultados. Los primeros: 1. Cabo Sheen De La Rosa Kaira | Femenino | Cabo 2. Calzado De Jesus Greily | | query | 18ms |
| #54 | Dame la lista de cabos masculinos. | ✅ | Se encontraron 13 resultados. Los primeros: 1. Batistta Muñoz Lia Marie | Masculino | Cabo 2. Cruz Bencosme Maria F | Ma | query | 14ms |
| #55 | Dame la lista de sargentos femeninos. | ✅ | Se encontraron 7 resultados. Los primeros: 1. Acosta Ramos, Miguelina Alexandra | Femenino | Sargento 2. Balbuena Reyes, | query | 13ms |
| #56 | Dame la lista de sargentos masculinos. | ✅ | Se encontraron 14 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Alvarez Monegro Raym | query | 17ms |
| #57 | Exporta en PDF los pasantes femeninos. | ✅ | Aquí tienes el reporte solicitado. (5 registros, PDF). | export | 345ms |
| #58 | Exporta en PDF los cabos masculinos. | ✅ | Aquí tienes el reporte solicitado. (13 registros, PDF). | export | 40ms |
| #59 | Exporta en Excel los sargentos femeninos. | ✅ | Aquí tienes el reporte solicitado. (7 registros, EXCEL). | export | 167ms |
| #60 | Exporta en PDF los sargentos mayores masculinos. | ✅ | Aquí tienes el reporte solicitado. (14 registros, PDF). | export | 53ms |
| #61 | Cuantos masculino y femenino tienen rango pasante? | ✅ | Se encontraron 2 resultados: 1. Femenino | 5 2. Masculino | 10 | query | 20ms |
| #62 | Cuantos hombres y mujeres son cabo? | ✅ | Se encontraron 2 resultados: 1. Femenino | 9 2. Masculino | 13 | query | 22ms |
| #63 | Dame el desglose por sexo de los sargentos. | ✅ | Se encontraron 21 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Acosta Ramos, Miguel | query | 133ms |
| #64 | Exporta el desglose por sexo de los cabos. | ✅ | Aquí tienes el reporte solicitado. (22 registros, PDF). | export | 129ms |
| #65 | Son 24 o 23 sargentos femeninos? | ✅ | Se encontraron 7 resultados. Los primeros: 1. Acosta Ramos, Miguelina Alexandra | Femenino | Sargento 2. Balbuena Reyes, | query | 25ms |
| #66 | De esos sargentos femeninos, dame el listado. | ✅ | Se encontraron 7 resultados. Los primeros: 1. Acosta Ramos, Miguelina Alexandra | Femenino | Sargento 2. Balbuena Reyes, | query | 25ms |
| #67 | De esos, exportalo en PDF. | ✅ | Se encontraron 68 resultados. Los primeros: 1. cd98fa06-d87a-4e28-b0b2-98c5e844ee83 | Rafael cedano | male 2. b2e1568b-3 | query_db | 5976ms |
| #68 | Ahora dame solo los masculinos. | ✅ | Se encontraron 53 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Alvarez Monegro Raym | query | 36ms |
| #69 | Exporta esos masculinos en Excel. | ✅ | Aquí tienes el reporte solicitado. (53 registros, EXCEL). | export | 88ms |
| #70 | Cuantos cabos massulino tengo? | ✅ | Resultado: total: 13 | query | 13ms |

## Bloque 4

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #71 | Cuantos medicos hay por departamento? | ✅ | Se encontraron 3 resultados: 1. Evaluaciones Médicas | 2 2. Enseñanza | 2 3. Licencias Médicas | 1 | query | 3401ms |
| #72 | Cuantos medicos hay en Licencias Medicas? | ✅ | Resultado: total: 1 | query | 18ms |
| #73 | Cuantos medicos hay en Ensenanza? | ✅ | Resultado: total: 2 | query | 16ms |
| #74 | Cuantos medicos hay en Evaluaciones Medicas? | ✅ | Resultado: total: 2 | query | 13ms |
| #75 | Cuantos medicos hay en Subdireccion? | ✅ | Resultado: total: 0 | query | 15ms |
| #76 | Cuantos medicos hay en Recurso Humanos? | ✅ | Se encontraron 3 resultados: 1. Evaluaciones Médicas | 2 2. Enseñanza | 2 3. Licencias Médicas | 1 | query | 1197ms |
| #77 | Dame la lista de medicos de Licencias Medicas. | ✅ | Resultado: name: Cuevas Cuevas Katherine | sex: Femenino | rank: Sargento | query | 27ms |
| #78 | Dame la lista de medicos de Ensenanza. | ✅ | Se encontraron 2 resultados: 1. Balbuena Reyes, Luisa Manuela | Femenino | Sargento 2. Batistta Muñoz Lia Marie | Mascul | query | 20ms |
| #79 | Dame la lista de medicos de Evaluaciones Medicas. | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Sargento 2. Acosta Ramos, Miguelina Alexandra | | query | 21ms |
| #80 | Dame la lista de medicos de Subdireccion. | ✅ | No se encontraron resultados. | query | 25ms |
| #81 | Dame la lista de medicos de Recurso Humanos. | ✅ | Se encontraron 5 resultados: 1. Amador Burgos, Cynhtia Isabel. | Masculino | Contrata 2. Payero Guzman, Jennifer. | Masc | query | 1748ms |
| #82 | Exporta en PDF los medicos de Licencias Medicas. | ✅ | Aquí tienes el reporte solicitado. (1 registros, PDF). | export | 226ms |
| #83 | Exporta en Excel los medicos de Ensenanza. | ✅ | Aquí tienes el reporte solicitado. (2 registros, EXCEL). | export | 269ms |
| #84 | Cuantos cabos hay en Recurso Humanos? | ✅ | Resultado: total: 22 | query | 12ms |
| #85 | Cuantos sargentos femeninos hay en Evaluaciones Medicas? | ✅ | Resultado: total: 1 | query | 14ms |
| #86 | Dame los pasantes masculinos de Subdireccion. | ✅ | No se encontraron resultados. | query | 11ms |
| #87 | Exporta los sargentos de Ensenanza. | ✅ | Aquí tienes el reporte solicitado. (1 registros, PDF). | export | 27ms |
| #88 | Dame un resumen por departamento y sexo. | ✅ | Se encontraron 3 resultados: 1. Evaluaciones Médicas | 2 2. Enseñanza | 2 3. Licencias Médicas | 1 | query | 1384ms |
| #89 | Dame un resumen por departamento y rango. | ✅ | Se encontraron 3 resultados: 1. Evaluaciones Médicas | 2 2. Enseñanza | 2 3. Licencias Médicas | 1 | query | 1536ms |
| #90 | Exporta el resumen por departamento en PDF. | ✅ | Aquí tienes el reporte solicitado. (3 registros, PDF). | export | 1346ms |
| #91 | Busca el medico Acosta. | ✅ | Se encontraron 3 resultados: 1. Acosta Cabrera, José. | Masculino | Fijo 2. Acosta Ramos, Miguelina A. | Masculino | Fij | query | 1521ms |
| #92 | Busca medicos con apellido Ramos. | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina Alexandra | Fem | query | 1190ms |
| #93 | Dame informacion de Acosta Ramos. | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina Alexandra | Fem | query | 1266ms |
| #94 | Dame detalle del medico Miguelina. | ✅ | Encontré más de un médico con el apellido Miguelina.: 1. Acosta Ramos, Miguelina A., 2. Acosta Ramos, Miguelina Alexandr | ambiguous | 10ms |
| #95 | Cual es el rango de Acosta Ramos? | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina Alexandra | Fem | query | 1628ms |
| #96 | Cual es el sexo de Acosta Ramos? | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina Alexandra | Fem | query | 1435ms |
| #97 | En que departamento esta Acosta Ramos? | ✅ | Se encontraron 2 resultados: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina Alexandra | Fem | query | 1333ms |
| #98 | Ese medico esta activo para servicio? | ✅ | Se encontraron 80 resultados. Los primeros: 1. Rafael cedano | Masculino | Fijo 2. Hendrick Rafael | Masculino | Fijo 3. | query | 1535ms |
| #99 | Ese medico participa en misiones? | ✅ | ¿A qué médico te refieres? Por favor, proporciona el nombre o ID del médico para consultar su historial de misiones. | ambiguous | 1636ms |
| #100 | Exporta el perfil de ese medico en PDF. | ✅ | Aquí tienes el reporte solicitado. (80 registros, PDF). | export | 1459ms |
| #225 | Busca al medico Fulanito Perez. | ✅ | Encontré más de un médico con el apellido Perez: 1. Batista Perez, Greissy., 2. Dr. Juan Perez, 3. Feliz Perez Sahira, 4 | ambiguous | 8ms |
| #226 | Hay calendario de diciembre 2030? | ✅ | No se encontraron resultados. | query_db | 2736ms |
| #227 | Cuantos cabos femeninos hay en Subdireccion? | ✅ | Resultado: total: 0 | query | 13ms |
| #228 | Dame las misiones de enero 2030. | ✅ | No se encontraron resultados. | query_db | 3571ms |

## Bloque 5

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #101 | Dame los dias de servicio de ese medico. | ✅ | ¿A qué médico te refieres? Por favor, proporciona el nombre o ID del médico para consultar sus días de servicio. | ambiguous | 3019ms |
| #102 | Dame las areas asignadas de ese medico. | ✅ | Por favor, especifica el nombre o ID del médico para consultar sus áreas asignadas. | ambiguous | 1410ms |
| #103 | Dame el historial de servicios de ese medico. | ✅ | No se encontraron resultados. | query_db | 4002ms |
| #104 | Dame el historial de misiones de ese medico. | ✅ | No se encontraron resultados. | query_db | 3991ms |
| #105 | Ese medico tiene restricciones? | ✅ | ¿A qué médico te refieres? Por favor, proporciona el nombre o ID del médico para consultar sus restricciones. | ambiguous | 1633ms |
| #106 | Ese medico esta desactivado? | ✅ | Se encontraron 80 resultados. Los primeros: 1. Rafael cedano | Masculino | Fijo 2. Hendrick Rafael | Masculino | Fijo 3. | query | 1232ms |
| #107 | Por que esta desactivado ese medico? | ✅ | Para conocer el motivo por el cual un médico está desactivado, necesito el nombre o ID del médico. ¿Podrías proporcionár | reply | 1634ms |
| #108 | Dame todos los medicos que se llamen igual. | ✅ | No entiendo exactamente qué quieres decir con 'medicos que se llamen igual'. ¿Te refieres a buscar médicos con el mismo  | ambiguous | 1639ms |
| #109 | Hay medicos duplicados por nombre? | ✅ | Resultado: total: 79 | query | 1743ms |
| #110 | Exporta la lista de posibles duplicados. | ✅ | No tengo una consulta específica para 'posibles duplicados'. ¿Podrías especificar si te refieres a médicos duplicados, a | ambiguous | 1621ms |

## Bloque 6

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #111 | Hay calendario de junio 2026? | ✅ | Resultado: status: Aprobado | month: 6 | year: 2026 | query | 2896ms |
| #112 | Hay calendario de julio 2026? | ✅ | Se encontraron 3 resultados: 1. Borrador | 7 | 2026 2. Borrador | 7 | 2026 3. Aprobado | 7 | 2026 | query | 1525ms |
| #113 | Hay calendario de agosto 2026? | ✅ | Se encontraron 3 resultados: 1. Borrador | 8 | 2026 2. Borrador | 8 | 2026 3. Borrador | 8 | 2026 | query | 1330ms |
| #114 | Cual es el estado del calendario de junio? | ✅ | No se encontraron resultados. | query_db | 2576ms |
| #115 | Cual es el estado del calendario de julio? | ✅ | No se encontraron resultados. | query_db | 2443ms |
| #116 | Cual es el estado del calendario de agosto? | ✅ | No se encontraron resultados. | query_db | 2709ms |
| #117 | El calendario de julio esta aprobado? | ✅ | No se encontraron resultados. | query_db | 2691ms |
| #118 | El calendario de agosto esta aprobado? | ✅ | No se encontraron resultados. | query_db | 2995ms |
| #119 | Hay borrador para agosto? | ✅ | No se encontraron resultados. | query_db | 2972ms |
| #120 | Cuantos calendarios hay para julio? | ✅ | Resultado: total_calendarios: 0 | query_db | 2660ms |
| #121 | Cuantos calendarios hay para agosto? | ✅ | Resultado: total_calendarios: 0 | query_db | 2561ms |
| #122 | Dame los calendarios pendientes de aprobacion. | ✅ | Se encontraron 3 resultados: 1. 7ea6f5f4-23c5-4cdf-80a6-e9468407c6e7 | 2026 | 9 2. f919beda-93ba-409f-bc97-c479c85e02de  | query_db | 3693ms |
| #123 | Dame los calendarios aprobados. | ✅ | Resultado: id_calendario: f136a1c0-96c8-4e32-8356-f8ac9d6496a1 | año: 2026 | mes: 7 | estado: approved | modo_generacion | query_db | 3049ms |
| #124 | Dame el ultimo calendario generado. | ✅ | ¿A qué mes y año te refieres? Necesito el periodo para consultar el calendario. | ambiguous | 1449ms |
| #125 | Dame el calendario oficial de julio. | ✅ | No se encontraron resultados. | query_db | 3496ms |
| #126 | Exporta el calendario aprobado de julio en PDF. | ✅ | No se encontraron resultados. | query_db | 3676ms |
| #127 | Exporta el calendario aprobado de julio en Excel. | ✅ | No se encontraron resultados. | query_db | 4205ms |
| #128 | Exporta el borrador de agosto en PDF. | ✅ | No se encontraron resultados. | query_db | 4503ms |
| #129 | Dame un resumen operativo de julio. | ✅ | Resultado: active_doctors: 79 | total_assignments: 0 | unresolved_gaps: 0 | query | 1531ms |
| #130 | Dame un resumen operativo de agosto. | ✅ | Resultado: active_doctors: 79 | total_assignments: 0 | unresolved_gaps: 0 | query | 1434ms |
| #131 | Cuantos medicos estan incluidos en el calendario de julio? | ✅ | Resultado: total: 79 | query | 20ms |
| #132 | Cuantos medicos estan incluidos en el calendario de agosto? | ✅ | No hay calendario aprobado para ese mes. Existe un borrador con 79 médico(s) incluido(s), pendiente de aprobación. | query | 25ms |
| #133 | Cuantos medicos estan de servicio en julio? | ✅ | Resultado: total: 79 | query | 21ms |
| #134 | Cuantos medicos estan de servicio en agosto? | ✅ | No hay calendario aprobado para ese mes. Existe un borrador con 79 médico(s) incluido(s), pendiente de aprobación. | query | 20ms |
| #135 | Dame la lista de medicos de servicio en julio. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Cabrera, José. | 3 2. Acosta Ramos, Miguelina A. | 2 3. Acosta Ram | query | 22ms |
| #136 | Dame la lista de medicos de servicio en agosto. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Cabrera, José. | 2 2. Acosta Ramos, Miguelina A. | 2 3. Acosta Ram | query | 26ms |
| #137 | Cuales son los medicos de servicio la primera semana de julio? | ✅ | Se encontraron 21 resultados. Los primeros: 1. 2026-07-01 | Torres Desena, Kiara | Disponible 2. 2026-07-01 | Peña Polan | query | 29ms |
| #138 | Cuales son los medicos de servicio la primera semana de agosto? | ✅ | No hay calendario aprobado para ese periodo. Existe un borrador con 21 asignación(es), pendiente de aprobación. | query | 28ms |
| #139 | Cuales son los medicos de servicio la segunda semana de julio? | ✅ | Se encontraron 21 resultados. Los primeros: 1. 2026-07-08 | Castillo Peña Nicole | Disponible 2. 2026-07-08 | Nunez Eric | query | 15ms |
| #140 | Cuales son los medicos de servicio la tercera semana de julio? | ✅ | Se encontraron 21 resultados. Los primeros: 1. 2026-07-15 | Santana Brito, Vanessa Yamely | Disponible 2. 2026-07-15 | M | query | 16ms |
| #141 | Cuales son los medicos de servicio la cuarta semana de julio? | ✅ | Se encontraron 21 resultados. Los primeros: 1. 2026-07-22 | De Jesús Herrera, Ruth. | Disponible 2. 2026-07-22 | Placenc | query | 17ms |
| #142 | Y el de agosto? | ✅ | No se encontraron resultados. | query_db | 3279ms |
| #143 | Y el de julio? | ✅ | ¿A qué te refieres con 'el de julio'? Por favor, especifica si quieres información sobre médicos, asignaciones, calendar | ambiguous | 2011ms |
| #144 | Cuales medicos trabajan el primer lunes de agosto? | ✅ | No se encontraron resultados. | query_db | 4417ms |
| #145 | Cuales medicos trabajan el primer lunes de julio? | ✅ | No se encontraron resultados. | query_db | 4604ms |
| #146 | Cuales medicos trabajan el 4 de julio? | ✅ | No se encontraron resultados. | query_db | 3166ms |
| #147 | Cuales medicos trabajan el 15 de agosto? | ✅ | No se encontraron resultados. | query_db | 3584ms |
| #148 | Exporta los servicios de la primera semana de julio. | ✅ | No se encontraron resultados. | query_db | 5331ms |
| #149 | Exporta los servicios de julio en PDF. | ✅ | Aquí tienes el reporte solicitado. (1 registros, PDF). | export | 1829ms |
| #150 | Exporta los servicios de agosto en Excel. | ✅ | No se encontraron resultados. | query_db | 4937ms |
| #151 | Cuantos servicios hay en julio? | ✅ | Resultado: total: 0 | query | 1423ms |
| #152 | Cuantos servicios hay en agosto? | ✅ | Resultado: total: 0 | query | 1453ms |
| #153 | Cuantos servicios tiene cada medico en julio? | ✅ | Resultado: total: 79 | query | 34ms |
| #154 | Cuantos servicios tiene cada medico en agosto? | ✅ | No hay calendario aprobado para ese mes. Existe un borrador con 79 médico(s) incluido(s), pendiente de aprobación. | query | 28ms |
| #155 | Quienes no fueron asignados en julio? | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. 2. Acosta Ramos, Miguelina Alexandra 3. Alvare | query | 1559ms |
| #156 | Quienes no fueron asignados en agosto? | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. 2. Acosta Ramos, Miguelina Alexandra 3. Alvare | query | 1640ms |
| #157 | Dame los huecos sin cubrir de julio. | ✅ | No se encontraron resultados. | query_db | 3679ms |
| #158 | Dame los huecos sin cubrir de agosto. | ✅ | No se encontraron resultados. | query_db | 3294ms |
| #159 | Hay cobertura completa en julio? | ✅ | Resultado: dias_con_asignacion: 0 | areas_servicio: 0 | total_combinaciones_posibles: 0 | combinaciones_cubiertas: 0 | c | query_db | 4492ms |
| #160 | Hay cobertura completa en agosto? | ✅ | Resultado: total_slots: 0 | assigned_slots: 0 | gaps: 0 | cobertura_completa: Sí | query_db | 4092ms |

## Bloque 7

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #161 | Cuantos servicios hay por area en julio? | ✅ | No se encontraron resultados. | query_db | 7710ms |
| #162 | Cuantos servicios hay por area en agosto? | ✅ | No se encontraron resultados. | query_db | 3885ms |
| #163 | Quienes estan en Emergencia en julio? | ✅ | No se encontraron resultados. | query_db | 4816ms |
| #164 | Quienes estan en Pista en julio? | ✅ | No se encontraron resultados. | query_db | 5774ms |
| #165 | Quienes estan en UCI en julio? | ✅ | No se encontraron resultados. | query_db | 4157ms |
| #166 | Quienes estan en Consulta Externa en julio? | ✅ | No se encontraron resultados. | query_db | 3964ms |
| #167 | Exporta los servicios por area de julio. | ✅ | No se encontraron resultados. | query_db | 4441ms |
| #168 | Cual medico tiene mas servicios en julio? | ✅ | No se encontraron resultados. | query_db | 4204ms |
| #169 | Cual medico tiene menos servicios en julio? | ✅ | No se encontraron resultados. | query_db | 3875ms |
| #170 | Dame la carga de trabajo de julio. | ✅ | Resultado: active_doctors: 79 | total_assignments: 0 | unresolved_gaps: 0 | query | 1948ms |
| #171 | Dame la carga de trabajo de agosto. | ✅ | No se encontraron resultados. | query_db | 4202ms |
| #172 | Exporta la carga de trabajo de julio en PDF. | ✅ | Aquí tienes el reporte solicitado. (1 registros, PDF). | export | 2594ms |
| #173 | Exporta la carga de trabajo de agosto en Excel. | ✅ | No se encontraron resultados. | query_db | 5502ms |
| #174 | Quienes tienen 3 servicios en julio? | ✅ | No se encontraron resultados. | query_db | 3675ms |
| #175 | Quienes tienen menos de 3 servicios en julio? | ✅ | Se encontraron 80 resultados. Los primeros: 1. dba19ed2-f3b4-4618-8430-19e714400b15 | Cuevas Cuevas, Katherine P. | 0 2. | query_db | 3542ms |
| #176 | Quienes exceden la meta mensual? | ✅ | Para determinar quiénes exceden la meta mensual, necesito saber el mes y año específicos. Por favor, indíqueme el períod | ambiguous | 1828ms |
| #177 | Quienes no cumplen la meta mensual? | ✅ | Para determinar quiénes no cumplen la meta mensual, necesito más información. ¿A qué meta se refiere? Por ejemplo, ¿es l | ambiguous | 2007ms |
| #178 | Dame la distribucion por area y rango. | ✅ | No tengo una consulta específica para distribución por área y rango combinados. ¿Podrías aclarar si quieres la cantidad  | ambiguous | 2449ms |
| #179 | Dame la distribucion por area y sexo. | ✅ | No tengo una consulta específica para distribución por área y sexo combinados. ¿Podrías aclarar si quieres el conteo de  | ambiguous | 2205ms |
| #180 | Dame los medicos con servicio en las tres areas. | ✅ | Para obtener los médicos con servicio en las tres áreas, necesito que me especifiques qué áreas son y el rango de fechas | ambiguous | 2711ms |
| #229 | Dame los medicos. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina  | query | 1435ms |
| #230 | Cuantos hay? | ✅ | ¿A qué te refieres con 'cuantos hay'? Por favor especifica si quieres saber cuántos médicos hay por sexo, rango, departa | ambiguous | 1844ms |
| #231 | Como esta el sistema? | ✅ | El sistema está operativo. ¿En qué puedo ayudarte? Puedo consultar información sobre médicos, asignaciones, calendarios  | reply | 1840ms |
| #232 | Que me recomiendas? | ✅ | Puedo ayudarte a consultar información sobre médicos, asignaciones, calendarios y más. ¿Qué te gustaría saber? Por ejemp | reply | 1981ms |

## Bloque 8

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #181 | Hay ranking de misiones para julio? | ✅ | Se encontraron 20 resultados. Los primeros: 1. 2026 | 7 | 1 2. 2026 | 7 | 2 3. 2026 | 7 | 3 4. 2026 | 7 | 4 5. 2026 | 7  | query | 105ms |
| #182 | Hay ranking de misiones para agosto? | ✅ | No se encontraron resultados. | query_db | 5386ms |
| #183 | Dame el ranking de misiones de julio. | ✅ | Se encontraron 20 resultados. Los primeros: 1. 2026 | 7 | 1 2. 2026 | 7 | 2 3. 2026 | 7 | 3 4. 2026 | 7 | 4 5. 2026 | 7  | query | 21ms |
| #184 | Dame el ranking de misiones de agosto. | ✅ | No se encontraron resultados. | query_db | 4173ms |
| #185 | Cuales son los 3 primeros del ranking de misiones de agosto? | ✅ | No se encontraron resultados. | query_db | 4297ms |
| #186 | Cuales son los 5 primeros del ranking de misiones de julio? | ✅ | Se encontraron 20 resultados. Los primeros: 1. 2026 | 7 | 1 2. 2026 | 7 | 2 3. 2026 | 7 | 3 4. 2026 | 7 | 4 5. 2026 | 7  | query | 15ms |
| #187 | Dame todos los candidatos de misiones de agosto. | ✅ | No se encontraron resultados. | query_db | 4266ms |
| #188 | Exporta el ranking de misiones de agosto en PDF. | ✅ | No se encontraron resultados. | query_db | 4530ms |
| #189 | Exporta el ranking de misiones de julio en Excel. | ✅ | Se encontraron 20 resultados. Los primeros: 1. 2026 | 7 | 1 2. 2026 | 7 | 2 3. 2026 | 7 | 3 4. 2026 | 7 | 4 5. 2026 | 7  | query | 10ms |
| #190 | Quien es el candidato numero 1 para misiones en agosto? | ✅ | No se encontraron resultados. | query_db | 3995ms |
| #191 | Quienes son elegibles para mision el 15 de agosto? | ✅ | No se encontraron resultados. | query_db | 5880ms |
| #192 | Quienes no son elegibles para mision el 15 de agosto? | ✅ | Se encontraron 79 resultados. Los primeros: 1. Rafael cedano | rafael cedano | male 2. Hendrick Rafael | hendrick rafael | query_db | 5025ms |
| #193 | Dame los candidatos disponibles para mision el 20 de julio. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | male | sargento 2. Acosta Ramos, Miguelina A | query_db | 5035ms |
| #194 | Dame candidatos ordenados de menor carga a mayor carga. | ✅ | Se encontraron 4 resultados: 1. Cuevas Garo, Yancarla. | Masculino | Sargento Mayor 2. De Leon Taveraz, Aimee Mercedes | | query | 16ms |
| #195 | Si el primero no puede, quien sigue? | ✅ | Necesito más información para ayudarte. ¿A qué te refieres con 'el primero'? ¿Estás preguntando por un ranking de médico | ambiguous | 2517ms |
| #196 | Hay misiones creadas en julio? | ✅ | No se encontraron resultados. | query_db | 3738ms |
| #197 | Hay misiones creadas en agosto? | ✅ | No se encontraron resultados. | query_db | 3191ms |
| #198 | Dame las misiones de julio. | ✅ | Se encontraron 2 resultados: 1. 6fd83f4c-7d07-43ff-8672-c06fbb8370c1 | 2026-07-22 |  2. 8c1e2f54-56de-4d0c-b62e-6ad787aa | query_db | 4287ms |
| #199 | Dame las misiones de agosto. | ✅ | No se encontraron resultados. | query_db | 3877ms |
| #200 | Exporta las misiones de agosto. | ✅ | No se encontraron resultados. | query_db | 4086ms |
| #201 | Quienes participan en la mision del 15 de agosto? | ✅ | No se encontraron resultados. | query_db | 4090ms |
| #202 | Esa mision esta confirmada? | ✅ | Para verificar si una misión está confirmada, necesito más detalles. ¿Podrías indicarme el mes y año de la misión, o el  | ambiguous | 2041ms |
| #203 | Quienes no han confirmado la mision? | ✅ | ¿A qué mes y año te refieres? Necesito el período para consultar el ranking de candidatos a misiones. | ambiguous | 1636ms |
| #204 | Quienes confirmaron recibido de la mision? | ✅ | No tengo información sobre confirmaciones de recepción de misiones. ¿Podrías especificar a qué misión te refieres o qué  | ambiguous | 1737ms |
| #205 | Hay advertencias en misiones? | ✅ | No tengo información sobre advertencias en misiones. ¿Podrías especificar a qué tipo de advertencia te refieres o qué co | ambiguous | 1738ms |
| #206 | Hay medicos desactivados dentro de misiones? | ✅ | No se encontraron resultados. | query_db | 4914ms |
| #207 | Que medicos debo reemplazar en misiones? | ✅ | Para ayudarte con reemplazos en misiones, necesito que me indiques el mes y año del periodo que te interesa. Por ejemplo | ambiguous | 2145ms |
| #208 | Dame las misiones pendientes de reemplazo. | ✅ | Para consultar misiones pendientes de reemplazo, necesito que me especifiques el mes y año. Por ejemplo: 'Misiones pendi | ambiguous | 1942ms |
| #209 | Exporta las misiones con advertencias. | ✅ | No tengo una consulta específica para exportar misiones con advertencias. ¿Podrías proporcionar más detalles, como el pe | ambiguous | 1535ms |
| #210 | Dame resumen de misiones por mes. | ✅ | Se encontraron 2 resultados: 1. 2026 | 7 | 2 2. 2026 | 5 | 1 | query_db | 3384ms |

## Bloque 9

| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |
|---|----------|--------|-----------|--------|--------|
| #211 | Hay notificaciones pendientes? | ✅ | No tengo acceso a notificaciones pendientes. Mi función es gestionar consultas sobre médicos, asignaciones y calendarios | reply | 5368ms |
| #212 | Hay alertas importantes? | ✅ | No tengo información sobre alertas en este momento. ¿Te gustaría consultar el resumen operativo del sistema para un mes  | reply | 2231ms |
| #213 | Que medicos no han confirmado servicio? | ✅ | No tengo una consulta específica para médicos que no han confirmado servicio. ¿Podrías aclarar si te refieres a médicos  | ambiguous | 2251ms |
| #214 | Que medicos confirmaron servicio? | ✅ | Se encontraron 79 resultados. Los primeros: 1. Acosta Ramos, Miguelina A. | Masculino | Fijo 2. Acosta Ramos, Miguelina  | query | 1946ms |
| #215 | Que medicos no han confirmado mision? | ✅ | Para consultar médicos que no han confirmado misión, necesito que me indiques el año y el mes del período que deseas rev | ambiguous | 3073ms |
| #216 | Exporta los pendientes de confirmacion. | ✅ | Se encontraron 79 resultados. Los primeros: 1. Rafael cedano 2. Hendrick Rafael 3. Pineda Mora, Andry 4. Torres Desena,  | query | 2261ms |
| #217 | Dame auditoria de cambios del calendario de julio. | ✅ | No se encontraron resultados. | query_db | 4661ms |
| #218 | Quien aprobo el calendario de julio? | ❌ | No pude encontrar informacion sobre eso en el sistema. | query_db | 6083ms |
| #219 | Que cambios se hicieron despues de aprobar el calendario? | ✅ | Para consultar cambios posteriores a la aprobación de un calendario, necesito más información: ¿a qué mes y año se refie | ambiguous | 2449ms |
| #220 | Dame un reporte general operativo del sistema para julio. | ✅ | Resultado: active_doctors: 79 | total_assignments: 0 | unresolved_gaps: 0 | query | 1844ms |
| #233 | Que hora es? | ✅ | No tengo acceso a la hora actual. Soy un asistente para gestionar turnos médicos. Puedo ayudarte con consultas sobre méd | reply | 2242ms |
| #234 | Quien es el presidente? | ✅ | No tengo información sobre quién es el presidente. Mi función es gestionar turnos médicos. ¿Puedo ayudarte con alguna co | reply | 2244ms |
| #235 | Cuentame un chiste. | ✅ | Lo siento, soy un asistente de gestión de turnos médicos y no tengo chistes programados. ¿Puedo ayudarte con alguna cons | reply | 2154ms |
| #236 | Que puedes hacer? | ✅ | Puedo ayudarte a consultar información sobre médicos, asignaciones, calendarios y generar reportes. Por ejemplo, puedo c | reply | 2443ms |
| #237 | /start | ✅ | ¡Hola! Soy el asistente del sistema de gestión de turnos médicos. Puedo ayudarte con consultas sobre médicos, asignacion | reply | 2350ms |
| #238 | Ayuda | ✅ | ¡Hola! Soy el asistente del sistema de gestión de turnos médicos. Puedo ayudarte a consultar información sobre médicos,  | reply | 2250ms |
| #239 | Cuantos cabos hay? -> No, de sargentos. -> Y de pasantes? | ✅ | Resultado: total: 22 | query | 37ms |
| #240 | Dame los pasantes femeninos. -> No, masculinos. -> Y tambien los de Ensenanza. | ✅ | No se encontraron resultados. | query | 29ms |
| #241 | Cuantos medicos hay en julio? -> No, en agosto. -> Los que estan en Emergencia. | ✅ | Resultado: medicos_en_emergencia_agosto: 54 | query_db | 4999ms |
| #242 | Busca al medico Ramos. -> No, al que se llama Miguelina Ramos. -> Dame su rango. | ✅ | Encontré más de un médico con el apellido Miguelina.: 1. Acosta Ramos, Miguelina A., 2. Acosta Ramos, Miguelina Alexandr | ambiguous | 12ms |
| #243 | Cuantos sargentos hay? -> De esos, cuantos son femeninos? -> Exportalos en PDF. | ✅ | Aquí tienes el reporte solicitado. (7 registros, PDF). | export | 337ms |

