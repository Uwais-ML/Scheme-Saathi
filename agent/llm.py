"""Factory and wrappers for the main LLM with structured output."""

import json
import logging
from typing import Any
import requests

from config.settings import settings
from agent.schemas import AgentTurn, ToolCall

logger = logging.getLogger(__name__)


class MockMainLLM:
    """Mock LLM returning predefined or rule-based AgentTurn objects for testing."""

    def __init__(self, responses: list[AgentTurn] | None = None):
        self.responses: list[AgentTurn] = responses or []
        self._call_count = 0

    def set_responses(self, responses: list[AgentTurn]) -> None:
        """Queue responses to return on consecutive invocations."""
        self.responses = responses
        self._call_count = 0

    def invoke(self, messages: list[Any]) -> AgentTurn:
        """Return the next queued response, or an echo fallback."""
        if self._call_count < len(self.responses):
            res = self.responses[self._call_count]
            self._call_count += 1
            return res

        last_msg = messages[-1] if messages else ""
        content = (
            last_msg.get("content")
            if isinstance(last_msg, dict)
            else getattr(last_msg, "content", str(last_msg))
        )
        return AgentTurn(content=f"नमस्ते, आपकी क्या सहायता कर सकता हूँ? (प्राप्त: {content})", tool=None)


class CohereMainLLM:
    """Cohere API wrapper producing structured AgentTurn responses."""

    def __init__(self, api_key: str, model: str = "command-r-plus-08-2024"):
        self.api_key = api_key
        self.model = model

    def invoke(self, messages: list[Any]) -> AgentTurn:
        """Send chat messages to Cohere v2 chat API with json_object format."""
        formatted_msgs = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role", "user")
                # Cohere roles: system, user, assistant
                if role == "function":
                    role = "user"
                content = str(m.get("content", ""))
                formatted_msgs.append({"role": role, "content": content})
            else:
                formatted_msgs.append({"role": "user", "content": str(m)})

        try:
            resp = requests.post(
                "https://api.cohere.com/v2/chat",
                headers={
                    "Authorization": f"bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": formatted_msgs,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
                timeout=25,
            )
            if resp.status_code == 200:
                data = resp.json()
                content_blocks = data.get("message", {}).get("content", [])
                text_response = content_blocks[0].get("text", "{}") if content_blocks else "{}"
                parsed = json.loads(text_response)
                return AgentTurn.model_validate(parsed)
            else:
                logger.error("Cohere API returned %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("Cohere invoke failed: %s", exc)

        return AgentTurn(
            content="क्षमा करें, सर्वर से संपर्क नहीं हो पाया। कृपया दोबारा प्रयास करें।",
            tool=None,
        )


class OpenRouterLLM:
    """OpenRouter API wrapper producing structured AgentTurn responses."""

    def __init__(self, api_key: str, model: str = "openai/gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def invoke(self, messages: list[Any]) -> AgentTurn:
        """Send chat messages to OpenRouter chat completion API with JSON output."""
        formatted_msgs = []
        for m in messages:
            if isinstance(m, dict):
                role = m.get("role", "user")
                if role == "function":
                    role = "user"
                content = str(m.get("content", ""))
                formatted_msgs.append({"role": role, "content": content})
            else:
                formatted_msgs.append({"role": "user", "content": str(m)})

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": formatted_msgs,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return AgentTurn.model_validate(parsed)
            else:
                logger.error("OpenRouter API returned %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.error("OpenRouter invoke failed: %s", exc)

        return AgentTurn(
            content="क्षमा करें, सर्वर से संपर्क नहीं हो पाया। कृपया दोबारा प्रयास करें।",
            tool=None,
        )


def get_main_llm(override_provider: str | None = None):
    """Build the main LLM configured with AgentTurn structured output."""
    provider = override_provider or settings.MAIN_LLM_PROVIDER
    api_key = settings.MAIN_LLM_API_KEY

    if provider == "openrouter" or (api_key and api_key.startswith("sk-or-v1")):
        return OpenRouterLLM(api_key=api_key, model=settings.MAIN_LLM_MODEL)

    if provider == "cohere" and api_key and "placeholder" not in api_key.lower():
        return CohereMainLLM(api_key=api_key, model=settings.MAIN_LLM_MODEL)

    if provider == "mock" or not api_key or "placeholder" in api_key.lower():
        return MockMainLLM()

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=settings.MAIN_LLM_MODEL, api_key=api_key, temperature=0.2)
            return llm.with_structured_output(AgentTurn)
        except ImportError:
            raise ImportError("langchain-openai is required for OpenAI provider.")

    if provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            llm = ChatGoogleGenerativeAI(model=settings.MAIN_LLM_MODEL, google_api_key=api_key, temperature=0.2)
            return llm.with_structured_output(AgentTurn)
        except ImportError:
            raise ImportError("langchain-google-genai is required for Google provider.")

    return MockMainLLM()
