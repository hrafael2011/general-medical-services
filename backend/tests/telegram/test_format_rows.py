"""Tests for the shared _format_rows helper."""
from backend.app.application.telegram.sanitize import format_rows


def test_format_rows_empty() -> None:
    """0 filas → 'No se encontraron resultados.'"""
    assert format_rows([], []) == "No se encontraron resultados."


def test_format_rows_filters_id_columns() -> None:
    """Columnas 'id' y '*_id' se filtran automáticamente."""
    rows = [{"id": 42, "doctor_id": 7, "name": "Dr. A", "count": 1}]
    result = format_rows(rows, ["id", "doctor_id", "name", "count"])
    assert "42" not in result
    assert "7" not in result
    assert "Dr. A" in result
    assert "count" in result


def test_format_rows_filters_columns_containing_uuid_values() -> None:
    """Columnas con UUIDs embebidos no deben mostrarse al encargado."""
    rows = [
        {
            "dedupe_key": "service:a21bbd1c-02e8-44e5-b234-889087e6006c:4da49bc3-24b4-44c6-9bab-0ae6313577f0",
            "doctor_name": "Dr. Seguro",
            "status": "pending",
        }
    ]

    result = format_rows(rows, ["dedupe_key", "doctor_name", "status"])

    assert "a21bbd1c-02e8-44e5-b234-889087e6006c" not in result
    assert "Dr. Seguro" in result
    assert "Pendiente" in result


def test_format_rows_single_row() -> None:
    """1 fila → muestra todos los campos no-ID con 'Resultado:'."""
    rows = [{"name": "Dr. García", "rank": "Cabo"}]
    result = format_rows(rows, ["name", "rank"])
    assert result.startswith("Resultado:")
    assert "Dr. García" in result
    assert "Cabo" in result


def test_format_rows_multiple_rows_up_to_five() -> None:
    """2-5 filas → lista numerada."""
    rows = [{"name": f"Dr. {i}"} for i in range(3)]
    result = format_rows(rows, ["name"])
    assert "Se encontraron 3 resultados" in result
    assert "Dr. 0" in result
    assert "Dr. 2" in result


def test_format_rows_more_than_five() -> None:
    """>5 filas → solo primeros 5 con 'Los primeros:'."""
    rows = [{"name": f"Dr. {i}"} for i in range(10)]
    result = format_rows(rows, ["name"])
    assert "Se encontraron 10 resultados" in result
    assert "Los primeros:" in result
    # solo 5 items
    assert result.count("Dr.") == 5


def test_format_rows_truncates_to_5_columns_per_row() -> None:
    """En multi-fila solo muestra primeras 5 columnas por fila."""
    rows = [{"a": "1", "b": "2", "c": "3", "d": "4", "e": "5", "f": "6"},
            {"a": "7", "b": "8", "c": "9", "d": "10", "e": "11", "f": "12"}]
    result = format_rows(rows, ["a", "b", "c", "d", "e", "f"])
    assert "6" not in result
    assert "12" not in result


def test_format_rows_translates_operational_values_to_spanish() -> None:
    rows = [
        {
            "name": "Dra. Uno",
            "sex": "female",
            "status": "approved",
            "eligible": True,
            "service_active": False,
        }
    ]

    result = format_rows(rows, ["name", "sex", "status", "eligible", "service_active"])

    assert "female" not in result
    assert "approved" not in result
    assert "True" not in result
    assert "False" not in result
    assert "Femenino" in result
    assert "Aprobado" in result
    assert "Sí" in result
    assert "No" in result
