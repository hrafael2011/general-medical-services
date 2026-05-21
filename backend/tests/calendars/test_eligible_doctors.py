"""Tests for eligible-doctors endpoint and evaluate endpoint."""
import pytest
from datetime import date
from unittest.mock import MagicMock


class TestEligibleDoctorsService:
    def test_version_not_found(self):
        from backend.app.application.calendars.errors import CalendarServiceError
        from backend.app.infrastructure.repositories.calendars import CalendarRepository
        from backend.app.infrastructure.repositories.doctors import DoctorRepository
        from backend.app.infrastructure.repositories.availability import AvailabilityRepository
        from backend.app.application.calendars.assignment_service import AssignmentService

        repo = MagicMock(spec=CalendarRepository)
        repo.get_version_by_id.return_value = None
        doctor_repo = MagicMock(spec=DoctorRepository)
        availability_repo = MagicMock(spec=AvailabilityRepository)

        svc = AssignmentService(repo, doctor_repo, availability_repo)

        with pytest.raises(CalendarServiceError) as exc:
            svc.get_eligible_doctors_for_slot(
                version_id="v-nonexistent",
                target_date=date(2026, 5, 1),
                service_area_id="area-1",
            )
        assert exc.value.code == "version_not_found"


class TestEvaluateSlot:
    def test_evaluate_for_nonexistent_version(self):
        from backend.app.application.calendars.errors import CalendarServiceError
        from backend.app.infrastructure.repositories.calendars import CalendarRepository
        from backend.app.infrastructure.repositories.doctors import DoctorRepository
        from backend.app.infrastructure.repositories.availability import AvailabilityRepository
        from backend.app.application.calendars.assignment_service import AssignmentService

        repo = MagicMock(spec=CalendarRepository)
        repo.get_version_by_id.return_value = None
        doctor_repo = MagicMock(spec=DoctorRepository)
        availability_repo = MagicMock(spec=AvailabilityRepository)

        svc = AssignmentService(repo, doctor_repo, availability_repo)

        with pytest.raises(CalendarServiceError) as exc:
            svc.evaluate_slot(
                version_id="v-nonexistent",
                doctor_id="doc-1",
                target_date=date(2026, 5, 1),
                service_area_id="area-1",
            )
        assert exc.value.code == "version_not_found"

    def test_evaluate_nonexistent_doctor(self):
        from backend.app.application.calendars.errors import CalendarServiceError
        from backend.app.infrastructure.repositories.calendars import CalendarRepository
        from backend.app.infrastructure.repositories.doctors import DoctorRepository
        from backend.app.infrastructure.repositories.availability import AvailabilityRepository
        from backend.app.application.calendars.assignment_service import AssignmentService

        repo = MagicMock(spec=CalendarRepository)
        repo.get_version_by_id.return_value = MagicMock(calendar_id="cal-1")
        repo.get_calendar_by_id.return_value = MagicMock(year=2026, month=5)
        doctor_repo = MagicMock(spec=DoctorRepository)
        doctor_repo.get_by_id.return_value = None
        availability_repo = MagicMock(spec=AvailabilityRepository)

        svc = AssignmentService(repo, doctor_repo, availability_repo)

        with pytest.raises(CalendarServiceError) as exc:
            svc.evaluate_slot(
                version_id="v-1",
                doctor_id="nonexistent",
                target_date=date(2026, 5, 1),
                service_area_id="area-1",
            )
        assert exc.value.code == "doctor_not_found"
