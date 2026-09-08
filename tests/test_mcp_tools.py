"""Tests for the FastMCP tools: ticket status, password reset, ticket creation."""

from src.tools.mcp_server import (
    create_ticket,
    get_ticket_owner,
    get_ticket_status,
    list_tickets_for_user,
    request_password_reset,
)


def test_get_ticket_status_found() -> None:
    result = get_ticket_status("TCK-1001")
    assert result.found is True
    assert result.ticket_id == "TCK-1001"
    assert result.status is not None
    assert result.error_code is None
    assert result.title == "Cannot connect to VPN"


def test_get_ticket_status_not_found() -> None:
    result = get_ticket_status("TCK-9999")
    assert result.found is False
    assert result.error_code == "ERR-NOT-FOUND"
    assert result.status is None


def test_get_ticket_status_blank_id_does_not_raise() -> None:
    result = get_ticket_status("")
    assert result.found is False
    assert result.error_code == "ERR-NOT-FOUND"


def test_request_password_reset_completed() -> None:
    result = request_password_reset(user_id="u-001", reason="Forgot my password after vacation.")
    assert result["status"] == "completed"
    assert "MFA" in result["next_action"]


def test_request_password_reset_escalates_on_identity_risk() -> None:
    result = request_password_reset(
        user_id="u-001", reason="This request is not my account, someone else set it up."
    )
    assert result["status"] == "escalated"


def test_request_password_reset_rejects_invalid_input() -> None:
    result = request_password_reset(user_id="u-001", reason="hi")
    assert result["status"] == "rejected"


def test_list_tickets_for_user_returns_only_that_users_tickets() -> None:
    results = list_tickets_for_user("u-001")
    assert len(results) == 1
    assert results[0].ticket_id == "TCK-1001"
    assert results[0].found is True


def test_list_tickets_for_user_empty_for_unknown_user() -> None:
    assert list_tickets_for_user("no-such-user") == []


def test_get_ticket_owner_returns_requester_user_id() -> None:
    assert get_ticket_owner("TCK-1001") == "u-001"


def test_get_ticket_owner_is_case_and_whitespace_insensitive() -> None:
    assert get_ticket_owner(" tck-1001 ") == "u-001"


def test_get_ticket_owner_none_for_unknown_ticket() -> None:
    assert get_ticket_owner("TCK-9999") is None


def test_create_ticket_success() -> None:
    result = create_ticket(
        tenant_id="tenant-a",
        requester_user_id="u-099",
        title="Monitor flickers randomly",
        description="External monitor flickers every few minutes since the last driver update.",
        category="hardware",
        priority="medium",
    )
    assert result["status"] == "created"
    assert result["ticket_id"].startswith("TCK-")

    # The new ticket must be immediately visible through the lookup tool too.
    lookup = get_ticket_status(result["ticket_id"])
    assert lookup.found is True


def test_create_ticket_rejects_invalid_priority() -> None:
    result = create_ticket(
        tenant_id="tenant-a",
        requester_user_id="u-099",
        title="Valid title here",
        description="A description that is definitely long enough to pass validation.",
        category="hardware",
        priority="urgent-ish",
    )
    assert result["status"] == "rejected"
    assert result["ticket_id"] is None


def test_create_ticket_rejects_short_title() -> None:
    result = create_ticket(
        tenant_id="tenant-a",
        requester_user_id="u-099",
        title="Hi",
        description="A description that is definitely long enough to pass validation.",
        category="hardware",
        priority="low",
    )
    assert result["status"] == "rejected"
