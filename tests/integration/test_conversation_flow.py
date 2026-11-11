"""Full end-to-end integration test of conversational workflow in Hindi."""

import tempfile
from pathlib import Path
from agent.schemas import AgentTurn, ToolCall
from agent.llm import MockMainLLM
from agent.loop import run_agent_turn
from state.store import load_profile


def test_full_hindi_conversation_flow():
    """Simulate a complete 5-turn conversation in Hindi from greeting to form preview."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "conversation_test.db"
        user_id = "farmer_ramesh"

        # Turn 1: User asks for farming schemes
        llm_turn1 = MockMainLLM(
            responses=[
                AgentTurn(
                    content="मैं आपके लिए किसान योजनाओं की तलाश कर रहा हूँ...",
                    tool=ToolCall(name="search_schemes", args={"query": "किसान सम्मान निधि"}),
                ),
                AgentTurn(
                    content="मुझे प्रधानमंत्री किसान सम्मान निधि योजना मिली है, जिसमें हर साल 6000 रुपये मिलते हैं। क्या आप किसान हैं?",
                    tool=None,
                ),
            ]
        )
        spoken_1 = run_agent_turn(
            "मैं खेती करता हूँ, क्या कोई योजना है?",
            user_id,
            llm=llm_turn1,
            db_path=db_path,
            skip_scam_intro=True,
        )
        assert len(spoken_1) == 2
        assert "किसान सम्मान निधि" in spoken_1[1]

        # Turn 2: User confirms being a farmer with 2.5 acres
        llm_turn2 = MockMainLLM(
            responses=[
                AgentTurn(
                    content=None,
                    tool=ToolCall(
                        name="update_user_profile",
                        args={"fields": {"is_farmer": True, "land_holding": 2.5, "age": 40}},
                    ),
                ),
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="check_eligibility", args={"scheme_id": "pm_kisan"}),
                ),
                AgentTurn(
                    content="बधाई हो, आप पीएम-किसान योजना के लिए पूरी तरह पात्र हैं। क्या हम दस्तावेजों की जांच शुरू करें?",
                    tool=None,
                ),
            ]
        )
        spoken_2 = run_agent_turn("हाँ, मेरे पास ढाई एकड़ जमीन है।", user_id, llm=llm_turn2, db_path=db_path)
        assert len(spoken_2) == 1
        assert "पात्र हैं" in spoken_2[0]

        profile_after_t2 = load_profile(user_id, db_path=db_path)
        assert profile_after_t2.is_farmer is True
        assert profile_after_t2.land_holding == 2.5

        # Turn 3: User asks for document checklist
        llm_turn3 = MockMainLLM(
            responses=[
                AgentTurn(
                    content=None,
                    tool=ToolCall(
                        name="build_document_checklist",
                        args={"scheme_id": "pm_kisan"},
                    ),
                ),
                AgentTurn(
                    content="इस योजना के लिए आधार कार्ड, बैंक पासबुक और खतौनी की आवश्यकता है। कृपया एक-एक करके इनकी फोटो भेजें।",
                    tool=None,
                ),
            ]
        )
        spoken_3 = run_agent_turn("कौन-कौन से दस्तावेज लगेंगे?", user_id, llm=llm_turn3, db_path=db_path)
        assert len(spoken_3) == 1
        assert "आधार कार्ड" in spoken_3[0]

        # Turn 4: User submits document photos
        llm_turn4 = MockMainLLM(
            responses=[
                AgentTurn(
                    content="मैं आपके दस्तावेजों की जांच कर रहा हूँ...",
                    tool=ToolCall(
                        name="verify_documents",
                        args={
                            "scheme_id": "pm_kisan",
                            "image_refs": ["aadhaar.jpg", "bank_passbook.jpg", "land_records.jpg"],
                        },
                    ),
                ),
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="form_plan", args={"scheme_id": "pm_kisan"}),
                ),
                AgentTurn(
                    content="आपके सभी 3 दस्तावेज सत्यापित हो गए हैं और फॉर्म की सभी जानकारियां तैयार हैं। क्या मैं फॉर्म भर दूँ?",
                    tool=None,
                ),
            ]
        )
        spoken_4 = run_agent_turn("ये रहे मेरे सारे कागज।", user_id, llm=llm_turn4, db_path=db_path)
        assert len(spoken_4) == 2
        assert "सत्यापित हो गए हैं" in spoken_4[1]

        # Turn 5: User agrees to fill and preview form
        llm_turn5 = MockMainLLM(
            responses=[
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="fill_form", args={"scheme_id": "pm_kisan"}),
                ),
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="form_preview", args={"scheme_id": "pm_kisan"}),
                ),
                AgentTurn(
                    content="मैंने आपका फॉर्म तैयार कर दिया है। क्या ये सभी विवरण सही हैं?",
                    tool=None,
                ),
            ]
        )
        spoken_5 = run_agent_turn("हाँ, फॉर्म भर दीजिए।", user_id, llm=llm_turn5, db_path=db_path)
        assert len(spoken_5) == 1
        assert "फॉर्म तैयार कर दिया है" in spoken_5[0]

        final_profile = load_profile(user_id, db_path=db_path)
        assert final_profile.active_scheme == "pm_kisan"
        assert len(final_profile.form_draft) > 0
