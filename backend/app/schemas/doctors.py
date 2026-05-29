from pydantic import BaseModel, Field, model_validator


class DoctorRead(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    name: str
    sex: str
    rank_id: str | None
    department_id: str | None
    phone: str | None
    notes: str | None
    active: bool
    service_active: bool
    service_inactive_reason_id: str | None
    service_inactive_detail: str | None
    participa_misiones: bool
    whatsapp_phone: str | None
    monthly_service_target: int
    monthly_service_max: int
    monthly_service_limit_mode: str
    availability_mode: str
    allowed_area_ids: list[str] = []

    model_config = {"from_attributes": True}


class CreateDoctorRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=160)
    last_name: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sex: str = Field(pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    service_active: bool = True
    participa_misiones: bool = True
    whatsapp_phone: str = Field(..., max_length=40)
    monthly_service_target: int = Field(default=3, ge=0)
    monthly_service_max: int = Field(default=3, ge=0)
    monthly_service_limit_mode: str = Field(default="warn_only", pattern="^(warn_only|hard_limit)$")
    availability_mode: str = Field(default="monthly", pattern="^(fixed|monthly)$")
    allowed_area_ids: list[str] = []

    @model_validator(mode="after")
    def require_name_or_parts(self) -> "CreateDoctorRequest":
        if self.name is not None:
            return self
        if self.first_name is not None and self.last_name is not None:
            return self
        raise ValueError("Debe indicar nombre y apellido.")


class UpdateDoctorRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=160)
    last_name: str | None = Field(default=None, min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sex: str | None = Field(default=None, pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    service_active: bool | None = None
    participa_misiones: bool | None = None
    whatsapp_phone: str | None = Field(default=None, max_length=40)
    monthly_service_target: int | None = Field(default=None, ge=0)
    monthly_service_max: int | None = Field(default=None, ge=0)
    monthly_service_limit_mode: str | None = Field(default=None, pattern="^(warn_only|hard_limit)$")
    availability_mode: str | None = Field(default=None, pattern="^(fixed|monthly)$")
    allowed_area_ids: list[str] | None = None


class DeactivateDoctorServiceRequest(BaseModel):
    reason_id: str
    detail: str | None = Field(default=None, max_length=500)


class DoctorListResponse(BaseModel):
    items: list[DoctorRead]
    total: int


class DoctorByDayItem(BaseModel):
    id: str
    name: str
    rank_name: str | None = None
    department_name: str | None = None
    phone: str | None = None
    whatsapp_phone: str | None = None
    recurring_tag: str | None = None

    model_config = {"from_attributes": True}


class DayGroup(BaseModel):
    label: str
    count: int
    doctors: list[DoctorByDayItem]


class DoctorByDayResponse(BaseModel):
    days: dict[str, DayGroup]
