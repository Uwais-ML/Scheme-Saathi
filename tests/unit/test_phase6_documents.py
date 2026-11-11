"""Unit tests for Phase 6: Document checklist, VLM verifier, and find_schemes_by_documents."""

from agent.schemas import DocumentCheck, VerificationResult
from state.models import UserProfile
from tools.documents import build_document_checklist, verify_documents
from tools.scheme_by_documents import find_schemes_by_documents
from vlm.verifier import get_vlm_verifier


def test_build_document_checklist():
    """Verify document checklist returns expected documents for PM-KISAN."""
    res = build_document_checklist(scheme_id="pm_kisan")
    assert res["ok"] is True
    docs = res["data"]["documents"]
    doc_ids = [d["doc_id"] for d in docs]
    assert "aadhaar" in doc_ids
    assert "bank_passbook" in doc_ids
    assert "land_records" in doc_ids


def test_partial_verification_flow_6_of_9():
    """Test partial verification where 6 out of 9 documents pass and 3 fail/missing."""
    verifier = get_vlm_verifier()

    # Construct a 9-document verification scenario
    checks = []
    doc_names = [f"doc_{i}" for i in range(1, 10)]
    for i in range(1, 10):
        if i <= 6:
            checks.append(
                DocumentCheck(
                    doc_id=f"doc_{i}",
                    status="verified",
                    reason="दस्तावेज स्पष्ट और सही है",
                    extracted_fields={"id": f"NUM_{i}"},
                    confidence=0.95,
                )
            )
        elif i == 7:
            checks.append(
                DocumentCheck(
                    doc_id=f"doc_{i}",
                    status="rejected",
                    reason="फोटो धुंधली है",
                    confidence=0.4,
                )
            )
        else:
            checks.append(
                DocumentCheck(
                    doc_id=f"doc_{i}",
                    status="not_provided",
                    reason="दस्तावेज उपलब्ध नहीं है",
                    confidence=0.0,
                )
            )

    mock_result = VerificationResult(
        checks=checks,
        verified_count=6,
        total_required=9,
        summary="9 में से 6 दस्तावेज सत्यापित हुए।",
    )
    verifier.set_mock_result(mock_result)

    profile = UserProfile(user_id="test_user_vlm")
    res = verify_documents(
        scheme_id="pm_kisan",
        image_refs=["img1.jpg", "img2.jpg"],
        profile=profile,
    )

    assert res["ok"] is True
    assert res["data"]["verified_count"] == 6
    assert res["data"]["total_required"] == 9
    assert len(profile.documents) == 9

    # Check verified status in profile
    verified_in_profile = [d.doc_id for d in profile.documents if d.status == "verified"]
    assert len(verified_in_profile) == 6
    assert "doc_1" in verified_in_profile
    assert "doc_6" in verified_in_profile

    # Check rejected doc status in profile
    rejected = profile.get_document("doc_7")
    assert rejected is not None
    assert rejected.status == "rejected"

    # Reset mock after test
    verifier.set_mock_result(None)


def test_find_schemes_by_documents_finds_applicable_schemes():
    """Verify that possessing aadhaar and bank_passbook finds matching schemes."""
    profile = UserProfile(user_id="user_farmer", is_farmer=True, age=25)
    # Give user aadhaar and bank_passbook and photo (MGNREGA needs aadhaar, bank_passbook, photo)
    res = find_schemes_by_documents(
        doc_ids=["aadhaar", "bank_passbook", "photo"],
        profile=profile,
    )
    assert res["ok"] is True
    matching = res["data"]["matching_schemes"]
    matching_ids = [m["scheme_id"] for m in matching]
    assert "mgnrega" in matching_ids
