---
spec: 10
version: 1.0.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Spec 10 - Seguridad, Acceso y Usuarios

## Goal

Define the access model for a small institutional system with a minimal user base and strong operational controls.

The system is not a commercial self-service product. It should avoid unnecessary password recovery complexity while preserving good security practices, auditability, and role separation.

## Roles

MVP roles:

- `admin`
- `encargado`

The role model may evolve later, but MVP behavior must remain simple and explicit.

Internal role codes should remain stable and lowercase. User-facing labels in the panel and assistant responses must be Spanish, such as "Administrador" and "Encargado".

## Admin Role

The `admin` is responsible for account administration and critical configuration.

Allowed actions:

- create `encargado` users,
- activate or deactivate `encargado` users,
- reset `encargado` passwords,
- view critical security and account audit events,
- manage basic institutional configuration.

The `admin` should not be required for daily medical scheduling operations unless the installation chooses to use the admin account that way.

## Encargado Role

The `encargado` is responsible for daily operation.

Allowed actions:

- manage doctors,
- manage availability,
- manage restrictions and licenses,
- generate calendar drafts,
- review and modify calendars according to validation rules,
- approve or mark calendars according to the configured workflow,
- link and manage Telegram users,
- consult operational reports,
- use Telegram assistant intents allowed for operations.

The `encargado` cannot:

- create other `encargado` users,
- reset another user's password,
- reset the `admin` password,
- bypass mandatory password change,
- disable non-disableable baseline rules.

## User Model Requirements

The `User` model must support:

- `id`
- `name`
- `email`
- `role`
- `active`
- `password_hash`
- `must_change_password`
- `last_login_at`
- `created_by`
- `created_at`
- `updated_at`

Recommended additional fields:

- `failed_login_count`
- `locked_until`
- `password_changed_at`
- `deactivated_at`
- `deactivated_by`

Passwords must be stored only as secure hashes, using an accepted password hashing algorithm such as Argon2 or bcrypt.

Passwords must never be logged.

## Creating Encargado Users

Flow:

1. Admin creates an `encargado`.
2. System creates or accepts a temporary password.
3. User is stored with `must_change_password = true`.
4. Account creation creates an audit event.
5. The temporary password must be delivered through an agreed secure operational channel outside system logs.

## Mandatory Password Change

Any user with `must_change_password = true` is blocked from all operational functionality.

Allowed actions while blocked:

- login,
- change own password,
- logout.

Blocked actions while password change is pending:

- manage doctors,
- manage availability,
- manage calendars,
- view reports,
- use Telegram assistant,
- perform administrative actions,
- call operational API endpoints.

When the password is changed successfully:

- store new password hash,
- set `must_change_password = false`,
- set `password_changed_at`,
- invalidate previous sessions,
- create an audit event.

The new password must not be the same as the temporary or reset password.

## Encargado Password Reset

Flow:

1. Admin selects an active or inactive `encargado`.
2. Admin resets the password.
3. System creates or accepts a temporary password.
4. System sets `must_change_password = true`.
5. Existing sessions for that user are invalidated.
6. Password reset creates an audit event.

The `encargado` cannot use panel features or Telegram until the password is changed.

## Admin Password Recovery

If the `admin` forgets the password, recovery is performed by CLI from a secure backend environment.

No public email-based recovery flow is required for MVP.

CLI requirements:

- identify the admin account explicitly,
- require confirmation before reset,
- never display the current password,
- create or accept a temporary password,
- set `must_change_password = true`,
- invalidate existing admin sessions,
- create an audit event or security log entry,
- avoid printing secrets to logs.

Conceptual command:

```bash
python manage.py reset-admin-password --email admin@example.local
```

The exact command may change by implementation, but behavior must remain auditable and restricted to trusted operators with server access.

## Authentication Requirements

The system must enforce:

- password hash verification,
- session expiration,
- session invalidation after password reset,
- temporary lockout or throttling after repeated failed logins,
- active account check,
- mandatory password change check before operational access.

## Authorization Requirements

Every API endpoint must validate:

- authenticated user,
- active account,
- password change completed,
- role permission for the action.

Every Telegram intent must validate:

- Telegram user is linked,
- linked system user is active,
- linked system user does not have pending password change,
- role is allowed for the requested intent.

Unauthorized access attempts must be rejected and logged.

## Telegram User Linking

Telegram users must be linked manually or through an approved controlled flow by an `encargado`.

The system must store:

- Telegram user id,
- linked system user id,
- active status,
- linked_by,
- linked_at,
- last_used_at.

Unlinked or inactive Telegram users must not receive operational data.

## Audit Events

Minimum security audit events:

- user created,
- user activated,
- user deactivated,
- password reset by admin,
- admin password reset by CLI,
- mandatory password change completed,
- login success,
- login failure,
- account lockout,
- Telegram user linked,
- Telegram user unlinked or disabled,
- unauthorized access attempt.

Audit entries must include actor, target user where applicable, timestamp, action type, request id where available, and metadata without storing plaintext secrets.

## Acceptance Criteria

1. Given an admin user, when they create an encargado, then the encargado is created with `must_change_password = true` and cannot access operational features until changing the password.
2. Given an encargado with pending password change, when they call an operational panel endpoint, then the request is rejected.
3. Given an encargado with pending password change, when they use Telegram, then the assistant rejects the request without exposing operational data.
4. Given an admin resets an encargado password, when reset succeeds, then previous sessions are invalidated and the encargado must change password on next login.
5. Given the admin password is forgotten, when trusted server access is available, then a CLI reset can set a temporary password, force password change, invalidate sessions, and log the event.
6. Given any user login attempt, when the credentials are wrong repeatedly, then throttling or temporary lockout is applied and audit events are recorded.
7. Given an unlinked Telegram user, when they message the bot, then no operational data is returned.
8. Given an unauthorized role attempts a restricted action, then the system rejects the action and records an audit event.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Define roles admin/encargado, modelo de usuario, flujos de creación y reset de contraseña, bloqueo por cambio pendiente y eventos de auditoría de seguridad. |