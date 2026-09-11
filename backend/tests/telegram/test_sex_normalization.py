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
