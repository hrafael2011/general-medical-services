"""Vinculación por teléfono: exacto primero, últimos 8 dígitos solo si es único."""

from datetime import UTC, datetime

from backend.app.application.doctors.phone_lookup import find_doctor_by_phone
from backend.app.infrastructure.db.models.doctors import DoctorModel


def _doctor(session, *, id: str, phone: str) -> DoctorModel:
    doctor = DoctorModel(
        id=id,
        name=f"Dr. {id}",
        normalized_name=f"dr {id}",
        sex="male",
        whatsapp_phone=phone,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(doctor)
    session.commit()
    return doctor


def test_exact_match_wins(session):
    doctor = _doctor(session, id="d1", phone="+1 809 123 4567")

    result = find_doctor_by_phone(session, "18091234567")

    assert result.reason == "exact"
    assert result.doctor is not None and result.doctor.id == doctor.id


def test_last_eight_digits_only_when_unique(session):
    doctor = _doctor(session, id="d1", phone="+1 809 123 4567")

    result = find_doctor_by_phone(session, "8091234567")

    assert result.reason == "tail"
    assert result.doctor is not None and result.doctor.id == doctor.id


def test_two_doctors_with_the_same_tail_are_ambiguous(session):
    _doctor(session, id="d1", phone="+1 809 123 4567")
    _doctor(session, id="d2", phone="+1 829 123 4567")

    result = find_doctor_by_phone(session, "8091234567")

    assert result.reason == "ambiguous"
    assert result.doctor is None


def test_unknown_phone_is_not_found(session):
    _doctor(session, id="d1", phone="+1 809 123 4567")

    result = find_doctor_by_phone(session, "8099999999")

    assert result.reason == "not_found"
    assert result.doctor is None
