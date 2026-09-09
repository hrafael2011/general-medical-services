"""Smoke E2E: login HTTP con el admin del seed + listado de doctores."""
import pytest

from backend.scripts.seed_e2e import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.mark.e2e
def test_smoke_login_and_list_doctors(client):
    resp = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    assert token

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/doctors", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 3
    assert {item["name"] for item in body["items"]} >= {
        "Dra. Ana E2E",
        "Dr. Bruno E2E",
        "Dr. Carlos E2E",
    }
