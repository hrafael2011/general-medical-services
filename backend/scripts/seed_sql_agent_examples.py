#!/usr/bin/env python3
"""Seed the SQL Agent example store with known queries + synthetic examples.

Usage:
    cd backend && .venv/bin/python scripts/seed_sql_agent_examples.py

This populates the local sqlite-vec vector store so the PromptBuilder can
retrieve few-shot examples for ad-hoc queries.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root.parent))

from backend.app.application.telegram.registry import DEFAULT_QUERY_TYPES
from backend.app.application.telegram.sql_agent.example_store import (
    SQLExample,
    ExampleStore,
)


# ---------------------------------------------------------------------------
# Synthetic examples — ad-hoc questions not covered by the registry
# ---------------------------------------------------------------------------
_SYNTHETIC_EXAMPLES: list[SQLExample] = [
    SQLExample(
        nl_query="muestra todos los rangos disponibles",
        sql="SELECT id, name FROM ranks ORDER BY name",
        category="catalog",
        description="Listado de rangos militares",
    ),
    SQLExample(
        nl_query="cuales son las areas de servicio",
        sql="SELECT code, display_name FROM service_areas ORDER BY display_name",
        category="catalog",
        description="Listado de áreas de servicio",
    ),
    SQLExample(
        nl_query="medicos que participan en misiones",
        sql="SELECT DISTINCT d.name FROM doctors d JOIN mission_participants mp ON mp.doctor_id = d.id WHERE d.active = TRUE ORDER BY d.name",
        category="mission",
        description="Médicos asignados a misiones",
    ),
    SQLExample(
        nl_query="cuantas misiones hay este mes",
        sql="SELECT COUNT(*) AS total FROM mission_assignments WHERE EXTRACT(MONTH FROM mission_date) = EXTRACT(MONTH FROM CURRENT_DATE) AND EXTRACT(YEAR FROM mission_date) = EXTRACT(YEAR FROM CURRENT_DATE) AND deleted_at IS NULL",
        category="mission",
        description="Conteo de misiones del mes actual",
    ),
    SQLExample(
        nl_query="ultima version de cada calendario",
        sql="SELECT c.year, c.month, MAX(cv.version_number) AS latest_version FROM calendars c JOIN calendar_versions cv ON cv.calendar_id = c.id GROUP BY c.year, c.month ORDER BY c.year DESC, c.month DESC",
        category="calendar",
        description="Última versión de cada calendario",
    ),
    SQLExample(
        nl_query="medicamentos con mas servicios asignados",
        sql="SELECT d.name, COUNT(ca.id) AS total_services FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id GROUP BY d.name ORDER BY total_services DESC LIMIT 10",
        category="ranking",
        description="Top médicos por cantidad de servicios",
    ),
    SQLExample(
        nl_query="cuantos doctores hay en total sin importar si estan activos",
        sql="SELECT COUNT(*) AS total FROM doctors",
        category="count",
        description="Conteo total sin filtros",
    ),
    SQLExample(
        nl_query="doctores que no tienen restricciones",
        sql="SELECT d.name FROM doctors d WHERE NOT EXISTS (SELECT 1 FROM doctor_restrictions dr WHERE dr.doctor_id = d.id AND dr.end_date >= CURRENT_DATE)",
        category="availability",
        description="Médicos sin restricciones activas",
    ),
    SQLExample(
        nl_query="doctores con disponibilidad semanal",
        sql="SELECT d.name, da.day_of_week, da.start_time, da.end_time FROM doctors d JOIN doctor_availability da ON da.doctor_id = d.id WHERE d.availability_mode = 'weekly' ORDER BY d.name, da.day_of_week",
        category="availability",
        description="Disponibilidad semanal de médicos",
    ),
    SQLExample(
        nl_query="servicios del ultimo mes",
        sql="SELECT d.name, ca.service_date, sa.display_name AS area FROM calendar_assignments ca JOIN doctors d ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE ca.service_date >= CURRENT_DATE - INTERVAL '1 month' ORDER BY ca.service_date DESC",
        category="history",
        description="Servicios del último mes",
    ),
    SQLExample(
        nl_query="promedio de servicios por medico",
        sql="SELECT AVG(cnt) AS avg_services FROM (SELECT COUNT(*) AS cnt FROM calendar_assignments GROUP BY doctor_id) AS sub",
        category="analytics",
        description="Promedio de servicios por médico",
    ),
    SQLExample(
        nl_query="areas sin servicios asignados esta semana",
        sql="SELECT sa.code, sa.display_name FROM service_areas sa WHERE NOT EXISTS (SELECT 1 FROM calendar_assignments ca WHERE ca.service_area_id = sa.id AND ca.service_date >= CURRENT_DATE - INTERVAL '7 days')",
        category="gap",
        description="Áreas sin servicios recientes",
    ),
    SQLExample(
        nl_query="misiones confirmadas vs pendientes",
        sql="SELECT status, COUNT(*) AS total FROM mission_assignments WHERE deleted_at IS NULL GROUP BY status",
        category="mission",
        description="Estadísticas de estados de misiones",
    ),
    SQLExample(
        nl_query="ranking de misiones de enero 2025",
        sql="SELECT mcre.ranking_position, d.name AS doctor_name, mcre.total_load_score FROM mission_candidate_rankings mcr JOIN mission_candidate_ranking_entries mcre ON mcre.mission_candidate_ranking_id = mcr.id JOIN doctors d ON mcre.doctor_id = d.id WHERE mcr.year = 2025 AND mcr.month = 1 ORDER BY mcre.ranking_position LIMIT 20",
        category="mission",
        description="Ranking de candidatos para misiones",
    ),
    SQLExample(
        nl_query="quien aprobo el calendario de marzo 2025",
        sql="SELECT ae.action_type, ae.occurred_at AS fecha, u.name AS actor FROM audit_events ae JOIN users u ON ae.actor_id = u.id JOIN calendars c ON ae.entity_id = c.id WHERE c.year = 2025 AND c.month = 3 AND c.deleted_at IS NULL ORDER BY ae.occurred_at DESC LIMIT 10",
        category="audit",
        description="Auditoría de aprobaciones de calendario",
    ),
    SQLExample(
        nl_query="medicos con nombres duplicados",
        sql="SELECT name, COUNT(*) AS count FROM doctors WHERE active = TRUE AND service_active = TRUE GROUP BY name HAVING COUNT(*) > 1 ORDER BY count DESC, name",
        category="data_quality",
        description="Nombres duplicados en el sistema",
    ),
    SQLExample(
        nl_query="calendarios sin versiones",
        sql="SELECT c.year, c.month FROM calendars c WHERE NOT EXISTS (SELECT 1 FROM calendar_versions cv WHERE cv.calendar_id = c.id)",
        category="calendar",
        description="Calendarios sin versiones",
    ),
    SQLExample(
        nl_query="doctores que nunca han sido asignados",
        sql="SELECT d.name FROM doctors d WHERE d.active = TRUE AND d.service_active = TRUE AND NOT EXISTS (SELECT 1 FROM calendar_assignments ca WHERE ca.doctor_id = d.id)",
        category="assignment",
        description="Médicos sin asignaciones históricas",
    ),
    SQLExample(
        nl_query="servicios por area en febrero 2025",
        sql="SELECT sa.display_name AS area, COUNT(ca.id) AS total FROM calendar_assignments ca JOIN service_areas sa ON ca.service_area_id = sa.id JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = 2025 AND c.month = 2 GROUP BY sa.display_name ORDER BY total DESC",
        category="analytics",
        description="Servicios agrupados por área",
    ),
    SQLExample(
        nl_query="medicina interna cuantos servicios tiene",
        sql="SELECT COUNT(*) AS total FROM calendar_assignments ca JOIN service_areas sa ON ca.service_area_id = sa.id WHERE sa.display_name ILIKE '%medicina interna%'",
        category="count",
        description="Servicios de un área específica",
    ),
    SQLExample(
        nl_query="medicos con carga mayor al promedio",
        sql="WITH loads AS (SELECT doctor_id, COUNT(*) AS cnt FROM calendar_assignments GROUP BY doctor_id) SELECT d.name, l.cnt FROM doctors d JOIN loads l ON l.doctor_id = d.id WHERE l.cnt > (SELECT AVG(cnt) FROM loads) ORDER BY l.cnt DESC",
        category="analytics",
        description="Médicos con carga sobre el promedio",
    ),
    SQLExample(
        nl_query="misiones sin participantes asignados",
        sql="SELECT ma.mission_date, ma.location, ma.description FROM mission_assignments ma WHERE ma.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM mission_participants mp WHERE mp.mission_assignment_id = ma.id) ORDER BY ma.mission_date",
        category="mission",
        description="Misiones sin médicos asignados",
    ),
    SQLExample(
        nl_query="doctores inactivos pero con servicios futuros",
        sql="SELECT DISTINCT d.name FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id WHERE d.active = FALSE AND ca.service_date >= CURRENT_DATE",
        category="data_quality",
        description="Inconsistencias de activación",
    ),
    SQLExample(
        nl_query="cuantas areas de servicio existen",
        sql="SELECT COUNT(*) AS total FROM service_areas",
        category="catalog",
        description="Conteo de áreas de servicio",
    ),
    SQLExample(
        nl_query="disponibilidad del doctor Garcia",
        sql="SELECT da.day_of_week, da.start_time, da.end_time, da.is_available FROM doctor_availability da JOIN doctors d ON da.doctor_id = d.id WHERE d.name ILIKE '%Garcia%' ORDER BY da.day_of_week",
        category="availability",
        description="Disponibilidad por nombre de médico",
    ),
    SQLExample(
        nl_query="reporte de huecos sin asignar en abril",
        sql="SELECT ug.service_date, sa.display_name AS area, ug.reason_code, ug.description FROM unresolved_gaps ug JOIN service_areas sa ON ug.service_area_id = sa.id JOIN calendar_versions cv ON ug.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = EXTRACT(YEAR FROM CURRENT_DATE) AND c.month = 4 ORDER BY ug.service_date",
        category="gap",
        description="Huecos sin asignar en un mes",
    ),
    SQLExample(
        nl_query="doctores por departamento ordenados alfabeticamente",
        sql="SELECT dep.name AS department, d.name AS doctor_name FROM doctors d JOIN departments dep ON d.department_id = dep.id WHERE d.active = TRUE AND d.service_active = TRUE ORDER BY dep.name, d.name",
        category="listing",
        description="Listado por departamento",
    ),
    SQLExample(
        nl_query="servicios asignados por fuente manual vs automatica",
        sql="SELECT ca.assignment_source, COUNT(*) AS total FROM calendar_assignments ca GROUP BY ca.assignment_source ORDER BY total DESC",
        category="analytics",
        description="Distribución por fuente de asignación",
    ),
    SQLExample(
        nl_query="calendario actual estado",
        sql="SELECT status, month, year FROM calendars WHERE year = EXTRACT(YEAR FROM CURRENT_DATE) AND month = EXTRACT(MONTH FROM CURRENT_DATE)",
        category="calendar",
        description="Estado del calendario actual",
    ),
    SQLExample(
        nl_query="medicos con mas de 10 servicios este mes",
        sql="SELECT d.name, COUNT(ca.id) AS total FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = EXTRACT(YEAR FROM CURRENT_DATE) AND c.month = EXTRACT(MONTH FROM CURRENT_DATE) GROUP BY d.name HAVING COUNT(ca.id) > 10 ORDER BY total DESC",
        category="filter",
        description="Médicos con alta carga mensual",
    ),
    SQLExample(
        nl_query="participantes de la mision del 15 de marzo",
        sql="SELECT d.name, mp.status FROM mission_participants mp JOIN doctors d ON mp.doctor_id = d.id JOIN mission_assignments ma ON mp.mission_assignment_id = ma.id WHERE ma.mission_date = '2025-03-15'",
        category="mission",
        description="Participantes de misión por fecha",
    ),
    SQLExample(
        nl_query="areas que no tienen medicos asignados hoy",
        sql="SELECT sa.code, sa.display_name FROM service_areas sa WHERE NOT EXISTS (SELECT 1 FROM calendar_assignments ca WHERE ca.service_area_id = sa.id AND ca.service_date = CURRENT_DATE)",
        category="gap",
        description="Áreas sin cobertura hoy",
    ),
    SQLExample(
        nl_query="doctores con restricciones activas",
        sql="SELECT d.name, dr.start_date, dr.end_date, dr.reason FROM doctors d JOIN doctor_restrictions dr ON dr.doctor_id = d.id WHERE dr.end_date >= CURRENT_DATE ORDER BY dr.end_date",
        category="availability",
        description="Restricciones activas de médicos",
    ),
    SQLExample(
        nl_query="comparativa de servicios entre enero y febrero",
        sql="SELECT c.month, COUNT(ca.id) AS total FROM calendar_assignments ca JOIN calendar_versions cv ON ca.calendar_version_id = cv.id JOIN calendars c ON cv.calendar_id = c.id WHERE c.year = EXTRACT(YEAR FROM CURRENT_DATE) AND c.month IN (1, 2) GROUP BY c.month ORDER BY c.month",
        category="analytics",
        description="Comparativa mensual de servicios",
    ),
    SQLExample(
        nl_query="medicos que tienen email registrado",
        sql="SELECT name, email FROM doctors WHERE email IS NOT NULL AND email != '' ORDER BY name",
        category="listing",
        description="Médicos con email",
    ),
    SQLExample(
        nl_query="ultima mision programada",
        sql="SELECT mission_date, location, description, status FROM mission_assignments WHERE deleted_at IS NULL ORDER BY mission_date DESC LIMIT 1",
        category="mission",
        description="Última misión programada",
    ),
    SQLExample(
        nl_query="servicios por dia de la semana",
        sql="SELECT EXTRACT(DOW FROM service_date) AS day_of_week, COUNT(*) AS total FROM calendar_assignments GROUP BY EXTRACT(DOW FROM service_date) ORDER BY day_of_week",
        category="analytics",
        description="Distribución de servicios por día",
    ),
    SQLExample(
        nl_query="medicos nuevos este ano",
        sql="SELECT name, created_at FROM doctors WHERE EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE) ORDER BY created_at DESC",
        category="listing",
        description="Médicos registrados recientemente",
    ),
    SQLExample(
        nl_query="quien tiene mas servicios en urgencias",
        sql="SELECT d.name, COUNT(ca.id) AS total FROM doctors d JOIN calendar_assignments ca ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE sa.display_name ILIKE '%urgencia%' GROUP BY d.name ORDER BY total DESC LIMIT 5",
        category="ranking",
        description="Top en área de urgencias",
    ),
    SQLExample(
        nl_query="calendarios aprobados vs borrador",
        sql="SELECT status, COUNT(*) AS total FROM calendars GROUP BY status",
        category="calendar",
        description="Estadísticas de estados de calendario",
    ),
    SQLExample(
        nl_query="medicos con objetivo mensual de 5 servicios",
        sql="SELECT name, monthly_service_target FROM doctors WHERE monthly_service_target = 5 ORDER BY name",
        category="filter",
        description="Filtro por objetivo de servicios",
    ),
    SQLExample(
        nl_query="asignaciones manuales del mes pasado",
        sql="SELECT d.name, ca.service_date, sa.display_name AS area FROM calendar_assignments ca JOIN doctors d ON ca.doctor_id = d.id JOIN service_areas sa ON ca.service_area_id = sa.id WHERE ca.assignment_source = 'manual' AND ca.service_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AND ca.service_date < DATE_TRUNC('month', CURRENT_DATE) ORDER BY ca.service_date",
        category="history",
        description="Asignaciones manuales recientes",
    ),
    SQLExample(
        nl_query="doctores que cubren mas de un area",
        sql="SELECT d.name, COUNT(daa.service_area_id) AS area_count FROM doctors d JOIN doctor_allowed_areas daa ON daa.doctor_id = d.id GROUP BY d.name HAVING COUNT(daa.service_area_id) > 1 ORDER BY area_count DESC",
        category="analytics",
        description="Médicos polivalentes",
    ),
    SQLExample(
        nl_query="cantidad de misiones por mes este ano",
        sql="SELECT EXTRACT(MONTH FROM mission_date) AS month, COUNT(*) AS total FROM mission_assignments WHERE deleted_at IS NULL AND EXTRACT(YEAR FROM mission_date) = EXTRACT(YEAR FROM CURRENT_DATE) GROUP BY EXTRACT(MONTH FROM mission_date) ORDER BY month",
        category="mission",
        description="Misiones por mes",
    ),
    SQLExample(
        nl_query="medicos con numero de telefono",
        sql="SELECT name, whatsapp_phone FROM doctors WHERE whatsapp_phone IS NOT NULL AND whatsapp_phone != '' ORDER BY name",
        category="listing",
        description="Médicos con teléfono registrado",
    ),
    SQLExample(
        nl_query="servicios duplicados mismo medico misma fecha",
        sql="SELECT doctor_id, service_date, COUNT(*) AS cnt FROM calendar_assignments GROUP BY doctor_id, service_date HAVING COUNT(*) > 1",
        category="data_quality",
        description="Detección de duplicados",
    ),
    SQLExample(
        nl_query="historial de cambios de un medico",
        sql="SELECT ae.action_type, ae.occurred_at, ae.details FROM audit_events ae WHERE ae.entity_type = 'doctor' AND ae.entity_id = :doctor_id ORDER BY ae.occurred_at DESC LIMIT 20",
        category="audit",
        description="Auditoría por médico",
    ),
    SQLExample(
        nl_query="areas de servicio sin usar en el ultimo trimestre",
        sql="SELECT sa.code, sa.display_name FROM service_areas sa WHERE NOT EXISTS (SELECT 1 FROM calendar_assignments ca WHERE ca.service_area_id = sa.id AND ca.service_date >= CURRENT_DATE - INTERVAL '3 months')",
        category="gap",
        description="Áreas inactivas recientemente",
    ),
    SQLExample(
        nl_query="medicos ordenados por fecha de creacion",
        sql="SELECT name, created_at FROM doctors ORDER BY created_at DESC LIMIT 20",
        category="listing",
        description="Médicos más recientes",
    ),
]


def _examples_from_registry() -> list[SQLExample]:
    """Convert DEFAULT_QUERY_TYPES into SQLExample objects."""
    examples = []
    for entry in DEFAULT_QUERY_TYPES:
        qt = entry["query_type"]
        sql = entry["sql_template"]
        desc = entry.get("description", "")
        # Generate 1-2 natural-language variants per query type
        examples.append(
            SQLExample(
                nl_query=desc,
                sql=sql,
                category=qt,
                description=desc,
            )
        )
    return examples


def main() -> int:
    store = ExampleStore()
    print(f"Store opened. Current count: {store.count()}")

    # Clear existing (optional — comment out to append instead)
    store.clear()
    print("Cleared existing examples.")

    registry_examples = _examples_from_registry()
    all_examples = registry_examples + _SYNTHETIC_EXAMPLES

    ids = store.add(all_examples)
    print(f"Added {len(ids)} examples. Store count: {store.count()}")

    # Quick sanity check
    sample = store.search("cuantos medicos hay", k=3)
    print(f"\nSample search 'cuantos medicos hay' → {len(sample)} results:")
    for ex in sample:
        print(f"  - {ex.nl_query[:60]}...")

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
