"""Unit tests for Phase 21: Human Handoff and Printable Offline Packets."""

from state.models import UserProfile, DocumentRecord
from state.store import save_profile
from tools.handoff_tools import find_nearest_office, create_handoff_packet
from agent.loop import run_agent_turn
from agent.schemas import AgentTurn


def test_find_nearest_office_unverified_fallback():
    # Bhopal entries are currently verified: false with TODO_VERIFY address
    res = find_nearest_office(district="Bhopal")
    assert res["ok"] is True
    # Must NOT invent an address or return unverified address
    assert res["found_verified"] is False
    assert len(res["offices"]) == 0
    assert "ग्राम पंचायत" in res["advice"] or "सीएससी" in res["advice"]


def test_create_handoff_packet_content(tmp_path):
    db_file = tmp_path / "handoff_test.db"
    prof = UserProfile(
        user_id="handoff_user_1",
        name="Manohar Lal",
        district="Sehore",
        state="Madhya Pradesh",
        active_scheme="pm_kisan",
        documents=[
            DocumentRecord(doc_id="aadhaar_card", status="verified"),
            DocumentRecord(doc_id="land_record", status="rejected", reason="खतौनी की फोटो धुंधली है"),
            DocumentRecord(doc_id="bank_passbook", status="missing"),
        ],
    )
    save_profile(prof, db_path=db_file)

    res = create_handoff_packet(
        member_id="handoff_user_1",
        issue_description="खतौनी सत्यापन में समस्या आ रही है।",
        db_path=db_file,
    )
    assert res["ok"] is True
    assert "packet_html" in res
    html = res["packet_html"]

    # Verify structure & fields
    assert "Manohar Lal" in html
    assert "Sehore" in html
    assert "pm_kisan" in html
    assert "aadhaar_card" in html
    assert "खतौनी की फोटो धुंधली है" in html
    assert "डिजिटल सहायक द्वारा तैयार किया गया है" in html


def test_human_escalation_trigger_in_agent_loop(tmp_path):
    db_file = tmp_path / "escalate_test.db"

    class DummyLLM:
        def invoke(self, messages):
            return AgentTurn(content="Normal turn", tool=None)

    res = run_agent_turn(
        user_input="मुझे किसी इंसान से बात करनी है, कंप्यूटर से नहीं",
        user_id="escalate_user_1",
        llm=DummyLLM(),
        db_path=db_file,
    )
    assert len(res) > 0
    full_speech = " ".join(res)
    assert "सहायता पर्ची" in full_speech or "handoff" in full_speech.lower() or "ग्राम पंचायत" in full_speech
