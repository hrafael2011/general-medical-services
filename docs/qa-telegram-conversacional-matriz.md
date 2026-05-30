# Matriz QA Conversacional — Fase 9

| ID | Conversación / Pregunta | Dominio | Acción | Ruta | Entidades | Memoria | Formato | Resultado esperado | Documento |
|----|------------------------|---------|--------|------|-----------|---------|---------|-------------------|-----------|
| 1 | ¿Cuántos médicos tengo en total? | conteo | query | SemanticLayer → count_doctors_total | — | — | texto | Conteo exacto de médicos activos | — |
| 2 | Dame la lista de pasante femeninos | listado | query | SemanticLayer → doctors_by_sex | sex=female, rank=pasante | last_filters | texto | Lista filtrada por sexo y rango | — |
| 3 | Conteo → listado → PDF | conteo → listado → export | query → export | SemanticLayer → IntentRouter | — | followup | PDF | Reporte generado correctamente | Sí |
| 4 | Mes agosto → y julio | calendario | query | IntentRouter → calendar_status_month | month=8, year=2026 | month_followup | texto | Estado de calendario para ambos meses | — |
| 5 | Pasantes femeninos → y masculinos | doctor | query | DoctorQueryService | sex, rank | sex_toggle | texto | Resultados alternando filtro de sexo | — |
| 6 | Ranking agosto → top 3 → exportar | mission | query → export | IntentRouter → mission_ranking | year, month, top_n | — | PDF | Ranking con top N exportado | Sí |
| 7 | Calendario aprobado → borrador | calendario | query | IntentRouter → calendar_status_month | status | — | texto | Estado del calendario (aprobado/borrador) | — |
| 8 | Rango inválido | doctor | ambiguous | — | rank=xyz | — | texto | Pedir clarificación sobre rango | — |
| 9 | Mes sin calendario | calendario | query | IntentRouter → calendar_status_month | month=13 | — | texto | "No se encontraron resultados" | — |
| 10 | Ranking inexistente | mission | query | IntentRouter → mission_ranking | year=1999 | — | texto | "No se encontraron resultados" | — |
| 11 | Pregunta fuera del sistema | — | reply | LLM directo | — | — | texto | Respuesta informativa fuera de dominio | — |
| 12 | Médico inexistente | doctor | query | EntityResolver | name="NoExiste" | — | texto | "No pude encontrar información" | — |
| 13 | Departamento mal escrito | doctor | ambiguous | — | department="xyz" | — | texto | Pedir clarificación | — |
| 14 | UUID visible en respuesta | — | — | — | — | — | texto | UUIDs nunca visibles al usuario | — |
| 15 | Inglés visible | — | — | — | — | — | texto | Texto siempre en español | — |
| 16 | Cero resultados | — | — | — | — | — | texto | Mensaje amigable cuando no hay datos | — |
