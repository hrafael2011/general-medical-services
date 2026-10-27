"""Búsqueda de médico por teléfono para la vinculación de Telegram.

El emparejamiento por últimos 8 dígitos existía para tolerar diferencias de
formato (código de país, guiones). El problema era que aceptaba la primera
coincidencia aunque hubiera varias: un error de un dígito en el prefijo podía
vincular el chat de un médico con la ficha de otro, en silencio.

Aquí el número exacto gana siempre y los últimos 8 dígitos solo se aceptan
cuando hay **un único** candidato. Si hay ambigüedad no se adivina.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.application.notifications.phone_utils import normalize_phone
from backend.app.infrastructure.db.models.doctors import DoctorModel


@dataclass(frozen=True)
class PhoneLookupResult:
    doctor: DoctorModel | None
    reason: str  # "exact" | "tail" | "not_found" | "ambiguous"


def find_doctor_by_phone(session: Session, phone: str) -> PhoneLookupResult:
    """Find a doctor by phone, refusing to guess when the match is not unique.

    Exact normalized match wins. The last eight digits are used only as a
    fallback and only when exactly one doctor matches: a typo in the area code
    must never link a doctor to somebody else's chat.
    """
    normalized = normalize_phone(phone)
    if len(normalized) < 7:
        return PhoneLookupResult(None, "not_found")

    doctors = list(
        session.scalars(
            select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
        )
    )
    stored = [(doctor, normalize_phone(doctor.whatsapp_phone or "")) for doctor in doctors]

    exact = [doctor for doctor, number in stored if number == normalized]
    if len(exact) == 1:
        return PhoneLookupResult(exact[0], "exact")
    if len(exact) > 1:
        return PhoneLookupResult(None, "ambiguous")

    if len(normalized) >= 8:
        tail = normalized[-8:]
        matches = [doctor for doctor, number in stored if number.endswith(tail)]
        if len(matches) == 1:
            return PhoneLookupResult(matches[0], "tail")
        if len(matches) > 1:
            return PhoneLookupResult(None, "ambiguous")

    return PhoneLookupResult(None, "not_found")
