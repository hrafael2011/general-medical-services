# Tasks — Aprobación segura: deshacer sí deshace

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [2026-11-01-aprobacion-segura-notificaciones.md](2026-11-01-aprobacion-segura-notificaciones.md)

**Goal:** que desbloquear una semana o un calendario cancele los avisos que todavía no han salido, y
que la pantalla diga cuántos se cancelaron.

**Architecture:** la cancelación vive en los repositorios (una sola consulta por tabla), se expone
como método en los servicios existentes, y `NotificationTriggers` la orquesta para que
`CalendarService` no conozca repositorios de notificaciones.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, pytest, React + TypeScript, vitest.

**Estado:** ⬜ Sin empezar.

**Alcance de este documento:** solo **Fase 1 (P1)**. Las fases 2 (margen de 15 minutos) y 3
(corregir sí avisa) se detallan cuando esta cierre: ambas dependen de la semántica de cancelación
que aquí se define — en particular, qué hacer con una fila `cancelled` cuando se vuelve a aprobar.

---

## Fase 1 — El error de aprobar (P1)

Los siete arreglos A1–A6 y D2 del spec. Al terminar, desbloquear deja la semana sin avisos en vuelo
y sin confirmaciones fantasma, y queda auditado.

### Task 1.1 — Cancelar los avisos pendientes de un conjunto de asignaciones (A3)

**Files:**
- Modify: `backend/app/infrastructure/repositories/notifications.py`
- Test: `backend/tests/notifications/test_cancel_notifications.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Cancelar avisos que todavía no han salido.

Regla del spec: solo `pending`. Nunca `sending` (puede estar en vuelo) ni `sent`
(no se recupera).
"""

from datetime import UTC, datetime, timedelta

from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.repositories.notifications import NotificationRepository


def _event(session, *, assignment_id: str, status: str) -> NotificationEventModel:
    now = datetime.now(UTC)
    event = NotificationEventModel(
        id=f"ev-{assignment_id}-{status}",
        notification_type="initial_assignment",
        idempotency_key=f"assign:{assignment_id}",
        recipient_doctor_id="doc1",
        recipient_phone="123",
        payload={"message": "hola"},
        assignment_id=assignment_id,
        status=status,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    session.commit()
    return event


def test_cancela_solo_los_pendientes(db_session):
    pending = _event(db_session, assignment_id="a1", status="pending")
    enviado = _event(db_session, assignment_id="a2", status="sent")
    en_vuelo = _event(db_session, assignment_id="a3", status="sending")

    cancelados = NotificationRepository(db_session).cancel_pending_for_assignments(
        ["a1", "a2", "a3"]
    )

    assert cancelados == [pending.id]
    db_session.refresh(pending)
    db_session.refresh(enviado)
    db_session.refresh(en_vuelo)
    assert pending.status == "cancelled"
    assert enviado.status == "sent"
    assert en_vuelo.status == "sending"


def test_sin_asignaciones_no_consulta(db_session):
    assert NotificationRepository(db_session).cancel_pending_for_assignments([]) == []
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/notifications/test_cancel_notifications.py -x -q`
Expected: FAIL con `AttributeError: 'NotificationRepository' object has no attribute 'cancel_pending_for_assignments'`

- [ ] **Step 3: Implementar**

En `backend/app/infrastructure/repositories/notifications.py`, junto a `list_pending`:

```python
    def cancel_pending_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Marca `cancelled` los avisos que aún no han salido.

        Nunca toca `sending` (el worker puede tenerlo en vuelo) ni `sent`
        (lo enviado no se recupera). Devuelve los ids cancelados.
        """
        if not assignment_ids:
            return []
        now = datetime.now(UTC)
        stmt = select(NotificationEventModel).where(
            NotificationEventModel.assignment_id.in_(assignment_ids),
            NotificationEventModel.status == "pending",
        )
        events = list(self.session.scalars(stmt))
        for event in events:
            event.status = "cancelled"
            event.updated_at = now
        self.session.flush()
        return [event.id for event in events]
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `pytest backend/tests/notifications/test_cancel_notifications.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/infrastructure/repositories/notifications.py backend/tests/notifications/test_cancel_notifications.py
git commit -m "feat(notifications): allow cancelling unsent events"
```

---

### Task 1.2 — Cancelar las confirmaciones pendientes (A4)

**Files:**
- Modify: `backend/app/infrastructure/repositories/confirmations.py`
- Modify: `backend/app/application/confirmations/service.py`
- Test: `backend/tests/confirmations/test_cancel_confirmations.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Una confirmación de un turno cancelado no puede seguir viva: escalaría por un
turno que ya no existe."""

from datetime import UTC, datetime, timedelta

from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.repositories.confirmations import ConfirmationRequestRepository


def _request(session, doctor_id: str, *, key: str, status: str, assignment_id: str):
    now = datetime.now(UTC)
    request = ConfirmationRequestModel(
        id=f"cr-{key}",
        confirmation_type="service",
        status=status,
        idempotency_key=key,
        response_token=f"tok-{key}",
        doctor_id=doctor_id,
        assignment_id=assignment_id,
        due_at=now + timedelta(hours=2),
        created_at=now,
        updated_at=now,
    )
    session.add(request)
    session.commit()
    return request


def test_cancela_pendientes_y_recibidas(db_session, doctor_factory):
    doctor = doctor_factory(db_session, name="Dra. Cancelación")
    pendiente = _request(db_session, doctor.id, key="k1", status="pending", assignment_id="a1")
    recibida = _request(db_session, doctor.id, key="k2", status="received", assignment_id="a2")
    confirmada = _request(db_session, doctor.id, key="k3", status="confirmed", assignment_id="a3")

    ids = ConfirmationRequestRepository(db_session).cancel_pending_for_assignments(["a1", "a2", "a3"])

    assert set(ids) == {pendiente.id, recibida.id}
    for row in (pendiente, recibida, confirmada):
        db_session.refresh(row)
    assert pendiente.status == "cancelled"
    assert recibida.status == "cancelled"
    assert confirmada.status == "confirmed"
```

> Si no existe un `doctor_factory` en `backend/tests/conftest.py`, crear el doctor a mano con
> `DoctorModel(id=..., name=..., rank_id=None, department_id=None, active=True, ...)` siguiendo
> `backend/tests/doctors/` para los campos obligatorios.

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/confirmations/test_cancel_confirmations.py -x -q`
Expected: FAIL con `AttributeError: ... 'cancel_pending_for_assignments'`

- [ ] **Step 3: Implementar el repositorio**

En `backend/app/infrastructure/repositories/confirmations.py`:

```python
    def cancel_pending_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Cancela las confirmaciones que aún esperan respuesta.

        `confirmed` y `declined` son hechos consumados: no se tocan.
        """
        if not assignment_ids:
            return []
        now = datetime.now(UTC)
        stmt = select(ConfirmationRequestModel).where(
            ConfirmationRequestModel.assignment_id.in_(assignment_ids),
            ConfirmationRequestModel.status.in_(["pending", "received"]),
        )
        requests = list(self.session.scalars(stmt))
        for request in requests:
            request.status = "cancelled"
            request.updated_at = now
        self.session.flush()
        return [request.id for request in requests]
```

- [ ] **Step 4: Exponerlo en el servicio**

En `backend/app/application/confirmations/service.py`, junto a los métodos de creación:

```python
    def cancel_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Cancela las confirmaciones de turnos que ya no existen."""
        return self.repo.cancel_pending_for_assignments(assignment_ids)
```

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `pytest backend/tests/confirmations/test_cancel_confirmations.py -q`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/infrastructure/repositories/confirmations.py backend/app/application/confirmations/service.py backend/tests/confirmations/test_cancel_confirmations.py
git commit -m "feat(confirmations): cancel requests for unsent assignments"
```

---

### Task 1.3 — Exponer la cancelación en `NotificationService` y orquestarla en los disparadores

**Files:**
- Modify: `backend/app/application/notifications/service.py`
- Modify: `backend/app/application/notifications/triggers.py`
- Test: `backend/tests/notifications/test_triggers_unapproval.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Deshacer la aprobación debe deshacer el aviso."""

from unittest.mock import MagicMock

from backend.app.application.notifications.triggers import NotificationTriggers


def test_on_week_unapproved_cancela_avisos_y_confirmaciones():
    notifications = MagicMock()
    notifications.cancel_for_assignments.return_value = ["ev1", "ev2"]
    confirmations = MagicMock()
    confirmations.cancel_for_assignments.return_value = ["cr1"]

    triggers = NotificationTriggers(
        notification_service=notifications,
        doctor_repo=MagicMock(),
        confirmation_service=confirmations,
    )
    a1, a2 = MagicMock(id="a1"), MagicMock(id="a2")

    result = triggers.on_week_unapproved(actor_id="user1", assignments=[a1, a2])

    notifications.cancel_for_assignments.assert_called_once_with(["a1", "a2"])
    confirmations.cancel_for_assignments.assert_called_once_with(["a1", "a2"])
    assert result == {"notifications": 2, "confirmations": 1}
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/notifications/test_triggers_unapproval.py -x -q`
Expected: FAIL con `AttributeError: 'NotificationTriggers' object has no attribute 'on_week_unapproved'`

- [ ] **Step 3: Implementar en el servicio**

En `backend/app/application/notifications/service.py`, después de `queue`:

```python
    def cancel_for_assignments(self, assignment_ids: list[str]) -> list[str]:
        """Cancela los avisos aún no enviados de esos turnos."""
        return self.repo.cancel_pending_for_assignments(assignment_ids)
```

- [ ] **Step 4: Implementar en los disparadores**

En `backend/app/application/notifications/triggers.py`, junto a `on_week_approved`:

```python
    def on_week_unapproved(self, *, actor_id: str, assignments: list) -> dict[str, int]:
        """Deshace lo que encoló `on_week_approved`.

        Solo alcanza a lo que no ha salido: un aviso ya enviado no se puede
        recoger, y uno en vuelo podría duplicarse.
        """
        assignment_ids = [assignment.id for assignment in assignments]
        notification_ids = self.notification_service.cancel_for_assignments(assignment_ids)
        confirmation_ids: list[str] = []
        if self.confirmation_service is not None:
            confirmation_ids = self.confirmation_service.cancel_for_assignments(assignment_ids)
        logger.info(
            "Unapproval by %s cancelled %d notifications and %d confirmations",
            actor_id,
            len(notification_ids),
            len(confirmation_ids),
        )
        return {
            "notifications": len(notification_ids),
            "confirmations": len(confirmation_ids),
        }
```

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `pytest backend/tests/notifications/test_triggers_unapproval.py -q`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/notifications/service.py backend/app/application/notifications/triggers.py backend/tests/notifications/test_triggers_unapproval.py
git commit -m "feat(notifications): orchestrate cancellation on unapproval"
```

---

### Task 1.4 — `unlock_week` cancela (A1)

**Files:**
- Modify: `backend/app/application/calendars/service.py:484-553`
- Test: `backend/tests/calendars/test_unlock_cancels.py`

- [ ] **Step 1: Escribir el test que falla**

Se apoya en el `FakeWeekRepo` de `backend/tests/calendars/test_week_service.py`.

```python
"""Desbloquear una semana cancela lo que esa semana encoló."""

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.application.calendars.service import CalendarService
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
)

from .test_week_service import FakeWeekRepo


def _approved_week():
    repo = FakeWeekRepo()
    cal = CalendarModel(id=str(uuid4()), year=2026, month=5, status="approved",
                        generation_mode="manual")
    repo.add_calendar(cal)
    version = CalendarVersionModel(id=str(uuid4()), calendar_id=cal.id,
                                   version_number=1, status="approved")
    repo.add_version(version)
    week = CalendarWeekModel(id=str(uuid4()), calendar_id=cal.id,
                             calendar_version_id=version.id, week_number=1,
                             label="1RA SEMANA", start_date=date(2026, 5, 4),
                             end_date=date(2026, 5, 10), status="approved")
    repo.add_week(week)
    dentro = CalendarAssignmentModel(id=str(uuid4()), calendar_version_id=version.id,
                                     calendar_week_id=week.id, service_date=date(2026, 5, 5),
                                     service_area_id="area1", doctor_id="doc1")
    fuera = CalendarAssignmentModel(id=str(uuid4()), calendar_version_id=version.id,
                                    calendar_week_id=None, service_date=date(2026, 5, 20),
                                    service_area_id="area1", doctor_id="doc2")
    repo.add_assignment(dentro)
    repo.add_assignment(fuera)
    return repo, week, dentro, fuera


def test_unlock_week_cancela_solo_lo_de_la_semana():
    repo, week, dentro, fuera = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 1, "confirmations": 1}

    CalendarService(repo=repo, triggers=triggers).unlock_week(
        actor_id="user1", week_id=week.id
    )

    triggers.on_week_unapproved.assert_called_once()
    enviadas = triggers.on_week_unapproved.call_args.kwargs["assignments"]
    assert [a.id for a in enviadas] == [dentro.id]
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/calendars/test_unlock_cancels.py -x -q`
Expected: FAIL — `on_week_unapproved` no se llama

- [ ] **Step 3: Implementar**

En `unlock_week`, justo después del bloque que calcula `assignments_hash` (línea ~519) y antes
de `self.repo.update_week_status(...)`:

```python
        # Deshacer debe deshacer: lo que esta semana encoló y aún no ha salido
        # se cancela aquí, mientras seguimos sabiendo a qué semana pertenece.
        cancelled = {"notifications": 0, "confirmations": 0}
        if self.triggers is not None:
            cancelled = self.triggers.on_week_unapproved(
                actor_id=actor_id,
                assignments=week_assignments,
            )
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `pytest backend/tests/calendars/test_unlock_cancels.py -q`
Expected: 1 passed

- [ ] **Step 5: Comprobar que no rompió nada**

Run: `pytest backend/tests/calendars/ -q`
Expected: todo passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/calendars/service.py backend/tests/calendars/test_unlock_cancels.py
git commit -m "fix(calendars): cancel unsent notifications when a week is unlocked"
```

---

### Task 1.5 — `unlock_calendar` cancela (A2)

**Files:**
- Modify: `backend/app/application/calendars/service.py:253-313`
- Test: `backend/tests/calendars/test_unlock_cancels.py`

- [ ] **Step 1: Escribir el test que falla**

```python
def test_unlock_calendar_cancela_todas_las_asignaciones():
    repo, week, dentro, fuera = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 2, "confirmations": 2}

    CalendarService(repo=repo, triggers=triggers).unlock_calendar(
        actor_id="user1", calendar_id=week.calendar_id
    )

    enviadas = triggers.on_week_unapproved.call_args.kwargs["assignments"]
    assert [a.id for a in enviadas] == [dentro.id, fuera.id]
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/calendars/test_unlock_cancels.py::test_unlock_calendar_cancela_todas_las_asignaciones -x -q`
Expected: FAIL — `on_week_unapproved` no se llama

- [ ] **Step 3: Implementar**

En `unlock_calendar`, después de `snap_hash = ...` y antes de `version.status = "draft"`:

```python
        cancelled = {"notifications": 0, "confirmations": 0}
        if self.triggers is not None:
            cancelled = self.triggers.on_week_unapproved(
                actor_id=actor_id,
                assignments=current_assignments,
            )
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `pytest backend/tests/calendars/test_unlock_cancels.py -q`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/calendars/service.py backend/tests/calendars/test_unlock_cancels.py
git commit -m "fix(calendars): cancel unsent notifications when a calendar is unlocked"
```

---

### Task 1.6 — Auditoría de la cancelación (A5)

**Files:**
- Modify: `backend/app/application/audit/service.py`
- Modify: `backend/app/application/calendars/service.py`
- Test: `backend/tests/audit/test_notifications_cancelled_audit.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Sin rastro no se puede investigar qué pasó cuando alguien deshizo una aprobación."""

from unittest.mock import MagicMock

from backend.app.application.audit.service import AuditService


def test_registra_la_cancelacion(db_session):
    calendar = MagicMock(id="cal1")

    event = AuditService(db_session).log_notifications_cancelled(
        actor_id="user1",
        calendar=calendar,
        scope="week",
        notification_count=3,
        confirmation_count=2,
    )

    assert event.action_type == "notifications_cancelled"
    assert event.entity_id == "cal1"
    assert event.after["notifications"] == 3
    assert event.after["confirmations"] == 2
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/audit/test_notifications_cancelled_audit.py -x -q`
Expected: FAIL con `AttributeError: ... 'log_notifications_cancelled'`

- [ ] **Step 3: Implementar la auditoría**

En `backend/app/application/audit/service.py`, junto a `log_calendar_unlocked`:

```python
    def log_notifications_cancelled(
        self,
        *,
        actor_id: str,
        calendar,
        scope: str,
        notification_count: int,
        confirmation_count: int,
    ) -> AuditEventModel:
        return self._create(
            actor_id=actor_id,
            action_type="notifications_cancelled",
            entity_type="calendar",
            entity_id=calendar.id,
            after={
                "scope": scope,
                "notifications": notification_count,
                "confirmations": confirmation_count,
            },
        )
```

- [ ] **Step 4: Llamarla desde las dos operaciones**

En `unlock_week`, después de `self.repo.session.flush()` (línea ~551):

```python
        if self.audit is not None and (cancelled["notifications"] or cancelled["confirmations"]):
            self.audit.log_notifications_cancelled(
                actor_id=actor_id,
                calendar=calendar,
                scope="week",
                notification_count=cancelled["notifications"],
                confirmation_count=cancelled["confirmations"],
            )
```

En `unlock_calendar`, después de `self.repo.session.flush()` (línea ~304):

```python
        if self.audit is not None and (cancelled["notifications"] or cancelled["confirmations"]):
            self.audit.log_notifications_cancelled(
                actor_id=actor_id,
                calendar=calendar,
                scope="calendar",
                notification_count=cancelled["notifications"],
                confirmation_count=cancelled["confirmations"],
            )
```

> `unlock_week` necesita una referencia al calendario: la variable `calendar` ya existe en ese
> método (línea ~533); reutilizarla. Si es `None`, no registrar auditoría.

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `pytest backend/tests/audit/ backend/tests/calendars/ -q`
Expected: todo passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/application/audit/service.py backend/app/application/calendars/service.py backend/tests/audit/test_notifications_cancelled_audit.py
git commit -m "feat(audit): record how many notifications an unapproval cancelled"
```

---

### Task 1.7 — Quitar un turno aprobado cancela su confirmación (D2)

**Files:**
- Modify: `backend/app/application/notifications/triggers.py:237-256`
- Test: `backend/tests/notifications/test_triggers_unapproval.py`

- [ ] **Step 1: Escribir el test que falla**

```python
def test_quitar_un_turno_cancela_su_confirmacion():
    confirmations = MagicMock()
    confirmations.cancel_for_assignments.return_value = ["cr1"]
    triggers = NotificationTriggers(
        notification_service=MagicMock(),
        doctor_repo=MagicMock(),
        confirmation_service=confirmations,
    )
    triggers._queue_service_change = MagicMock(return_value=1)
    assignment = MagicMock(id="a1", doctor_id="doc1", service_date="2026-05-05")

    triggers.on_calendar_assignment_removed_after_approval(
        actor_id="user1", assignment=assignment, service_area_name="Emergencia"
    )

    confirmations.cancel_for_assignments.assert_called_once_with(["a1"])
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/notifications/test_triggers_unapproval.py::test_quitar_un_turno_cancela_su_confirmacion -x -q`
Expected: FAIL — no se llama `cancel_for_assignments`

- [ ] **Step 3: Implementar**

Al principio de `on_calendar_assignment_removed_after_approval`:

```python
        # Sin esto, la confirmación sigue viva y escala por un turno que ya no
        # existe. El aviso de "removido" se encola igual más abajo.
        if self.confirmation_service is not None:
            self.confirmation_service.cancel_for_assignments([assignment.id])
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `pytest backend/tests/notifications/ -q`
Expected: todo passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/application/notifications/triggers.py backend/tests/notifications/test_triggers_unapproval.py
git commit -m "fix(notifications): cancel the confirmation of a removed assignment"
```

---

### Task 1.8 — Mostrar cuántos avisos se cancelaron (A6)

**Files:**
- Modify: `backend/app/schemas/calendars.py`
- Modify: `backend/app/application/calendars/service.py`
- Modify: `frontend/src/api/calendars.ts`
- Modify: `frontend/src/features/calendars/CalendarGrid.tsx`
- Test: `frontend/src/features/calendars/CalendarGrid.test.tsx`

- [ ] **Step 1: Escribir el test de backend que falla**

```python
def test_unlock_week_expone_cuantos_cancelo():
    repo, week, _, _ = _approved_week()
    triggers = MagicMock()
    triggers.on_week_unapproved.return_value = {"notifications": 4, "confirmations": 4}

    result = CalendarService(repo=repo, triggers=triggers).unlock_week(
        actor_id="user1", week_id=week.id
    )

    assert result.cancelled_notifications == 4
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `pytest backend/tests/calendars/test_unlock_cancels.py -x -q`
Expected: FAIL con `AttributeError: ... 'cancelled_notifications'`

- [ ] **Step 3: Exponer el dato**

En `CalendarService.unlock_week`, antes del `return week`:

```python
        week.cancelled_notifications = cancelled["notifications"]
```

En `unlock_calendar`, antes del `return version`:

```python
        version.cancelled_notifications = cancelled["notifications"]
```

En `backend/app/schemas/calendars.py`, añadir a `WeekRead` y a `CalendarVersionRead`:

```python
    cancelled_notifications: int = 0
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `pytest backend/tests/calendars/ -q`
Expected: todo passed

- [ ] **Step 5: Escribir el test de frontend que falla**

En `frontend/src/features/calendars/CalendarGrid.test.tsx`, un caso que desbloquee una semana y
espere un mensaje con el número:

```tsx
it("dice cuántos avisos se cancelaron al desbloquear", async () => {
  // ... render con la semana aprobada y el mock de unlock resolviendo
  // cancelled_notifications: 4
  await screen.findByText(/4 avisos/i);
});
```

- [ ] **Step 6: Ejecutar y ver que falla**

Run: `npm test -- CalendarGrid` (dentro de `frontend/`)
Expected: FAIL — no aparece el texto

- [ ] **Step 7: Implementar**

En `frontend/src/api/calendars.ts`, añadir `cancelled_notifications: number;` a los tipos de semana
y versión. En el manejador de desbloqueo de `CalendarGrid.tsx`, tras la mutación:

```tsx
addToast(
  "success",
  result.cancelled_notifications > 0
    ? `Semana desbloqueada. Se cancelaron ${result.cancelled_notifications} avisos que aún no habían salido.`
    : "Semana desbloqueada.",
);
```

- [ ] **Step 8: Ejecutar y ver que pasa**

Run: `npm test -- CalendarGrid`
Expected: todo passed

- [ ] **Step 9: Verificación completa**

Run: `pytest backend/tests -q` y `npm test` en `frontend/`
Expected: todo passed, sin regresiones

- [ ] **Step 10: Commit**

```bash
git add backend/app/schemas/calendars.py backend/app/application/calendars/service.py frontend/src/api/calendars.ts frontend/src/features/calendars/CalendarGrid.tsx frontend/src/features/calendars/CalendarGrid.test.tsx
git commit -m "feat(calendars): tell the user how many notifications were cancelled"
```

---

## Fase 2 y 3 — pendientes de detallar

Se escriben cuando la Fase 1 esté verde y verificada:

- **Fase 2 (P2)** — el margen de 15 minutos: `approval_grace_minutes`, `scheduled_for` al encolar,
  y el banner con cuenta atrás.
- **Fase 3 (P3)** — D3: re-aprobar tras corregir vuelve a avisar. Depende de una decisión que la
  Fase 1 deja planteada: qué hacer con una fila `cancelled` cuando se vuelve a aprobar la misma
  asignación (reutilizarla, o emitir una nueva con otra clave).

## Criterios de aceptación

Los del spec, que esta fase debe cumplir: **AC1**, **AC2** y **AC6**. AC3–AC5 son de las fases
2 y 3.
