---
spec: 05
version: 1.0.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Spec 05 - Reportes y Auditoria

## Goal

Provide institutional reporting and full traceability for critical actions.

## Required Reports

- Monthly calendar
- Doctor history
- Notifications sent
- Overrides
- Fairness applied
- Services by area
- Debts/penalties
- Licenses
- Institutional summary

## Export Formats

- PDF
- Excel

Each report includes:

- Generation date
- Institution metadata
- Status/context
- Audit reference when applicable

Reports intended for institutional users must be written in Spanish.

Internal report identifiers, export job names, and code-level names may be written in English.

## Audit Events (Minimum)

- Doctor creation/update
- Availability/restriction updates
- Calendar generation/approval
- Manual modifications and overrides
- Rule toggles and skipped rules
- Telegram critical queries
- Notification send attempts/results
- System errors affecting operations
- Security/account events such as user creation, password reset, mandatory password change, login failures, and Telegram user linking
- Unauthorized assistant or panel access attempts

## Acceptance Criteria

1. Critical domain actions produce an immutable audit event.
2. Weekly and monthly report exports are generated successfully.
3. Fairness conflict rationale is traceable from UI/export to audit data.
4. Audit queries can filter by actor, date range, action type.
5. Security and assistant access events are available for audit filtering without exposing plaintext secrets.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Define reportes institucionales, formatos de exportación y eventos mínimos de auditoría. |