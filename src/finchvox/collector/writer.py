import json
from collections.abc import Callable
from pathlib import Path

from google.protobuf.json_format import MessageToDict, SerializeToJsonError
from loguru import logger

from finchvox import telemetry
from finchvox.collector.config import get_session_dir


class SpanWriter:
    """Handles writing spans to JSONL files organized by trace_id."""

    def __init__(self, data_dir: Path, *, on_write: Callable[[], None] | None = None):
        """
        Initialize SpanWriter.

        Args:
            data_dir: Base data directory (e.g., ~/.finchvox)
        """
        self.data_dir = data_dir
        self.on_write = on_write

    def write_span(self, span, resource_spans, scope_spans) -> bool:
        """Append a span and report whether the write completed."""
        try:
            # Extract trace_id as hex string
            trace_id_hex = span.trace_id.hex()

            session_dir = get_session_dir(self.data_dir, trace_id_hex)
            session_dir.mkdir(parents=True, exist_ok=True)

            span_dict = self._convert_span_to_dict(span, resource_spans, scope_spans)

            trace_file = session_dir / f"trace_{trace_id_hex}.jsonl"

            is_new_session = not trace_file.exists()

            if is_new_session:
                span_name = span.name if span.name else "UNKNOWN"
                logger.info(
                    f"New session {trace_id_hex} - first span type: {span_name}"
                )
                telemetry.send_event("session_ingest")

            with trace_file.open("a") as f:
                json.dump(span_dict, f)
                f.write("\n")

            logger.debug(f"Wrote span {span.span_id.hex()} to {trace_file}")
        except (OSError, SerializeToJsonError, TypeError, ValueError) as e:
            # One unwritable span must not drop the rest of its export batch.
            logger.exception(f"Failed to write span: {e}")
            return False
        if self.on_write is not None:
            self.on_write()
        return True

    def _convert_span_to_dict(self, span, resource_spans, scope_spans):
        """Convert protobuf span to dictionary, preserving all fields."""
        # Use MessageToDict for automatic conversion
        span_data = MessageToDict(span, preserving_proto_field_name=True)

        # Note: MessageToDict converts bytes to base64 by default
        # We'll enhance with hex representation for trace_id/span_id
        span_data["trace_id_hex"] = span.trace_id.hex()
        span_data["span_id_hex"] = span.span_id.hex()
        if span.parent_span_id:
            span_data["parent_span_id_hex"] = span.parent_span_id.hex()

        # Include resource attributes for context
        if resource_spans.resource:
            span_data["resource"] = MessageToDict(
                resource_spans.resource, preserving_proto_field_name=True
            )

        # Include instrumentation scope
        if scope_spans.scope:
            span_data["instrumentation_scope"] = MessageToDict(
                scope_spans.scope, preserving_proto_field_name=True
            )

        return span_data
