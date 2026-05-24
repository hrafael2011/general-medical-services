from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    ENCARGADO = "encargado"


class Permission(StrEnum):
    MANAGE_DOCTORS = "manage_doctors"
    MANAGE_CALENDARS = "manage_calendars"
    MANAGE_MISSIONS = "manage_missions"
    MANAGE_AVAILABILITY = "manage_availability"
    MANAGE_CATALOGS = "manage_catalogs"
    MANAGE_USERS = "manage_users"
    MANAGE_ADMINS = "manage_admins"
    MANAGE_TRASH = "manage_trash"
    VIEW_AUDIT = "view_audit"
    VIEW_NOTIFICATIONS = "view_notifications"
    MANAGE_CONFIRMATIONS = "manage_confirmations"
    MANAGE_ALERTS = "manage_alerts"
    EXPORT_REPORTS = "export_reports"
    RECEIVE_ESCALATION_ALERTS = "receive_escalation_alerts"


@dataclass(frozen=True)
class AuthenticatedUser:
    id: str
    name: str
    email: str
    role: UserRole
    active: bool
    must_change_password: bool
    token_version: int
    locked_until: datetime | None
    is_superadmin: bool = False
    permissions: list[str] = field(default_factory=list)
