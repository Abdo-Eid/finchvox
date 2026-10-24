from finchvox.adapters.base import BaseTraceAdapter, SpanTypeConfig
from finchvox.adapters.pipecat import PipecatAdapter
from finchvox.adapters.livekit import LiveKitAdapter


LIVEKIT_SPAN_NAMES = {
    "agent_session",
    "session_start",
    "agent_turn",
    "user_turn",
    "user_speaking",
    "agent_speaking",
    "stt_node",
    "stt_request",
    "eou_wait",
    "llm_node",
    "llm_request",
    "llm_request_run",
    "realtime_inference",
    "tts_node",
    "tts_request",
    "tts_request_run",
    "function_tool",
    "execute_tool",
    "update_agent",
    "room_connect",
    "room_io",
}


def detect_platform(spans: list[dict]) -> str:
    for span in spans:
        scope = span.get("instrumentation_scope", {})
        scope_name = scope.get("name", "")
        if scope_name == "livekit-agents":
            return "livekit"

        if span.get("name") in LIVEKIT_SPAN_NAMES:
            return "livekit"

        attrs = span.get("attributes", [])
        for attr in attrs:
            key = attr.get("key", "")
            if key.startswith("lk."):
                return "livekit"

    return "pipecat"


def get_adapter(spans: list[dict]) -> BaseTraceAdapter:
    platform = detect_platform(spans)
    if platform == "livekit":
        return LiveKitAdapter()
    return PipecatAdapter()


__all__ = [
    "BaseTraceAdapter",
    "SpanTypeConfig",
    "PipecatAdapter",
    "LiveKitAdapter",
    "detect_platform",
    "get_adapter",
]
