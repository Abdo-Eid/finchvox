from opentelemetry.proto.collector.trace.v1.trace_service_pb2_grpc import (
    TraceServiceServicer,
)

from .otlp_requests import write_trace_request
from .writer import SpanWriter


class TraceCollectorServicer(TraceServiceServicer):
    """Implements the OTLP TraceService gRPC interface."""

    def __init__(self, span_writer: SpanWriter):
        self.span_writer = span_writer

    def Export(self, request, context):
        return write_trace_request(request, self.span_writer)
