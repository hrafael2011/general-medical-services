from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.users import UserRepository

if TYPE_CHECKING:
    from backend.app.infrastructure.repositories.audit import AuditRepository


class TrashServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class TrashService:
    VALID_TYPES = {"doctors", "users", "ranks", "departments", "deactivation_reasons"}
    _ANONYMIZABLE_TYPES = {"doctors", "users"}

    def __init__(
        self,
        doctors: DoctorRepository,
        users: UserRepository,
        catalogs: CatalogRepository,
        audit: "AuditRepository | None" = None,
    ) -> None:
        self.doctors = doctors
        self.users = users
        self.catalogs = catalogs
        self.audit = audit

    def list_deleted(self, entity_type: str) -> list:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Tipo de entidad no válido: {entity_type}")
        if entity_type == "doctors":
            return self.doctors.list_deleted()
        if entity_type == "users":
            return self.users.list_deleted()
        if entity_type == "ranks":
            return self.catalogs.list_deleted_ranks()
        if entity_type == "departments":
            return self.catalogs.list_deleted_departments()
        return self.catalogs.list_deleted_deactivation_reasons()

    def restore(self, entity_type: str, entity_id: str) -> None:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Tipo de entidad no válido: {entity_type}")
        entity = self._get_entity_including_deleted(entity_type, entity_id)
        if entity is None:
            raise TrashServiceError("not_found", f"{entity_type} con id {entity_id} no encontrado.")
        if entity.deleted_at is None:
            raise TrashServiceError("not_deleted", "La entidad no está eliminada.")
        self._restore_entity(entity_type, entity_id)

    def hard_delete(self, entity_type: str, entity_id: str) -> None:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Tipo de entidad no válido: {entity_type}")
        entity = self._get_entity_including_deleted(entity_type, entity_id)
        if entity is None:
            raise TrashServiceError("not_found", f"{entity_type} con id {entity_id} no encontrado.")
        if entity.deleted_at is None:
            raise TrashServiceError("not_deleted", "La entidad no está eliminada.")
        if entity_type in self._ANONYMIZABLE_TYPES and self.audit is not None:
            self.audit.anonymize_entity(entity_id)
        try:
            self._hard_delete_entity(entity_type, entity_id)
        except IntegrityError:
            raise TrashServiceError(
                "integrity_violation",
                "No se puede eliminar permanentemente: la entidad tiene registros asociados. Elimina esos registros primero.",
            )

    def _get_entity_including_deleted(self, entity_type: str, entity_id: str):
        if entity_type == "doctors":
            return self.doctors.get_by_id_including_deleted(entity_id)
        if entity_type == "users":
            return self.users.get_by_id_including_deleted(entity_id)
        if entity_type == "ranks":
            return self.catalogs.get_rank_by_id_including_deleted(entity_id)
        if entity_type == "departments":
            return self.catalogs.get_department_by_id_including_deleted(entity_id)
        return self.catalogs.get_deactivation_reason_by_id_including_deleted(entity_id)

    def _restore_entity(self, entity_type: str, entity_id: str) -> None:
        if entity_type == "doctors":
            self.doctors.restore(entity_id)
        elif entity_type == "users":
            self.users.restore(entity_id)
        elif entity_type == "ranks":
            self.catalogs.restore_rank(entity_id)
        elif entity_type == "departments":
            self.catalogs.restore_department(entity_id)
        else:
            self.catalogs.restore_deactivation_reason(entity_id)

    def _hard_delete_entity(self, entity_type: str, entity_id: str) -> None:
        if entity_type == "doctors":
            self.doctors.hard_delete(entity_id)
        elif entity_type == "users":
            self.users.hard_delete(entity_id)
        elif entity_type == "ranks":
            self.catalogs.hard_delete_rank(entity_id)
        elif entity_type == "departments":
            self.catalogs.hard_delete_department(entity_id)
        else:
            self.catalogs.hard_delete_deactivation_reason(entity_id)
