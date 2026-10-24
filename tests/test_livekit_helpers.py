from opentelemetry import trace as otel_trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

from finchvox.livekit import current_trace_id, session_report_json


def test_current_trace_id_returns_active_otel_trace():
    trace_id_int = int("0123456789abcdef0123456789abcdef", 16)
    span_context = SpanContext(
        trace_id=trace_id_int,
        span_id=int("0123456789abcdef", 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=otel_trace.DEFAULT_TRACE_STATE,
    )

    with otel_trace.use_span(NonRecordingSpan(span_context), end_on_exit=False):
        assert current_trace_id() == "0123456789abcdef0123456789abcdef"


def test_session_report_json_accepts_dict():
    rendered = session_report_json({"room_name": "local-room", "events": []})

    assert '"room_name": "local-room"' in rendered


def test_upload_session_artifacts_requires_report_without_trace_id():
    import asyncio
    from finchvox.livekit import upload_session_artifacts

    async def run():
        try:
            await upload_session_artifacts()
        except ValueError as exc:
            return str(exc)
        raise AssertionError("expected ValueError")

    assert "report is required" in asyncio.run(run())
