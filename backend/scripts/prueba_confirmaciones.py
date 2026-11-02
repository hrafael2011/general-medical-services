"""Prueba real del ciclo aviso → confirmación → escalación por Telegram.

No toca calendarios ni misiones: crea `confirmation_requests` con
`assignment_id = NULL` y clave `prueba:<fecha>:<doctor>`, y encola el aviso
por la misma ruta que usa una aprobación real (`notification_events`).

Todo lo que escribe lleva el prefijo `prueba:` para poder borrarlo con
`limpiar` sin tocar datos de producción.

Uso:
    python -m backend.scripts.prueba_confirmaciones enviar [--no-enviar]
    python -m backend.scripts.prueba_confirmaciones estado
    python -m backend.scripts.prueba_confirmaciones escalar
    python -m backend.scripts.prueba_confirmaciones limpiar
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from backend.app.application.confirmations.service import ConfirmationRequestService
from backend.app.application.notifications.providers import (
    FakeProvider,
    TelegramNotificationProvider,
)
from backend.app.application.notifications.service import NotificationService
from backend.app.application.notifications.templates import (
    render_escalamiento_consolidado,
    render_initial_assignment,
    with_telegram_buttons,
)
from backend.app.core.config import settings
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import DoctorModel
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.user import UserModel
from backend.app.infrastructure.db.session import SessionLocal
from backend.app.infrastructure.repositories.confirmations import (
    ConfirmationRequestRepository,
)
from backend.app.infrastructure.repositories.notifications import NotificationRepository

PREFIX = "prueba:"
AREA = "Medicina General (PRUEBA)"
START = "07:00"
TEST_HOURS_TO_DUE = 2


def _today_tag() -> str:
    """Con la hora, para poder repetir la prueba el mismo día sin chocar con la clave."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")


def _test_key(doctor_id: str, tag: str) -> str:
    return f"{PREFIX}{tag}:{doctor_id}"


def _provider():
    if settings.telegram_notification_bot_token:
        return TelegramNotificationProvider()
    print("! Sin TELEGRAM_NOTIFICATION_BOT_TOKEN: no se puede enviar nada.")
    return FakeProvider()


def _linked_doctors(session) -> list[DoctorModel]:
    return list(
        session.scalars(
            select(DoctorModel)
            .where(DoctorModel.telegram_chat_id.is_not(None))
            .order_by(DoctorModel.name)
        )
    )


def _test_message(doctor: DoctorModel, request: ConfirmationRequestModel) -> dict:
    """Mismo cuerpo que una aprobación real, con aviso de que es una prueba."""
    service_date = (datetime.now(UTC) + timedelta(days=1)).strftime("%d/%m/%Y")
    body = render_initial_assignment(service_date, AREA, START)
    url = (
        f"{settings.frontend_origin.rstrip('/')}"
        f"/confirmacion-medica?token={request.response_token}"
    )
    text = (
        "🧪 PRUEBA — este mensaje no corresponde a un turno real.\n\n"
        f"{body}\n\nSi el botón no funciona, abra: {url}"
    )
    return with_telegram_buttons(text, request.id)


def cmd_enviar(args: argparse.Namespace) -> int:
    session = SessionLocal()
    try:
        doctors = _linked_doctors(session)
        if not doctors:
            print("No hay médicos con Telegram vinculado: no hay a quién enviar.")
            return 1

        tag = _today_tag()
        confirmations = ConfirmationRequestService(
            ConfirmationRequestRepository(session)
        )
        notifications = NotificationService(
            repo=NotificationRepository(session), provider=_provider()
        )

        print(f"Médicos vinculados: {len(doctors)}")
        for doctor in doctors:
            # "service" es el valor real: el acuse elige la palabra a partir de él.
            request = confirmations.create_request(
                confirmation_type="service",
                idempotency_key=_test_key(doctor.id, tag),
                doctor_id=doctor.id,
                due_at=datetime.now(UTC) + timedelta(hours=TEST_HOURS_TO_DUE),
                created_by=None,
            )
            event = notifications.queue(
                notification_type="asignacion_inicial",
                idempotency_key=f"prueba:aviso:{tag}:{doctor.id}",
                recipient_doctor_id=doctor.id,
                recipient_phone=doctor.telegram_chat_id,
                payload={"message": _test_message(doctor, request)},
            )
            if request.notification_id != event.id:
                request.notification_id = event.id
            session.commit()
            print(f"  · {doctor.name:<40} chat {doctor.telegram_chat_id}  solicitud {request.id}")

        if args.no_enviar:
            print("\nEncolado sin enviar. El worker lo enviará en su próxima pasada.")
            return 0

        result = notifications.process_pending()
        print(f"\nEnvío: {result}")
        return 0
    finally:
        session.close()


def cmd_estado(_: argparse.Namespace) -> int:
    session = SessionLocal()
    try:
        doctor_names = {
            d.id: d.name for d in session.scalars(select(DoctorModel))
        }
        rows = session.execute(
            select(ConfirmationRequestModel, NotificationEventModel)
            .outerjoin(
                NotificationEventModel,
                NotificationEventModel.id == ConfirmationRequestModel.notification_id,
            )
            .where(ConfirmationRequestModel.idempotency_key.like(f"{PREFIX}%"))
            .order_by(ConfirmationRequestModel.created_at)
        ).all()

        if not rows:
            print("No hay solicitudes de prueba registradas.")
            return 0

        confirmadas = 0
        for request, event in rows:
            name = doctor_names.get(request.doctor_id, request.doctor_id)
            marca = {"confirmed": "✅ confirmó"}.get(request.status, f"— {request.status}")
            if request.status == "confirmed":
                confirmadas += 1
            respondio = request.responded_at.strftime("%H:%M:%S") if request.responded_at else "—"
            envio = event.status if event else "sin aviso"
            escalado = request.escalated_at.strftime("%H:%M:%S") if request.escalated_at else "—"
            print(
                f"{name:<40} {marca:<12} respondió {respondio:<9} "
                f"aviso {envio:<9} escalado {escalado}"
            )

        print(f"\nConfirmaron {confirmadas} de {len(rows)}.")
        return 0
    finally:
        session.close()


def cmd_escalar(_: argparse.Namespace) -> int:
    """Envía ya el consolidado de la prueba a los encargados con el permiso."""
    session = SessionLocal()
    try:
        pendientes = list(
            session.scalars(
                select(ConfirmationRequestModel).where(
                    ConfirmationRequestModel.idempotency_key.like(f"{PREFIX}%"),
                    ConfirmationRequestModel.status.in_(["pending", "received"]),
                    ConfirmationRequestModel.escalated_at.is_(None),
                )
            )
        )
        if not pendientes:
            print("No hay solicitudes de prueba pendientes que escalar.")
            return 0

        encargados = list(
            session.scalars(
                select(UserModel).where(
                    UserModel.active.is_(True),
                    UserModel.telegram_chat_id.is_not(None),
                    UserModel.permissions.contains(["receive_escalation_alerts"]),
                )
            )
        )
        if not encargados:
            print(
                "Hay "
                f"{len(pendientes)} pendientes, pero ningún encargado activo con "
                "telegram_chat_id y el permiso receive_escalation_alerts: "
                "no hay destinatario."
            )
            return 1

        doctor_names = {
            d.id: d.name for d in session.scalars(select(DoctorModel))
        }
        names = [doctor_names.get(r.doctor_id, r.doctor_id) for r in pendientes]
        message = render_escalamiento_consolidado(names)

        notifications = NotificationService(
            repo=NotificationRepository(session), provider=_provider()
        )
        now = datetime.now(UTC)
        for req in pendientes:
            req.escalated_at = now
            req.updated_at = now

        for encargado in encargados:
            notifications.queue(
                notification_type="escalamiento",
                idempotency_key=f"prueba:escalamiento:{now.strftime('%Y%m%d%H%M')}:{encargado.id}",
                recipient_doctor_id=None,
                recipient_phone=encargado.telegram_chat_id,
                payload={"message": message},
            )
        session.commit()

        result = notifications.process_pending()
        print(f"Pendientes: {names}")
        print(f"Encargados: {[e.name for e in encargados]}")
        print(f"Envío: {result}")
        return 0
    finally:
        session.close()


def cmd_limpiar(_: argparse.Namespace) -> int:
    session = SessionLocal()
    try:
        # Primero las solicitudes: tienen FK al aviso.
        confirmations = session.execute(
            delete(ConfirmationRequestModel).where(
                ConfirmationRequestModel.idempotency_key.like(f"{PREFIX}%")
            )
        ).rowcount
        events = session.execute(
            delete(NotificationEventModel).where(
                NotificationEventModel.idempotency_key.like(f"{PREFIX}%")
            )
        ).rowcount
        session.commit()
        print(f"Borradas {confirmations} solicitudes y {events} avisos de prueba.")
        return 0
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    enviar = sub.add_parser(
        "enviar", help="Crea y envía el aviso de prueba a cada médico vinculado"
    )
    enviar.add_argument(
        "--no-enviar",
        action="store_true",
        help="Solo encola; deja que el worker lo mande en su próxima pasada",
    )
    enviar.set_defaults(func=cmd_enviar)

    sub.add_parser("estado", help="Quién confirmó y quién no").set_defaults(func=cmd_estado)
    sub.add_parser("escalar", help="Envía el consolidado a los encargados").set_defaults(
        func=cmd_escalar
    )
    sub.add_parser("limpiar", help="Borra solo las filas de prueba").set_defaults(
        func=cmd_limpiar
    )

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
