"""E2E del flujo crítico del modo manual sobre PostgreSQL real (5434).

Contrato verificado contra la app real (FastAPI TestClient + seed E2E):

1.  POST /api/auth/login {email, password} → 200 {access_token, user}
2.  POST /api/calendars {year, month, generation_mode:"manual"} → 201
    (calendario draft del mes actual + versión v1)
3.  GET  /api/calendars/{id}/eligible-doctors?date=YYYY-MM-DD&area_id=<uuid>
    → 200; el médico en modo monthly sin disponibilidad del mes aparece en
    `unavailable` con code="no_availability", is_hard=False
4.  POST /api/calendars/{id}/evaluate {doctor_id, service_date, service_area_id}
    → 200 {hard_blocks:[], warnings:[no_availability, ...]}
5.  POST /api/calendars/{id}/versions/{vid}/assignments con force_warnings y
    SIN override_justification → 422 detail.code="justification_required"
6.  Igual CON override_justification → 201; la asignación persiste la
    justificación
7.  GET /api/audit?action_type=assignment_added&entity_type=assignment → 200;
    el evento contiene after_snapshot.override_justification
8.  POST /api/calendars/{id}/weeks/{wid}/approve sobre una semana vacía
    → 422 detail.code="week_empty" (guard)
9.  POST .../approve sobre la semana del slot → 200 status="approved"
10. GET /api/calendars/{id} → status="partial"; GET .../grid → la asignación
    persiste con su justificación.
"""
from datetime import date, datetime

import pytest

from backend.app.domain.calendars.weeks import compute_weeks
from backend.scripts.seed_e2e import ADMIN_EMAIL, ADMIN_PASSWORD


@pytest.mark.e2e
def test_manual_flow_forced_warning_requires_justification(client, seed_ids):
    # ── 1. Login admin ─────────────────────────────────────────────────────
    resp = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # ── 2. Calendario draft del mes actual (modo manual) ──────────────────
    now = datetime.now()
    year, month = now.year, now.month
    resp = client.post(
        "/api/calendars",
        json={"year": year, "month": month, "generation_mode": "manual"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    calendar = resp.json()
    assert calendar["status"] == "draft"
    assert calendar["generation_mode"] == "manual"
    calendar_id = calendar["id"]

    resp = client.get(f"/api/calendars/{calendar_id}/grid", headers=headers)
    assert resp.status_code == 200, resp.text
    version_id = resp.json()["version"]["id"]

    # Slot: lunes de la primera semana del mes (Dra. Ana tiene lunes-miércoles).
    weeks = compute_weeks(year, month)
    slot_date = date(weeks[0][2], weeks[0][3], weeks[0][4])
    area_id = seed_ids["areas"]["emergencia"]
    monthly_id = seed_ids["monthly_doctor"]
    weekly_a_id = seed_ids["weekly_doctors"][0]

    # ── 3. Candidatos del slot: el médico monthly está unavailable (no-dura) ──
    resp = client.get(
        f"/api/calendars/{calendar_id}/eligible-doctors",
        params={"date": slot_date.isoformat(), "area_id": area_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    eligible_ids = {doctor["id"] for doctor in body["doctors"]}
    assert weekly_a_id in eligible_ids, body
    unavailable = {item["doctor_id"]: item for item in body["unavailable"]}
    assert monthly_id in unavailable, body
    unavailable_item = unavailable[monthly_id]
    assert unavailable_item["code"] == "no_availability"
    assert unavailable_item["is_hard"] is False
    assert unavailable_item["description"]

    # ── 4. Evaluación del slot para el médico monthly ──────────────────────
    resp = client.post(
        f"/api/calendars/{calendar_id}/evaluate",
        json={
            "doctor_id": monthly_id,
            "service_date": slot_date.isoformat(),
            "service_area_id": area_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    evaluation = resp.json()
    assert evaluation["hard_blocks"] == [], evaluation
    warning_codes = [warning["code"] for warning in evaluation["warnings"]]
    assert "no_availability" in warning_codes, evaluation

    assignment_payload = {
        "doctor_id": monthly_id,
        "service_date": slot_date.isoformat(),
        "service_area_id": area_id,
    }
    assignment_url = (
        f"/api/calendars/{calendar_id}/versions/{version_id}/assignments"
    )

    # ── 5. Forzar warnings SIN justificación → 422 justification_required ──
    resp = client.post(
        assignment_url,
        json={**assignment_payload, "force_warnings": warning_codes},
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "justification_required"

    # ── 6. Con justificación → 201 y la asignación persiste la justificación ──
    justification = "Cobertura de emergencia: disponibilidad pendiente (E2E)."
    resp = client.post(
        assignment_url,
        json={
            **assignment_payload,
            "force_warnings": warning_codes,
            "override_justification": justification,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assignment = resp.json()
    assert assignment["doctor_id"] == monthly_id
    assert assignment["override_justification"] == justification
    assignment_id = assignment["id"]

    # ── 7. Auditoría: el evento de la asignación contiene la justificación ──
    resp = client.get(
        "/api/audit",
        params={"action_type": "assignment_added", "entity_type": "assignment"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    events = resp.json()["items"]
    event = next(
        (item for item in events if item["entity_id"] == assignment_id),
        None,
    )
    assert event is not None, events
    assert event["after_snapshot"]["override_justification"] == justification
    assert event["after_snapshot"]["doctor_id"] == monthly_id

    # ── 8. Guard week_empty: aprobar una semana sin asignaciones → 422 ──────
    resp = client.get(f"/api/calendars/{calendar_id}/weeks", headers=headers)
    assert resp.status_code == 200, resp.text
    weeks_resp = resp.json()
    slot_iso = slot_date.isoformat()
    target_week = next(
        week for week in weeks_resp
        if week["start_date"] <= slot_iso <= week["end_date"]
    )
    empty_week = next(
        week for week in weeks_resp if week["id"] != target_week["id"]
    )
    resp = client.post(
        f"/api/calendars/{calendar_id}/weeks/{empty_week['id']}/approve",
        headers=headers,
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"]["code"] == "week_empty"

    # ── 9. Aprobar la semana que contiene el slot ───────────────────────────
    resp = client.post(
        f"/api/calendars/{calendar_id}/weeks/{target_week['id']}/approve",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # ── 10. Calendario partial y asignación persistente ─────────────────────
    resp = client.get(f"/api/calendars/{calendar_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "partial"

    resp = client.get(f"/api/calendars/{calendar_id}/grid", headers=headers)
    assert resp.status_code == 200, resp.text
    slots = resp.json()["slots"]
    slot = next(
        item for item in slots
        if item["service_date"] == slot_iso and item["service_area_id"] == area_id
    )
    assert slot["assignment"]["doctor_id"] == monthly_id
    assert slot["assignment"]["override_justification"] == justification
