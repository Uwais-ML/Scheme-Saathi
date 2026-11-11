"""Main plain-Python agent execution loop without LangGraph."""

import json
import logging
from pathlib import Path
from typing import Any, Callable

from config.settings import settings
from state.models import UserProfile, Household, Member
from state.store import load_profile, save_profile, load_household, save_household, get_active_member
from agent.schemas import AgentTurn, ToolCall
from agent.prompts import MAIN_SYSTEM_PROMPT
from agent.llm import get_main_llm
from agent.fallback_messages import get_fallback_message
from tools import execute_tool, get_tool_descriptions
from guardrails.input_check import check_input
from guardrails.output_check import check_output
from guardrails.helplines import format_crisis_response
from utils.model_router import log_trace_span

logger = logging.getLogger(__name__)

# Track user sessions where standing scam warning has been shown
_SCAM_MSG_SHOWN: set[str] = set()


def build_system_message(profile: UserProfile) -> str:
    """Format the system prompt with current user state and available tools."""
    state_dict = profile.to_safe_dict()
    # Compact JSON representation
    state_json = json.dumps(state_dict, ensure_ascii=False)
    tool_descriptions = get_tool_descriptions()

    return MAIN_SYSTEM_PROMPT.format(
        preferred_language=profile.preferred_language,
        tool_descriptions=tool_descriptions,
        user_state_json=state_json,
    )


def format_tool_result_message(tool: ToolCall, result: dict[str, Any]) -> dict[str, str]:
    """Format tool execution output for feeding back to LLM."""
    return {
        "role": "function",
        "name": tool.name,
        "content": json.dumps(result, ensure_ascii=False),
    }


def run_agent_turn(
    user_input: str,
    user_id: str,
    llm: Any = None,
    db_path: Path | str | None = None,
    on_speech: Callable[[str], None] | None = None,
    skip_scam_intro: bool = False,
) -> list[str]:
    """Run a single conversational turn through the agent loop.

    Follows the 4-case behavior matrix from Section 8 of plan.md:
    1. content set, tool None: Speak & print, wait for user.
    2. content set, tool set: Speak & print, run tool, feed back to LLM.
    3. content None, tool set: Run tool silently, feed back to LLM.
    4. content None, tool None: Retry once; fallback to polite request.

    Args:
        user_input: Text spoken or entered by the user.
        user_id: ID of the user.
        llm: LLM instance to use (defaults to get_main_llm()).
        db_path: Optional custom SQLite DB path (for tests).
        on_speech: Callback for TTS speech/printing.

    Returns:
        List of all spoken contents delivered to the user during this turn.
    """
    household = load_household(user_id, db_path=db_path)
    active_member = get_active_member(household)
    profile = active_member.profile
    active_llm = llm or get_main_llm()
    spoken_responses: list[str] = []

    def speak(text: str) -> None:
        if text:
            spoken_responses.append(text)
            if on_speech:
                on_speech(text)
            else:
                print(f"Agent: {text}")

    # Step 1: Input safety guardrails check
    lang = profile.preferred_language or "hi"
    flags = check_input(user_input, language=lang)

    # 1.1 Crisis detection -> Immediate assistance with verified/unverified helpline
    if flags.crisis != "none":
        crisis_reply = format_crisis_response(flags.crisis, language=lang)
        speak(crisis_reply)
        save_profile(profile, db_path=db_path)
        return spoken_responses

    # 1.2 Out of scope -> Kind redirection
    if flags.out_of_scope != "none":
        oos_reply = (
            "यह विषय सरकारी योजनाओं के कार्यक्षेत्र से बाहर है। "
            "कृपया इसके लिए उचित विशेषज्ञ या कार्यालय से संपर्क करें। "
            "क्या आप किसी सरकारी कल्याणकारी योजना (जैसे PM-KISAN, आयुष्मान भारत) की जानकारी लेना चाहते हैं?"
        ) if lang == "hi" else (
            "This falls outside government welfare schemes. Please contact a relevant professional or office. "
            "Would you like assistance with government welfare schemes?"
        )
        speak(oos_reply)
        save_profile(profile, db_path=db_path)
        return spoken_responses

    # 1.3 Human escalation requested
    if flags.needs_human:
        handoff_msg = (
            "मैं समझ सकता हूँ कि आप किसी अधिकारी या व्यक्ति से सीधे संपर्क करना चाहते हैं। "
            "मैं एक डिजिटल सहायक हूँ, इसलिए मैंने आपके लिए एक 'कार्यालय सहायता पर्ची' तैयार कर दी है। "
            "आप अपने मूल दस्तावेज लेकर नजदीकी ग्राम पंचायत या सीएससी केंद्र पर आसानी से सहायता ले सकते हैं।"
        ) if lang == "hi" else (
            "I understand you would like to speak to a person. As an AI assistant without a live operator, "
            "I have prepared an offline handoff summary for you to carry to your nearest Panchayat or CSC office."
        )
        speak(handoff_msg)
        save_household(household, db_path=db_path)
        save_profile(profile, db_path=db_path)
        return spoken_responses

    # 1.3 Standing scam message: once per session early
    if skip_scam_intro:
        _SCAM_MSG_SHOWN.add(user_id)
    elif user_id not in _SCAM_MSG_SHOWN:
        _SCAM_MSG_SHOWN.add(user_id)
        scam_intro = (
            "सुरक्षा सूचना: सरकारी योजनाओं के लिए आवेदन निशुल्क होता है। किसी को पैसे या अपना OTP कभी न दें।"
            if lang == "hi"
            else "Security Notice: Applying for government schemes is free. Never pay anyone or share your OTP."
        )
        speak(scam_intro)
    elif flags.scam_risk:
        scam_warn = (
            "⚠️ चेतावनी: सरकारी योजनाओं के लिए किसी को भी पैसे या OTP न दें। किसी भी धोखाधड़ी के लिए साइबर हेल्पलाइन 1930 पर संपर्क करें।"
        )
        speak(scam_warn)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_message(profile)},
        {"role": "user", "content": user_input},
    ]

    max_steps = settings.MAX_TOOL_STEPS
    retry_done = False
    guardrail_retried = False

    for step in range(max_steps):
        turn: AgentTurn = active_llm.invoke(messages)

        # Case 4: Both are None -> Invalid
        if turn.content is None and turn.tool is None:
            if not retry_done:
                logger.warning("Agent returned both content and tool as None. Retrying once.")
                retry_done = True
                messages.append(
                    {
                        "role": "system",
                        "content": "Correction: Both content and tool were null. Please provide either a spoken response or a tool call.",
                    }
                )
                continue
            else:
                fallback_msg = "कृपया अपनी बात दोबारा कहें, मैं ठीक से समझ नहीं पाया।"
                speak(fallback_msg)
                break

        # Output content check & sanitization (Cases 1 & 2)
        if turn.content:
            cleaned_content, violations = check_output(turn.content)
            if violations:
                log_trace_span(
                    role="guardrail",
                    provider="code",
                    model="output_check",
                    latency_ms=1.0,
                    outcome=f"violations: {','.join(violations)}",
                    key_env="",
                )
                if not guardrail_retried:
                    guardrail_retried = True
                    messages.append(
                        {
                            "role": "system",
                            "content": f"Safety correction: Your response contained violations: {', '.join(violations)}. Do not promise approval, do not ask for OTP/PIN, and do not provide unlisted links.",
                        }
                    )
                    continue
                else:
                    turn.content = cleaned_content
            else:
                turn.content = cleaned_content

            speak(turn.content)

        # Case 1: content set, tool is None -> Done with this turn
        if turn.tool is None:
            break

        # Case 2 & 3: tool is set -> execute tool and loop
        # Record the assistant turn in messages
        messages.append(
            {
                "role": "assistant",
                "content": turn.content,
                "tool_calls": [turn.tool.model_dump()],
            }
        )

        # Execute tool
        result = execute_tool(turn.tool.name, turn.tool.args, profile)

        # Feed tool result back to the LLM
        messages.append(format_tool_result_message(turn.tool, result))

    # Save state at the end of turn
    active_member.profile = profile
    save_household(household, db_path=db_path)
    save_profile(profile, db_path=db_path)
    return spoken_responses
