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
    display_name: str = Field(min_length=1, max_length=160)
    applies_to_sex: str | None = Field(default=None, pattern="^(male|female)$")


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
