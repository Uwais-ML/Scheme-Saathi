"""Unit tests for Phase 19: Document Acquisition Help and Alternative Recommendations."""

from tools.document_help_tools import (
    get_document_help,
    find_accepted_alternatives,
    get_acquisition_plan,
)
from tools.scheme_by_documents import find_schemes_by_documents


def test_get_document_help_returns_record():
    res = get_document_help("aadhaar_card")
    assert res["ok"] is True
    assert res["doc_id"] == "aadhaar_card"
    assert "आधार कार्ड" in res["name"]["hi"]
    assert len(res["how_to_get"]) > 0


def test_get_document_help_flags_unverified():
    res = get_document_help("income_certificate")
    assert res["ok"] is True
    # Must flag typical_cost_inr or typical_days as unverified
    assert "typical_cost_inr" in res["unverified_fields"] or "typical_days" in res["unverified_fields"]
    # Agent must not receive literal 'TODO_VERIFY' in typical_cost
    assert "TODO_VERIFY" not in res["typical_cost"]


def test_find_accepted_alternatives():
    res = find_accepted_alternatives("bank_passbook")
    assert res["ok"] is True
    assert res["has_alternatives"] is True
    assert "cancelled_cheque" in res["alternatives"] or "bank_statement" in res["alternatives"]


def test_get_acquisition_plan_topological_order():
    # income_certificate requires ration_card which requires aadhaar_card
    missing = ["income_certificate", "ration_card", "aadhaar_card"]
    plan = get_acquisition_plan(missing)
    assert plan["ok"] is True
    assert plan["total_documents"] == 3

    ordered = plan["ordered_plan"]
    # Aadhaar must be acquired before ration card
    aadhaar_idx = ordered.index("aadhaar_card")
    ration_idx = ordered.index("ration_card")
    income_idx = ordered.index("income_certificate")

    assert aadhaar_idx < ration_idx
    assert ration_idx < income_idx


def test_find_schemes_by_documents_ordered_by_effort():
    # User has aadhaar and bank_passbook
    res = find_schemes_by_documents(doc_ids=["aadhaar_card", "bank_passbook"])
    assert res["ok"] is True
    schemes = res["data"]["matching_schemes"]
    assert len(schemes) > 0

    # Schemes with 0 missing docs should come before schemes with 1 or 2 missing docs
    efforts = [s["effort_score"] for s in schemes]
    assert efforts == sorted(efforts)
