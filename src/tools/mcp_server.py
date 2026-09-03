"""FastMCP server with seeded ticket and password-reset tools."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastmcp import FastMCP
from pydantic import ValidationError

from src.schemas.models import (
    PasswordResetRequest,
    PasswordResetResult,
    SupportTicket,
    TicketCreateRequest,
    TicketCreateResult,
    TicketLookupRequest,
    TicketPriority,
    TicketStatus,
    TicketStatusResponse,
)

mcp = FastMCP("it-support-agent-tools")

_NOW = datetime.now(timezone.utc)

_TICKETS: list[SupportTicket] = [
    SupportTicket(
        ticket_id="TCK-1001",
        tenant_id="tenant-a",
        requester_user_id="u-001",
        title="Cannot connect to VPN",
        description="VPN client reports authentication timeout.",
        category="network",
        priority=TicketPriority.high,
        status=TicketStatus.open,
        assigned_queue="network-ops",
        escalation_level=0,
        created_at=_NOW - timedelta(hours=5),
        updated_at=_NOW - timedelta(hours=2),
    ),
    SupportTicket(
        ticket_id="TCK-1002",
        tenant_id="tenant-a",
        requester_user_id="u-002",
        title="Password reset needed",
        description="Unable to log in after credential expiration.",
        category="identity",
        priority=TicketPriority.medium,
        status=TicketStatus.resolved,
        assigned_queue="identity-helpdesk",
        escalation_level=0,
        created_at=_NOW - timedelta(days=1, hours=4),
        updated_at=_NOW - timedelta(hours=10),
    ),
    SupportTicket(
        ticket_id="TCK-1003",
        tenant_id="tenant-b",
        requester_user_id="u-010",
        title="Email outage for executive mailbox",
        description="Mailbox intermittently rejects inbound messages.",
        category="email",
        priority=TicketPriority.critical,
        status=TicketStatus.in_progress,
        assigned_queue="tier-3-escalations",
        escalation_level=2,
        created_at=_NOW - timedelta(hours=12),
        updated_at=_NOW - timedelta(minutes=35),
    ),
    SupportTicket(
        ticket_id="TCK-1004",
        tenant_id="tenant-b",
        requester_user_id="u-021",
        title="Laptop battery drains rapidly",
        description="Battery drops from 100 to 20 percent in one hour.",
        category="hardware",
        priority=TicketPriority.low,
        status=TicketStatus.open,
        assigned_queue="endpoint-support",
        escalation_level=1,
        created_at=_NOW - timedelta(days=2),
        updated_at=_NOW - timedelta(days=1, minutes=15),
    ),
]


def _not_found_response(ticket_id: str) -> TicketStatusResponse:
    """Build a stable not-found result for unknown ticket IDs."""
    return TicketStatusResponse(
        found=False,
        ticket_id=ticket_id,
        status=None,
        assigned_queue=None,
        escalation_level=None,
        updated_at=datetime.now(timezone.utc),
        error_code="ERR-NOT-FOUND",
        message="Ticket was not found.",
    )


def _generate_ticket_id() -> str:
    """Generate the next sequential ticket identifier."""
    max_num = 1000
    for ticket in _TICKETS:
        parts = ticket.ticket_id.split("-", 1)
        if len(parts) == 2 and parts[0] == "TCK" and parts[1].isdigit():
            max_num = max(max_num, int(parts[1]))
    return f"TCK-{max_num + 1:04d}"


@mcp.tool()
def get_ticket_status(ticket_id: str) -> TicketStatusResponse:
    """Return ticket status details from an in-memory seeded list."""
    try:
        request = TicketLookupRequest(ticket_id=ticket_id)
    except ValidationError:
        return _not_found_response(ticket_id=str(ticket_id).strip() if ticket_id else "")

    for ticket in _TICKETS:
        if ticket.ticket_id == request.ticket_id:
            return TicketStatusResponse(
                found=True,
                ticket_id=ticket.ticket_id,
                status=ticket.status,
                assigned_queue=ticket.assigned_queue,
                escalation_level=ticket.escalation_level,
                updated_at=ticket.updated_at,
                error_code=None,
                message=None,
            )

    return _not_found_response(request.ticket_id)


@mcp.tool()
def request_password_reset(user_id: str, reason: str) -> dict[str, str]:
    """Validate password reset input and return next action guidance."""
    try:
        request = PasswordResetRequest(user_id=user_id, reason=reason)
    except ValidationError:
        result = PasswordResetResult(
            status="rejected",
            next_action="Provide a valid user_id and a detailed reason (5-400 chars).",
        )
        return result.model_dump()

    lower_reason = request.reason.casefold()
    escalation_markers = ("someone else", "not my account")
    if any(marker in lower_reason for marker in escalation_markers):
        result = PasswordResetResult(
            status="escalated",
            next_action="Identity verification required; route to human support queue.",
        )
        return result.model_dump()

    result = PasswordResetResult(
        status="completed",
        next_action="Send reset link and enforce MFA challenge on next login.",
    )
    return result.model_dump()


@mcp.tool()
def create_ticket(
    tenant_id: str,
    requester_user_id: str,
    title: str,
    description: str,
    category: str,
    priority: str,
) -> dict[str, str | None]:
    """Create a new ticket, append it to memory, and return a generated ticket ID."""
    try:
        request = TicketCreateRequest(
            tenant_id=tenant_id,
            requester_user_id=requester_user_id,
            title=title,
            description=description,
            category=category,
            priority=TicketPriority(priority.strip().lower()),
        )
    except (ValidationError, ValueError):
        result = TicketCreateResult(
            status="rejected",
            ticket_id=None,
            message=(
                "Provide valid tenant_id, requester_user_id, title, description, "
                "category, and priority (low|medium|high|critical)."
            ),
        )
        return result.model_dump()

    now = datetime.now(timezone.utc)
    new_ticket = SupportTicket(
        ticket_id=_generate_ticket_id(),
        tenant_id=request.tenant_id,
        requester_user_id=request.requester_user_id,
        title=request.title,
        description=request.description,
        category=request.category,
        priority=request.priority,
        status=TicketStatus.open,
        assigned_queue="triage",
        escalation_level=0,
        created_at=now,
        updated_at=now,
    )
    _TICKETS.append(new_ticket)

    result = TicketCreateResult(
        status="created",
        ticket_id=new_ticket.ticket_id,
        message="Ticket created successfully.",
    )
    return result.model_dump()


if __name__ == "__main__":
    mcp.run()
