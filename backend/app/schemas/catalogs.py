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
