from opentelemetry.proto.collector.logs.v1.logs_service_pb2_grpc import (
    LogsServiceServicer,
)

from .log_writer import LogWriter
from .otlp_requests import write_logs_request


class LogCollectorServicer(LogsServiceServicer):
    """Implements the OTLP LogsService gRPC interface."""

    def __init__(self, log_writer: LogWriter):
        self.log_writer = log_writer

    def Export(self, request, context):
        return write_logs_request(request, self.log_writer)
