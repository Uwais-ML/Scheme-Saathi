"""Unit tests for the plain Python agent loop and AgentTurn response matrix."""

import tempfile
from pathlib import Path
from agent.schemas import AgentTurn, ToolCall
from agent.llm import MockMainLLM
from agent.loop import (
    _search_topic,
    _summarize_scheme_search,
    build_system_message,
    is_form_request,
    is_scheme_discovery_request,
    run_agent_turn,
)
from state.store import load_profile
from state.models import UserProfile
from tools.registry import register_tool


def test_agent_loop_case_1_content_only():
    """Case 1: content set, tool None -> speaks content and terminates."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(content="नमस्ते, मैं आपकी क्या सहायता कर सकता हूँ?", tool=None)
            ]
        )

        spoken = run_agent_turn("नमस्ते", "user_1", llm=mock_llm, db_path=db_path, skip_scam_intro=True)
        assert len(spoken) == 1
        assert "नमस्ते" in spoken[0]


def test_agent_loop_case_2_content_and_tool():
    """Case 2: content set, tool set -> speaks content, runs tool, feeds to next turn."""
    called_args = []

    @register_tool("mock_check_user", description="Test tool")
    def mock_check_user(args, profile):
        called_args.append(args)
        return {"eligible": True}

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(
                    content="मैं आपकी पात्रता जांच रहा हूँ...",
                    tool=ToolCall(name="mock_check_user", args={"scheme": "pm_kisan"}),
                ),
                AgentTurn(content="आप इस योजना के लिए पात्र हैं।", tool=None),
            ]
        )

        spoken = run_agent_turn("क्या मैं पात्र हूँ?", "user_2", llm=mock_llm, db_path=db_path, skip_scam_intro=True)
        assert len(spoken) == 2
        assert "पात्रता जांच रहा हूँ" in spoken[0]
        assert "पात्र हैं" in spoken[1]
        assert called_args == [{"scheme": "pm_kisan"}]


def test_agent_loop_case_3_silent_tool():
    """Case 3: content None, tool set -> executes tool silently, speaks on next turn."""
    called_tool = []

    @register_tool("mock_silent_search", description="Silent search")
    def mock_silent_search(args, profile):
        called_tool.append(args)
        return {"result": "scheme_found"}

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="mock_silent_search", args={"q": "farmer"}),
                ),
                AgentTurn(content="मुझे किसान योजना मिली है।", tool=None),
            ]
        )

        spoken = run_agent_turn("योजना ढूंढें", "user_3", llm=mock_llm, db_path=db_path, skip_scam_intro=True)
        assert len(spoken) == 1
        assert "मुझे किसान योजना मिली है" in spoken[0]
        assert called_tool == [{"q": "farmer"}]


def test_agent_loop_case_4_both_none_retries_and_falls_back():
    """Case 4: content None, tool None -> retries once, then fallback polite phrase."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(content=None, tool=None),  # First invalid
                AgentTurn(content=None, tool=None),  # Second invalid after correction
            ]
        )

        spoken = run_agent_turn("कुछ समझ नहीं आया", "user_4", llm=mock_llm, db_path=db_path, skip_scam_intro=True)
        assert len(spoken) == 1
        assert "कृपया अपनी बात दोबारा कहें" in spoken[0]


def test_agent_loop_handles_unknown_tool_gracefully():
    """Verify unknown tool returns error result to LLM without crashing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(
                    content=None,
                    tool=ToolCall(name="non_existent_tool", args={}),
                ),
                AgentTurn(content="क्षमा करें, यह सुविधा उपलब्ध नहीं है।", tool=None),
            ]
        )

        spoken = run_agent_turn("अज्ञात", "user_5", llm=mock_llm, db_path=db_path, skip_scam_intro=True)
        assert len(spoken) == 1
        assert "क्षमा करें" in spoken[0]


def test_farmer_scheme_question_searches_dynamic_local_and_web_results(monkeypatch):
    import agent.loop as agent_loop

    web_queries = []
    local_queries = []
    def fake_local_search(**kwargs):
        local_queries.append(kwargs["query"])
        return {
            "ok": True,
            "data": {
                "schemes": [
                    {
                        "scheme_id": "crop_support",
                        "name": "कृषि सहायता योजना",
                        "score": 0.8,
                        "text": "किसानों को कृषि सहायता दी जाती है।",
                        "metadata": {"source_url": "https://agriculture.gov.in/scheme"},
                        "stale": False,
                    }
                ]
            },
        }

    monkeypatch.setattr(
        agent_loop,
        "search_schemes",
        fake_local_search,
    )
    def fake_web_search(query):
        web_queries.append(query)
        return {
            "ok": True,
            "data": {
                "results": [
                    {
                        "title": "नई कृषि योजना",
                        "url": "https://agriculture.gov.in/new-scheme",
                        "content": "किसानों के लिए सहायता।",
                    },
                    {
                        "title": "Untrusted scheme listing",
                        "url": "https://example.com/scheme",
                        "content": "Do not include this result.",
                    },
                ]
            },
        }

    monkeypatch.setattr(agent_loop, "web_search", fake_web_search)
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        mock_llm = MockMainLLM(
            responses=[
                AgentTurn(
                    content="आपकी वार्षिक आय कितनी है?",
                    tool=None,
                )
            ]
        )

        spoken = run_agent_turn(
            "मैं किसान हूँ, मेरे लिए सरकारी योजनाएं बता सकते हैं?",
            "farmer_user",
            llm=mock_llm,
            db_path=db_path,
            skip_scam_intro=True,
        )

        assert len(spoken) == 1
        assert "कृषि सहायता योजना" in spoken[0]
        assert "नई कृषि योजना" in spoken[0]
        assert "Untrusted scheme listing" not in spoken[0]
        assert "वार्षिक आय" not in spoken[0]
        assert len(spoken[0]) < 500
        assert mock_llm._call_count == 0
        assert local_queries == ["farmer government welfare schemes"]
        assert web_queries == ["official government welfare schemes for farmer in India"]
        profile = load_profile("farmer_user", db_path=db_path)
        assert profile.is_farmer is True
        assert profile.occupation == "farmer"


def test_scheme_discovery_detects_general_queries():
    assert is_scheme_discovery_request("मैं किसान हूँ, मेरे लिए योजनाएं बताइए")
    assert is_scheme_discovery_request("What benefits are available for widows?")
    assert is_scheme_discovery_request("मुझे सहायता योजना बताइए")
    assert not is_scheme_discovery_request("मैं किसान हूँ")


def test_form_help_request_routes_to_llm_form_capabilities(monkeypatch):
    import agent.loop as agent_loop

    text = "मुझे पीम किसान योजना का फॉर्म भरना है, क्या तुम मेरी मदद कर सकते हो?"
    assert is_form_request(text)
    assert not is_scheme_discovery_request(text)

    monkeypatch.setattr(
        agent_loop,
        "search_schemes",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not search schemes")),
    )
    monkeypatch.setattr(
        agent_loop,
        "web_search",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("should not search the web")),
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        mock_llm = MockMainLLM(
            responses=[AgentTurn(content="मैं उपलब्ध फॉर्म देखता हूँ।", tool=None)]
        )

        spoken = run_agent_turn(
            text,
            "form_help_user",
            llm=mock_llm,
            db_path=Path(tmp_dir) / "test.db",
            skip_scam_intro=True,
        )

        assert spoken == ["मैं उपलब्ध फॉर्म देखता हूँ।"]
        prompt = build_system_message(UserProfile(user_id="form_help_user"))
        for capability in ("list_form_templates", "form_plan", "fill_form", "form_preview"):
            assert capability in prompt
        assert "APPLICATION FORM HELP" in prompt


def test_web_query_uses_profile_context_without_sending_personal_numbers():
    profile = UserProfile(user_id="user", is_farmer=True, occupation="farmer", state="Maharashtra")

    query = _search_topic("मैं किसान हूँ, मेरा फोन 9876543210 है, योजनाएं बताएं", profile)

    assert query == "official government welfare schemes for farmer in Maharashtra"
    assert "9876543210" not in query


def test_scheme_summary_only_includes_official_web_sources():
    response = _summarize_scheme_search(
        {"data": {"schemes": []}},
        {
            "data": {
                "results": [
                    {
                        "title": "Unofficial offer",
                        "url": "https://example.com",
                        "content": "Unverified promise.",
                    }
                ]
            }
        },
        "hi",
    )

    assert "Unofficial offer" not in response
    assert "पुष्टि नहीं कर सका" in response
