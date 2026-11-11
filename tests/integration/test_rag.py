"""Integration tests for RAG ingestion and parent-child retrieval."""

import tempfile
from pathlib import Path
from rag.ingest import ingest_schemes
from rag.retriever import ParentChildRetriever


def test_rag_ingest_and_retrieval_hindi_and_english():
    """Verify that known Hindi and English queries retrieve correct schemes."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        persist_dir = Path(tmp_dir) / "chroma"

        # Step 1: Ingest schemes
        stats = ingest_schemes(persist_dir=persist_dir)
        assert stats["parents_count"] >= 5
        assert stats["children_count"] >= 5

        retriever = ParentChildRetriever(persist_dir=persist_dir)

        # Query 1: Hindi farmer query -> PM-KISAN
        res_farmer = retriever.search("मुझे किसान योजना के बारे में बताएं", threshold=0.4)
        assert res_farmer["relevant"] is True
        assert len(res_farmer["results"]) > 0
        scheme_ids = [r["scheme_id"] for r in res_farmer["results"]]
        assert "pm_kisan" in scheme_ids

        # Query 2: Hindi healthcare/treatment query -> PMJAY
        res_health = retriever.search("इलाज के लिए सरकारी अस्पताल में 5 लाख सहायता", threshold=0.4)
        assert res_health["relevant"] is True
        scheme_ids = [r["scheme_id"] for r in res_health["results"]]
        assert "pmjay" in scheme_ids

        # Query 3: Gas cylinder query -> PM Ujjwala (lower threshold for hashing embeddings)
        res_gas = retriever.search("मुफ्त गैस सिलेंडर योजना", threshold=0.25)
        assert res_gas["relevant"] is True
        scheme_ids = [r["scheme_id"] for r in res_gas["results"]]
        assert "pm_ujjwala" in scheme_ids


def test_rag_irrelevant_query_triggers_threshold():
    """Verify that an irrelevant query yields relevant=False."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        persist_dir = Path(tmp_dir) / "chroma"
        ingest_schemes(persist_dir=persist_dir)

        retriever = ParentChildRetriever(persist_dir=persist_dir)
        res = retriever.search(
            "quantum physics gravitational wave detection laser interferometer",
            threshold=0.85,
        )
        assert res["relevant"] is False
        assert len(res["results"]) == 0
