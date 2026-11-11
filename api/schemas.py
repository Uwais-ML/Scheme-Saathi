"""FastAPI request and response schemas."""

from typing import Any
from pydantic import BaseModel, Field


class SessionRequest(BaseModel):
    user_id: str | None = None
    language: str = "hi"


class SessionResponse(BaseModel):
    session_id: str
    greeting: str
    language: str


class ChatRequest(BaseModel):
    session_id: str
    text: str
    upload_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    messages: list[str]
    audio_url: str | None = None
    checklist: dict[str, Any] | None = None
    form_preview: dict[str, Any] | None = None
    notices: list[str] = Field(default_factory=list)
    member: dict[str, Any] | None = None
    ranked_schemes: list[dict[str, Any]] | None = None
    acquisition_plan: dict[str, Any] | None = None
    handoff: dict[str, Any] | None = None


class STTResponse(BaseModel):
    text: str
    confidence: float = 1.0


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int


class ConfirmFormRequest(BaseModel):
    session_id: str
    scheme_id: str
    confirmed: bool


class ConfirmFormResponse(BaseModel):
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    degraded: bool


class HouseholdMemberRequest(BaseModel):
    session_id: str
    relationship: str
    name: str = ""
    age: int | None = None
    gender: str | None = None


class SwitchMemberRequest(BaseModel):
    session_id: str
    member_id: str | None = None
    relationship: str | None = None


class HandoffPacketRequest(BaseModel):
    session_id: str
    reason: str = "general assistance"
    district: str = "bhopal"


class GrievanceDraftRequest(BaseModel):
    session_id: str
    scheme_id: str
    rejection_category: str
    user_facts: dict[str, Any] = Field(default_factory=dict)
