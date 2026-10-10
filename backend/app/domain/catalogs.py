from enum import StrEnum


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"


class DeactivationSeverity(StrEnum):
    HARD_BLOCK = "hard_block"
    WARN = "warn"
    INFORMATIONAL = "informational"


INITIAL_SERVICE_AREAS = [
    {
        "code": "emergencia",
        "display_name": "Emergencia",
        "load_weight": 3,
        "required_for_daily_coverage": True,
        "start_hour": 7,
    },
    {
        "code": "pista",
        "display_name": "Pista",
        "load_weight": 2,
        "required_for_daily_coverage": True,
        "start_hour": 6,
    },
    {
        "code": "disponible",
        "display_name": "Disponible",
        "load_weight": 1,
        "required_for_daily_coverage": True,
        "start_hour": 7,
    },
]

INITIAL_DEPARTMENTS = [
    {"name": "Licencias Médicas"},
    {"name": "Enseñanza"},
    {"name": "Evaluaciones Médicas"},
    {"name": "Subdirección"},
    {"name": "Recursos Humanos"},
]

INITIAL_DEACTIVATION_REASONS = [
    {
        "code": "medical_license",
        "display_name": "Licencia medica",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "pregnancy",
        "display_name": "Embarazo",
        "requires_detail": False,
        "applies_to_sex": Sex.FEMALE.value,
        "expects_return": True,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "no_service",
        "display_name": "No realiza servicio",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": False,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "vacation",
        "display_name": "Vacaciones",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.WARN.value,
    },
    {
        "code": "loan",
        "display_name": "Préstamo",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.WARN.value,
    },
    {
        "code": "administrative_restriction",
        "display_name": "Restriccion administrativa",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "transfer_or_area_change",
        "display_name": "Traslado / cambio de area",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.WARN.value,
    },
    {
        "code": "temporarily_suspended",
        "display_name": "Suspendido temporalmente",
        "requires_detail": False,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "other",
        "display_name": "Otro",
        "requires_detail": True,
        "applies_to_sex": None,
        "expects_return": True,
        "severity": DeactivationSeverity.WARN.value,
    },
]


# --- Configuración de avisos (system_settings) ---
#
# Cuántos días antes del reintegro se avisa al encargado. Es global a propósito: el
# recordatorio es uno por ausencia y no necesita un plazo distinto por caso (decisión 7 del
# spec 2026-10-09-licencias-con-fechas-y-recordatorio).
LICENSE_REMINDER_DAYS_KEY = "notifications.license_reminder_days"
DEFAULT_LICENSE_REMINDER_DAYS = 2
