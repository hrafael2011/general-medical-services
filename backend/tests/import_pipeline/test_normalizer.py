"""
Pure-Python unit tests for import_pipeline/normalizer.py.
No DB or fixtures needed — all functions are stateless.
"""


from backend.app.application.import_pipeline.normalizer import (
    classify_cell,
    normalize_area,
    normalize_name,
    parse_marker,
)

# ---------------------------------------------------------------------------
# normalize_area
# ---------------------------------------------------------------------------


def test_normalize_area_exact() -> None:
    """Exact key 'EMERGENCIA' maps to ('emergencia', 1.0)."""
    area, conf = normalize_area("EMERGENCIA")
    assert area == "emergencia"
    assert conf == 1.0


def test_normalize_area_partial() -> None:
    """'EMERG' is an exact key in AREA_ALIASES so it maps to ('emergencia', 1.0)."""
    area, conf = normalize_area("EMERG")
    assert area == "emergencia"
    assert conf == 1.0


def test_normalize_area_unknown() -> None:
    """Unrecognized value returns (None, 0.0)."""
    area, conf = normalize_area("QUIROFANO")
    assert area is None
    assert conf == 0.0


def test_normalize_area_alias_pista() -> None:
    """'PISTA AEREA' is an exact key mapping to 'pista'."""
    area, conf = normalize_area("PISTA AEREA")
    assert area == "pista"
    assert conf == 1.0


def test_normalize_area_disponible() -> None:
    """'MEDICO DISPONIBLE' is an exact key mapping to 'disponible'."""
    area, conf = normalize_area("MEDICO DISPONIBLE")
    assert area == "disponible"
    assert conf == 1.0


# ---------------------------------------------------------------------------
# parse_marker
# ---------------------------------------------------------------------------


def test_parse_marker_licencia() -> None:
    """'LICENCIA MEDICA' → type='license'."""
    result = parse_marker("LICENCIA MEDICA")
    assert result is not None
    assert result["type"] == "license"


def test_parse_marker_embarazada() -> None:
    """'EMBARAZADA' → type='restriction', value='pregnancy'."""
    result = parse_marker("EMBARAZADA")
    assert result is not None
    assert result["type"] == "restriction"
    assert result["value"] == "pregnancy"


def test_parse_marker_no_realiza() -> None:
    """'NO REALIZA SERVICIO' → type='restriction', value='no_service'."""
    result = parse_marker("NO REALIZA SERVICIO")
    assert result is not None
    assert result["type"] == "restriction"
    assert result["value"] == "no_service"


def test_parse_marker_fijo() -> None:
    """'FIJO' → type='fixed_availability'."""
    result = parse_marker("FIJO")
    assert result is not None
    assert result["type"] == "fixed_availability"


def test_parse_marker_monthly_limit() -> None:
    """'1 SERV AL MES' → type='monthly_limit', value=1."""
    result = parse_marker("1 SERV AL MES")
    assert result is not None
    assert result["type"] == "monthly_limit"
    assert result["value"] == 1


def test_parse_marker_monthly_limit_alt() -> None:
    """'2 SER AL MES' → type='monthly_limit', value=2."""
    result = parse_marker("2 SER AL MES")
    assert result is not None
    assert result["type"] == "monthly_limit"
    assert result["value"] == 2


def test_parse_marker_monthly_target() -> None:
    """'3 AL MES' → type='monthly_target', value=3, requires_review=True."""
    result = parse_marker("3 AL MES")
    assert result is not None
    assert result["type"] == "monthly_target"
    assert result["value"] == 3
    assert result["requires_review"] is True


def test_parse_marker_unknown() -> None:
    """An unrecognized marker string returns None."""
    result = parse_marker("HOLA MUNDO")
    assert result is None


# ---------------------------------------------------------------------------
# normalize_name
# ---------------------------------------------------------------------------


def test_normalize_name_strips_accents() -> None:
    """Accented characters are stripped; result contains 'GARCIA LOPEZ'."""
    result = normalize_name("García López")
    assert "GARCIA" in result
    assert "LOPEZ" in result


def test_normalize_name_uppercase() -> None:
    """Input is converted to uppercase and punctuation is removed/replaced."""
    result = normalize_name("dr. pedro")
    assert result == result.upper()
    assert "DR" in result
    assert "PEDRO" in result


# ---------------------------------------------------------------------------
# classify_cell
# ---------------------------------------------------------------------------


def test_classify_cell_area() -> None:
    """'PISTA' is recognized as service_area."""
    result = classify_cell("PISTA")
    assert result["field"] == "service_area"


def test_classify_cell_marker() -> None:
    """'LICENCIA' is recognized as a marker."""
    result = classify_cell("LICENCIA")
    assert result["field"] == "marker"


def test_classify_cell_empty() -> None:
    """Empty string returns field=None."""
    result = classify_cell("")
    assert result["field"] is None


def test_classify_cell_name_heuristic() -> None:
    """Two-word all-letter string is classified as doctor_name."""
    result = classify_cell("Pedro Garcia")
    assert result["field"] == "doctor_name"
