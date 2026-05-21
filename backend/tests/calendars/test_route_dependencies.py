from backend.app.api.routes.calendars import get_generation_service
from backend.app.application.calendars.generation_service import GenerationService


def test_generation_service_dependency_builds(db_session) -> None:
    service = get_generation_service(db_session)

    assert isinstance(service, GenerationService)
