"""Tests for Pydantic schema validation (src/schemas/models.py)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.schemas.models import (
    ChatRequest,
    KnowledgeChunk,
    TicketCreateRequest,
    TicketPriority,
    TicketStatus,
)


def test_chat_request_accepts_valid_input() -> None:
    request = ChatRequest(user_id="u-1", session_id="s-1", user_message="Hello")
    assert request.user_message == "Hello"


def test_chat_request_rejects_blank_message() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(user_id="u-1", session_id="s-1", user_message="   ")


def test_chat_request_strips_whitespace() -> None:
    request = ChatRequest(user_id=" u-1 ", session_id="s-1", user_message=" hi ")
    assert request.user_id == "u-1"
    assert request.user_message == "hi"


def test_chat_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(user_id="u-1", session_id="s-1", user_message="hi", extra_field="nope")


def test_ticket_create_request_rejects_short_title() -> None:
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            tenant_id="t-1",
            requester_user_id="u-1",
            title="Hi",
            description="A sufficiently long description of the problem being reported.",
            category="hardware",
            priority=TicketPriority.low,
        )


def test_ticket_create_request_rejects_short_description() -> None:
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            tenant_id="t-1",
            requester_user_id="u-1",
            title="Valid title here",
            description="too short",
            category="hardware",
            priority=TicketPriority.low,
        )


def test_knowledge_chunk_rejects_empty_policy_tags() -> None:
    with pytest.raises(ValidationError):
        KnowledgeChunk(
            chunk_id="c-1",
            tenant_id="t-1",
            source_doc_id="d-1",
            source_title="VPN Policy",
            content="Some policy text.",
            embedding_vector_ref="ref-1",
            policy_tags=["   "],
            active=True,
            revision=1,
            updated_at=datetime.now(timezone.utc),
        )


def test_knowledge_chunk_accepts_valid_tags() -> None:
    chunk = KnowledgeChunk(
        chunk_id="c-1",
        tenant_id="t-1",
        source_doc_id="d-1",
        source_title="VPN Policy",
        content="Some policy text.",
        embedding_vector_ref="ref-1",
        policy_tags=[" vpn ", "access"],
        active=True,
        revision=1,
        updated_at=datetime.now(timezone.utc),
    )
    assert chunk.policy_tags == ["vpn", "access"]


def test_ticket_status_enum_values() -> None:
    assert TicketStatus.open.value == "open"
    assert TicketStatus.in_progress.value == "in_progress"
