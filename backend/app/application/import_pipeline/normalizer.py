"""
Pure-Python normalizers and classifiers for legacy import data.
No DB dependencies — all functions are stateless transformations.
"""

import re
import unicodedata

# ── Area normalization ──────────────────────────────────────────────────────

AREA_ALIASES: dict[str, str] = {
    "EMERGENCIA": "emergencia",
    "EMERG": "emergencia",
    "EMERGENCIAS": "emergencia",
    "PISTA": "pista",
    "PISTA AEREA": "pista",
    "DISPONIBLE": "disponible",
    "MEDICO DISPONIBLE": "disponible",
    "DISPONIBLES": "disponible",
    "DISP": "disponible",
}

def normalize_area(raw: str) -> tuple[str | None, float]:
    """Return (canonical_area, confidence). Returns (None, 0.0) if not recognized."""
    key = raw.strip().upper()
    if key in AREA_ALIASES:
        return AREA_ALIASES[key], 1.0
    # partial match
    for alias, canonical in AREA_ALIASES.items():
        if alias in key or key in alias:
            return canonical, 0.8
    return None, 0.0


# ── Name normalization ──────────────────────────────────────────────────────

def normalize_name(raw: str) -> str:
    """
    Uppercase, strip accents, collapse whitespace, strip punctuation except hyphens.
    Used for identity matching — not for display.
    """
    if not raw:
        return ""
    # NFD decompose → strip combining chars (accents)
    nfkd = unicodedata.normalize("NFD", raw)
    no_accents = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    # uppercase, collapse spaces, strip trailing/leading
    cleaned = re.sub(r"[^\w\s\-]", " ", no_accents.upper())
    return re.sub(r"\s+", " ", cleaned).strip()


# ── Marker parsing ──────────────────────────────────────────────────────────

# Return type for parse_marker: {"type": str, "value": Any, "confidence": float, "requires_review": bool}

def parse_marker(raw: str) -> dict | None:
    """
    Recognize free-text legacy markers and return a classification dict.
    Returns None if not recognized.

    Types: "license", "restriction", "monthly_limit", "monthly_target", "fixed_availability"
    """
    text = raw.strip().upper()

    if text in ("LICENCIA", "LICENCIA MEDICA", "LICENCIAS", "LICENCIAS MEDICAS"):
        return {"type": "license", "value": "medical_license", "confidence": 0.95, "requires_review": False}

    if text in ("EMBARAZADA", "EMBARAZO"):
        return {"type": "restriction", "value": "pregnancy", "confidence": 0.95, "requires_review": False}

    if text in ("NO REALIZA SERVICIO", "NO REALIZA SERVICIOS", "NRS"):
        return {"type": "restriction", "value": "no_service", "confidence": 0.95, "requires_review": False}

    if text in ("N/A", "NA", "-", ""):
        return {"type": "restriction", "value": "not_applicable", "confidence": 0.7, "requires_review": True}

    if text in ("FIJO", "FIJOS", "FIJA", "FIJAS"):
        return {"type": "fixed_availability", "value": True, "confidence": 0.9, "requires_review": False}

    # Monthly service limit: "1 SER AL MES", "1 SERV AL MES", "2 SERV AL MES" etc.
    m = re.match(r"^(\d+)\s*(?:SER|SERV|SERVICIO|SERVICIOS)\s+AL\s+MES$", text)
    if m:
        n = int(m.group(1))
        return {"type": "monthly_limit", "value": n, "confidence": 0.9, "requires_review": False}

    # Monthly target/max: "3 AL MES", "4 AL MES", "4 SERVICIOS AL MES"
    m = re.match(r"^(\d+)\s*(?:AL\s+MES|SERVICIOS?\s+AL\s+MES)$", text)
    if m:
        n = int(m.group(1))
        return {"type": "monthly_target", "value": n, "confidence": 0.75, "requires_review": True}

    return None


# ── Rank abbreviation normalization ────────────────────────────────────────

RANK_ALIASES: dict[str, str] = {
    "GRAL": "General",
    "GENERAL": "General",
    "CNEL": "Coronel",
    "CORONEL": "Coronel",
    "TCNEL": "Teniente Coronel",
    "TTE CNEL": "Teniente Coronel",
    "TENIENTE CORONEL": "Teniente Coronel",
    "MAYOR": "Mayor",
    "MY": "Mayor",
    "CAPITAN": "Capitán",
    "CPT": "Capitán",
    "TTE": "Teniente",
    "TENIENTE": "Teniente",
    "SUBTENIENTE": "Subteniente",
    "SUBTTE": "Subteniente",
    "MGM": "Médico General Militar",
    "MG": "Médico General",
    "DR": "Doctor",
    "DRA": "Doctora",
}

def normalize_rank(raw: str) -> tuple[str | None, float]:
    """Return (normalized_rank_name, confidence). Returns (None, 0.0) if not recognized."""
    key = raw.strip().upper().rstrip(".")
    if key in RANK_ALIASES:
        return RANK_ALIASES[key], 1.0
    for alias, canonical in RANK_ALIASES.items():
        if key.startswith(alias):
            return canonical, 0.85
    return None, 0.0


# ── Generic field classifier ────────────────────────────────────────────────

def classify_cell(raw_value: str) -> dict:
    """
    Attempt to classify a raw cell value into a domain field.
    Returns:
        {
            "field": str | None,       # e.g. "service_area", "marker", "doctor_name", "rank"
            "parsed_value": Any,
            "confidence": float,
            "requires_review": bool,
            "parser_rule": str,
        }
    """
    if not raw_value or not raw_value.strip():
        return {"field": None, "parsed_value": None, "confidence": 0.0, "requires_review": False, "parser_rule": "empty"}

    # Try area
    area, conf = normalize_area(raw_value)
    if area and conf >= 0.8:
        return {"field": "service_area", "parsed_value": area, "confidence": conf, "requires_review": conf < 1.0, "parser_rule": "area_alias"}

    # Try marker
    marker = parse_marker(raw_value)
    if marker:
        return {"field": "marker", "parsed_value": marker, "confidence": marker["confidence"], "requires_review": marker["requires_review"], "parser_rule": "marker_text"}

    # Try rank
    rank, conf = normalize_rank(raw_value)
    if rank and conf >= 0.85:
        return {"field": "rank", "parsed_value": rank, "confidence": conf, "requires_review": False, "parser_rule": "rank_alias"}

    # Numeric — possibly a date day or count
    if raw_value.strip().isdigit():
        n = int(raw_value.strip())
        if 1 <= n <= 31:
            return {"field": "day_number", "parsed_value": n, "confidence": 0.6, "requires_review": True, "parser_rule": "numeric_day"}
        return {"field": "numeric", "parsed_value": n, "confidence": 0.5, "requires_review": True, "parser_rule": "numeric"}

    # Looks like a name: 2+ words, mostly letters
    words = raw_value.strip().split()
    if len(words) >= 2 and all(re.match(r"^[A-ZÁÉÍÓÚÜÑa-záéíóúüñ'\-\.]+$", w) for w in words):
        return {"field": "doctor_name", "parsed_value": raw_value.strip(), "confidence": 0.6, "requires_review": True, "parser_rule": "name_heuristic"}

    return {"field": "unknown", "parsed_value": raw_value.strip(), "confidence": 0.3, "requires_review": True, "parser_rule": "unrecognized"}
