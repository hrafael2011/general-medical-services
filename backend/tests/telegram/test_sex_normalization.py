"""Normalización de valores de sexo — «femenino»/«M»/«female» deben ser lo mismo."""
import pytest

from backend.app.application.telegram.entity_resolver import normalize_sex_value


@pytest.mark.parametrize(
    "raw",
    ["F", "f", "female", "Female", "femenino", "femenina", "femeninos", "mujer", "mujeres"],
)
def test_female_values_normalize_to_F(raw):
    assert normalize_sex_value(raw) == "F"


@pytest.mark.parametrize(
    "raw",
    ["M", "m", "male", "Male", "masculino", "masculinos", "hombre", "hombres", "varon", "varones"],
)
def test_male_values_normalize_to_M(raw):
    assert normalize_sex_value(raw) == "M"


@pytest.mark.parametrize("raw", [None, "", "otra cosa", 3])
def test_unknown_values_are_ignored(raw):
    assert normalize_sex_value(raw) is None


def test_mujer_is_not_read_as_masculino():
    """«mujer» empieza por 'm': un matcheo por prefijo lo contaría como masculino."""
    assert normalize_sex_value("mujer") == "F"
    assert normalize_sex_value("mujeres") == "F"


class TestSemanticLayerSexFilter:
    def _resolver(self):
        from backend.app.application.telegram.semantic_layer.resolver import (
            SemanticLayerResolver,
        )

        return object.__new__(SemanticLayerResolver)

    def test_femenino_becomes_F_filter(self):
        filters = self._resolver()._extract_common_filters({"sex": "femenino"})
        assert len(filters) == 1
        assert filters[0].field == "sex"
        assert filters[0].value == "F"

    def test_list_of_sex_values_normalizes_each(self):
        filters = self._resolver()._extract_common_filters({"sex": ["M", "female"]})
        assert len(filters) == 2
        assert {f.value for f in filters} == {"M", "F"}


class TestSexWhereClause:
    """La BD guarda 'male'/'female'; el filtro llega como 'M'/'F'.

    Sin traducir en el WHERE, el filtro normalizado no encuentra nada: el
    arreglo de arriba y éste son una sola unidad.
    """

    def _build(self, value):
        from backend.app.application.telegram.semantic_layer.definitions import (
            _build_where,
        )
        from backend.app.application.telegram.semantic_layer.models import Filter

        return _build_where([Filter(field="sex", operator="eq", value=value)])

    def test_female_covers_both_representations(self):
        sql, params = self._build("F")
        assert "lower(d.sex)" in sql.lower(), sql
        assert set(params.values()) == {"f", "female"}, params

    def test_male_covers_both_representations(self):
        sql, params = self._build("M")
        assert set(params.values()) == {"m", "male"}, params

    def test_unknown_value_falls_back_to_literal(self):
        """Un valor que no es de sexo no debe romper: se compara tal cual."""
        sql, params = self._build("otro")
        assert set(params.values()) == {"otro"}, params

    def test_rank_where_uses_sql_expression_not_key(self):
        """Protege el arreglo de 5950a0a: `r.name`, nunca la clave `rank`."""
        from backend.app.application.telegram.semantic_layer.definitions import (
            _build_where,
        )
        from backend.app.application.telegram.semantic_layer.models import Filter

        sql, _ = _build_where([Filter(field="rank", operator="eq", value="Cabo")])
        assert "r.name" in sql.lower(), sql
        assert "rank =" not in sql.lower(), sql
