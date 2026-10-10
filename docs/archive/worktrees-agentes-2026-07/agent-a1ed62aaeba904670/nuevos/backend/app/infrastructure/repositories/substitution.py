"""Repository for substitution records."""

from backend.app.infrastructure.db.models.substitution import (
    SubstitutionRecordModel,
)


class SubstitutionRepository:
    def __init__(self, session):
        self.session = session

    def list_by_version(self, version_id: str) -> list[SubstitutionRecordModel]:
        return (
            self.session.query(SubstitutionRecordModel)
            .filter(SubstitutionRecordModel.calendar_version_id == version_id)
            .all()
        )

    def create(
        self, record: SubstitutionRecordModel
    ) -> SubstitutionRecordModel:
        self.session.add(record)
        self.session.flush()
        return record
