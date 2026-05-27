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
    """Compara dos números de teléfono independientemente del formato.

    Maneja diferencias de código de país (ej: 18092186876 vs 8092186876).
    """
    a = normalize_phone(phone_a)
    b = normalize_phone(phone_b)
    if a == b:
        return True
    # One number may include country code while the other doesn't
    if len(a) > len(b) and a.endswith(b):
        return True
    if len(b) > len(a) and b.endswith(a):
        return True
    return False
