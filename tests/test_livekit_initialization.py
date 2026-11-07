import sys
from types import ModuleType
from unittest.mock import Mock

import pytest
from opentelemetry import trace
from opentelemetry.context import get_current
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

import finchvox


@pytest.fixture
def livekit_setup(monkeypatch):
    from opentelemetry.exporter.otlp.proto.grpc import trace_exporter
    from opentelemetry.sdk import trace as sdk_trace
    from opentelemetry.sdk.trace import export

    telemetry = ModuleType("livekit.agents.telemetry")
    telemetry.set_tracer_provider = Mock()
    monkeypatch.setitem(sys.modules, "livekit.agents.telemetry", telemetry)
    provider = Mock()
    monkeypatch.setattr(sdk_trace, "TracerProvider", Mock(return_value=provider))
    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", Mock())
    monkeypatch.setattr(export, "BatchSpanProcessor", Mock())
    return telemetry, provider


@pytest.mark.parametrize("allow_pii", [False, True])
def test_init_livekit_passes_explicit_privacy_policy(livekit_setup, allow_pii):
    telemetry, provider = livekit_setup
    result = finchvox.init_livekit(
        capture_logs=False, allow_pii=allow_pii, metadata={"environment": "test"}
    )

    assert result is provider
    telemetry.set_tracer_provider.assert_called_once_with(
        provider, metadata={"environment": "test"}, allow_pii=allow_pii
    )


def test_init_livekit_never_retries_without_privacy_policy(livekit_setup):
    telemetry, _ = livekit_setup
    telemetry.set_tracer_provider.side_effect = TypeError("unsupported allow_pii")

    with pytest.raises(TypeError, match="unsupported allow_pii"):
        finchvox.init_livekit(capture_logs=False, allow_pii=False)

    assert telemetry.set_tracer_provider.call_count == 1


def test_init_livekit_reports_the_environment_for_the_environment_tab(
    livekit_setup, monkeypatch
):
    from finchvox.environment import EnvironmentSpanProcessor

    captured = Mock()
    monkeypatch.setattr(finchvox, "capture_environment", captured)
    _, provider = livekit_setup

    finchvox.init_livekit(capture_logs=False, endpoint="http://finchvox:4317")

    captured.assert_called_once_with()
    processors = [
        call.args[0]
        for call in provider.add_span_processor.call_args_list
        if isinstance(call.args[0], EnvironmentSpanProcessor)
    ]
    assert len(processors) == 1
    assert processors[0]._endpoint == "http://finchvox:3000"


def test_pipecat_log_context_prefers_active_native_span():
    context = SpanContext(123, 456, False, TraceFlags(TraceFlags.SAMPLED))
    with trace.use_span(NonRecordingSpan(context), end_on_exit=False):
        assert finchvox._get_pipecat_context() is get_current()
