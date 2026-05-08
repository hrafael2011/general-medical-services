"""
Tests de integración para TelegramBotClient.

Requieren TELEGRAM_BOT_TOKEN en .env. Se saltean automáticamente si no está configurado.
Envían mensajes reales al chat de prueba TEST_TELEGRAM_CHAT_ID.
"""

import pytest

from backend.app.application.telegram.bot_client import TelegramBotClient
from backend.app.core.config import settings

TEST_CHAT_ID = 1368828040

pytestmark = pytest.mark.skipif(
    not settings.telegram_bot_token,
    reason="TELEGRAM_BOT_TOKEN no configurado",
)


@pytest.fixture(scope="module")
def client() -> TelegramBotClient:
    return TelegramBotClient()


def test_send_simple_message(client: TelegramBotClient) -> None:
    ok = client.send_message(TEST_CHAT_ID, "✅ Test integración: send_message OK")
    assert ok is True


def test_send_html_formatted_message(client: TelegramBotClient) -> None:
    text = "<b>Test</b> de formato HTML — <i>cursiva</i> y <code>código</code>"
    ok = client.send_message(TEST_CHAT_ID, text)
    assert ok is True


def test_send_multiline_message(client: TelegramBotClient) -> None:
    text = "Línea 1\nLínea 2\nLínea 3"
    ok = client.send_message(TEST_CHAT_ID, text)
    assert ok is True


def test_send_message_invalid_chat_returns_false(client: TelegramBotClient) -> None:
    ok = client.send_message(chat_id=0, text="Este mensaje no debería llegar.")
    assert ok is False


def test_send_document_pdf(client: TelegramBotClient) -> None:
    pdf_bytes = b"%PDF-1.4 test document content"
    ok = client.send_document(TEST_CHAT_ID, pdf_bytes, "test_reporte.pdf")
    assert ok is True


def test_send_document_excel(client: TelegramBotClient) -> None:
    import openpyxl
    import io

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Médico", "Turnos"])
    ws.append(["Dr. Test", 10])
    buf = io.BytesIO()
    wb.save(buf)
    excel_bytes = buf.getvalue()

    ok = client.send_document(TEST_CHAT_ID, excel_bytes, "test_reporte.xlsx")
    assert ok is True


def test_send_document_invalid_chat_returns_false(client: TelegramBotClient) -> None:
    ok = client.send_document(chat_id=0, file_bytes=b"data", filename="file.pdf")
    assert ok is False


def test_token_is_loaded_from_settings(client: TelegramBotClient) -> None:
    assert client.token == settings.telegram_bot_token
    assert len(client.token) > 10


def test_base_url_format(client: TelegramBotClient) -> None:
    assert client.base_url.startswith("https://api.telegram.org/bot")
    assert client.token in client.base_url
