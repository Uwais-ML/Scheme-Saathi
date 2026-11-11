"""RAG search tool over local welfare schemes database."""

from typing import Any
from pydantic import BaseModel, Field

from rag.retriever import ParentChildRetriever
from tools.registry import register_tool


class SchemeSearchArgs(BaseModel):
    """Arguments for scheme search tool."""

    query: str = Field(description="Search query or need in Hindi or English")
    state: str | None = Field(default=None, description="Optional state filter")
    category: str | None = Field(default=None, description="Optional scheme category")


# Cached retriever instance
_retriever: ParentChildRetriever | None = None


def get_retriever() -> ParentChildRetriever:
    """Return singleton instance of retriever."""
    global _retriever
    if _retriever is None:
        _retriever = ParentChildRetriever()
    return _retriever


@register_tool(
    name="search_schemes",
    description="Search the verified database of government welfare schemes using RAG.",
)
def search_schemes(
    query: str | None = None,
    state: str | None = None,
    category: str | None = None,
    args: dict[str, Any] | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Search scheme database."""
    params = args or {}
    q = query or params.get("query")
    s = state or params.get("state")
    c = category or params.get("category")

    if not q:
        return {"ok": False, "data": None, "error": "Query parameter is required."}

    retriever = get_retriever()
    search_res = retriever.search(query=q, state=s, category=c)

    if not search_res.get("relevant"):
        return {
            "ok": True,
            "data": {
                "relevant": False,
                "message": "स्थानीय डेटाबेस में इस विषय पर कोई प्रासंगिक योजना नहीं मिली। कृपया web_search का उपयोग करें।",
            },
            "error": None,
        }

    results = search_res.get("results", [])
    for r in results:
        if r.get("stale"):
            last_date = r.get("last_verified") or "अनिर्दिष्ट"
            r["stale_note"] = f"यह जानकारी पुरानी हो सकती है (अंतिम सत्यापन: {last_date})। कृपया स्थानीय कार्यालय से पुष्टि करें।"

    return {
        "ok": True,
        "data": {
            "relevant": True,
            "best_score": search_res.get("best_score"),
            "schemes": results,
        },
        "error": None,
    }
