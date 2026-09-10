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


class TestExecuteResolvesName:
    def test_search_by_surname_filters_rows(self, db_session):
        """Con médicos sembrados, «Acosta» debe devolver solo filas que lo contienen."""
        from backend.app.infrastructure.db.models.doctors import DoctorModel

        service = DoctorQueryService(db_session)
        result = service.execute("Busca al medico Acosta", {})

        if result is None:
            pytest.skip("execute devolvió None (¿no hay médicos sembrados?)")

        rows = (result.tool_result or {}).get("data", {}).get("rows", [])
        assert rows, "no debe devolver vacío si hay médicos"
        assert all("acosta" in r.get("name", "").lower() for r in rows)
        assert len(rows) < db_session.query(DoctorModel).count()


class TestSexValidationNormalized:
    def test_male_rows_pass_validation_for_M_filter(self):
        service = object.__new__(DoctorQueryService)
        result = service._validate_result_filters(
            rows=[{"sex": "male"}, {"sex": "M"}],
            filters={"sex": ["M"]},
            operation="list",
        )
        assert result["ok"] is True

    def test_female_row_fails_validation_for_M_filter(self):
        service = object.__new__(DoctorQueryService)
        result = service._validate_result_filters(
            rows=[{"sex": "female"}],
            filters={"sex": ["M"]},
            operation="list",
        )
        assert result["ok"] is False
