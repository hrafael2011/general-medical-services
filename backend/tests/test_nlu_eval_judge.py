"""El juez decide el porcentaje: su lógica tiene que ser aburrida y correcta."""
import pytest

from backend.scripts.nlu_eval.judge_243 import is_degraded, match


class TestDegradedNeverPasses:
    @pytest.mark.parametrize(
        "response",
        [
            "Error de configuración del servicio de IA.",
            "El servicio de IA no está disponible en este momento.",
            "El servicio de IA respondió con un error.",
        ],
    )
    def test_api_failure_is_never_a_pass(self, response):
        """Aunque el turno esté sin anotar, un fallo de API no es un acierto."""
        assert is_degraded(response) is True
        assert match({"matcher": "any", "expected": None}, response) is False

    def test_normal_response_is_not_degraded(self):
        assert is_degraded("Resultado: total: 40") is False


class TestNumberMatcher:
    def test_exact_number_passes(self):
        assert match({"matcher": "number", "expected": 40}, "Resultado: total: 40") is True

    def test_wrong_number_fails(self):
        assert match({"matcher": "number", "expected": 40}, "Resultado: total: 39") is False

    def test_no_number_at_all_fails(self):
        assert match({"matcher": "number", "expected": 40}, "No se encontraron resultados.") is False

    def test_first_integer_is_the_one_compared(self):
        """«Se encontraron 11 resultados. Los primeros: 1. ...» cuenta 11."""
        response = "Se encontraron 11 resultados. Los primeros:\n1. ANA | female"
        assert match({"matcher": "number", "expected": 11}, response) is True


class TestContainsMatcher:
    def test_case_insensitive(self):
        assert match({"matcher": "contains", "expected": "no existe"},
                     "NO EXISTE un calendario para 06/2026.") is True

    def test_absent_text_fails(self):
        assert match({"matcher": "contains", "expected": "No existe"},
                     "El calendario de 08/2026 existe con estado: partial.") is False


class TestAnyMatcher:
    def test_any_passes_anything_not_degraded(self):
        assert match({"matcher": "any", "expected": None}, "lo que sea") is True

    def test_unannotated_turn_counts_as_any(self):
        assert match({}, "lo que sea") is True


class TestZeroExpectation:
    """«No se encontraron resultados» es el cero dicho con palabras."""

    @pytest.mark.parametrize(
        "response",
        [
            "No se encontraron resultados.",
            "No se encontraron resultados para esa consulta.",
            "No hay médicos con ese rango.",
        ],
    )
    def test_empty_response_satisfies_zero(self, response):
        assert match({"matcher": "number", "expected": 0}, response) is True

    def test_empty_response_does_not_satisfy_nonzero(self):
        assert match({"matcher": "number", "expected": 11}, "No se encontraron resultados.") is False

    def test_zero_still_accepts_an_explicit_zero(self):
        assert match({"matcher": "number", "expected": 0}, "Resultado: total: 0") is True
