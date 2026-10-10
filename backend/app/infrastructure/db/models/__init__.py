"""SQLAlchemy models.

Every model is imported here on purpose, and this module must be imported before any
query runs.

SQLAlchemy resolves a relationship by table name, so a model whose module was never
imported is simply absent from the metadata and any foreign key pointing at it raises
`NoReferencedTableError`. The API process never noticed because importing the routes
pulls everything in; the scheduler does not import routes, so its jobs lazily imported
only the models they used and crashed on the first foreign key that pointed elsewhere.
That is how a month of notifications queued without ever being delivered, while the
runner reported zeros as if there had been nothing to send.
"""

from backend.app.infrastructure.db.models.action_alerts import ActionAlertModel
from backend.app.infrastructure.db.models.audit import AuditEventModel
from backend.app.infrastructure.db.models.availability import (
    DoctorAvailabilityModel,
    DoctorRestrictionModel,
)
from backend.app.infrastructure.db.models.calendars import (
    CalendarAssignmentModel,
    CalendarModel,
    CalendarVersionModel,
    CalendarWeekModel,
    UnresolvedGapModel,
)
from backend.app.infrastructure.db.models.catalogs import (
    DeactivationReasonModel,
    DepartmentModel,
    RankModel,
    ServiceAreaModel,
    SystemSettingModel,
)
from backend.app.infrastructure.db.models.confirmations import ConfirmationRequestModel
from backend.app.infrastructure.db.models.doctors import (
    DoctorAllowedAreaModel,
    DoctorModel,
)
from backend.app.infrastructure.db.models.missions import (
    MissionAssignmentModel,
    MissionCandidateRankingEntryModel,
    MissionCandidateRankingModel,
    MissionParticipantModel,
)
from backend.app.infrastructure.db.models.notifications import NotificationEventModel
from backend.app.infrastructure.db.models.set_password_token import SetPasswordTokenModel
from backend.app.infrastructure.db.models.telegram import (
    TelegramInteractionModel,
    TelegramLinkTokenModel,
    TelegramUserLinkModel,
)
from backend.app.infrastructure.db.models.telegram_session import TelegramSessionModel
from backend.app.infrastructure.db.models.user import (
    LoginAttemptModel,
    PasswordHistoryModel,
    PasswordRecoveryAttemptModel,
    UserModel,
)

__all__ = [
    "ActionAlertModel",
    "AuditEventModel",
    "CalendarAssignmentModel",
    "CalendarModel",
    "CalendarVersionModel",
    "CalendarWeekModel",
    "ConfirmationRequestModel",
    "DeactivationReasonModel",
    "DepartmentModel",
    "DoctorAllowedAreaModel",
    "DoctorAvailabilityModel",
    "DoctorModel",
    "DoctorRestrictionModel",
    "LoginAttemptModel",
    "MissionAssignmentModel",
    "MissionCandidateRankingEntryModel",
    "MissionCandidateRankingModel",
    "MissionParticipantModel",
    "NotificationEventModel",
    "PasswordHistoryModel",
    "PasswordRecoveryAttemptModel",
    "RankModel",
    "ServiceAreaModel",
    "SetPasswordTokenModel",
    "SystemSettingModel",
    "TelegramInteractionModel",
    "TelegramLinkTokenModel",
    "TelegramSessionModel",
    "TelegramUserLinkModel",
    "UnresolvedGapModel",
    "UserModel",
]
