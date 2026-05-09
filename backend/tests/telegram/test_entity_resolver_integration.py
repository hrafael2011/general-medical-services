"""Integration tests for EntityResolver with real database."""

import uuid
from datetime import UTC, datetime

from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.infrastructure.db.models.catalogs import (
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
)
from backend.app.infrastructure.db.models.doctors import DoctorModel


def _seed_for_resolver(db_session):
    """Seed minimal data for EntityResolver integration tests."""
    # Areas
    emerg = ServiceAreaModel(
        id=str(uuid.uuid4()),
        code="EMERG",
        display_name="Emergencia",
        load_weight=3,
        active=True,
        required_for_daily_coverage=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    pista = ServiceAreaModel(
        id=str(uuid.uuid4()),
        code="PISTA",
        display_name="Pista",
        load_weight=2,
        active=True,
        required_for_daily_coverage=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([emerg, pista])

    # Ranks
    cabo = RankModel(
        id=str(uuid.uuid4()),
        name="Cabo",
        normalized_name="cabo",
        abbreviation="CBO",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    sargento = RankModel(
        id=str(uuid.uuid4()),
        name="Sargento",
        normalized_name="sargento",
        abbreviation="SGT",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add_all([cabo, sargento])

    # Department
    dept = DepartmentModel(
        id=str(uuid.uuid4()),
        name="Medicina General",
        normalized_name="medicina general",
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(dept)
    db_session.flush()

    # Doctors with searchable names (flush first so FK refs exist)
    doctors = [
        DoctorModel(
            id=str(uuid.uuid4()),
            name="Dr. Garcia Perez",
            normalized_name="dr. garcia perez",
            sex="male",
            active=True,
            service_active=True,
            availability_mode="variable",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            rank_id=cabo.id,
            department_id=dept.id,
            whatsapp_phone=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        DoctorModel(
            id=str(uuid.uuid4()),
            name="Dr. Garcia Lopez",
            normalized_name="dr. garcia lopez",
            sex="male",
            active=True,
            service_active=True,
            availability_mode="variable",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            rank_id=sargento.id,
            department_id=dept.id,
            whatsapp_phone=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
        DoctorModel(
            id=str(uuid.uuid4()),
            name="Dra. Ana Martinez",
            normalized_name="dra. ana martinez",
            sex="female",
            active=True,
            service_active=True,
            availability_mode="variable",
            participa_misiones=True,
            monthly_service_target=3,
            monthly_service_max=3,
            monthly_service_limit_mode="warn_only",
            rank_id=cabo.id,
            department_id=dept.id,
            whatsapp_phone=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    ]
    for d in doctors:
        db_session.add(d)
    db_session.flush()

    return {
        "areas": [emerg, pista],
        "ranks": [cabo, sargento],
        "doctors": doctors,
    }


class TestEntityResolverIntegration:
    """Integration tests for EntityResolver with real DB."""

    # ------------------------------------------------------------------
    # Doctor resolution
    # ------------------------------------------------------------------

    def test_resolve_doctor_by_partial_name(self, db_session) -> None:
        """Partial name 'Garcia' with 2 matches returns both."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_doctor("Garcia")
        assert len(result) == 2

    def test_resolve_doctor_unique_match(self, db_session) -> None:
        """Unique name 'Martinez' resolves to one doctor."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_doctor("Martinez")
        assert len(result) == 1
        assert result[0]["name"] == "Dra. Ana Martinez"

    def test_resolve_doctor_not_found(self, db_session) -> None:
        """Non-existent name returns empty list."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_doctor("Fernandez")
        assert result == []

    # ------------------------------------------------------------------
    # Area resolution
    # ------------------------------------------------------------------

    def test_resolve_area_by_display_name(self, db_session) -> None:
        """Case-insensitive area display_name match."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_area("emergencia")
        assert len(result) == 1
        assert result[0]["display_name"] == "Emergencia"

    def test_resolve_area_by_code(self, db_session) -> None:
        """Area code can also be used as query (falls through to display_name)."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_area("PISTA")
        assert len(result) == 1
        # resolve_area matches on display_name; "PISTA".lower() is in "Pista".lower()
        assert result[0]["code"] == "PISTA"

    # ------------------------------------------------------------------
    # Rank resolution
    # ------------------------------------------------------------------

    def test_resolve_rank_by_normalized_name(self, db_session) -> None:
        """Rank normalized_name match."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.resolve_rank("cabo")
        assert len(result) == 1
        assert result[0]["name"] == "Cabo"

    # ------------------------------------------------------------------
    # Pre-processing
    # ------------------------------------------------------------------

    def test_pre_process_integrates_all_resolvers(self, db_session) -> None:
        """pre_process scans message and returns hints with resolved/ambiguous."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.pre_process(
            "cuantos servicios tiene Garcia en emergencia en mayo"
        )
        assert "hints" in result
        assert isinstance(result["hints"], str)
        assert "resolved" in result
        assert "ambiguous" in result

    def test_pre_process_with_date(self, db_session) -> None:
        """pre_process detects date expressions like 'manana'."""
        _seed_for_resolver(db_session)
        resolver = EntityResolver(session=db_session)
        result = resolver.pre_process("medicos que trabajan manana en pista")
        assert "hints" in result
        assert isinstance(result["hints"], str)
        # Should contain date info
        assert result["hints"] != ""
