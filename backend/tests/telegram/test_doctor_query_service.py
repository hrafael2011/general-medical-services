"""Filtro por nombre en DoctorQueryService — la causa del cluster de 41 resultados."""
import pytest

from backend.app.application.telegram.doctor_query_service import DoctorQueryService


class TestNameFilterFromResolved:
    def test_doctor_dict_becomes_name_filter(self):
        resolved = {"doctor": {"id": "uuid-1", "name": "ACOSTA RAMOS"}}
        filters = DoctorQueryService._filters_from_resolved(resolved)
        assert filters["doctor_name"] == "ACOSTA RAMOS"

    def test_doctor_name_string_becomes_name_filter(self):
        resolved = {"doctor_name": "Acosta"}
        filters = DoctorQueryService._filters_from_resolved(resolved)
        assert filters["doctor_name"] == "Acosta"

    def test_other_filters_are_kept(self):
        resolved = {
            "doctor": {"id": "uuid-1", "name": "ACOSTA RAMOS"},
            "rank": {"normalized_name": "Cabo"},
            "sex": "F",
        }
        filters = DoctorQueryService._filters_from_resolved(resolved)
        assert filters["doctor_name"] == "ACOSTA RAMOS"
        assert filters["rank"] == "Cabo"
        assert filters["sex"] == ["F"]


class TestNameCondition:
    def test_name_filter_adds_ilike_condition(self):
        service = object.__new__(DoctorQueryService)
        conditions = service._base_conditions({"doctor_name": "ACOSTA"})
        rendered = [str(c) for c in conditions]
        # La condición de nombre debe estar presente...
        assert any("lower(doctors.name)" in r.lower() for r in rendered), rendered
        # ...y el valor debe viajar parametrizado (nunca interpolado en el SQL).
        bound = [v for c in conditions for v in c.compile().params.values()]
        assert any("acosta" in str(v).lower() for v in bound), bound

    def test_empty_filters_keep_base_conditions_only(self):
        service = object.__new__(DoctorQueryService)
        conditions = service._base_conditions({})
        assert len(conditions) == 2  # active + service_active


def _seed_doctor(session, *, doctor_id: str, name: str, sex: str = "male"):
    """Siembra un médico con los campos mínimos no nulables del modelo."""
    from datetime import UTC, datetime

    from backend.app.infrastructure.db.models.doctors import DoctorModel

    now = datetime.now(UTC)
    doctor = DoctorModel(
        id=doctor_id,
        name=name,
        normalized_name=name,
        sex=sex,
        whatsapp_phone="000-000-0000",
        active=True,
        service_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(doctor)
    return doctor


class TestExecuteResolvesName:
    def test_search_by_surname_filters_rows(self, db_session):
        """Con médicos sembrados, «Acosta» debe devolver solo filas que lo contienen."""
        from backend.app.infrastructure.db.models.doctors import DoctorModel

        # El apellido buscado tiene que ser la ÚLTIMA palabra del nombre:
        # así lo indexa EntityResolver.pre_process.
        _seed_doctor(db_session, doctor_id="d-1", name="PEDRO PEREZ ACOSTA")
        _seed_doctor(db_session, doctor_id="d-2", name="LUIS GARCIA")
        _seed_doctor(db_session, doctor_id="d-3", name="ANA MARTINEZ", sex="female")
        db_session.flush()

        service = DoctorQueryService(db_session)
        result = service.execute("Busca al medico Acosta", {})

        assert result is not None, "execute debe producir un resultado"
        rows = (result.tool_result or {}).get("data", {}).get("rows", [])
        assert rows, "no debe devolver vacío si hay un médico con ese apellido"
        assert all("acosta" in r.get("name", "").lower() for r in rows)
        assert len(rows) < db_session.query(DoctorModel).count()

    def test_search_by_other_surname_returns_only_that_doctor(self, db_session):
        """Un apellido distinto no debe arrastrar al resto del listado."""
        from backend.app.infrastructure.db.models.doctors import DoctorModel

        _seed_doctor(db_session, doctor_id="d-1", name="PEDRO PEREZ ACOSTA")
        _seed_doctor(db_session, doctor_id="d-2", name="LUIS GARCIA")
        db_session.flush()

        service = DoctorQueryService(db_session)
        result = service.execute("Busca al medico Garcia", {})

        assert result is not None
        rows = (result.tool_result or {}).get("data", {}).get("rows", [])
        assert len(rows) == 1, rows
        assert "garcia" in rows[0]["name"].lower()

    def test_unknown_name_says_not_found_explicitly(self, db_session):
        """Un nombre pedido sin coincidencias debe decirlo, no devolver nada mudo."""
        _seed_doctor(db_session, doctor_id="d-1", name="PEDRO PEREZ ACOSTA")
        db_session.flush()

        service = DoctorQueryService(db_session)
        result = service.execute("Busca al medico Zzzz", {"doctor_name": "Zzzz"})

        assert result is not None
        assert "no encontr" in result.response_text.lower(), result.response_text
        assert "zzzz" in result.response_text.lower(), result.response_text


# `TestSexValidationNormalized` vive en la Fase 2 (normalización de sexo):
# hasta que el normalizador exista, esas dos pruebas fallan por diseño.
