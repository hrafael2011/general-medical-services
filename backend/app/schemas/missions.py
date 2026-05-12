from datetime import date, datetime

from pydantic import BaseModel, Field

# --- Mission Participant ---

class MissionParticipantRead(BaseModel):
    id: str
    mission_assignment_id: str
    doctor_id: str
    doctor_name: str | None = None
    selection_source: str
    ranking_position: int | None
    score: float | None
    reasons: dict | None
    warnings: list | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Mission Assignment ---

class MissionAssignmentRead(BaseModel):
    id: str
    mission_date: date
    mission_start_at: datetime | None
    mission_end_at: datetime | None
    participant_count: int
    location: str | None
    description: str | None
    source: str
    status: str
    created_by: str | None
    confirmed_by: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    participants: list[MissionParticipantRead] = []

    model_config = {"from_attributes": True}


class CreateMissionRequest(BaseModel):
    mission_date: date
    participant_count: int = Field(ge=1)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    mission_start_at: datetime | None = None


class UpdateMissionRequest(BaseModel):
    mission_date: date | None = None
    participant_count: int | None = Field(default=None, ge=1)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None
    mission_start_at: datetime | None = None
    mission_end_at: datetime | None = None


# --- Mission Candidate Ranking ---

class MissionCandidateRankingEntryRead(BaseModel):
    id: str
    doctor_id: str
    doctor_name: str | None = None
    ranking_position: int
    total_load_score: float
    monthly_service_load: float
    recent_service_load: float
    monthly_mission_load: float
    eligible: bool
    reasons: dict | None
    warnings: list | None

    model_config = {"from_attributes": True}


class MissionCandidateRankingRead(BaseModel):
    id: str
    month: int
    year: int
    calendar_version_id: str | None
    generated_at: datetime
    created_by: str | None
    entries: list[MissionCandidateRankingEntryRead] = []

    model_config = {"from_attributes": True}


# --- Mission Candidate Selection ---

class MissionCandidateRequest(BaseModel):
    """Request candidates for a specific mission date and participant count."""
    mission_date: date
    participant_count: int = Field(ge=1)
    include_alternates: bool = False


class MissionCandidateResponse(BaseModel):
    """Recommended candidates for a mission slot."""
    mission_date: date
    participant_count: int
    primary: list[MissionCandidateRankingEntryRead]
    alternates: list[MissionCandidateRankingEntryRead]


class MissionCandidateDateRankingEntryRead(BaseModel):
    id: str
    doctor_id: str
    doctor_name: str | None = None
    ranking_position: int
    adjusted_position: int
    recommendation_status: str
    selectable: bool
    total_load_score: float
    monthly_service_load: float
    recent_service_load: float
    monthly_mission_load: float
    eligible: bool
    reasons: list[str]
    warnings: list[str]


class MissionCandidateDateRankingResponse(BaseModel):
    mission_date: date
    month: int
    year: int
    entries: list[MissionCandidateDateRankingEntryRead]


# --- Mission Confirmation ---

class ConfirmMissionRequest(BaseModel):
    """Confirm selected doctors for a mission."""
    doctor_ids: list[str]
