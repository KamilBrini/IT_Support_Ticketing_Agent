"""Core schema models for the IT support agent domain."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TicketPriority(str, Enum):
    """Allowed ticket priority values."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TicketStatus(str, Enum):
    """Allowed ticket status values."""

    open = "open"
    in_progress = "in_progress"
    waiting_user = "waiting_user"
    resolved = "resolved"
    closed = "closed"


class ChatRole(str, Enum):
    """Role values for chat messages."""

    user = "user"
    assistant = "assistant"
    tool = "tool"
    system = "system"


class MemoryScope(str, Enum):
    """Persistence scopes for agent memory records."""

    ephemeral = "ephemeral"
    session = "session"
    ticket = "ticket"


class SupportTicket(BaseModel):
    """Tenant-scoped support ticket record."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    requester_user_id: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(min_length=1, max_length=6000)
    category: str = Field(min_length=1, max_length=80)
    priority: TicketPriority
    status: TicketStatus
    assigned_queue: str | None = None
    escalation_level: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "ticket_id",
        "tenant_id",
        "requester_user_id",
        "title",
        "description",
        "category",
        "assigned_queue",
        mode="before",
    )
    @classmethod
    def _strip_and_reject_empty(cls, value: object) -> object:
        """Trim string fields and reject blank-only values."""
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class ChatMessage(BaseModel):
    """Single chat message persisted for a ticket conversation."""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    role: ChatRole
    content: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    tool_call_id: str | None = None
    redaction_applied: bool
    injection_screened: bool
    created_at: datetime

    @field_validator(
        "message_id",
        "ticket_id",
        "tenant_id",
        "content",
        "tool_call_id",
        mode="before",
    )
    @classmethod
    def _strip_text_fields(cls, value: object) -> object:
        """Normalize text fields and block blank strings."""
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value

    @field_validator("citations")
    @classmethod
    def _normalize_citations(cls, citations: list[str]) -> list[str]:
        """Trim citation items and remove empty entries."""
        cleaned = [item.strip() for item in citations if item and item.strip()]
        return cleaned


class ChatRequest(BaseModel):
    """Input payload for non-streaming chat requests."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=80)
    session_id: str = Field(min_length=1, max_length=120)
    user_message: str = Field(min_length=1, max_length=6000)

    @field_validator("user_id", "session_id", "user_message", mode="before")
    @classmethod
    def _strip_chat_fields(cls, value: object) -> object:
        """Normalize chat input fields and reject blank strings."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class KnowledgeChunk(BaseModel):
    """Indexed knowledge chunk used by tenant-scoped retrieval."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    source_doc_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    embedding_vector_ref: str = Field(min_length=1)
    policy_tags: list[str] = Field(min_length=1)
    active: bool
    revision: int = Field(ge=1)
    updated_at: datetime

    @field_validator(
        "chunk_id",
        "tenant_id",
        "source_doc_id",
        "source_title",
        "content",
        "embedding_vector_ref",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        """Trim required text fields and reject blank values."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value

    @field_validator("policy_tags")
    @classmethod
    def _normalize_policy_tags(cls, tags: list[str]) -> list[str]:
        """Ensure policy tags are non-empty after normalization."""
        cleaned = [tag.strip() for tag in tags if tag and tag.strip()]
        if not cleaned:
            raise ValueError("policy_tags must include at least one non-empty tag")
        return cleaned


class MemoryRecord(BaseModel):
    """Scoped memory key-value entry for conversation continuity."""

    model_config = ConfigDict(extra="forbid")

    memory_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    ticket_id: str | None = None
    memory_scope: MemoryScope
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    expires_at: datetime | None = None
    created_at: datetime

    @field_validator("memory_id", "tenant_id", "ticket_id", "key", "value", mode="before")
    @classmethod
    def _strip_memory_strings(cls, value: object) -> object:
        """Normalize memory string fields and reject blanks."""
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class TicketLookupRequest(BaseModel):
    """Input payload for ticket status lookup."""

    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(min_length=1, max_length=64)

    @field_validator("ticket_id", mode="before")
    @classmethod
    def _strip_ticket_id(cls, value: object) -> object:
        """Normalize and validate incoming ticket IDs."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("ticket_id must not be empty")
            return normalized
        return value


class TicketStatusResponse(BaseModel):
    """Structured result for ticket status lookup operations."""

    model_config = ConfigDict(extra="forbid")

    found: bool
    ticket_id: str
    status: TicketStatus | None = None
    assigned_queue: str | None = None
    escalation_level: int | None = None
    updated_at: datetime
    error_code: str | None = None
    message: str | None = None


class PasswordResetRequest(BaseModel):
    """Validated request payload for password reset tool usage."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=5, max_length=400)

    @field_validator("user_id", "reason", mode="before")
    @classmethod
    def _strip_reset_text(cls, value: object) -> object:
        """Trim and validate required password reset fields."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class PasswordResetResult(BaseModel):
    """Structured outcome returned by password reset requests."""

    model_config = ConfigDict(extra="forbid")

    status: str
    next_action: str

    @field_validator("status", "next_action", mode="before")
    @classmethod
    def _strip_result_text(cls, value: object) -> object:
        """Normalize output fields to avoid blank strings."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class TicketCreateRequest(BaseModel):
    """Validated input payload for creating a new support ticket."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(min_length=1, max_length=80)
    requester_user_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=20, max_length=6000)
    category: str = Field(min_length=2, max_length=80)
    priority: TicketPriority

    @field_validator(
        "tenant_id",
        "requester_user_id",
        "title",
        "description",
        "category",
        mode="before",
    )
    @classmethod
    def _strip_create_ticket_fields(cls, value: object) -> object:
        """Normalize create-ticket text fields and reject blanks."""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class TicketCreateResult(BaseModel):
    """Structured result returned by the create ticket tool."""

    model_config = ConfigDict(extra="forbid")

    status: str
    ticket_id: str | None = None
    message: str

    @field_validator("status", "ticket_id", "message", mode="before")
    @classmethod
    def _strip_create_result_fields(cls, value: object) -> object:
        """Normalize output text fields and reject blank values."""
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                raise ValueError("must not be empty")
            return normalized
        return value


class AgentState(TypedDict):
    """LangGraph state shared between orchestration nodes."""

    user_id: str
    session_id: str
    sanitized_message: str
    intent: NotRequired[str | None]
    retrieved_context: NotRequired[str | None]
    tool_result: NotRequired[dict[str, Any] | None]
    response: NotRequired[str | None]
    session_history: NotRequired[list[tuple[str, str]]]
    user_facts: NotRequired[list[str]]
