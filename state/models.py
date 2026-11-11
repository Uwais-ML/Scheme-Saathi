"""Pydantic data models for persistent user profile and state."""

import re
from typing import Any, Literal
from pydantic import BaseModel, Field


def mask_sensitive_id(value: str) -> str:
    """Mask 12-digit Aadhaar or sensitive IDs, showing only the last 4 digits.

    Example: '123456789012' -> 'XXXX XXXX 9012'
    """
    clean = re.sub(r"\s+", "", str(value))
    if len(clean) == 12 and clean.isdigit():
        return f"XXXX XXXX {clean[-4:]}"
    elif len(clean) > 4:
        return f"{'X' * (len(clean) - 4)}{clean[-4:]}"
    return value


class DocumentRecord(BaseModel):
    """Represents a single document submitted or needed by the user."""

    doc_id: str
    status: Literal["missing", "submitted", "verified", "rejected"] = "missing"
    reason: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)


class SchemeEligibility(BaseModel):
    """Represents an eligibility decision for a scheme."""

    scheme_id: str
    reason: str


class UserProfile(BaseModel):
    """Persistent profile of a user across sessions."""

    user_id: str
    name: str | None = None
    preferred_language: str = "hi"

    # Demographics & socio-economic
    age: int | None = None
    gender: str | None = None
    state: str | None = None
    district: str | None = None
    village_or_city: str | None = None

    occupation: str | None = None
    annual_income: float | None = None
    caste_category: str | None = None
    is_farmer: bool | None = None
    land_holding: float | None = None  # in acres
    family_size: int | None = None
    bank_account_exists: bool | None = None
    disability_status: bool | None = None
    bpl_card: bool | None = None

    # Documents & Schemes
    documents: list[DocumentRecord] = Field(default_factory=list)
    schemes_discussed: list[str] = Field(default_factory=list)
    schemes_eligible: list[SchemeEligibility] = Field(default_factory=list)
    active_scheme: str | None = None
    form_draft: dict[str, Any] = Field(default_factory=dict)
    conversation_summary: str = ""

    def get_document(self, doc_id: str) -> DocumentRecord | None:
        """Find a document record by doc_id."""
        for doc in self.documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def upsert_document(self, doc_record: DocumentRecord) -> None:
        """Update or insert a document record."""
        for idx, doc in enumerate(self.documents):
            if doc.doc_id == doc_record.doc_id:
                self.documents[idx] = doc_record
                return
        self.documents.append(doc_record)

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict with sensitive fields like Aadhaar masked for logging."""
        data = self.model_dump()
        for doc in data.get("documents", []):
            fields = doc.get("extracted_fields", {})
            for k, v in fields.items():
                if any(sub in k.lower() for sub in ("aadhaar", "id", "account", "card_no")):
                    fields[k] = mask_sensitive_id(str(v))
        return data


class HouseholdShared(BaseModel):
    """Shared household-level facts reused for every member."""

    address: str = ""
    district: str = ""
    state: str = ""
    ration_card_number: str = ""
    family_size: int = 0
    family_income_yearly: float = 0.0


class ConsentRecord(BaseModel):
    """Audit log of consent granted to handle a family member's details."""

    member_id: str
    consented_by: str
    timestamp: str
    purpose: str


class Member(BaseModel):
    """An individual member of a household."""

    member_id: str
    display_name: str
    relation: str  # "self", "spouse", "mother", "father", "son", "daughter", etc.
    profile: UserProfile
    documents: list[DocumentRecord] = Field(default_factory=list)
    schemes_eligible: list[SchemeEligibility] = Field(default_factory=list)
    form_drafts: dict[str, dict[str, Any]] = Field(default_factory=dict)


class Household(BaseModel):
    """A household group containing one or more members sharing address/income."""

    household_id: str
    members: list[Member] = Field(default_factory=list)
    active_member_id: str = ""
    shared: HouseholdShared = Field(default_factory=HouseholdShared)
    consent_log: list[ConsentRecord] = Field(default_factory=list)

    def get_active_member(self) -> Member | None:
        """Return the currently selected active member."""
        for m in self.members:
            if m.member_id == self.active_member_id:
                return m
        return self.members[0] if self.members else None

    def get_member(self, member_id: str) -> Member | None:
        """Return member by ID."""
        for m in self.members:
            if m.member_id == member_id:
                return m
        return None

