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
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import chromadb

DEFAULT_CHROMA_PATH = Path("./data/chroma")

_client: chromadb.ClientAPI | None = None
_lock = threading.Lock()
_operation_lock = threading.Lock()


def get_client() -> chromadb.ClientAPI:
    """Return the process-wide ChromaDB client, creating it on first use."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                chroma_path = Path(os.getenv("CHROMA_DB_PATH", str(DEFAULT_CHROMA_PATH)))
                _client = chromadb.PersistentClient(path=str(chroma_path))
    return _client


@contextmanager
def collection_operation_lock() -> Iterator[None]:
    """Serialize actual ChromaDB reads/writes across request threads.

    The shared PersistentClient is backed by a single on-disk SQLite file.
    FastAPI runs each sync request handler on its own thread, and every
    single chat turn touches Chroma at least once (RAG retrieval or
    long-term memory recall in load_session_memory) even on fast/no-LLM
    paths - so under real concurrent traffic (multiple browser tabs, a demo
    running alongside a test script, ...) several threads can end up
    calling collection.query()/get_or_create_collection()/add() on the same
    SQLite file at once. Reproduced live: this wedged the entire backend -
    every worker thread ended up blocked waiting on the same file lock, so
    even unrelated requests stopped getting any response at all, not just
    the ones touching Chroma concurrently. `get_client()`'s own `_lock`
    above only ever guarded one-time client *creation*, not this. Kept as
    narrow as possible (just the actual Chroma call, not the whole request)
    since it's now on the hot path for every turn.
    """
    with _operation_lock:
        yield
