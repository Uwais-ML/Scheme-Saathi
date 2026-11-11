"""Parent-child retriever with query rewriting, metadata filtering, and relevance threshold."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
import chromadb

from config.settings import settings
from rag.embeddings import get_embedding_function
from rag.ingest import get_parent_document, load_parent_store

logger = logging.getLogger(__name__)

# Common Hindi, Regional, and English welfare keyword expansions for cross-lingual RAG
HINDI_QUERY_EXPANSIONS = {
    # Hindi keywords
    "किसान": "farmer agriculture kisan samman nidhi kheti pm_kisan",
    "खेती": "farmer agriculture kisan samman nidhi kheti pm_kisan",
    "इलाज": "health healthcare hospital medical ayushman card pmjay 5 lakh",
    "दवा": "medicine health healthcare ayushman pmjay",
    "अस्पताल": "hospital treatment healthcare pmjay ayushman",
    "गैस": "lpg gas cylinder ujjwala fuel chulha pm_ujjwala",
    "चूल्हा": "lpg gas cylinder ujjwala pm_ujjwala",
    "सिलेंडर": "gas cylinder lpg ujjwala pm_ujjwala",
    "काम": "employment work job mgnrega rozgar",
    "रोजगार": "employment work mgnrega 100 days job labour",
    "मजदूरी": "wages manual labour mgnrega",
    "बहना": "ladli behna women mp madhya pradesh",
    "महिला": "women welfare female empowerment ladli behna",
    # English keywords
    "farmer": "किसान खेती agriculture kisan samman nidhi pm_kisan",
    "agriculture": "किसान खेती agriculture kisan pm_kisan",
    "health": "इलाज स्वास्थ्य अस्पताल hospital treatment ayushman pmjay",
    "healthcare": "इलाज स्वास्थ्य अस्पताल hospital treatment ayushman pmjay",
    "hospital": "इलाज अस्पताल hospital treatment ayushman pmjay",
    "insurance": "स्वास्थ्य बीमा इलाज ayushman pmjay",
    "lpg": "गैस सिलेंडर ujjwala gas cylinder pm_ujjwala",
    "gas": "गैस सिलेंडर ujjwala gas cylinder pm_ujjwala",
    "cylinder": "गैस सिलेंडर ujjwala cylinder pm_ujjwala",
    "mgnrega": "मनरेगा रोजगार मजदूरी job card employment 100 days",
    "job card": "मनरेगा जॉब कार्ड mgnrega employment rozgar",
    "employment": "मनरेगा रोजगार employment mgnrega 100 days",
    # Marathi keywords
    "शेतकऱ्यांसाठी": "किसान farmer agriculture kisan samman nidhi pm_kisan",
    "आरोग्य": "इलाज hospital health ayushman pmjay",
    "गॅस": "गैस cylinder ujjwala lpg",
    # Tamil keywords
    "விவசாயிகளுக்கான": "किसान farmer agriculture kisan pm_kisan",
    "மருத்துவ": "इलाज hospital healthcare treatment ayushman pmjay",
    "எரிவாயு": "गैस cylinder ujjwala gas lpg",
}


def rewrite_query(query: str) -> str:
    """Expand Hindi or regional terms with relevant domain synonyms."""
    expanded = [query]
    for term, syns in HINDI_QUERY_EXPANSIONS.items():
        if term in query:
            expanded.append(syns)
    return " ".join(expanded)


class ParentChildRetriever:
    """Retrieves child chunks from Chroma and resolves them to full parent documents."""

    def __init__(self, persist_dir: Path | str | None = None):
        self.persist_dir = Path(persist_dir) if persist_dir else settings.CHROMA_DIR
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.embedding_fn = get_embedding_function()
        load_parent_store(self.persist_dir)

    def _get_collection(self):
        try:
            return self.client.get_collection(
                name="scheme_children",
                embedding_function=self.embedding_fn,
            )
        except Exception:
            return None

    def search(
        self,
        query: str,
        state: str | None = None,
        category: str | None = None,
        top_k: int = 3,
        threshold: float | None = None,
    ) -> dict[str, Any]:
        """Search child vectors, map to parents, rank, and apply relevance threshold.

        Args:
            query: The user's search query (Hindi or English).
            state: Optional state filter (e.g. 'Madhya Pradesh' or 'central').
            category: Optional category filter.
            top_k: Number of parent results to return.
            threshold: Minimum relevance score (0.0 to 1.0).

        Returns:
            dict: {"relevant": bool, "results": list[dict], "best_score": float}
        """
        collection = self._get_collection()
        if collection is None or collection.count() == 0:
            return {"relevant": False, "results": [], "best_score": 0.0}

        min_threshold = threshold if threshold is not None else settings.RELEVANCE_THRESHOLD
        expanded_query = rewrite_query(query)

        # Build metadata where filter if provided
        where_clause = None
        conditions = []
        if state and state.lower() != "central":
            # Match state or central schemes
            conditions.append({"$or": [{"state": state}, {"state": "central"}]})
        if category:
            conditions.append({"category": category})

        if len(conditions) == 1:
            where_clause = conditions[0]
        elif len(conditions) > 1:
            where_clause = {"$and": conditions}

        # Query child chunks
        try:
            query_kwargs: dict[str, Any] = {
                "query_texts": [expanded_query],
                "n_results": min(10, collection.count()),
            }
            if where_clause:
                query_kwargs["where"] = where_clause

            results = collection.query(**query_kwargs)
        except Exception as exc:
            logger.warning("Chroma query with filter failed (%s), retrying without filter.", exc)
            results = collection.query(
                query_texts=[expanded_query],
                n_results=min(10, collection.count()),
            )

        if not results or not results.get("ids") or not results["ids"][0]:
            return {"relevant": False, "results": [], "best_score": 0.0}

        ids = results["ids"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if results.get("distances") else [0.5] * len(ids)

        parent_scores: dict[str, float] = {}

        for meta, dist in zip(metadatas, distances):
            p_id = meta.get("parent_id")
            # In cosine space: similarity = 1 - distance
            similarity = max(0.0, 1.0 - float(dist))
            if p_id:
                # Keep highest score for this parent
                if p_id not in parent_scores or similarity > parent_scores[p_id]:
                    parent_scores[p_id] = similarity

        if not parent_scores:
            return {"relevant": False, "results": [], "best_score": 0.0}

        # Sort parents by similarity
        sorted_parents = sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)
        best_score = sorted_parents[0][1]

        if best_score < min_threshold:
            logger.info("Search query '%s' best score %.2f < threshold %.2f", query, best_score, min_threshold)
            return {"relevant": False, "results": [], "best_score": best_score}

        top_results = []
        now_dt = datetime.utcnow()
        stale_threshold = settings.STALE_AFTER_DAYS if hasattr(settings, "STALE_AFTER_DAYS") else 30

        for p_id, score in sorted_parents[:top_k]:
            parent_doc = get_parent_document(p_id, self.persist_dir)
            if parent_doc:
                meta = parent_doc.get("metadata", {})
                last_ver = meta.get("last_verified")
                # Determine stale status
                is_stale = True
                if last_ver:
                    try:
                        lv_dt = datetime.fromisoformat(last_ver)
                        is_stale = (now_dt - lv_dt).days >= stale_threshold
                    except Exception:
                        is_stale = True

                top_results.append(
                    {
                        "scheme_id": meta.get("scheme_id"),
                        "name": meta.get("name"),
                        "score": round(score, 3),
                        "text": parent_doc["text"],
                        "metadata": meta,
                        "stale": is_stale,
                        "last_verified": last_ver,
                    }
                )

        return {
            "relevant": True,
            "best_score": round(best_score, 3),
            "results": top_results,
        }
