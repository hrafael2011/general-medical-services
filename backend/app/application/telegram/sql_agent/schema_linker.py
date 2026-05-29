"""SchemaLinker — reduces the full DB schema to only tables/columns relevant to the user query.

This cuts token usage and improves LLM accuracy by removing distracting tables.
"""

from __future__ import annotations

import re
from typing import Any


# Keywords that hint at which tables are relevant
_TABLE_KEYWORDS: dict[str, list[str]] = {
    "doctors": ["medico", "medicos", "doctor", "doctores", "personal", "médico", "médicos"],
    "doctor_allowed_areas": ["area permitida", "areas permitidas", "puede cubrir"],
    "calendars": ["calendario", "calendarios", "mes", "año", "semana"],
    "calendar_versions": ["version", "versiones", "borrador", "aprobado"],
    "calendar_assignments": ["asignacion", "asignaciones", "servicio", "servicios", "turno", "turnos"],
    "unresolved_gaps": ["hueco", "huecos", "sin cubrir", "falta"],
    "doctor_availability": ["disponibilidad", "disponible", "no disponible"],
    "doctor_restrictions": ["restriccion", "restricciones", "baja", "limitacion"],
    "mission_assignments": ["mision", "misiones", "operativo"],
    "mission_participants": ["participante", "participantes", "mision"],
    "mission_candidate_rankings": ["ranking", "candidato", "candidatos", "idoneidad"],
    "mission_candidate_ranking_entries": ["puntaje", "score", "ranking"],
    "service_areas": ["area", "areas", "urgencias", "pista", "uci", "consulta"],
    "ranks": ["rango", "rangos", "grado", "grados", "sargento", "cabo", "pasante", "contrata"],
    "departments": ["departamento", "departamentos", "cirugia", "pediatria"],
    "deactivation_reasons": ["baja", "razon", "motivo"],
    "notifications": ["notificacion", "notificaciones", "mensaje"],
}

# Column keywords that are commonly referenced
_COLUMN_KEYWORDS: dict[str, list[str]] = {
    "sex": ["sexo", "hombre", "mujer", "masculino", "femenino"],
    "status": ["estado", "aprobado", "borrador", "pendiente"],
    "service_date": ["fecha", "dia"],
    "name": ["nombre"],
    "rank": ["rango", "grado"],
    "department": ["departamento"],
}


class SchemaLinker:
    """Reduces schema scope based on the user's question."""

    def __init__(self, full_schema: str) -> None:
        self.full_schema = full_schema

    def reduce(self, user_text: str) -> str:
        """Return a reduced schema containing only likely-relevant tables.

        Uses a fast keyword heuristic. If no tables match, falls back to the
        full schema so the LLM still has a chance.
        """
        normalized = user_text.lower()
        relevant_tables = self._detect_relevant_tables(normalized)

        if not relevant_tables:
            return self.full_schema

        return self._extract_tables(relevant_tables)

    def _detect_relevant_tables(self, text: str) -> set[str]:
        tables: set[str] = set()
        for table, keywords in _TABLE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    tables.add(table)
                    break

        # Also add related tables via FK relationships (simple heuristics)
        if "doctors" in tables:
            tables.update({"ranks", "departments", "doctor_allowed_areas"})
        if "calendar_assignments" in tables or "unresolved_gaps" in tables:
            tables.update({"calendars", "calendar_versions", "service_areas", "doctors"})
        if "mission_assignments" in tables or "mission_participants" in tables:
            tables.update({"doctors", "mission_candidate_rankings", "mission_candidate_ranking_entries"})

        return tables

    def _extract_tables(self, table_names: set[str]) -> str:
        """Parse the full schema text and keep only the selected tables."""
        lines: list[str] = []
        keep = False
        for line in self.full_schema.splitlines():
            if line.startswith("TABLE "):
                table_name = line[6:].split(":")[0].strip()
                keep = table_name in table_names
            if keep:
                lines.append(line)
        return "\n".join(lines)
