"""Ingest policy markdown files into a ChromaDB collection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from src.rag.embeddings import build_embedding_function

COLLECTION_NAME = "it_policy_docs"
DEFAULT_POLICIES_DIR = Path("data/policies")
DEFAULT_CHROMA_PATH = Path("./data/chroma")
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 50


@dataclass(frozen=True)
class ChunkRecord:
    """Container for chunk text and metadata prior to persistence."""

    chunk_text: str
    source_document: str
    policy_category: str
    last_updated: str
    chunk_index: int


def _tokenize(text: str) -> list[str]:
    """Approximate tokenization using whitespace splitting."""
    return text.split()


def _chunk_text(text: str, size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    """Split text into overlapping chunks using approximate token windows."""
    if size <= 0:
        raise ValueError("size must be > 0")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    tokens = _tokenize(text)
    if not tokens:
        return []

    chunks: list[str] = []
    step = size - overlap
    for start in range(0, len(tokens), step):
        window = tokens[start : start + size]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + size >= len(tokens):
            break
    return chunks


def _get_collection(client: chromadb.PersistentClient) -> Collection:
    """Get or create the target Chroma collection."""
    embedding_fn = build_embedding_function()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"purpose": "it policy retrieval"},
    )


def _file_last_updated(path: Path) -> str:
    """Return file mtime as ISO-8601 UTC string."""
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified.isoformat()


def _category_from_filename(path: Path) -> str:
    """Derive policy category from file name."""
    stem = path.stem
    if stem.endswith("_policy"):
        stem = stem[: -len("_policy")]
    return stem.replace("_", " ")


def _build_records(path: Path) -> list[ChunkRecord]:
    """Build chunk records for a single markdown policy document."""
    raw_text = path.read_text(encoding="utf-8")
    chunks = _chunk_text(raw_text)
    last_updated = _file_last_updated(path)
    category = _category_from_filename(path)

    records: list[ChunkRecord] = []
    for idx, chunk in enumerate(chunks):
        records.append(
            ChunkRecord(
                chunk_text=chunk,
                source_document=path.name,
                policy_category=category,
                last_updated=last_updated,
                chunk_index=idx,
            )
        )
    return records


def ingest_policies(policies_dir: Path = DEFAULT_POLICIES_DIR) -> int:
    """Chunk, embed, and store policy documents in ChromaDB."""
    chroma_path = Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_CHROMA_PATH)))
    chroma_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = _get_collection(client)

    md_files = sorted(policies_dir.glob("*.md"))
    if not md_files:
        return 0

    all_records: list[ChunkRecord] = []
    for file_path in md_files:
        all_records.extend(_build_records(file_path))

    if not all_records:
        return 0

    ids = [f"{r.source_document}:{r.chunk_index}" for r in all_records]
    documents = [r.chunk_text for r in all_records]
    metadatas = [
        {
            "source_document": r.source_document,
            "policy_category": r.policy_category,
            "last_updated": r.last_updated,
            "chunk_index": r.chunk_index,
        }
        for r in all_records
    ]

    existing_ids = set(collection.get(include=[]).get("ids", []))
    if existing_ids:
        delete_ids = [doc_id for doc_id in ids if doc_id in existing_ids]
        if delete_ids:
            collection.delete(ids=delete_ids)

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(all_records)


if __name__ == "__main__":
    count = ingest_policies()
    print(f"Ingested {count} chunks into '{COLLECTION_NAME}'.")
