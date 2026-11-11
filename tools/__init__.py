"""Tools package exposing and registering all welfare agent tools."""

from tools.registry import register_tool, execute_tool, get_tool_descriptions
from tools.scheme_search import search_schemes
from tools.web_search import web_search
from tools.eligibility import check_eligibility
from tools.documents import build_document_checklist, verify_documents
from tools.scheme_by_documents import find_schemes_by_documents
from tools.form import form_plan, fill_form, form_preview
from tools.profile_tools import update_user_profile, set_active_scheme
from tools.upload_tools import (
    analyze_uploaded_document,
    register_form_template,
    list_form_templates,
    explain_uploaded_scheme,
)
from tools.guardrail_tools import check_scam_risk
from tools.household_tools import (
    add_member,
    switch_member,
    list_members,
    check_household_eligibility,
)
from tools.document_help_tools import (
    get_document_help,
    find_accepted_alternatives,
    get_acquisition_plan,
)
from tools.ranking_tools import rank_schemes
from tools.handoff_tools import find_nearest_office, create_handoff_packet
from tools.rejection_tools import explain_rejection, draft_grievance

__all__ = [
    "register_tool",
    "execute_tool",
    "get_tool_descriptions",
    "search_schemes",
    "web_search",
    "check_eligibility",
    "build_document_checklist",
    "verify_documents",
    "find_schemes_by_documents",
    "form_plan",
    "fill_form",
    "form_preview",
    "update_user_profile",
    "set_active_scheme",
    "analyze_uploaded_document",
    "register_form_template",
    "list_form_templates",
    "explain_uploaded_scheme",
    "check_scam_risk",
    "add_member",
    "switch_member",
    "list_members",
    "check_household_eligibility",
    "get_document_help",
    "find_accepted_alternatives",
    "get_acquisition_plan",
    "rank_schemes",
    "find_nearest_office",
    "create_handoff_packet",
    "explain_rejection",
    "draft_grievance",
]
