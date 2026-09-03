"""Tests for per-user long-term memory (US-009, src/agent/long_term_memory.py).

Runs against the real local ChromaDB index (offline embedding model, no
network/API key needed) using dedicated throwaway user_ids so it never
touches real demo data and cleans up after itself.
"""

from __future__ import annotations

import uuid

import pytest

from src.agent import long_term_memory
from src.rag.chroma_client import get_client


@pytest.fixture
def user_id():
    """A fresh, isolated user_id per test; its collection is deleted after."""
    uid = f"test-user-{uuid.uuid4().hex[:8]}"
    yield uid
    try:
        get_client().delete_collection(long_term_memory._collection_name(uid))
    except Exception:
        pass  # never stored anything, nothing to clean up


def test_recall_before_any_fact_is_empty(user_id: str) -> None:
    assert long_term_memory.recall_facts(user_id, "what device do I use?") == []


def test_remember_then_recall_relevant_fact(user_id: str) -> None:
    long_term_memory.remember_fact(user_id, "I work from the London office on a MacBook Pro.")
    results = long_term_memory.recall_facts(user_id, "what device does this employee use?")
    assert any("MacBook" in fact for fact in results)


def test_remember_ignores_blank_input(user_id: str) -> None:
    long_term_memory.remember_fact(user_id, "   ")
    assert long_term_memory.recall_facts(user_id, "anything") == []


def test_recall_ignores_blank_query(user_id: str) -> None:
    long_term_memory.remember_fact(user_id, "I work from the London office.")
    assert long_term_memory.recall_facts(user_id, "   ") == []


def test_facts_are_isolated_per_user() -> None:
    user_a = f"test-user-a-{uuid.uuid4().hex[:8]}"
    user_b = f"test-user-b-{uuid.uuid4().hex[:8]}"
    client = get_client()

    try:
        long_term_memory.remember_fact(user_a, "I work from the London office on a MacBook Pro.")

        # user_b has never stored anything - must not see user_a's fact, even
        # asking the exact same question.
        results_b = long_term_memory.recall_facts(user_b, "what device does this employee use?")
        assert results_b == []

        results_a = long_term_memory.recall_facts(user_a, "what device does this employee use?")
        assert any("MacBook" in fact for fact in results_a)
    finally:
        for uid in (user_a, user_b):
            try:
                client.delete_collection(long_term_memory._collection_name(uid))
            except Exception:
                pass


def test_collection_name_sanitizes_unsafe_characters() -> None:
    name = long_term_memory._collection_name("demo user!@#$%^&*()")
    assert name.startswith("user_memory_")
    assert all(c.isalnum() or c in "_-" for c in name)
