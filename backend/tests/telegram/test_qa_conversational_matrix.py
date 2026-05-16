from pathlib import Path


QA_MATRIX_PATH = Path("docs/qa-telegram-conversacional-matriz.md")


def test_qa_matrix_document_exists() -> None:
    """Fase 9 requires a documented conversational QA matrix."""
    assert QA_MATRIX_PATH.exists()


def test_qa_matrix_has_required_columns() -> None:
    """Each QA row should be explicit enough to diagnose intent, route, memory and output."""
    text = QA_MATRIX_PATH.read_text(encoding="utf-8")

    required_columns = [
        "ID",
        "Conversación / Pregunta",
        "Dominio",
        "Acción",
        "Ruta",
        "Entidades",
        "Memoria",
        "Formato",
        "Resultado esperado",
        "Documento",
        "Cero resultados",
    ]
    for column in required_columns:
        assert column in text


def test_qa_matrix_covers_phase_9_required_scenarios() -> None:
    """The matrix must cover full conversations and negative cases from the plan."""
    text = QA_MATRIX_PATH.read_text(encoding="utf-8").lower()

    required_phrases = [
        "conteo -> listado -> pdf",
        "mes agosto -> y julio",
        "pasantes femeninos -> y masculinos",
        "ranking agosto -> top 3 -> exportar",
        "calendario aprobado -> borrador",
        "rango invalido",
        "mes sin calendario",
        "ranking inexistente",
        "pregunta fuera del sistema",
        "medico inexistente",
        "departamento mal escrito",
        "uuid",
        "ingles visible",
    ]
    for phrase in required_phrases:
        assert phrase in text
