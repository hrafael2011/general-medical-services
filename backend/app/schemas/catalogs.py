from pydantic import BaseModel, Field


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
    code: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=160)
    requires_detail: bool = False
    applies_to_sex: str | None = Field(default=None, pattern="^(male|female)$")
    severity: str = Field(pattern="^(hard_block|warn)$")


class UpdateRankRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    abbreviation: str | None = Field(default=None, min_length=1, max_length=40)
    active: bool | None = None


class UpdateDepartmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    active: bool | None = None


class UpdateDeactivationReasonRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[a-z0-9_]+$")
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    requires_detail: bool | None = None
    applies_to_sex: str | None = Field(default=None, pattern="^(male|female)$")
    severity: str | None = Field(default=None, pattern="^(hard_block|warn)$")
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
