"""
tests/test_proxy_addon.py — Unit tests for proxy/addon.py ArtifactCaptureAddon.

Requirements: PROXY-01, PROXY-02, PROXY-03, PROXY-04
"""

import pytest
from unittest.mock import MagicMock
from proxy.addon import ArtifactCaptureAddon

SESSION_CTX = {
    "intent_id": "intent-aaa",
    "cascade_id": "cascade-bbb",
    "stage_id": "stage-ccc",
}


def make_flow(
    url="https://api.anthropic.com/v1/messages",
    status=200,
    content_type="application/json",
    session_id="sess-001",
):
    flow = MagicMock()
    flow.request.pretty_url = url
    flow.response.status_code = status
    flow.response.headers = {"content-type": content_type}
    flow.metadata = {"session_id": session_id}
    return flow


@pytest.mark.asyncio
async def test_artifact_enqueued_on_response():
    addon = ArtifactCaptureAddon()
    addon.register_session("sess-001", SESSION_CTX)
    flow = make_flow()
    await addon.response(flow)
    assert not addon.queue.empty()
    item = addon.queue.get_nowait()
    assert item["url"] == "https://api.anthropic.com/v1/messages"
    assert item["status_code"] == 200


@pytest.mark.asyncio
async def test_artifact_carries_full_trace():
    addon = ArtifactCaptureAddon()
    addon.register_session("sess-001", SESSION_CTX)
    flow = make_flow()
    await addon.response(flow)
    item = addon.queue.get_nowait()
    assert item["intent_id"] == "intent-aaa"
    assert item["cascade_id"] == "cascade-bbb"
    assert item["stage_id"] == "stage-ccc"
    assert item["session_id"] == "sess-001"


@pytest.mark.asyncio
async def test_queue_full_drops_silently():
    addon = ArtifactCaptureAddon()
    # Fill queue to capacity
    for i in range(500):
        addon._queue.put_nowait({"dummy": i})
    addon.register_session("sess-001", SESSION_CTX)
    flow = make_flow()
    # Must not raise — circuit-breaker drops silently
    await addon.response(flow)
    assert addon.queue.full()


def test_sse_stream_passthrough():
    addon = ArtifactCaptureAddon()
    flow = make_flow(content_type="text/event-stream; charset=utf-8")
    flow.response.stream = False
    addon.responseheaders(flow)
    assert flow.response.stream is True
