"""Form preview and confirmation routes."""

from fastapi import APIRouter, HTTPException
from api.schemas import ConfirmFormRequest, ConfirmFormResponse
from api.deps import check_rate_limit
from state.store import load_profile, save_profile
from tools.form import form_preview

router = APIRouter(prefix="/api/form", tags=["form"])


@router.get("/preview/{scheme_id}")
def get_form_preview(scheme_id: str, session_id: str):
    """Return the current form preview for a session and scheme."""
    check_rate_limit(session_id)
    profile = load_profile(session_id)

    result = form_preview(scheme_id=scheme_id, profile=profile)
    if not result.get("ok"):
        raise HTTPException(
            status_code=404,
            detail=result.get("error", "Form template not found."),
        )
    return {"scheme_id": scheme_id, "preview": result.get("data")}


@router.post("/confirm", response_model=ConfirmFormResponse)
def confirm_form(req: ConfirmFormRequest):
    """Mark a form as confirmed by the user."""
    check_rate_limit(req.session_id)

    if not req.confirmed:
        return ConfirmFormResponse(
            status="cancelled",
            message="Form submission cancelled. Let me know if you'd like to make changes.",
        )

    profile = load_profile(req.session_id)
    # Mark submission flag in profile metadata
    profile.active_scheme = req.scheme_id
    save_profile(profile)

    return ConfirmFormResponse(
        status="confirmed",
        message=(
            "✅ आपने फ़ॉर्म की जानकारी सही मानी है। "
            "कृपया इसे अपने नज़दीकी CSC केंद्र या आधिकारिक पोर्टल पर जमा करें।"
        ),
    )
