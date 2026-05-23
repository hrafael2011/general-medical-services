"""Normalización de números de teléfono para WhatsApp."""

import re


def normalize_phone(phone: str) -> str:
    """Normaliza un número de teléfono al formato internacional sin '+' ni espacios.

    Meta Cloud API envía '521234567890' (sin +).
    La DB puede tener '+52 123 456 7890' o 'whatsapp:+521234567890'.

    Returns: string solo dígitos, sin '+', sin 'whatsapp:', sin espacios.
    """
    cleaned = phone.removeprefix("whatsapp:").strip()
    cleaned = cleaned.removeprefix("+")
    cleaned = re.sub(r"\D", "", cleaned)
    return cleaned


def phones_match(phone_a: str, phone_b: str) -> bool:
    """Compara dos números de teléfono independientemente del formato."""
    return normalize_phone(phone_a) == normalize_phone(phone_b)
