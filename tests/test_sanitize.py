"""Tests for trust boundary sanitization (ADAPT-04).

Four tests covering sanitize_email contract:
- Control character stripping from body
- Body length capping at MAX_RAW_LENGTH
- Valid email produces SanitizedIntent with correct fields
- Empty sender returns SanitizationError, never raises
"""

from adapters.sanitize import (
    MAX_RAW_LENGTH,
    SanitizationError,
    SanitizedIntent,
    sanitize_email,
)


def test_sanitize_strips_control_chars() -> None:
    """ADAPT-04: Control characters are stripped from raw email body."""
    body_with_controls = "Hello\x01World\x0bTest\x7fEnd"
    result = sanitize_email(
        message_id="<test-1@example.com>",
        sender="alice@example.com",
        subject="Test\x01Subject",
        body=body_with_controls,
    )
    assert isinstance(result, SanitizedIntent)
    # Control chars must be gone from raw body
    assert "\x01" not in result.raw
    assert "\x0b" not in result.raw
    assert "\x7f" not in result.raw
    assert "HelloWorldTestEnd" == result.raw
    # Control chars must also be gone from subject
    assert "\x01" not in result.subject
    assert result.subject == "TestSubject"


def test_sanitize_max_length() -> None:
    """ADAPT-04: Raw body is capped at MAX_RAW_LENGTH characters."""
    long_body = "A" * (MAX_RAW_LENGTH + 500)
    result = sanitize_email(
        message_id="<test-2@example.com>",
        sender="alice@example.com",
        subject="Long body test",
        body=long_body,
    )
    assert isinstance(result, SanitizedIntent)
    assert len(result.raw) == MAX_RAW_LENGTH


def test_sanitize_valid_email() -> None:
    """ADAPT-04: Valid email returns SanitizedIntent with correct fields."""
    result = sanitize_email(
        message_id="<msg-abc123@mail.example.com>",
        sender="bob@example.com",
        subject="Meeting tomorrow",
        body="Let us meet at 10am.",
    )
    assert isinstance(result, SanitizedIntent)
    assert result.source_message_id == "<msg-abc123@mail.example.com>"
    assert result.sender_email == "bob@example.com"
    assert result.subject == "Meeting tomorrow"
    assert result.raw == "Let us meet at 10am."


def test_sanitize_returns_error_on_empty_sender() -> None:
    """ADAPT-04: Missing sender returns SanitizationError, not raises."""
    result = sanitize_email(
        message_id="<test-3@example.com>",
        sender="",
        subject="Test",
        body="Some body text.",
    )
    assert isinstance(result, SanitizationError)
    assert result.raw_length == len("Some body text.")
