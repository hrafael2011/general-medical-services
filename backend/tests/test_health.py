from backend.app.api.routes.health import health_check
from backend.app.main import create_app


def test_health_check_returns_ok() -> None:
    response = health_check()

    assert response["status"] == "ok"


def test_app_registers_health_route() -> None:
    app = create_app()
    route_paths = {route.path for route in app.routes}

    assert "/api/health" in route_paths
