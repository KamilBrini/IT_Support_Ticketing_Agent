"""Single shared ChromaDB PersistentClient for the whole app.

Creating a new PersistentClient per call is not safe under concurrent
requests: initializing multiple clients against the same on-disk SQLite
file at the same time can race. Reproduced live under FastAPI's default
threadpool concurrency (each /chat request touches ChromaDB twice - once
for RAG retrieval, once for long-term-memory recall - so concurrent
requests were creating several clients per second): "Could not connect to
tenant default_tenant. Are you sure it exists?", "'RustBindingsAPI' object
has no attribute 'bindings'". One client, created once, reused everywhere,
guarded by a lock only around the one-time creation.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import chromadb

DEFAULT_CHROMA_PATH = Path("./data/chroma")

_client: chromadb.ClientAPI | None = None
_lock = threading.Lock()


def get_client() -> chromadb.ClientAPI:
    """Return the process-wide ChromaDB client, creating it on first use."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                chroma_path = Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_CHROMA_PATH)))
                _client = chromadb.PersistentClient(path=str(chroma_path))
    return _client
