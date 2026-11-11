"""Chat and session routes."""

import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from api.schemas import (
    SessionRequest,
    SessionResponse,
    ChatRequest,
    ChatResponse,
    HouseholdMemberRequest,
    SwitchMemberRequest,
    HandoffPacketRequest,
    GrievanceDraftRequest,
)
from api.deps import check_rate_limit, get_user_profile
from agent.loop import run_agent_turn
from state.store import load_profile, load_household, save_household, get_active_member
from tools.form import form_preview
from tools.household_tools import add_member, switch_member
from tools.handoff_tools import create_handoff_packet
from tools.rejection_tools import draft_grievance

router = APIRouter(prefix="/api", tags=["chat"])

GREETINGS = {
    "hi": "नमस्ते! मैं आपका योजना साथी हूँ। आज हम किस सरकारी योजना की जानकारी लें या आपकी क्या सहायता करूँ?",
    "en": "Hello! I am your Scheme Saathi. Which government welfare scheme would you like to explore today?",
    "mr": "नमस्कार! मी तुमचा योजना साथी आहे. आज आपण कोणत्या योजनेबद्दल माहिती जाणून घेऊ इच्छिता?",
    "ta": "வணக்கம்! நான் உங்கள் திட்ட தோழன். இன்று எந்த அரசு நலத்திட்டம் பற்றி அறிய விரும்புகிறீர்கள்?",
}


@router.post("/session", response_model=SessionResponse)
def create_session(req: SessionRequest):
    """Create or resume an agent session."""
    session_id = req.user_id or f"user_{uuid.uuid4().hex[:8]}"
    lang = req.language or "hi"
    profile = load_profile(session_id)
    profile.preferred_language = lang
    greeting = GREETINGS.get(lang, GREETINGS["hi"])
    return SessionResponse(session_id=session_id, greeting=greeting, language=lang)


@router.post("/chat", response_model=ChatResponse)
def chat_turn(req: ChatRequest):
    """Execute a conversational agent turn."""
    check_rate_limit(req.session_id)

    user_text = req.text.strip()
    if req.upload_ids:
        user_text = f"{user_text} [दस्तावेज अपलोड: {', '.join(req.upload_ids)}]"

    spoken_messages = run_agent_turn(
        user_input=user_text,
        user_id=req.session_id,
    )

    household = load_household(req.session_id)
    active_m = get_active_member(household)
    profile = active_m.profile

    preview_data = None
    if profile.active_scheme:
        try:
            prev_res = form_preview(scheme_id=profile.active_scheme, profile=profile)
            if prev_res.get("ok"):
                preview_data = prev_res.get("data")
        except Exception:
            pass

    # Extract checklist if documents are in progress
    checklist_data = None
    if profile.documents:
        checklist_data = {
            "total": len(profile.documents),
            "documents": [d.model_dump() for d in profile.documents],
        }

    member_data = {
        "active_member_id": active_m.member_id,
        "active_name": active_m.display_name or profile.name or "मुख्य सदस्य",
        "active_relation": active_m.relation,
        "members": [
            {
                "member_id": m.member_id,
                "display_name": m.display_name or m.profile.name or m.relation,
                "relation": m.relation,
                "is_active": (m.member_id == active_m.member_id),
            }
            for m in household.members
        ],
    }

    return ChatResponse(
        messages=spoken_messages,
        checklist=checklist_data,
        form_preview=preview_data,
        notices=[],
        member=member_data,
    )


@router.get("/household")
def get_household(session_id: str = Query(...)):
    """Return household structure with all members."""
    household = load_household(session_id)
    active_m = get_active_member(household)
    return {
        "ok": True,
        "household_id": household.household_id,
        "active_member_id": active_m.member_id,
        "members": [
            {
                "member_id": m.member_id,
                "display_name": m.display_name or m.profile.name or m.relation,
                "relation": m.relation,
                "is_active": (m.member_id == active_m.member_id),
                "profile": m.profile.to_safe_dict(),
            }
            for m in household.members
        ],
    }


@router.post("/household/member")
def add_household_member(req: HouseholdMemberRequest):
    """Add a new member to the household."""
    res = add_member(
        household_id=req.session_id,
        display_name=req.name or req.relationship,
        relation=req.relationship,
    )
    return res


@router.post("/household/switch")
def switch_household_member(req: SwitchMemberRequest):
    """Switch active member by member_id."""
    if not req.member_id:
        raise HTTPException(status_code=400, detail="member_id is required")
    res = switch_member(
        household_id=req.session_id,
        member_id=req.member_id,
    )
    return res


@router.post("/handoff/packet")
def generate_handoff_packet(req: HandoffPacketRequest):
    """Generate printable HTML handoff packet for offline CSC/Panchayat visit."""
    res = create_handoff_packet(
        household_id=req.session_id,
        issue_description=req.reason,
    )
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail="Could not create handoff packet")
    return Response(content=res.get("html", ""), media_type="text/html")


@router.post("/grievance/draft")
def generate_grievance_draft(req: GrievanceDraftRequest):
    """Generate formal grievance appeal letter."""
    res = draft_grievance(
        household_id=req.session_id,
        category=req.rejection_category,
        issue_details=req.user_facts.get("issue_details", ""),
        reference_number=req.user_facts.get("reference_number"),
    )
    return res
