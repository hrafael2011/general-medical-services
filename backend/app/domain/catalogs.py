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
    },
    {
        "code": "pista",
        "display_name": "Pista",
        "load_weight": 2,
        "required_for_daily_coverage": True,
    },
    {
        "code": "disponible",
        "display_name": "Disponible",
        "load_weight": 1,
        "required_for_daily_coverage": True,
    },
]

INITIAL_DEACTIVATION_REASONS = [
    {
        "code": "medical_license",
        "display_name": "Licencia medica",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "pregnancy",
        "display_name": "Embarazo",
        "requires_detail": False,
        "applies_to_sex": Sex.FEMALE.value,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "no_service",
        "display_name": "No realiza servicio",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "vacation",
        "display_name": "Vacaciones",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.WARN.value,
    },
    {
        "code": "administrative_restriction",
        "display_name": "Restriccion administrativa",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "transfer_or_area_change",
        "display_name": "Traslado / cambio de area",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.WARN.value,
    },
    {
        "code": "temporarily_suspended",
        "display_name": "Suspendido temporalmente",
        "requires_detail": False,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.HARD_BLOCK.value,
    },
    {
        "code": "other",
        "display_name": "Otro",
        "requires_detail": True,
        "applies_to_sex": None,
        "severity": DeactivationSeverity.WARN.value,
    },
]

