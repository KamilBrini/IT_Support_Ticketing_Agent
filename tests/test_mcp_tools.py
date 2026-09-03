"""Tests for the FastMCP tools: ticket status, password reset, ticket creation."""

from src.tools.mcp_server import create_ticket, get_ticket_status, request_password_reset


def test_get_ticket_status_found() -> None:
    result = get_ticket_status("TCK-1001")
    assert result.found is True
    assert result.ticket_id == "TCK-1001"
    assert result.status is not None
    assert result.error_code is None


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
