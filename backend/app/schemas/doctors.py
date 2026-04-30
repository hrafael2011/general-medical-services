from pydantic import BaseModel, Field


class DoctorRead(BaseModel):
    id: str
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
    name: str = Field(min_length=1, max_length=160)
    sex: str = Field(pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
    participa_misiones: bool = True
    whatsapp_phone: str | None = Field(default=None, max_length=40)
    monthly_service_target: int = Field(default=3, ge=0)
    monthly_service_max: int = Field(default=3, ge=0)
    monthly_service_limit_mode: str = Field(default="warn_only", pattern="^(warn_only|hard_limit)$")
    availability_mode: str = Field(default="monthly", pattern="^(fixed|monthly)$")
    allowed_area_ids: list[str] = []


class UpdateDoctorRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    sex: str | None = Field(default=None, pattern="^(male|female)$")
    rank_id: str | None = None
    department_id: str | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=500)
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
