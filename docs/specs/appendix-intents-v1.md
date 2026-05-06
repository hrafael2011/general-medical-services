---
spec: appendix-intents
version: 1.0.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Appendix - Telegram Intent Catalog v1

This is the closed intent set for MVP.

The catalog defines supported capabilities, not every possible user phrase. The LLM may map many natural language phrasings to the same intent when confidence is sufficient.

## Query Intents

### Doctor and Availability

1. `count_medicos`
2. `count_medicos_activos`
3. `list_medicos_activos`
4. `list_medicos_por_departamento`
5. `list_medicos_con_licencia`
6. `list_medicos_con_deuda`
7. `list_medicos_participa_misiones`
8. `list_medicos_no_misiones`
9. `list_disponibles_por_rango`
10. `list_disponibles_para_mision_rango`
11. `list_disponibles_por_area_rango`
12. `pendientes_disponibilidad_mes`

### History and Workload

13. `historial_medico`
14. `carga_medica_mes`
15. `medicos_mas_carga_mes`
16. `medicos_menos_carga_mes`
17. `servicios_por_area_semana`
18. `rank_medicos_por_carga_rango`
19. `list_medicos_bajo_meta_mes`
20. `list_medicos_sobre_maximo_mes`

### Calendar and Fairness

21. `estado_calendario_mes`
22. `conflictos_fairness_mes`
23. `recommend_medicos_para_contexto`
24. `explain_assignment_decision`
25. `explain_recommendation`
26. `get_calendar_pdf`
27. `generate_operational_report`
28. `send_report_export`
29. `get_mission_candidate_ranking`
30. `recommend_mission_candidates`
31. `confirm_mission_assignment`

### Notifications and Audit

32. `resumen_notificaciones_semana`
33. `audit_lookup`
34. `security_event_lookup`

## Intent Contract Template

For each intent define:

- `intent_id`
- `examples`
- `required_entities`
- `optional_entities`
- `allowed_roles`
- `tool_or_endpoint`
- `success_response_shape`
- `error_response_shape`
- `clarification_behavior`
- `cache_policy`
- `audit_level`
- `out_of_domain_behavior`

## Standard Entity Types

- `doctor_name`
- `doctor_id`
- `date`
- `date_range`
- `month`
- `year`
- `service_area`
- `department`
- `rank`
- `staff_category`
- `criteria`
- `limit`
- `monthly_service_target`
- `monthly_service_max`
- `report_type`
- `export_format`
- `participant_count`
- `mission_date`
- `location`
- `description`

## General Intent Examples

`recommend_medicos_para_contexto` may cover natural requests such as:

- "quienes estan mas descansados para emergencia esta semana"
- "dame candidatos para cubrir manana"
- "quienes convienen para una mision extra"
- "buscame medicos con menos carga reciente"

`explain_assignment_decision` may cover natural requests such as:

- "por que pusiste a Perez"
- "por que no pusiste a Gomez"
- "explicame esta asignacion"

`generate_operational_report` and `send_report_export` may cover natural requests such as:

- "mandame el calendario de mayo en pdf"
- "dame un reporte de los 5 medicos con mas servicios"
- "envia el listado de medicos por rango"
- "sacame los pendientes de disponibilidad"

`recommend_mission_candidates` and `confirm_mission_assignment` may cover natural requests such as:

- "necesito 5 medicos para mision manana"
- "dame otros dos candidatos"
- "por que esos cinco"
- "confirma esos para la mision"

The exact examples are not exhaustive and must not become the only accepted phrasing.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Catálogo cerrado de 34 intents MVP para el asistente Telegram, contrato de intent y tipos de entidad estándar. |