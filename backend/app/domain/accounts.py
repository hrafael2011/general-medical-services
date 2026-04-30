from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    ENCARGADO = "encargado"


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

