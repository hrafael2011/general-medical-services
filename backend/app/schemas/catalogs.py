from pydantic import BaseModel, Field, field_validator


class ServiceAreaRead(BaseModel):
    id: str
    code: str
    display_name: str
    active: bool
    required_for_daily_coverage: bool
    load_weight: int

    model_config = {"from_attributes": True}


class DeactivationReasonRead(BaseModel):
    id: str
    code: str
    display_name: str
    active: bool
    requires_detail: bool
    applies_to_sex: str | None
    severity: str
    # Si la ausencia por este motivo espera fecha de regreso. La pantalla de "No disponible"
    # lo usa para proponer "Indefinido" en vez de pedir una fecha.
    expects_return: bool = True

    @field_validator("expects_return", mode="before")
    @classmethod
    def true_if_none(cls, v: object) -> object:
        # El valor por defecto de la columna lo pone la base al insertar, así que un objeto
        # todavía sin confirmar puede traerlo a None. El catálogo dice que un motivo nuevo
        # **sí** espera regreso, así que ese es el valor que se informa.
        return True if v is None else v

    model_config = {"from_attributes": True}


class RankRead(BaseModel):
    id: str
    name: str
    normalized_name: str
    abbreviation: str
    active: bool

    model_config = {"from_attributes": True}


class DepartmentRead(BaseModel):
    id: str
    name: str
    normalized_name: str
    active: bool

    model_config = {"from_attributes": True}


class CreateRankRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    abbreviation: str = Field(min_length=1, max_length=40)


class CreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class CreateDeactivationReasonRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    applies_to_sex: str | None = Field(default=None, pattern="^(male|female)$")
    expects_return: bool = True


class UpdateRankRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    abbreviation: str | None = Field(default=None, min_length=1, max_length=40)
    active: bool | None = None


class UpdateDepartmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    active: bool | None = None


class UpdateDeactivationReasonRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    applies_to_sex: str | None = Field(default=None, pattern="^(male|female)$")
    expects_return: bool | None = None
    active: bool | None = None


class DeleteRankResponse(BaseModel):
    message: str
    affected_doctors: int = 0


class DeleteDepartmentResponse(BaseModel):
    message: str
    affected_doctors: int = 0


class DeleteDeactivationReasonResponse(BaseModel):
    message: str
    affected_doctors: int = 0


# --- Report signatures ---
#
# The left signature's *name* is deliberately absent: it is the user who exports the
# document, so it travels with the request instead of being stored here.


class ReportSignaturesRead(BaseModel):
    left_title1: str
    left_title2: str
    left_title3: str
    right_name: str
    right_title1: str
    right_title2: str
    right_title3: str


class ReportSignaturesUpdate(BaseModel):
    left_title1: str = Field(max_length=200)
    left_title2: str = Field(max_length=200)
    left_title3: str = Field(max_length=200)
    right_name: str = Field(max_length=200)
    right_title1: str = Field(max_length=200)
    right_title2: str = Field(max_length=200)
    right_title3: str = Field(max_length=200)


class NotificationSettingsRead(BaseModel):
    """Configuración de los avisos. Hoy: con cuánta antelación se avisa del reintegro."""

    license_reminder_days: int = 2


class NotificationSettingsRequest(BaseModel):
    license_reminder_days: int = Field(ge=1, le=60)
