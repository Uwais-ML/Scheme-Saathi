"""Ingest scheme documents, chunk into parents & children, and index into Chroma."""

import json
import logging
from pathlib import Path
from typing import Any
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings
from rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)

# Global in-memory parent store
PARENT_STORE: dict[str, dict[str, Any]] = {}


def get_parents_file_path(persist_dir: Path | str | None = None) -> Path:
    """Return path to stored parent chunks JSON file."""
    base = Path(persist_dir) if persist_dir else settings.CHROMA_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base / "parents.json"


def save_parent_store(persist_dir: Path | str | None = None) -> None:
    """Persist the in-memory parent store to disk."""
    path = get_parents_file_path(persist_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(PARENT_STORE, f, ensure_ascii=False, indent=2)


def load_parent_store(persist_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Load parent store into memory from disk."""
    global PARENT_STORE
    path = get_parents_file_path(persist_dir)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            PARENT_STORE.clear()
            PARENT_STORE.update(loaded)
    return PARENT_STORE


def get_parent_document(parent_id: str, persist_dir: Path | str | None = None) -> dict[str, Any] | None:
    """Retrieve parent chunk from in-memory store, loading from disk if store is empty."""
    if not PARENT_STORE:
        load_parent_store(persist_dir)
    return PARENT_STORE.get(parent_id)


def ingest_schemes(
    data_dir: Path | str | None = None,
    persist_dir: Path | str | None = None,
) -> dict[str, int]:
    """Load scheme files, chunk into parent & child, and store in Chroma and memory."""
    source_dir = Path(data_dir) if data_dir else settings.DATA_DIR
    target_dir = Path(persist_dir) if persist_dir else settings.CHROMA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=1800, chunk_overlap=150)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=350, chunk_overlap=40)

    client = chromadb.PersistentClient(path=str(target_dir))
    embedding_fn = get_embedding_function()

    # Reset or get collection
    try:
        client.delete_collection("scheme_children")
    except Exception:
        pass

    collection = client.create_collection(
        name="scheme_children",
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    child_docs: list[str] = []
    child_metadatas: list[dict[str, Any]] = []
    child_ids: list[str] = []

    scheme_files = list(source_dir.glob("*.json")) + list(source_dir.glob("*.md"))

    for filepath in scheme_files:
        if filepath.suffix == ".json":
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            scheme_id = data.get("scheme_id", filepath.stem)
            name = data.get("name", "")
            state = data.get("state", "central")
            category = data.get("category", "general")
            content = data.get("content", "")
            full_text = f"{name}\nCategory: {category}\nState: {state}\n\n{content}"
            meta = {
                "scheme_id": scheme_id,
                "name": name,
                "state": state,
                "category": category,
                "source_url": data.get("source_url", ""),
            }
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                full_text = f.read()
            scheme_id = filepath.stem
            name = filepath.stem
            state = "central"
            category = "general"
            meta = {"scheme_id": scheme_id, "name": name, "state": state, "category": category}

        # Step 1: Parent chunks
        parents = parent_splitter.split_text(full_text)
        for p_idx, p_text in enumerate(parents):
            parent_id = f"{scheme_id}_p_{p_idx}"
            PARENT_STORE[parent_id] = {
                "parent_id": parent_id,
                "text": p_text,
                "metadata": meta,
            }

            # Step 2: Child chunks
            children = child_splitter.split_text(p_text)
            for c_idx, c_text in enumerate(children):
                c_id = f"{parent_id}_c_{c_idx}"
                child_docs.append(c_text)
                child_ids.append(c_id)
                child_metadatas.append(
                    {
                        "parent_id": parent_id,
                        "scheme_id": scheme_id,
                        "state": state,
                        "category": category,
                        "name": name,
                    }
                )

    if child_docs:
        collection.add(documents=child_docs, metadatas=child_metadatas, ids=child_ids)

    save_parent_store(target_dir)

    logger.info(
        "Ingested %d parents and %d children into Chroma.",
        len(PARENT_STORE),
        len(child_docs),
    )
    return {"parents_count": len(PARENT_STORE), "children_count": len(child_docs)}


if __name__ == "__main__":
    print("Starting scheme ingestion...")
    stats = ingest_schemes()
    print(f"Ingestion complete: {stats}")
