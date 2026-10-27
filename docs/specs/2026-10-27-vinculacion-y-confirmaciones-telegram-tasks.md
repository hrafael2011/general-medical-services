# Tasks — Vinculación segura y confirmaciones confiables por Telegram

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-10-27-vinculacion-y-confirmaciones-telegram.md](2026-10-27-vinculacion-y-confirmaciones-telegram.md)

**Goal:** Que un médico vinculado reciba el aviso y pueda confirmarlo sin ambigüedades, y que el
sistema no finja haber avisado ni confirmado cuando no lo hizo.

**Architecture:** Se refuerzan tres piezas: la **vinculación** (emparejamiento exacto, nombre
visible), la **respuesta** (propiedad del chat y resultado honesto) y el **ciclo de vida**
(vencimiento, recordatorio y escalación atados al inicio del servicio). La desvinculación se
vuelve una acción explícita y auditada. La Fase 0 y la Fase 5 son operación, no código.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, pytest, React + TypeScript, Telegram Bot API.

**Estado:** 🟡 En ejecución. Fases 0 y 1 cerradas; Fase 0 deja pendiente la vinculación de
personas reales (no es código).

---

## Fase 0 — Operación previa (sin código)

> Sin esta fase el resto no se puede probar con datos reales. Hoy hay **0 de 74 médicos** y
> **0 de 6 usuarios** vinculados.

### Task 0.1 — Vincular médicos

**Files:** ninguno.

- [ ] **Step 1: Verificar que el bot responde**

```bash
railway run --no-local \
  -p 9c43a33f-124d-4de6-a8aa-d80fd3f6134b \
  -s general-medical-services -e production \
  bash -c 'curl -s "https://api.telegram.org/bot${TELEGRAM_NOTIFICATION_BOT_TOKEN}/getMe"'
```

Expected: `"ok": true` y `"username": "TurnosMedicosNotificaciones_bot"`.

- [ ] **Step 2: Enviar las instrucciones a los médicos**

Texto listo para reenviar:

```
Para recibir tus avisos de turnos por Telegram:
1. Abre este chat: https://t.me/TurnosMedicosNotificaciones_bot
2. Pulsa "Iniciar".
3. Escribe tu número de teléfono sin guiones ni espacios (ejemplo: 8091234567).
4. Pulsa "Confirmar".
```

No hay carga masiva: cada médico debe abrir el bot y escribir su número.

- [ ] **Step 3: Verificar cuántos quedaron vinculados**

```sql
select count(*) as total,
       count(*) filter (where telegram_chat_id is not null) as vinculados
from doctors;
```

Expected: `vinculados` mayor que 0. No se exige 74 para cerrar la tarea de código.

### Task 0.2 — Vincular encargados

**Files:** ninguno.

- [ ] **Step 1: Generar el link del usuario**

En el sistema: **Telegram → ¿Quién puede recibir avisos? → Generar link**.

- [ ] **Step 2: Enviarle el link y confirmar que lo abrió**

El link tiene la forma:

```
https://t.me/TurnosMedicosNotificaciones_bot?start=<token>
```

Al abrirlo, Telegram envía solo `/start <token>`.

- [ ] **Step 3: Verificar el vínculo y el permiso**

```sql
select id, name, role, telegram_chat_id, permissions
from users
where telegram_chat_id is not null;
```

Expected: al menos un usuario con `telegram_chat_id` y `receive_escalation_alerts` en
`permissions`.

### Task 0.3 — Medir la línea base técnica

**Files:** ninguno.

- [ ] **Step 1: Confirmar el webhook**

```bash
railway run --no-local \
  -p 9c43a33f-124d-4de6-a8aa-d80fd3f6134b \
  -s general-medical-services -e production \
  bash -c 'curl -s "https://api.telegram.org/bot${TELEGRAM_NOTIFICATION_BOT_TOKEN}/getWebhookInfo"'
```

Expected: `url` de producción, `pending_update_count: 0`, `last_error_message: null`.

- [ ] **Step 2: Confirmar que el worker corre**

```bash
railway logs --service worker --environment production
```

Expected: los 5 jobs (`process_notification_queue`, `send_pre_service_reminders`,
`check_unconfirmed_escalamiento`, `process_overdue_confirmations`,
`send_license_return_reminders`) sin traceback.

- [ ] **Step 3: Registrar los conteos iniciales**

```sql
select 'notification_events' as tabla, status, count(*)
from notification_events group by status
union all
select 'confirmation_requests', status, count(*)
from confirmation_requests group by status;
```

Expected: 92 `skipped` y 92 `expired`, 0 pendientes. Guardar el resultado en el registro de
avance de este documento.

---

## Fase 1 — Vinculación segura

### Task 1.1 — Módulo de emparejamiento de teléfono

**Files:**
- Create: `backend/app/application/doctors/phone_lookup.py`
- Test: `backend/tests/doctors/test_phone_lookup.py`

- [ ] **Step 1: Escribir el test que falla**

```python
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
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
./.venv/bin/python -m pytest backend/tests/doctors/test_phone_lookup.py -q
```

Expected: FAIL con `ModuleNotFoundError: backend.app.application.doctors.phone_lookup`.

- [ ] **Step 3: Implementar el módulo**

```python
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
```

- [ ] **Step 4: Ejecutar y ver que pasa**

```bash
./.venv/bin/python -m pytest backend/tests/doctors/test_phone_lookup.py -q
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/doctors/phone_lookup.py backend/tests/doctors/test_phone_lookup.py
git commit -m "feat(telegram): exact and unique phone matching for doctor linking"
```

### Task 1.2 — Mostrar el nombre y rechazar ambigüedad en el bot

**Files:**
- Modify: `backend/app/api/routes/telegram_notification_webhook.py`
- Test: `backend/tests/telegram/test_notification_webhook.py`

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `backend/tests/telegram/test_notification_webhook.py`:

```python
def _doctor_without_chat(session, *, id: str, phone: str) -> DoctorModel:
    doctor = DoctorModel(
        id=id,
        name="DRA. NUEVA",
        normalized_name="dra nueva",
        sex="female",
        whatsapp_phone=phone,
        telegram_chat_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(doctor)
    session.commit()
    return doctor


def test_the_phone_step_shows_the_doctor_name(client, session, monkeypatch):
    _doctor_without_chat(session, id="doc-name", phone="8091234567")
    sent: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(
        "backend.app.api.routes.telegram_notification_webhook._send_telegram_message",
        lambda chat_id, text, **kwargs: sent.append((chat_id, text, kwargs)) or {"ok": True},
    )

    _post(client, _message("321", "8091234567"))

    assert "DRA. NUEVA" in sent[0][1]
    assert "¿Es usted?" in sent[0][1]


def test_an_ambiguous_phone_is_refused(client, session, monkeypatch):
    _doctor_without_chat(session, id="doc-a", phone="+18091234567")
    _doctor_without_chat(session, id="doc-b", phone="+18291234567")
    sent: list[tuple[str, str, dict]] = []

    monkeypatch.setattr(
        "backend.app.api.routes.telegram_notification_webhook._send_telegram_message",
        lambda chat_id, text, **kwargs: sent.append((chat_id, text, kwargs)) or {"ok": True},
    )

    _post(client, _message("322", "8091234567"))

    assert "más de un médico" in sent[0][1]
    assert session.get(DoctorModel, "doc-a").telegram_chat_id is None
    assert session.get(DoctorModel, "doc-b").telegram_chat_id is None


def test_the_confirmation_callback_links_the_doctor(client, session):
    doctor = _doctor_without_chat(session, id="doc-link", phone="8091234567")

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-link",
                "from": {"id": 333},
                "data": f"link_phone:{doctor.id}",
                "message": {"message_id": 10, "chat": {"id": 333}},
            }
        },
    )

    session.refresh(doctor)
    assert doctor.telegram_chat_id == "333"
```

- [ ] **Step 2: Ejecutar y ver que fallan**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_notification_webhook.py -q
```

Expected: los tres tests nuevos fallan (el primero no muestra el nombre, el segundo vincula y el
tercero no encuentra el médico por UUID).

- [ ] **Step 3: Reemplazar `_find_doctor_by_phone` por el módulo nuevo**

En `telegram_notification_webhook.py`:

```python
from backend.app.application.doctors.phone_lookup import find_doctor_by_phone
```

Eliminar la función `_find_doctor_by_phone` (la búsqueda por últimos 8 dígitos sin unicidad).

- [ ] **Step 4: Cambiar el paso del teléfono**

Reemplazar el bloque `if text and _looks_like_phone(text):` por:

```python
        if text and _looks_like_phone(text):
            normalized = _normalize_phone(text)
            lookup = find_doctor_by_phone(session, normalized)

            if lookup.reason == "ambiguous":
                return _send_telegram_message(
                    chat_id,
                    "Hay más de un médico registrado con ese número. "
                    "Contacte al encargado para vincular su Telegram.",
                )
            if lookup.doctor is None:
                return _send_telegram_message(
                    chat_id,
                    f"No se encontró un médico registrado con el número +{normalized}.\n\n"
                    "Verifique que sea el mismo número registrado en el sistema "
                    "y contacte al encargado si el problema persiste.\n\n"
                    "Use /start para intentar de nuevo.",
                )

            return _send_telegram_message(
                chat_id,
                f"Teléfono +{normalized} — {lookup.doctor.name}\n\n¿Es usted?",
                inline_keyboard=[[
                    {"text": "✅ Sí, soy yo", "callback_data": f"link_phone:{lookup.doctor.id}"},
                    {"text": "🔄 Corregir", "callback_data": "link_retry"},
                ]],
            )
```

- [ ] **Step 5: Cambiar el callback para que reciba el ID del médico**

Reemplazar el bloque `if data.startswith("link_phone:"):` por:

```python
        if data.startswith("link_phone:"):
            doctor_id = data.split(":", 1)[1]
            doctor = session.get(DoctorModel, doctor_id)

            if doctor is None:
                _answer_callback(cb_id, "Médico no encontrado")
                return _edit_telegram_message(
                    chat_id, message_id,
                    "❌ No se encontró el médico. Use /start para intentar de nuevo.",
                )

            if doctor.telegram_chat_id and doctor.telegram_chat_id != chat_id:
                _answer_callback(cb_id, "Este medico ya esta vinculado a otra cuenta")
                return _edit_telegram_message(
                    chat_id, message_id,
                    f"❌ El Dr. {doctor.name} ya esta vinculado a otra cuenta "
                    "de Telegram.\n\n"
                    "Contacte al encargado si necesita cambiar la vinculacion.",
                )

            doctor.telegram_chat_id = chat_id
            session.commit()
            logger.info("Doctor %s linked to Telegram chat %s", doctor.name, chat_id)

            _answer_callback(cb_id, "Vinculado exitosamente")
            return _edit_telegram_message(
                chat_id, message_id,
                f"✅ Vinculado exitosamente, Dr. {doctor.name}.\n\n"
                "Recibira sus notificaciones de turnos por este medio.",
            )
```

- [ ] **Step 6: Ejecutar los tests del webhook**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_notification_webhook.py -q
```

Expected: todos pasan.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/telegram_notification_webhook.py backend/tests/telegram/test_notification_webhook.py
git commit -m "feat(telegram): show doctor name before linking and refuse ambiguous phones"
```

---

## Fase 2 — Respuesta confiable

### Task 2.1 — Verificar propiedad del chat y devolver un resultado

**Files:**
- Modify: `backend/app/api/routes/telegram_notification_webhook.py`
- Test: `backend/tests/telegram/test_notification_webhook.py`

- [ ] **Step 1: Escribir los tests que fallan**

Añadir:

```python
def test_a_foreign_chat_cannot_confirm(client, session):
    owner = _doctor(session, chat_id="123")
    _make_confirmation(session, owner)
    session.add(
        DoctorModel(
            id="doc-other",
            name="DR. OTRO",
            normalized_name="dr otro",
            sex="male",
            whatsapp_phone="8090000000",
            telegram_chat_id="999",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    session.commit()

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-foreign",
                "from": {"id": 999},
                "data": "confirm:conf-1",
                "message": {"message_id": 10, "chat": {"id": 999}},
            }
        },
    )

    assert session.get(ConfirmationRequestModel, "conf-1").status == "pending"


def test_an_expired_confirmation_is_not_confirmed(client, session):
    doctor = _make_doctor(session)
    request = _make_confirmation(session, doctor)
    request.status = "expired"
    session.commit()

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-expired",
                "from": {"id": 123},
                "data": "confirm:conf-1",
                "message": {"message_id": 10, "chat": {"id": 123}},
            }
        },
    )

    session.refresh(request)
    assert request.status == "expired"


def test_an_already_confirmed_request_does_not_queue_a_second_receipt(client, session):
    doctor = _make_doctor(session)
    request = _make_confirmation(session, doctor)
    request.status = "confirmed"
    session.commit()
    _make_user(session, telegram_chat_id="555")

    _post(
        client,
        {
            "callback_query": {
                "id": "cb-twice",
                "from": {"id": 123},
                "data": "confirm:conf-1",
                "message": {"message_id": 10, "chat": {"id": 123}},
            }
        },
    )

    assert session.query(NotificationEventModel).filter_by(
        notification_type="confirmation_receipt"
    ).count() == 0
```

- [ ] **Step 2: Ejecutar y ver que fallan**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_notification_webhook.py -q
```

Expected: el chat ajeno confirma; los otros dos pueden pasar parcialmente.

- [ ] **Step 3: Tipar el resultado y verificar el dueño**

Reemplazar `_process_confirmation` por:

```python
def _process_confirmation(session: Session, chat_id: str, confirmation_id: str) -> str:
    """Confirm a request only when the chat belongs to its doctor.

    Returns one of: confirmed, already_confirmed, already_answered, expired,
    not_found, unauthorized.
    """
    from datetime import UTC, datetime

    req = session.get(ConfirmationRequestModel, confirmation_id)
    if req is None:
        return "not_found"

    doctor = session.scalars(
        select(DoctorModel).where(DoctorModel.telegram_chat_id == chat_id)
    ).first()
    if doctor is None or doctor.id != req.doctor_id:
        logger.warning(
            "Chat %s tried to confirm request %s owned by doctor %s",
            chat_id, confirmation_id, req.doctor_id,
        )
        return "unauthorized"

    if req.status == "confirmed":
        return "already_confirmed"
    if req.status in {"declined", "expired"}:
        return "expired" if req.status == "expired" else "already_answered"
    if req.status not in {"pending", "received"}:
        return "already_answered"

    now = datetime.now(UTC)
    req.status = "confirmed"
    req.responded_at = now
    req.response_channel = "telegram"
    req.response_payload = {"telegram_chat_id": chat_id}

    message = (
        f"Dr. confirmó su {'servicio' if req.confirmation_type == 'service' else 'misión'}."
    )
    _queue_receipt_for_encargados(
        session,
        confirmation_id=confirmation_id,
        message=message,
        doctor_id=req.doctor_id,
        now=now,
    )

    session.commit()
    logger.info("Confirmation %s confirmed via Telegram (chat=%s)", confirmation_id, chat_id)
    return "confirmed"
```

- [ ] **Step 4: Mapear resultados a mensajes**

Añadir cerca de las constantes del módulo:

```python
_CONFIRMATION_TEXT = {
    "confirmed": "✅ Asistencia confirmada. Gracias.",
    "already_confirmed": "Esta confirmación ya fue respondida.",
    "already_answered": "Esta confirmación ya fue respondida.",
    "expired": "⏰ Esta confirmación ya venció. Contacte al encargado.",
    "not_found": "No encontramos esa confirmación.",
    "unauthorized": "No autorizado para responder esta confirmación.",
}

_CONFIRMATION_TOAST = {
    "confirmed": "Asistencia confirmada",
    "already_confirmed": "Ya estaba confirmada",
    "already_answered": "Ya fue respondida",
    "expired": "La confirmación venció",
    "not_found": "Confirmación no encontrada",
    "unauthorized": "No autorizado",
}
```

Y en el callback:

```python
        if data.startswith("confirm:") and not data.startswith("confirm:link"):
            confirmation_id = data.split(":", 1)[1]
            result = _process_confirmation(session, chat_id, confirmation_id)
            _answer_callback(cb_id, _CONFIRMATION_TOAST[result])
            return _edit_telegram_message(
                chat_id, message_id, _CONFIRMATION_TEXT[result],
            )
```

- [ ] **Step 5: Ejecutar los tests**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_notification_webhook.py -q
```

Expected: todos pasan, incluidos los dos tests de acuse que ya existían.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/telegram_notification_webhook.py backend/tests/telegram/test_notification_webhook.py
git commit -m "fix(telegram): only the owning doctor can confirm and outcomes are reported honestly"
```

---

## Fase 3 — Ciclo de vida atado al servicio

### Task 3.1 — Nombre del área y hora en la aprobación completa

**Files:**
- Modify: `backend/app/application/notifications/triggers.py`
- Test: `backend/tests/notifications/test_triggers.py`

- [ ] **Step 1: Añadir el helper**

```python
    def _resolve_area(self, assignment) -> tuple[str, datetime | None]:
        """Return the area display name and the service start time.

        The session is optional because week-trigger tests use a fake repo
        without one; in that case the area id is the best available label.
        """
        from backend.app.infrastructure.db.models.catalogs import ServiceAreaModel

        session = getattr(self.doctor_repo, "session", None)
        area = session.get(ServiceAreaModel, assignment.service_area_id) if session else None
        area_name = area.display_name if area is not None else str(assignment.service_area_id)

        start = getattr(assignment, "service_start_at", None)
        if start is None and getattr(assignment, "service_date", None) is not None:
            hour = area.start_hour if area is not None else 7
            start = datetime(
                assignment.service_date.year,
                assignment.service_date.month,
                assignment.service_date.day,
                hour,
                0,
                0,
                tzinfo=UTC,
            )
        return area_name, start
```

- [ ] **Step 2: Usarlo en `on_calendar_approved`**

Reemplazar el bloque de mensaje por:

```python
                area_name, service_start = self._resolve_area(assignment)
                message = render_initial_assignment(
                    service_date=str(assignment.service_date),
                    service_area=area_name,
                    service_start=(
                        service_start.strftime("%I:%M %p") if service_start else None
                    ),
                )
```

- [ ] **Step 3: Usarlo en `on_week_approved` y `_queue_service_change`**

Eliminar la resolución manual del área en `on_week_approved` y reutilizar `self._resolve_area`.
En `_queue_service_change`, reemplazar `service_area_name` por el resultado del helper si el
llamador no lo aporta. Mantener el parámetro `service_area_name` de las funciones públicas para no
romper las rutas, pero usarlo solo como fallback:

```python
                area_name, service_start = self._resolve_area(assignment)
                message = render_service_assignment_added(
                    service_date=str(assignment.service_date),
                    service_area=service_area_name or area_name,
                    service_start=(
                        service_start.strftime("%I:%M %p") if service_start else None
                    ),
                )
```

- [ ] **Step 4: Escribir el test**

En `backend/tests/notifications/test_triggers.py`, añadir una aserción al test de aprobación:

```python
def test_calendar_approval_uses_area_name_and_time(db_session, actor_user):
    from backend.app.infrastructure.db.models.notifications import NotificationEventModel

    doctor = _create_doctor(db_session)
    assignment = _make_assignment(db_session, doctor_id=doctor.id)
    triggers = _make_triggers(db_session)

    triggers.on_calendar_approved(actor_id=_ACTOR, assignments=[assignment])

    event = db_session.query(NotificationEventModel).one()
    assert "Emergencia" in event.payload["message"]
    assert "07:00 AM" in event.payload["message"]
    assert str(assignment.service_area_id) not in event.payload["message"]
```

- [ ] **Step 5: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/notifications/test_triggers.py backend/tests/notifications/test_week_triggers.py -q
```

Expected: todos pasan.

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/notifications/triggers.py backend/tests/notifications/test_triggers.py
git commit -m "fix(notifications): use area name and start time on full calendar approval"
```

### Task 3.2 — Vencimiento relativo al servicio

**Files:**
- Create: `backend/app/application/confirmations/deadlines.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/application/notifications/triggers.py`
- Modify: `backend/app/api/routes/calendars.py`
- Modify: `backend/app/api/routes/missions.py`
- Test: `backend/tests/confirmations/test_deadlines.py`

- [ ] **Step 1: Escribir el test que falla**

```python
from datetime import UTC, datetime, timedelta

from backend.app.application.confirmations.deadlines import due_at_for_service


def test_due_is_four_hours_before_the_service():
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)

    assert due_at_for_service(start, hours_before=4, now=now) == datetime(
        2026, 11, 1, 4, 0, tzinfo=UTC
    )


def test_due_never_lands_in_the_past():
    start = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)

    assert due_at_for_service(start, hours_before=4, now=now) == now + timedelta(hours=1)


def test_without_service_start_the_legacy_fallback_is_kept():
    now = datetime(2026, 11, 1, 7, 0, tzinfo=UTC)

    assert due_at_for_service(None, hours_before=4, now=now) == now + timedelta(hours=12)
```

- [ ] **Step 2: Ejecutar y ver que falla**

```bash
./.venv/bin/python -m pytest backend/tests/confirmations/test_deadlines.py -q
```

Expected: FAIL con `ModuleNotFoundError`.

- [ ] **Step 3: Implementar el cálculo**

```python
from datetime import UTC, datetime, timedelta

LEGACY_FALLBACK_HOURS = 12


def due_at_for_service(
    service_start: datetime | None,
    *,
    hours_before: int,
    now: datetime | None = None,
) -> datetime:
    """Deadline for a confirmation, anchored to the service start.

    A confirmation approved weeks in advance used to expire 12 hours after
    approval, long before the reminder. Anchoring it to the service keeps the
    doctor's window open and makes escalation reachable.
    """
    now = now or datetime.now(UTC)
    if service_start is None:
        return now + timedelta(hours=LEGACY_FALLBACK_HOURS)
    if service_start.tzinfo is None:
        service_start = service_start.replace(tzinfo=UTC)
    due = service_start - timedelta(hours=hours_before)
    return max(due, now + timedelta(hours=1))
```

- [ ] **Step 4: Añadir la configuración**

En `backend/app/core/config.py`:

```python
    confirmation_due_hours_before_service: int = 4
    confirmation_escalation_hours_before_service: int = 8
    confirmation_reminder_hours_before_service: int = 12
```

Y marcar el anterior como deprecado:

```python
    confirmation_overdue_hours: int = 12  # DEPRECATED: usar los tres valores de arriba
```

- [ ] **Step 5: Usar el cálculo en los triggers**

En `NotificationTriggers.__init__`, sustituir `confirmation_due_hours` por
`due_hours_before_service: int = 4` y guardarlo. Cambiar `_confirmation_due_at` por:

```python
    def _confirmation_due_at(self, service_start: datetime | None) -> datetime:
        from backend.app.application.confirmations.deadlines import due_at_for_service

        return due_at_for_service(
            service_start,
            hours_before=self.due_hours_before_service,
        )
```

En cada `create_request`, pasar el inicio resuelto:

- `on_calendar_approved`: `due_at=self._confirmation_due_at(self._resolve_area(assignment)[1])`
- `on_week_approved`: idem.
- `_queue_service_change`: idem.
- `on_mission_confirmed`: `due_at=self._confirmation_due_at(getattr(mission, "mission_start_at", None))`
- `on_mission_participants_changed` (altas): idem.

- [ ] **Step 6: Actualizar las rutas que construyen los triggers**

En `calendars.py` (2 lugares) y `missions.py` (1 lugar), reemplazar:

```python
        confirmation_due_hours=settings.confirmation_overdue_hours,
```

por:

```python
        due_hours_before_service=settings.confirmation_due_hours_before_service,
```

- [ ] **Step 7: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/confirmations/test_deadlines.py backend/tests/notifications -q
```

Expected: todos pasan.

- [ ] **Step 8: Commit**

```bash
git add backend/app/application/confirmations/deadlines.py backend/app/core/config.py \
  backend/app/application/notifications/triggers.py backend/app/api/routes/calendars.py \
  backend/app/api/routes/missions.py backend/tests/confirmations/test_deadlines.py
git commit -m "feat(confirmations): anchor deadlines to the service start"
```

### Task 3.3 — Recordatorio T-12 h siempre con botón

**Files:**
- Modify: `backend/app/application/scheduler/jobs.py`
- Modify: `backend/app/application/notifications/templates.py`
- Test: `backend/tests/scheduler/test_jobs.py`

- [ ] **Step 1: Cambiar el texto del recordatorio**

En `render_twelve_hour_reminder`, reemplazar la última línea:

```python
        "Por favor confirme su asistencia con el botón de abajo."
```

- [ ] **Step 2: Crear la confirmación si falta y adjuntar el botón**

En `send_pre_service_reminders`, dentro del `for`, después de calcular `start_str`:

```python
            from backend.app.application.confirmations.deadlines import due_at_for_service
            from backend.app.application.confirmations.service import ConfirmationRequestService
            from backend.app.infrastructure.repositories.confirmations import (
                ConfirmationRequestRepository,
            )

            confirmation = session.scalars(
                sa_select(ConfirmationRequestModel)
                .where(
                    ConfirmationRequestModel.assignment_id == a.id,
                    ConfirmationRequestModel.status == "pending",
                )
                .order_by(ConfirmationRequestModel.created_at.desc())
                .limit(1)
            ).first()

            if confirmation is None:
                confirmation = ConfirmationRequestService(
                    ConfirmationRequestRepository(session)
                ).create_request(
                    confirmation_type="service",
                    idempotency_key=(
                        f"reminder:{a.id}:{doctor.id}:{tomorrow.isoformat()}"
                    ),
                    doctor_id=doctor.id,
                    assignment_id=a.id,
                    due_at=due_at_for_service(
                        start_dt,
                        hours_before=settings.confirmation_due_hours_before_service,
                    ),
                )

            msg_payload: str | dict = with_telegram_buttons(message, confirmation.id)
```

Eliminar el bloque anterior que buscaba la confirmación y dejaba `msg_payload = message`.

- [ ] **Step 3: Usar la configuración de la ventana**

Reemplazar los dos `timedelta(hours=12)` de la ventana y el cálculo del recordatorio por:

```python
            reminder_target = start_dt - timedelta(
                hours=settings.confirmation_reminder_hours_before_service
            )
```

- [ ] **Step 4: Actualizar los tests**

En `backend/tests/scheduler/test_jobs.py`, los tests que simulan el doctor vinculado deben
devolver una confirmación pendiente en la segunda llamada a `session.scalars`. Usar:

```python
        pending = MagicMock()
        pending.id = "conf-reminder"

        mock_session.scalars.side_effect = [
            _make_scalars_result([assignment]),   # assignments
            _make_scalars_result([pending]),      # pending confirmation
        ]
```

Y añadir un test donde la segunda llamada devuelve `[]`, verificando que se crea una confirmación:

```python
def test_reminder_creates_a_confirmation_when_none_is_pending(...):
    ...
    assert result["reminders_sent"] == 1
    mock_create.assert_called_once()
```

> Ajustar los mocks existentes que hoy usan `scalars.return_value` para que el segundo consumo
> devuelva una confirmación o una lista vacía, según el caso.

- [ ] **Step 5: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_jobs.py -q
```

Expected: todos pasan.

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/scheduler/jobs.py backend/app/application/notifications/templates.py \
  backend/tests/scheduler/test_jobs.py
git commit -m "feat(reminders): always attach a confirmation button at T-12h"
```

### Task 3.4 — Escalación alcanzable

**Files:**
- Modify: `backend/app/application/scheduler/jobs.py`
- Test: `backend/tests/scheduler/test_jobs.py`

- [ ] **Step 1: Cambiar la consulta**

En `check_unconfirmed_escalamiento`, reemplazar el bloque de `cutoff` y el `stmt` por:

```python
        now = datetime.now(UTC)
        lead_hours = max(
            settings.confirmation_escalation_hours_before_service
            - settings.confirmation_due_hours_before_service,
            1,
        )
        horizon = now + timedelta(hours=lead_hours)

        stmt = (
            select(ConfirmationRequestModel)
            .where(
                ConfirmationRequestModel.status.in_(["pending", "received"]),
                ConfirmationRequestModel.due_at.is_not(None),
                ConfirmationRequestModel.due_at > now,
                ConfirmationRequestModel.due_at <= horizon,
                ConfirmationRequestModel.escalated_at.is_(None),
            )
        )
```

- [ ] **Step 2: Marcar la escalación**

En el bucle que recorre `unconfirmed`, mantener:

```python
            req.escalated_at = datetime.now(UTC)
```

Y asegurar que se hace antes del `session.commit()`.

- [ ] **Step 3: Añadir el test de ventana**

```python
def test_escalation_only_targets_requests_closing_in():
    """A pending confirmation far in the future must not be escalated."""
    from backend.app.application.scheduler.jobs import check_unconfirmed_escalamiento

    mock_session = MagicMock()
    mock_session.scalars.return_value = _make_scalars_result([])

    with patch(
        "backend.app.infrastructure.db.session.SessionLocal",
        return_value=mock_session,
    ):
        result = check_unconfirmed_escalamiento()

    assert result["escalations"] == 0
    compiled = str(mock_session.scalars.call_args.args[0])
    assert "due_at" in compiled
    assert "created_at" not in compiled
```

- [ ] **Step 4: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/scheduler/test_jobs.py -q
```

Expected: todos pasan.

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/scheduler/jobs.py backend/tests/scheduler/test_jobs.py
git commit -m "fix(escalation): escalate pending confirmations before they expire"
```

---

## Fase 4 — Desvinculación auditada

### Task 4.1 — Revocar el canal de avisos de un usuario

**Files:**
- Modify: `backend/app/api/routes/telegram.py`
- Test: `backend/tests/telegram/test_notification_webhook.py` o nuevo
  `backend/tests/telegram/test_alert_channel_admin.py`

- [ ] **Step 1: Escribir el test**

```python
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture()
def admin_user(session):
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Admin",
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=["manage_telegram"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture()
def client(session, admin_user):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _make_user(session, *, telegram_chat_id: str | None) -> UserModel:
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Encargado",
        email=f"enc-{uuid.uuid4().hex[:8]}@example.com",
        role="encargado",
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=["receive_escalation_alerts"],
        telegram_chat_id=telegram_chat_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


def test_admin_revokes_the_alerts_channel(client, session):
    user = _make_user(session, telegram_chat_id="555")

    response = client.post(f"/api/telegram/users/{user.id}/revoke-alerts")

    assert response.status_code == 204
    session.refresh(user)
    assert user.telegram_chat_id is None
```

- [ ] **Step 2: Implementar el endpoint**

En `telegram.py`:

```python
@router.post("/users/{user_id}/revoke-alerts", status_code=status.HTTP_204_NO_CONTENT)
def revoke_alerts_channel(
    user_id: str,
    admin: Annotated[UserModel, Depends(require_admin)],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Remove the chat id that the notification job reads.

    Deleting the assistant link does not touch this field; without this action
    an admin cannot revoke someone's alerts.
    """
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository

    user = UserRepository(session).get_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado.",
        )

    previous = {"telegram_chat_id": user.telegram_chat_id}
    user.telegram_chat_id = None
    user.updated_at = datetime.now(UTC)
    AuditService(AuditRepository(session)).log_user_updated(
        actor_id=admin.id,
        user=user,
        changed_fields={"telegram_chat_id": None},
        previous=previous,
    )
    session.commit()
```

- [ ] **Step 3: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/telegram/test_alert_channel_admin.py -q
```

Expected: pasa.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/telegram.py backend/tests/telegram/test_alert_channel_admin.py
git commit -m "feat(telegram): allow admins to revoke the alerts channel"
```

### Task 4.2 — Desvincular el Telegram de un médico

**Files:**
- Modify: `backend/app/api/routes/doctors.py`
- Test: `backend/tests/doctors/test_doctor_telegram_unlink.py`

- [ ] **Step 1: Escribir el test**

```python
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_current_user
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import get_db_session
from backend.app.main import create_app


@pytest.fixture()
def admin_user(session):
    user = UserModel(
        id=str(uuid.uuid4()),
        name="Admin",
        email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
        role="admin",
        active=True,
        password_hash="hashed",
        must_change_password=False,
        token_version=1,
        permissions=["manage_doctors"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    session.commit()
    return user


@pytest.fixture()
def client(session, admin_user):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _doctor_with_telegram(session) -> DoctorModel:
    doctor = DoctorModel(
        id=str(uuid.uuid4()),
        name="DR. VINCULADO",
        normalized_name="dr vinculado",
        sex="male",
        whatsapp_phone="8091234567",
        telegram_chat_id="555",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(doctor)
    session.commit()
    return doctor


def test_admin_unlinks_a_doctor(client, session):
    doctor = _doctor_with_telegram(session)

    response = client.post(f"/api/doctors/{doctor.id}/unlink-telegram")

    assert response.status_code == 204
    session.refresh(doctor)
    assert doctor.telegram_chat_id is None
```

- [ ] **Step 2: Implementar el endpoint**

En `doctors.py`:

```python
@router.post("/{doctor_id}/unlink-telegram", status_code=status.HTTP_204_NO_CONTENT)
def unlink_doctor_telegram(
    doctor_id: str,
    current_user: Annotated[UserModel, Depends(require_permission("manage_doctors"))],
    session: Annotated[Session, Depends(get_db_session)],
) -> None:
    from backend.app.application.audit.service import AuditService
    from backend.app.infrastructure.repositories.audit import AuditRepository

    doctor = DoctorRepository(session).get_by_id(doctor_id)
    if doctor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Médico no encontrado.",
        )

    doctor.telegram_chat_id = None
    doctor.updated_at = datetime.now(UTC)
    AuditService(AuditRepository(session)).log_doctor_updated(
        actor_id=current_user.id,
        doctor=doctor,
        changed_fields={"telegram_chat_id": None},
    )
    session.commit()
```

- [ ] **Step 3: Ejecutar**

```bash
./.venv/bin/python -m pytest backend/tests/doctors/test_doctor_telegram_unlink.py -q
```

Expected: pasa.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/doctors.py backend/tests/doctors/test_doctor_telegram_unlink.py
git commit -m "feat(doctors): allow admins to unlink a doctor's Telegram"
```

### Task 4.3 — Botones en la interfaz

**Files:**
- Modify: `frontend/src/api/telegram.ts`
- Modify: `frontend/src/api/doctors.ts`
- Modify: `frontend/src/features/telegram/TelegramLinks.tsx`
- Modify: `frontend/src/features/doctors/DoctorList.tsx`
- Test: `frontend/src/features/telegram/TelegramLinks.test.tsx`
- Test: `frontend/src/features/doctors/DoctorList.test.tsx`

- [ ] **Step 1: Añadir las llamadas de API**

En `frontend/src/api/telegram.ts`:

```ts
  revokeAlerts(userId: string): Promise<void> {
    return apiFetch<void>(`/telegram/users/${userId}/revoke-alerts`, {
      method: "POST",
    });
  },
```

En `frontend/src/api/doctors.ts`:

```ts
  unlinkTelegram(id: string): Promise<void> {
    return apiFetch<void>(`/doctors/${id}/unlink-telegram`, {
      method: "POST",
    });
  },
```

- [ ] **Step 2: Botón en TelegramLinks**

En la tabla de usuarios, cuando `u.telegram_chat_id` exista, mostrar:

```tsx
<button
  className="btn-ghost"
  style={{ padding: "3px 8px", fontSize: "0.8rem" }}
  onClick={() => revokeMutation.mutate(u.id)}
  disabled={revokeMutation.isPending}
>
  Revocar avisos
</button>
```

Con la mutación:

```tsx
const revokeMutation = useMutation({
  mutationFn: (userId: string) => telegramApi.revokeAlerts(userId),
  onSuccess: () => {
    void queryClient.invalidateQueries({ queryKey: ["telegram-users"] });
    addToast("success", "Canal de avisos revocado.");
  },
});
```

> Usar la misma `queryKey` que ya emplea la pantalla para cargar usuarios.

- [ ] **Step 3: Botón en el perfil del médico**

Pasar un callback al modal:

```tsx
          onUnlinkTelegram={() => {
            unlinkMutation.mutate(selectedDoctor.id);
          }}
```

Y dentro de `DoctorProfileModal`, en `profile-actions`:

```tsx
            {doctor.has_telegram && (
              <button className="btn-secondary" onClick={onUnlinkTelegram}>
                <Trash2 size={16} />
                Desvincular Telegram
              </button>
            )}
```

- [ ] **Step 4: Actualizar los tests de interfaz**

En `TelegramLinks.test.tsx`, añadir `revokeAlerts: vi.fn()` al mock del módulo y este test:

```tsx
it("revoca el canal de avisos de un usuario vinculado", async () => {
  const { telegramApi } = await import("../../api/telegram");
  await setupMocks({ admins: [ADMIN_LINKED] });
  vi.mocked(telegramApi.revokeAlerts).mockResolvedValue();

  renderComponent();

  const row = (await screen.findByText("Admin Vinculado")).closest("tr")!;
  fireEvent.click(within(row).getByRole("button", { name: /revocar avisos/i }));

  await waitFor(() => {
    expect(telegramApi.revokeAlerts).toHaveBeenCalledWith("u-admin");
  });
});
```

En `DoctorList.test.tsx`, añadir `unlinkTelegram: vi.fn()` al mock de `doctorsApi` y este test:

```tsx
it("desvincula el Telegram de un médico desde el perfil", async () => {
  const { doctorsApi } = await import("../../api/doctors");
  mockListDoctors.mockResolvedValue({
    items: [
      {
        id: "d1",
        name: "Dr. García",
        sex: "male",
        service_active: true,
        active: true,
        participa_misiones: true,
        monthly_service_target: 4,
        monthly_service_max: 6,
        monthly_service_limit_mode: "warn_only",
        availability_mode: "weekly",
        rank_id: null,
        department_id: "dept-1",
        notes: null,
        service_inactive_reason_id: null,
        service_inactive_detail: null,
        whatsapp_phone: "8091234567",
        has_telegram: true,
        allowed_area_ids: ["area-1"],
      },
    ],
    total: 1,
  });
  vi.mocked(doctorsApi.unlinkTelegram).mockResolvedValue();

  renderList();
  fireEvent.click(await screen.findByText("Dr. García"));
  fireEvent.click(await screen.findByRole("button", { name: /desvincular telegram/i }));

  await waitFor(() => {
    expect(doctorsApi.unlinkTelegram).toHaveBeenCalledWith("d1");
  });
});
```

- [ ] **Step 5: Ejecutar**

```bash
npm --prefix frontend run test -- --run TelegramLinks DoctorList
```

Expected: todos pasan.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/telegram.ts frontend/src/api/doctors.ts \
  frontend/src/features/telegram/TelegramLinks.tsx frontend/src/features/doctors/DoctorList.tsx \
  frontend/src/features/telegram/TelegramLinks.test.tsx frontend/src/features/doctors/DoctorList.test.tsx
git commit -m "feat(ui): revoke alerts channel and unlink doctor Telegram"
```

---

## Fase 5 — Cierre y opcionales

### Task 5.1 — Link público en el mensaje (opcional)

**Files:**
- Modify: `backend/app/application/notifications/templates.py`
- Modify: `backend/app/application/notifications/triggers.py`
- Test: `backend/tests/notifications/test_triggers.py`

- [ ] **Step 1: Pasar la confirmación completa al constructor del mensaje**

Cambiar la firma:

```python
def _with_telegram_confirmation(message: str, confirmation) -> dict:
    from backend.app.core.config import settings

    url = (
        f"{settings.frontend_origin.rstrip('/')}"
        f"/confirmacion-medica?token={confirmation.response_token}"
    )
    text = f"{message}\n\nSi el botón no funciona, abra: {url}"
    return with_telegram_buttons(text, confirmation.id)
```

Y en `triggers.py`, cambiar cada llamada:

```python
_build_confirmation_message(message, doctor, confirmation)
```

La función `_build_confirmation_message` debe aceptar la confirmación y pasar el objeto, no el id.

- [ ] **Step 2: Probar que el link aparece**

```python
def test_telegram_message_includes_the_public_link(db_session):
    # crear doctor con telegram_chat_id y una confirmación
    # ejecutar el trigger
    # leer el payload del evento
    assert "/confirmacion-medica?token=" in payload["message"]["text"]
```

- [ ] **Step 3: Ejecutar y commit**

```bash
./.venv/bin/python -m pytest backend/tests/notifications/test_triggers.py -q
git add backend/app/application/notifications/templates.py backend/app/application/notifications/triggers.py backend/tests/notifications/test_triggers.py
git commit -m "feat(notifications): include the public confirmation link (optional)"
```

> Riesgo aceptado: el link es una llave portable; quien lo tenga puede confirmar.

### Task 5.2 — Configuración de producción (opcional, requiere autorización)

**Files:** ninguno (Railway).

- [ ] **Step 1: Alinear `FEATURE_NOTIFICATIONS`**

En el servicio **worker**, cambiar `FEATURE_NOTIFICATIONS=false` a `true` (o eliminarla). Los jobs
no leen el flag hoy, pero la inconsistencia confunde.

> Cambiar variables de producción requiere autorización explícita del usuario.

- [ ] **Step 2: Bajar la latencia (solo si se decide)**

Cambiar el cron del worker de `*/30 * * * *` a `*/10 * * * *`. Más arranques del contenedor, menor
espera.

- [ ] **Step 3: Verificar**

```bash
railway variables --service worker --environment production
railway logs --service worker --environment production
```

Expected: `FEATURE_NOTIFICATIONS=true` y los jobs corriendo con los nuevos tiempos.

### Task 5.3 — Prueba de punta a punta y cierre del spec

**Files:**
- Modify: `docs/specs/2026-10-27-vinculacion-y-confirmaciones-telegram.md` (estado y registro)

- [ ] **Step 1: Ejecutar la suite completa**

```bash
./scripts/test.sh unit
npm --prefix frontend run test -- --run
```

Expected: todo en verde.

- [ ] **Step 2: Probar con un médico real**

1. Vincular un médico (Fase 0).
2. Aprobar una semana donde esté asignado.
3. Esperar al worker (≤30 min) o ejecutarlo a mano.
4. Verificar:

```sql
select id, notification_type, status, provider, recipient_phone, sent_at
from notification_events
order by created_at desc
limit 5;
```

Expected: el evento del médico queda `sent` con `provider = 'telegram'`.

5. El médico pulsa **✓ Confirmar asistencia**.
6. Verificar:

```sql
select id, status, response_channel, responded_at
from confirmation_requests
order by created_at desc
limit 5;
```

Expected: `status = 'confirmed'`, `response_channel = 'telegram'`.

7. Verificar que el encargado recibió el acuse:

```sql
select id, notification_type, status, recipient_phone
from notification_events
where notification_type = 'confirmation_receipt'
order by created_at desc
limit 3;
```

Expected: al menos un evento `sent` hacia el chat del encargado.

- [ ] **Step 3: Actualizar el spec**

Cambiar `status: accepted` por `status: implemented` y añadir al changelog la fecha y el resultado
de la prueba real.

- [ ] **Step 4: Commit**

```bash
git add docs/specs/2026-10-27-vinculacion-y-confirmaciones-telegram.md
git commit -m "docs(spec): mark Telegram linking and confirmations as implemented"
```

---

## Orden de ejecución

| Fase | Tasks | Qué resuelve | Depende de |
|---|---|---|---|
| 0 | 0.1, 0.2, 0.3 | Tener destinatarios y línea base | — |
| 1 | 1.1, 1.2 | Vincular sin ambigüedad | Fase 0 (para probar con reales) |
| 2 | 2.1 | Confirmar solo el dueño y con resultado honesto | Fase 1 |
| 3 | 3.1, 3.2, 3.3, 3.4 | Ciclo de vida atado al servicio | Fase 2 |
| 4 | 4.1, 4.2, 4.3 | Corregir y revocar vínculos | Fase 1 |
| 5 | 5.1, 5.2, 5.3 | Opcionales y cierre | Fases 1–4 |

## Registro de avance

| Fecha | Task | Nota |
|---|---|---|
| 2026-10-27 | — | Spec y tasks creadas. Sin implementar. |
| 2026-10-27 | 0.1 / 0.2 / 0.3 | Verificado: bot `ok` (`TurnosMedicosNotificaciones_bot`), webhook de producción con `pending_update_count: 0`, 5 jobs sin traceback. Línea base: 92 `skipped`, 92 `expired`, 0 pendientes. **Sigue en 0 de 74 médicos y 0 de 6 usuarios vinculados**: falta que las personas abran el bot (operación, no código). |
| 2026-10-27 | 1.1 | `phone_lookup.py` + 4 tests. Coincidencia exacta gana; últimos 8 dígitos solo si hay un único candidato; ambigüedad no vincula. Commit `4e69984`. |
| 2026-10-27 | 1.2 | El bot muestra el nombre y pide `¿Es usted?`; el callback usa `link_phone:<doctor_id>`. 10 tests del webhook en verde. Commit `18ae777`. |
