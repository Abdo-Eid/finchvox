from unittest.mock import Mock

import pytest

import finchvox.server as server_module
from finchvox.server import UnifiedServer


def test_unified_server_defaults_to_loopback(tmp_path):
    server = UnifiedServer(data_dir=tmp_path)
    assert server.host == "127.0.0.1"


@pytest.mark.asyncio
async def test_grpc_binds_to_configured_host(tmp_path, monkeypatch):
    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 4317

    monkeypatch.setattr(server_module.grpc, "server", lambda *args, **kwargs: grpc_server)
    monkeypatch.setattr(
        server_module, "add_TraceServiceServicer_to_server", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        server_module, "add_LogsServiceServicer_to_server", lambda *args, **kwargs: None
    )

    server = UnifiedServer(host="127.0.0.1", grpc_port=4317, data_dir=tmp_path)
    await server.start_grpc()

    grpc_server.add_insecure_port.assert_called_once_with("127.0.0.1:4317")
    grpc_server.start.assert_called_once_with()


@pytest.mark.asyncio
async def test_grpc_all_interfaces_is_explicit_opt_in(tmp_path, monkeypatch):
    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 4317

    monkeypatch.setattr(server_module.grpc, "server", lambda *args, **kwargs: grpc_server)
    monkeypatch.setattr(
        server_module, "add_TraceServiceServicer_to_server", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        server_module, "add_LogsServiceServicer_to_server", lambda *args, **kwargs: None
    )

    server = UnifiedServer(host="0.0.0.0", grpc_port=4317, data_dir=tmp_path)
    await server.start_grpc()

    grpc_server.add_insecure_port.assert_called_once_with("0.0.0.0:4317")
