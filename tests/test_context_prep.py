"""
tests/test_context_prep.py — TDD RED tests for judgment/context_prep.py.

Task 1 of 03-03-PLAN. Written before implementation (RED phase).
"""

from judgment.context_prep import prepare_context


def test_prepare_context_strips_tool_calls():
    """Tool-call messages must be excluded."""
    history = [
        {"kind": "request", "content": "analyze this"},
        {"kind": "tool-call", "content": "exec_bash"},
        {"kind": "tool-return", "content": "result"},
        {"kind": "response", "content": "here is my analysis"},
    ]
    result = prepare_context(history)
    assert "analyze this" in result
    assert "here is my analysis" in result
    assert "exec_bash" not in result
    assert "result" not in result


def test_prepare_context_keeps_requests_and_responses():
    """User requests and model responses are kept."""
    history = [
        {"kind": "request", "content": "hello"},
        {"kind": "response", "content": "world"},
    ]
    result = prepare_context(history)
    assert "hello" in result
    assert "world" in result


def test_prepare_context_truncates_long_middles():
    """Strings over max_chars are truncated with an omission marker."""
    # Build a history that produces a long string
    long_msg = "X" * 5000
    history = [
        {"kind": "request", "content": long_msg},
        {"kind": "response", "content": long_msg},
    ]
    result = prepare_context(history, max_chars=1000)
    assert "omitted" in result
    assert len(result) < len(long_msg) * 2


def test_prepare_context_returns_full_when_short():
    """Short histories are returned without truncation."""
    history = [
        {"kind": "request", "content": "short"},
        {"kind": "response", "content": "answer"},
    ]
    result = prepare_context(history, max_chars=8000)
    assert "short" in result
    assert "answer" in result
    assert "omitted" not in result


def test_prepare_context_handles_list_content():
    """Content as a list of part dicts (pydantic-ai platform format) is supported."""
    history = [
        {"kind": "request", "content": [{"content": "list format message"}]},
    ]
    result = prepare_context(history)
    assert "list format message" in result
