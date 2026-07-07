"""Tests for OrToolsEngine (CP-SAT model)."""
from types import SimpleNamespace
from backend.app.domain.calendars.cp_model import OrToolsEngine
from backend.app.domain.calendars.engine import GenerationContext
from backend.app.domain.calendars.scoring import AREA_WEIGHTS

_REQUIRED_AREAS = ["emergencia", "pista", "disponible"]
_YEAR, _MONTH = 2026, 2
_DAYS = 28
_TOTAL_SLOTS = _DAYS * 3


def _make_doctor(doc_id: str):
    return SimpleNamespace(id=doc_id, active=True, service_active=True)


def test_ortools_engine_single_doctor():
    """Single doctor fills 1 slot per day (28 assigned, 56 gaps)."""
    doc = _make_doctor("doc-1")
    ctx = GenerationContext(
        year=_YEAR, month=_MONTH,
        doctors=[doc],
        allowed_areas={"doc-1": _REQUIRED_AREAS},
        availability={},
        restrictions={},
        existing_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        required_areas=_REQUIRED_AREAS,
        area_weights=AREA_WEIGHTS,
        monthly_service_targets={"doc-1": 999},
        monthly_service_maxes={"doc-1": 999},
    )
    engine = OrToolsEngine()
    summary = engine.solve(ctx)
    assert summary.total_slots == _TOTAL_SLOTS
    assert summary.assigned_count == _DAYS
    assert summary.gap_count == _TOTAL_SLOTS - _DAYS


def test_ortools_engine_hard_block():
    """Hard block prevents assignment (0 assigned, all gaps)."""
    doc = _make_doctor("doc-1")
    import datetime
    block = SimpleNamespace(
        severity="hard_block",
        starts_at=datetime.datetime(2026, 1, 26, 0, 0, 0),
        ends_at=None,
    )
    ctx = GenerationContext(
        year=_YEAR, month=_MONTH,
        doctors=[doc],
        allowed_areas={"doc-1": _REQUIRED_AREAS},
        availability={},
        restrictions={"doc-1": [block]},
        existing_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        required_areas=_REQUIRED_AREAS,
        area_weights=AREA_WEIGHTS,
    )
    engine = OrToolsEngine()
    summary = engine.solve(ctx)
    assert summary.assigned_count == 0
    assert summary.gap_count == _TOTAL_SLOTS


def test_ortools_engine_monthly_max():
    """Monthly max limits total assignments per doctor."""
    doc = _make_doctor("doc-1")
    ctx = GenerationContext(
        year=_YEAR, month=_MONTH,
        doctors=[doc],
        allowed_areas={"doc-1": _REQUIRED_AREAS},
        availability={},
        restrictions={},
        existing_assignments=[],
        historical_assignments=[],
        mission_assignments=[],
        required_areas=_REQUIRED_AREAS,
        area_weights=AREA_WEIGHTS,
        monthly_service_maxes={"doc-1": 3},
        monthly_service_targets={"doc-1": 3},
    )
    engine = OrToolsEngine()
    summary = engine.solve(ctx)
    assert summary.assigned_count == 3
    assert summary.gap_count == _TOTAL_SLOTS - 3
    for r in summary.slot_results:
        if r.assigned_doctor_id is not None:
            assert r.assigned_doctor_id == "doc-1"
