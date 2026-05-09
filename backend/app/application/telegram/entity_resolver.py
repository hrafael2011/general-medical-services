"""EntityResolver — converts natural language references into real database entities."""

import logging
import re
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Date expression resolution
# ---------------------------------------------------------------------------

_MONTH_NAMES: dict[str, int] = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


class EntityResolver:
    """Resolves natural language references to database entities."""

    def __init__(self, session: Session | None = None) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Date resolution
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_date_expression(text: str) -> dict[str, Any] | None:
        """Parse a relative date expression and return a concrete value.

        Returns:
            A dict with a "type" key ("single_date", "date_range", "month",
            "month_year"), or None if no date found.
        """
        t = text.lower().strip()
        today = date.today()

        # "mañana" / "pasado mañana"
        if t in ("mañana", "manana"):
            tomorrow = today + timedelta(days=1)
            return {"type": "single_date", "value": tomorrow.strftime("%Y-%m-%d")}
        if t in ("pasado mañana", "pasado manana"):
            d = today + timedelta(days=2)
            return {"type": "single_date", "value": d.strftime("%Y-%m-%d")}

        # "hoy"
        if t == "hoy":
            return {"type": "single_date", "value": today.strftime("%Y-%m-%d")}

        # "ayer"
        if t == "ayer":
            yesterday = today - timedelta(days=1)
            return {"type": "single_date", "value": yesterday.strftime("%Y-%m-%d")}

        # "esta semana"
        if t == "esta semana":
            weekday = today.weekday()
            start = today - timedelta(days=weekday)
            end = start + timedelta(days=6)
            return {"type": "date_range", "start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}

        # "la próxima semana" / "la semana que viene"
        if t in ("la próxima semana", "la proxima semana", "la semana que viene", "próxima semana", "proxima semana"):
            weekday = today.weekday()
            next_monday = today - timedelta(days=weekday) + timedelta(days=7)
            return {"type": "date_range", "start": next_monday.strftime("%Y-%m-%d"), "end": (next_monday + timedelta(days=6)).strftime("%Y-%m-%d")}

        # "el mes pasado"
        if t == "el mes pasado":
            first_of_this_month = today.replace(day=1)
            last_of_last_month = first_of_this_month - timedelta(days=1)
            start = last_of_last_month.replace(day=1)
            return {"type": "date_range", "start": start.strftime("%Y-%m-%d"), "end": last_of_last_month.strftime("%Y-%m-%d")}

        # "este mes"
        if t == "este mes":
            first = today.replace(day=1)
            if first.month < 12:
                next_month = first.replace(month=first.month + 1)
            else:
                next_month = first.replace(year=first.year + 1, month=1)
            last = next_month - timedelta(days=1)
            return {"type": "date_range", "start": first.strftime("%Y-%m-%d"), "end": last.strftime("%Y-%m-%d")}

        # "el próximo mes" / "el mes que viene"
        if t in ("el próximo mes", "el proximo mes", "el mes que viene", "próximo mes", "proximo mes"):
            first_this = today.replace(day=1)
            if first_this.month < 12:
                first_next = first_this.replace(month=first_this.month + 1)
            else:
                first_next = first_this.replace(year=first_this.year + 1, month=1)
            if first_next.month < 12:
                last_next = first_next.replace(month=first_next.month + 1) - timedelta(days=1)
            else:
                last_next = first_next.replace(year=first_next.year + 1, month=1) - timedelta(days=1)
            return {"type": "date_range", "start": first_next.strftime("%Y-%m-%d"), "end": last_next.strftime("%Y-%m-%d")}

        # Named months: "abril", "enero", etc.
        if t in _MONTH_NAMES:
            month = _MONTH_NAMES[t]
            return {"type": "month", "month": month}

        # "abril 2026" → {"type": "month_year", "month": 4, "year": 2026}
        match = re.match(r"(\w+)\s+(\d{4})", t)
        if match:
            month_name = match.group(1)
            year = int(match.group(2))
            if month_name in _MONTH_NAMES:
                return {"type": "month_year", "month": _MONTH_NAMES[month_name], "year": year}

        return None

    # ------------------------------------------------------------------
    # Doctor resolution
    # ------------------------------------------------------------------

    def resolve_doctor(self, name: str) -> list[dict[str, Any]]:
        """Find doctors by name (case-insensitive ILIKE search)."""
        if self._session is None:
            return []
        from backend.app.infrastructure.repositories.doctors import DoctorRepository

        repo = DoctorRepository(self._session)
        all_docs = repo.list_service_active()
        name_lower = name.lower().strip()
        matches = [d for d in all_docs if name_lower in d.name.lower()]
        return [
            {"id": d.id, "name": d.name, "sex": d.sex, "availability_mode": d.availability_mode}
            for d in matches
        ]

    # ------------------------------------------------------------------
    # Area resolution
    # ------------------------------------------------------------------

    def resolve_area(self, name: str) -> list[dict[str, Any]]:
        """Find service areas by display_name (case-insensitive)."""
        if self._session is None:
            return []
        from backend.app.infrastructure.repositories.catalogs import CatalogRepository

        repo = CatalogRepository(self._session)
        areas = repo.list_service_areas()
        name_lower = name.lower().strip()
        matches = [a for a in areas if name_lower in a.display_name.lower()]
        return [
            {"id": m.id, "code": m.code, "display_name": m.display_name, "load_weight": float(m.load_weight)}
            for m in matches
        ]

    # ------------------------------------------------------------------
    # Rank resolution
    # ------------------------------------------------------------------

    def resolve_rank(self, name: str) -> list[dict[str, Any]]:
        """Find ranks by normalized_name (case-insensitive)."""
        if self._session is None:
            return []
        from backend.app.infrastructure.repositories.catalogs import CatalogRepository

        repo = CatalogRepository(self._session)
        all_ranks = repo.list_ranks()
        name_lower = name.lower().strip()
        matches = [r for r in all_ranks if name_lower in r.normalized_name.lower()]
        return [
            {"id": m.id, "name": m.name, "normalized_name": m.normalized_name}
            for m in matches
        ]

    # ------------------------------------------------------------------
    # Reference resolution for follow-ups
    # ------------------------------------------------------------------

    @staticmethod
    def resolve_reference(text: str, session_state: dict[str, Any] | None) -> int | None:
        """Resolve references like 'el segundo', 'el primero', 'el último'.

        Returns the index (0-based) into last_results, or None if not a reference.
        """
        if session_state is None:
            return None

        last_results = session_state.get("last_results") or []
        if not last_results:
            return None

        t = text.lower().strip()

        ordinal_map = {
            "primero": 0, "primer": 0, "primera": 0, "1": 0,
            "segundo": 1, "segunda": 1, "2": 1,
            "tercero": 2, "tercer": 2, "tercera": 2, "3": 2,
            "cuarto": 3, "cuarta": 3, "4": 3,
            "quinto": 4, "quinta": 4, "5": 4,
            "último": -1, "ultimo": -1, "última": -1, "ultima": -1,
        }

        for word, idx in ordinal_map.items():
            if word in t:
                if idx == -1:
                    return len(last_results) - 1
                if idx < len(last_results):
                    return idx
        return None

    # ------------------------------------------------------------------
    # Pre-processing: extract all entities from a user message
    # ------------------------------------------------------------------

    def pre_process(self, user_message: str) -> dict[str, Any]:
        """Extract and resolve all entities from a user message.

        Returns a dict with:
            resolved: dict of entity name → resolved value
            ambiguous: list of dicts with field, candidates, question
            hints: string to inject into the LLM system prompt
        """
        resolved: dict[str, Any] = {}
        ambiguous: list[dict[str, Any]] = []
        hints_parts: list[str] = []

        # Date expressions — scan the full message
        date_keywords = [
            "hoy", "ayer", "mañana", "manana", "pasado mañana", "pasado manana",
            "esta semana", "el mes pasado", "este mes",
            "la próxima semana", "la proxima semana", "la semana que viene",
            "el próximo mes", "el proximo mes", "el mes que viene",
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        msg_lower = user_message.lower()
        for kw in date_keywords:
            if kw in msg_lower:
                date_result = self.resolve_date_expression(kw)
                if date_result is not None:
                    resolved["date"] = date_result
                    dtype = date_result.get("type", "")
                    if dtype == "single_date":
                        hints_parts.append(f"date={date_result['value']}")
                    elif dtype == "date_range":
                        hints_parts.append(f"start={date_result['start']}, end={date_result['end']}")
                    elif dtype == "month":
                        hints_parts.append(f"month={date_result['month']}")
                    elif dtype == "month_year":
                        hints_parts.append(f"month={date_result['month']}, year={date_result['year']}")
                break

        # Doctor names — scan for known doctor surnames
        if self._session is not None:
            from backend.app.infrastructure.repositories.doctors import DoctorRepository
            doctor_repo = DoctorRepository(self._session)
            all_docs = doctor_repo.list_service_active()
            for doc in all_docs:
                parts = doc.name.lower().split()
                surname = parts[-1] if parts else ""
                if len(surname) >= 3 and re.search(rf"\b{re.escape(surname)}\b", msg_lower):
                    candidates = [d for d in all_docs if surname in d.name.lower()]
                    if len(candidates) == 1:
                        resolved["doctor"] = {"id": candidates[0].id, "name": candidates[0].name}
                        hints_parts.append(f"doctor_id={candidates[0].id}")
                    elif len(candidates) > 1:
                        ambiguous.append({
                            "field": "doctor",
                            "candidates": [{"id": d.id, "name": d.name} for d in candidates],
                            "question": f"Encontré más de un médico con el apellido {surname.title()}: "
                                        + ", ".join(f"{i+1}. {d.name}" for i, d in enumerate(candidates))
                                        + ". ¿Cuál deseas?",
                        })
                    break

        # Area detection
        if self._session is not None:
            from backend.app.infrastructure.repositories.catalogs import CatalogRepository
            catalog_repo = CatalogRepository(self._session)
            areas = catalog_repo.list_service_areas()
            for area in areas:
                if area.display_name.lower() in msg_lower or area.code.lower() in msg_lower:
                    resolved["area"] = {"id": area.id, "display_name": area.display_name}
                    hints_parts.append(f"area_id={area.id}")
                    break

        # Rank detection
        if self._session is not None:
            from backend.app.infrastructure.repositories.catalogs import CatalogRepository
            catalog_repo = CatalogRepository(self._session)
            ranks = catalog_repo.list_ranks()
            for rank in ranks:
                rank_words = rank.normalized_name.lower().split()
                if any(word in msg_lower for word in rank_words if len(word) >= 3):
                    resolved["rank"] = {"id": rank.id, "name": rank.name, "normalized_name": rank.normalized_name}
                    hints_parts.append(f"rank_id={rank.id}, rank_name='{rank.normalized_name}'")
                    break

        return {
            "resolved": resolved,
            "ambiguous": ambiguous,
            "hints": ", ".join(hints_parts) if hints_parts else "",
        }

    # ------------------------------------------------------------------
    # Post-processing: format results and store session context
    # ------------------------------------------------------------------

    def resolve_result(
        self,
        rows: list[dict[str, Any]],
        query_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich results and return session context for follow-ups."""
        return {
            "last_query_type": query_type,
            "last_params": params,
            "last_results": rows[:20],
        }
