"""Pydantic schemas for Agent interactions, tool calls, and VLM outputs."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a structured tool execution request from the agent."""

    name: str = Field(description="Name of the registered tool to call")
    args: dict[str, Any] = Field(
        default_factory=dict, description="Arguments to pass to the tool"
    )


class AgentTurn(BaseModel):
    """The strict response contract returned by the main LLM."""

    content: str | None = Field(
        default=None,
        description="Spoken response to user in their language, or None if purely running a tool",
    )
    tool: ToolCall | None = Field(
        default=None,
        description="Tool call to execute, or None if just talking to user",
    )


# --- Phase 2: Upload-to-Form Schemas (Section 1.3) ---


class FormField(BaseModel):
    """Field definition extracted from a physical/digital form."""

    key: str = Field(description="Unique snake_case identifier within form")
    label_original: str = Field(description="Exact label as printed on form")
    label_simple: str = Field(description="Plain-language version in user's language")
    type: Literal["text", "number", "date", "checkbox", "select", "signature", "photo", "table"] = "text"
    required: bool = True
    options: list[str] | None = None
    section: str | None = None
    profile_hint: str | None = None
    confidence: float = 1.0


class FormTemplateDraft(BaseModel):
    """Draft form template produced by VLM analysis."""

    draft_id: str
    scheme_id: str | None = None
    scheme_name: str | None = None
    form_title: str | None = None
    source_language: str = "hi"
    fields: list[FormField] = Field(default_factory=list)
    attachments_required: list[str] = Field(default_factory=list)
    declarations: list[str] = Field(default_factory=list)
    illegible_regions: list[str] = Field(default_factory=list)
    overall_confidence: float = 1.0
    status: Literal["draft", "provisional", "approved"] = "draft"
    source: Literal["official", "user_upload"] = "user_upload"


class SchemeSummary(BaseModel):
    """Structured scheme facts extracted from uploaded document."""

    name: str | None = None
    benefits: list[str] = Field(default_factory=list)
    eligibility_rules: list[str] = Field(default_factory=list)
    documents_required: list[str] = Field(default_factory=list)
    deadlines: list[str] = Field(default_factory=list)
    source_note: str = "user_upload"
    trust: str = "from_user_upload"


class UploadAnalysis(BaseModel):
    """VLM assessment of an uploaded document or form."""

    kind: Literal[
        "application_form",
        "scheme_info",
        "form_with_scheme_info",
        "identity_document",
        "supporting_document",
        "unknown",
    ]
    form_template: FormTemplateDraft | None = None
    scheme_summary: SchemeSummary | None = None
    notes_for_host: str
    next_action: Literal[
        "register_form_template",
        "explain_scheme",
        "verify_document",
        "ask_user_to_resend",
        "ask_user_what_this_is",
    ]
    mapping_coverage: float = 0.0
    missing_profile_fields: list[str] = Field(default_factory=list)



class DocumentCheck(BaseModel):
    """Verification outcome for an individual document."""

    doc_id: str
    status: Literal["verified", "rejected", "unreadable", "not_provided"]
    reason: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    """Aggregated document verification response."""

    checks: list[DocumentCheck] = Field(default_factory=list)
    verified_count: int = 0
    total_required: int = 0
    summary: str = ""


# --- Phase 22: Rejection and Grievance Schemas ---


RejectionCategory = Literal[
    "name_mismatch",
    "aadhaar_bank_link",
    "incomplete_documents",
    "ineligible_income",
    "ineligible_other",
    "duplicate",
    "wrong_details",
    "deadline_missed",
    "unknown",
]


class RejectionAnalysis(BaseModel):
    """Structured extraction from a rejection letter or rejection explanation."""

    scheme_name: str | None = None
    reason_text_original: str
    reason_category: RejectionCategory = "unknown"
    details: list[str] = Field(default_factory=list)
    reference_number: str | None = None
    date: str | None = None
    confidence: float = 1.0

