from sqlalchemy.exc import IntegrityError

from backend.app.infrastructure.repositories.catalogs import CatalogRepository
from backend.app.infrastructure.repositories.doctors import DoctorRepository
from backend.app.infrastructure.repositories.users import UserRepository


class TrashServiceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


class TrashService:
    VALID_TYPES = {"doctors", "users", "ranks", "departments"}

    def __init__(
        self,
        doctors: DoctorRepository,
        users: UserRepository,
        catalogs: CatalogRepository,
    ) -> None:
        self.doctors = doctors
        self.users = users
        self.catalogs = catalogs

    def list_deleted(self, entity_type: str) -> list:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Invalid entity type: {entity_type}")
        if entity_type == "doctors":
            return self.doctors.list_deleted()
        if entity_type == "users":
            return self.users.list_deleted()
        if entity_type == "ranks":
            return self.catalogs.list_deleted_ranks()
        return self.catalogs.list_deleted_departments()

    def restore(self, entity_type: str, entity_id: str) -> None:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Invalid entity type: {entity_type}")
        entity = self._get_entity_including_deleted(entity_type, entity_id)
        if entity is None:
            raise TrashServiceError("not_found", f"{entity_type} with id {entity_id} not found")
        if entity.deleted_at is None:
            raise TrashServiceError("not_deleted", "Entity is not deleted")
        self._restore_entity(entity_type, entity_id)

    def hard_delete(self, entity_type: str, entity_id: str) -> None:
        if entity_type not in self.VALID_TYPES:
            raise TrashServiceError("invalid_type", f"Invalid entity type: {entity_type}")
        entity = self._get_entity_including_deleted(entity_type, entity_id)
        if entity is None:
            raise TrashServiceError("not_found", f"{entity_type} with id {entity_id} not found")
        if entity.deleted_at is None:
            raise TrashServiceError("not_deleted", "Entity is not deleted")
        try:
            self._hard_delete_entity(entity_type, entity_id)
        except IntegrityError:
            raise TrashServiceError(
                "integrity_violation",
                "Cannot permanently delete: the entity has associated records. Remove those records first.",
            )

    def _get_entity_including_deleted(self, entity_type: str, entity_id: str):
        if entity_type == "doctors":
            return self.doctors.get_by_id_including_deleted(entity_id)
        if entity_type == "users":
            return self.users.get_by_id_including_deleted(entity_id)
        if entity_type == "ranks":
            return self.catalogs.get_rank_by_id_including_deleted(entity_id)
        return self.catalogs.get_department_by_id_including_deleted(entity_id)

    def _restore_entity(self, entity_type: str, entity_id: str) -> None:
        if entity_type == "doctors":
            self.doctors.restore(entity_id)
        elif entity_type == "users":
            self.users.restore(entity_id)
        elif entity_type == "ranks":
            self.catalogs.restore_rank(entity_id)
        else:
            self.catalogs.restore_department(entity_id)

    def _hard_delete_entity(self, entity_type: str, entity_id: str) -> None:
        if entity_type == "doctors":
            self.doctors.hard_delete(entity_id)
        elif entity_type == "users":
            self.users.hard_delete(entity_id)
        elif entity_type == "ranks":
            self.catalogs.hard_delete_rank(entity_id)
        else:
            self.catalogs.hard_delete_department(entity_id)
