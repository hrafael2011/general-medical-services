---
spec: 04
version: 1.0.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Spec 04 - WhatsApp Notifications (Twilio)

## Goal

Notify doctors of service assignments and send a reminder 12 hours before service start, minimizing messaging cost.

## Policy

- No confirmation flow in MVP.
- Notifications only:
  - Initial service notification
  - Reminder 12 hours before service
  - Encargado reminder for missing doctor availability before monthly calendar generation
  - Mission assignment notification to mission participants
  - Mission summary notification to encargado after mission confirmation

## Message Content

Required fields:

- Service date
- Service time
- Service area/location
- Institution context (if needed)

Mission participant notification fields:

- Mission date
- Mission time if available
- Mission location if available
- Mission description if available
- Institution context

Mission encargado summary fields:

- Mission date
- Mission location/description if available
- Participant list
- Recommendation to confirm final details with participants

Message templates sent to doctors must be written in Spanish.

Internal template identifiers may be written in English.

## Scheduling

- Trigger initial notification after calendar reaches `official`.
- Schedule reminder job at `service_start_at - 12h`.
- Send encargado missing-availability reminder two days before the configured calendar auto-generation day.
- Send mission participant and encargado summary notifications immediately after mission confirmation.
- Use timezone-aware datetimes.

## Delivery Reliability

- Idempotency key per doctor/event/service datetime.
- Retry policy for transient failures.
- Persist provider metadata for audit.

## Acceptance Criteria

1. Given official calendar assignments, initial notifications are queued and sent.
2. Given service start datetime, reminder is sent 12h before.
3. Duplicate scheduler/job retries do not create duplicate messages.
4. Delivery failures are logged and visible for operations.
5. Given the configured generation day is approaching, when doctors have missing required availability two days before generation, then the encargado receives a WhatsApp reminder listing pending doctors.
6. Given a mission is confirmed, then each mission participant receives a WhatsApp notification with mission details.
7. Given a mission is confirmed, then the encargado receives a WhatsApp summary with participant list and a recommendation to confirm details with participants.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Define notificaciones WhatsApp vía Twilio, política sin confirmación, contenido de mensajes, programación y fiabilidad de entrega. |