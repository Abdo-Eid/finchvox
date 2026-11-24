"""Write OpenTelemetry export requests, whichever transport (gRPC or HTTP) carried them."""

from collections.abc import Callable

from loguru import logger
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from .log_writer import LogWriter
from .writer import SpanWriter


def _stored(write: Callable[..., bool], *args) -> bool:
    try:
        return write(*args)
    except Exception as e:  # noqa: BLE001 - isolate unexpected failures to one record
        logger.exception(f"Unexpected error writing telemetry record: {e}")
        return False


def write_trace_request(
    request: ExportTraceServiceRequest, span_writer: SpanWriter
) -> ExportTraceServiceResponse:
    stored = rejected = 0
    for resource_spans in request.resource_spans:
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                if _stored(span_writer.write_span, span, resource_spans, scope_spans):
                    stored += 1
                else:
                    rejected += 1
    logger.info(f"Stored {stored} spans; rejected {rejected}")
    response = ExportTraceServiceResponse()
    if rejected:
        response.partial_success.rejected_spans = rejected
        response.partial_success.error_message = "Could not store spans; see Finchvox server logs."
    return response


def write_logs_request(
    request: ExportLogsServiceRequest,
    log_writer: LogWriter,
    fallback: Callable[..., bool] | None = None,
) -> ExportLogsServiceResponse:
    stored = rejected = 0
    for resource_logs in request.resource_logs:
        for scope_logs in resource_logs.scope_logs:
            for log_record in scope_logs.log_records:
                write = log_writer.write_log
                if fallback is not None and log_record.trace_id in (b"", b"\0" * 16):
                    write = fallback
                if _stored(write, log_record, resource_logs, scope_logs):
                    stored += 1
                else:
                    rejected += 1
    logger.info(f"Stored {stored} log records; rejected {rejected}")
    response = ExportLogsServiceResponse()
    if rejected:
        response.partial_success.rejected_log_records = rejected
        response.partial_success.error_message = (
            "Some logs could not be matched to a trace or saved; see Finchvox server logs."
        )
    return response
