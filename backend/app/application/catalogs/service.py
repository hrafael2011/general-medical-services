from datetime import UTC, datetime
import re
import unicodedata
from uuid import uuid4

from backend.app.domain.catalogs import (
    INITIAL_DEACTIVATION_REASONS,
    INITIAL_DEPARTMENTS,
    INITIAL_SERVICE_AREAS,
)
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
    SystemSettingModel,
)
from backend.app.infrastructure.repositories.catalogs import CatalogRepository


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_reason_code(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value.strip())
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    code = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    return code or "reason"


_MISSING = object()


class CatalogService:
    def __init__(self, catalogs: CatalogRepository) -> None:
        self.catalogs = catalogs

    def seed_initial_catalogs(self) -> None:
        now = datetime.now(UTC)
        for item in INITIAL_SERVICE_AREAS:
            if self.catalogs.get_service_area_by_code(item["code"]) is None:
                self.catalogs.add_service_area(
                    ServiceAreaModel(
                        id=str(uuid4()),
                        code=item["code"],
                        display_name=item["display_name"],
                        active=True,
                        required_for_daily_coverage=bool(item["required_for_daily_coverage"]),
                        load_weight=int(item["load_weight"]),
                        created_at=now,
                        updated_at=now,
                    )
                )

        for item in INITIAL_DEACTIVATION_REASONS:
            if self.catalogs.get_deactivation_reason_by_code(item["code"]) is None:
                self.catalogs.add_deactivation_reason(
                    DeactivationReasonModel(
                        id=str(uuid4()),
                        code=item["code"],
                        display_name=item["display_name"],
                        active=True,
                        requires_detail=bool(item["requires_detail"]),
                        applies_to_sex=item["applies_to_sex"],
                        severity=item["severity"],
                        created_at=now,
                        updated_at=now,
                    )
                )

        existing_department_names = {
            department.normalized_name
            for department in self.catalogs.list_departments()
        }
        for item in INITIAL_DEPARTMENTS:
            normalized_name = normalize_name(item["name"])
            if normalized_name not in existing_department_names:
                self.catalogs.add_department(
                    DepartmentModel(
                        id=str(uuid4()),
                        name=item["name"],
                        normalized_name=normalized_name,
                        active=True,
                        created_at=now,
                        updated_at=now,
                    )
                )
                existing_department_names.add(normalized_name)

        from backend.app.application.reports.weasyprint_gen import DEFAULT_SIGNATURES as _sigs
        for key, value, description in [
            ("pdf.sig_left_name",   _sigs.left_name,   "Nombre de la firmante izquierda en PDFs institucionales."),
            ("pdf.sig_left_title1", _sigs.left_title1, "Título 1 de la firmante izquierda."),
            ("pdf.sig_left_title2", _sigs.left_title2, "Título 2 de la firmante izquierda."),
            ("pdf.sig_left_title3", _sigs.left_title3, "Título 3 de la firmante izquierda."),
            ("pdf.sig_right_name",   _sigs.right_name,   "Nombre del firmante derecho en PDFs institucionales."),
            ("pdf.sig_right_title1", _sigs.right_title1, "Título 1 del firmante derecho."),
            ("pdf.sig_right_title2", _sigs.right_title2, "Título 2 del firmante derecho."),
            ("pdf.sig_right_title3", _sigs.right_title3, "Título 3 del firmante derecho."),
        ]:
            self.catalogs.upsert_setting(
                SystemSettingModel(key=key, value=value, description=description, updated_at=now)
            )

    def create_rank(self, name: str, abbreviation: str) -> RankModel:
        now = datetime.now(UTC)
        rank = RankModel(
            id=str(uuid4()),
            name=name.strip(),
            normalized_name=normalize_name(name),
            abbreviation=abbreviation.strip(),
            active=True,
            created_at=now,
            updated_at=now,
        )
        return self.catalogs.add_rank(rank)

    def create_department(self, name: str) -> DepartmentModel:
        now = datetime.now(UTC)
        department = DepartmentModel(
            id=str(uuid4()),
            name=name.strip(),
            normalized_name=normalize_name(name),
            active=True,
            created_at=now,
            updated_at=now,
        )
        return self.catalogs.add_department(department)

    def create_deactivation_reason(
        self,
        *,
        display_name: str,
        applies_to_sex: str | None,
    ) -> DeactivationReasonModel:
        now = datetime.now(UTC)
        display_name = display_name.strip()
        reason = DeactivationReasonModel(
            id=str(uuid4()),
            code=normalize_reason_code(display_name),
            display_name=display_name,
            active=True,
            requires_detail=False,
            applies_to_sex=applies_to_sex,
            severity="hard_block",
            created_at=now,
            updated_at=now,
        )
        return self.catalogs.add_deactivation_reason(reason)

    def update_rank(
        self,
        rank_id: str,
        *,
        name: str | None = None,
        abbreviation: str | None = None,
        active: bool | None = None,
    ) -> RankModel:
        rank = self.catalogs.get_rank_by_id(rank_id)
        if rank is None:
            raise CatalogError("rank_not_found", "Rango no encontrado.")
        changed: dict[str, object] = {}
        if name is not None:
            rank.name = name.strip()
            rank.normalized_name = normalize_name(name)
            changed["name"] = rank.name
            changed["normalized_name"] = rank.normalized_name
        if abbreviation is not None:
            rank.abbreviation = abbreviation.strip()
            changed["abbreviation"] = rank.abbreviation
        if active is not None:
            rank.active = active
            changed["active"] = active
        if changed:
            self.catalogs.update_rank(rank_id, **changed)
        return rank

    def soft_delete_rank(self, rank_id: str) -> int:
        rank = self.catalogs.get_rank_by_id(rank_id)
        if rank is None:
            raise CatalogError("rank_not_found", "Rango no encontrado.")
        affected = self.catalogs.count_doctors_by_rank(rank_id)
        self.catalogs.soft_delete_rank(rank_id)
        return affected

    def update_deactivation_reason(
        self,
        reason_id: str,
        *,
        display_name: str | None = None,
        applies_to_sex: str | None | object = _MISSING,
        active: bool | None = None,
    ) -> DeactivationReasonModel:
        reason = self.catalogs.get_deactivation_reason_by_id(reason_id)
        if reason is None:
            raise CatalogError("deactivation_reason_not_found", "Razón de desactivación no encontrada.")
        changed: dict[str, object] = {}
        if display_name is not None:
            reason.display_name = display_name.strip()
            reason.code = normalize_reason_code(reason.display_name)
            changed["display_name"] = reason.display_name
            changed["code"] = reason.code
        if applies_to_sex is not _MISSING:
            reason.applies_to_sex = applies_to_sex
            changed["applies_to_sex"] = applies_to_sex
        if active is not None:
            reason.active = active
            changed["active"] = active
        if changed:
            self.catalogs.update_deactivation_reason(reason_id, **changed)
        return reason

    def soft_delete_deactivation_reason(self, reason_id: str) -> int:
        reason = self.catalogs.get_deactivation_reason_by_id(reason_id)
        if reason is None:
            raise CatalogError("deactivation_reason_not_found", "Razón de desactivación no encontrada.")
        affected = self.catalogs.count_doctors_by_deactivation_reason(reason_id)
        self.catalogs.soft_delete_deactivation_reason(reason_id)
        return affected

    def update_department(
        self,
        department_id: str,
        *,
        name: str | None = None,
        active: bool | None = None,
    ) -> DepartmentModel:
        department = self.catalogs.get_department_by_id(department_id)
        if department is None:
            raise CatalogError("department_not_found", "Departamento no encontrado.")
        changed: dict[str, object] = {}
        if name is not None:
            department.name = name.strip()
            department.normalized_name = normalize_name(name)
            changed["name"] = department.name
            changed["normalized_name"] = department.normalized_name
        if active is not None:
            department.active = active
            changed["active"] = active
        if changed:
            self.catalogs.update_department(department_id, **changed)
        return department

    def soft_delete_department(self, department_id: str) -> int:
        department = self.catalogs.get_department_by_id(department_id)
        if department is None:
            raise CatalogError("department_not_found", "Departamento no encontrado.")
        affected = self.catalogs.count_doctors_by_department(department_id)
        self.catalogs.soft_delete_department(department_id)
        return affected


class CatalogError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
