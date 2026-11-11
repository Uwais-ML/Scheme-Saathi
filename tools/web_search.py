"""Web search tool using Tavily with automatic API key rotation and fallback."""

import logging
from typing import Any
from pydantic import BaseModel, Field
import requests

from config.settings import settings
from utils.key_rotation import execute_with_key_rotation
from tools.registry import register_tool

logger = logging.getLogger(__name__)


class WebSearchArgs(BaseModel):
    """Arguments for web search tool."""

    query: str = Field(description="Search query string to search on the web")


def _call_tavily_api(key: str, query: str) -> dict[str, Any]:
    """Execute a single HTTP request to Tavily API."""
    if not key or "placeholder" in key.lower():
        raise Exception("401 Unauthorized: Invalid or placeholder API key")

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 3,
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    data = response.json()
    return {
        "answer": data.get("answer"),
        "results": [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
            for r in data.get("results", [])
        ],
    }


@register_tool(
    name="web_search",
    description="Search the web for government scheme updates or details when local database has no relevant match.",
)
def web_search(
    query: str | None = None,
    args: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Web search with automatic key rotation and graceful fallback."""
    q = query or (args.get("query") if args else None)
    if not q:
        return {"ok": False, "data": None, "error": "No query provided for web search."}

    keys = settings.TAVILY_API_KEYS

    # Function wrapper for rotation
    def call_with_key(k: str):
        return _call_tavily_api(k, q)

    res = execute_with_key_rotation(
        keys=keys,
        call_fn=call_with_key,
        fallback_error="search_unavailable",
    )
    return res
