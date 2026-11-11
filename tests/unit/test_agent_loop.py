"""Unit tests for the plain Python agent loop and AgentTurn response matrix."""

import tempfile
from pathlib import Path
from agent.schemas import AgentTurn, ToolCall
from agent.llm import MockMainLLM
from agent.loop import run_agent_turn
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
