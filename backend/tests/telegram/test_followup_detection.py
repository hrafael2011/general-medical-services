"""Detección de turnos de seguimiento — `_looks_like_followup`.

`_looks_like_followup` es la puerta de `_merge_followup_context`: si no
reconoce el turno como seguimiento, los filtros del turno anterior NO se
arrastran y la conversación pierde el hilo. Los casos multi-turno del corpus
real (docs/telegram_220_casos_prueba.md, #239-#243) son en su mayoría
**correcciones** — «No, de sargentos», «No, en agosto» — y ninguna de ellas
estaba reconocida: 5 de los 14 turnos de seguimiento del corpus se caían acá.
"""

import pytest

from backend.app.application.telegram.agent import _looks_like_followup


class TestCorrectionsAreFollowups:
    """Una corrección sólo tiene sentido sobre el turno anterior."""

    @pytest.mark.parametrize(
        "text",
        [
            "No, de sargentos.",
            "No, en agosto.",
            "No, al que se llama Miguelina Ramos.",
            "Mejor los de Ensenanza.",
            "Más bien en julio.",
            "Perdón, quise decir los cabos.",
        ],
    )
    def test_correction_is_a_followup(self, text: str) -> None:
        assert _looks_like_followup(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Los que estan en Emergencia.",
            "Las que sean de julio.",
            "El que se llama Ramos.",
        ],
    )
    def test_restriction_of_the_previous_set_is_a_followup(self, text: str) -> None:
        assert _looks_like_followup(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "Dame su rango.",
            "Cual es su sexo?",
            "Y sus areas?",
        ],
    )
    def test_possessive_reference_is_a_followup(self, text: str) -> None:
        assert _looks_like_followup(text) is True

    def test_exportalos_plural_is_a_followup(self) -> None:
        """«Exportalos» es el plural de «exportalo»: el patrón sólo cubría el singular."""
        assert _looks_like_followup("Exportalos en PDF.") is True


class TestPlainQuestionsAreNotFollowups:
    """La puerta no puede abrirse de más: un turno nuevo no arrastra filtros viejos."""

    @pytest.mark.parametrize(
        "text",
        [
            "Cuantos medicos hay en total?",
            "Dame la lista de medicos activos para servicio.",
            "Hay calendario de julio 2026?",
            "Quien aprobo el calendario de julio?",
            "Dame el ranking de misiones de agosto.",
            "Exporta en PDF los medicos femeninos.",
        ],
    )
    def test_new_question_is_not_a_followup(self, text: str) -> None:
        assert _looks_like_followup(text) is False


class TestAnaphoraOnly:
    """La puerta se abre por anáfora o corrección, nunca por el tema.

    Un falso positivo no es inocuo: `_merge_followup_context` inyecta los
    filtros del turno anterior en la consulta nueva y el usuario recibe un
    número creíble y equivocado.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "Cuantos medicos son cabo?",
            "Cuales son los medicos de servicio la primera semana de julio?",
            "Quienes son elegibles para mision el 15 de agosto?",
            "Dame un resumen por departamento y sexo.",
            "Cuantos medicos femeninos tengo?",
            "Dame la lista de medicos masculinos.",
            "Exporta en Excel los medicos masculinos.",
            "No hay calendario de julio 2026?",
        ],
    )
    def test_thematic_word_does_not_open_the_gate(self, text: str) -> None:
        assert _looks_like_followup(text) is False

    @pytest.mark.parametrize(
        "text",
        [
            "Y de pasantes?",
            "Y femeninos?",
            "ok entiendo y de julio ?",
            "De esos, cuantos son femeninos?",
            "Esa mision esta confirmada?",
        ],
    )
    def test_real_anaphora_still_opens_the_gate(self, text: str) -> None:
        assert _looks_like_followup(text) is True
