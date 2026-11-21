"""Fixtures for fixture-backed KiCad MCP integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import pytest

from tests.test_harness.fake_kicad_socket import FakeKiCadSocket
from tests.test_harness.mcp_server import (
    McpServerHarness,
    mcp_server,
    mcp_server_without_kicad,
)
from tests.test_harness.record_ipc_fixture import Exchange, read_recording

RECORDINGS = Path(__file__).parent / "test_harness" / "ipc_recordings"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fake_kicad_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[..., FakeKiCadSocket]]:
    """Start fake KiCad sockets that replay recorded IPC exchanges."""
    servers: list[FakeKiCadSocket] = []

    def replay(
        *fixture_names: str,
        verify_requests: bool = True,
    ) -> FakeKiCadSocket:
        exchanges: list[Exchange] = []
        for fixture_name in fixture_names:
            path = RECORDINGS / fixture_name
            if not path.is_file():
                path = Path(fixture_name)
            exchanges.extend(read_recording(path))

        server = FakeKiCadSocket(
            exchanges,
            verify_requests=verify_requests,
        ).start()
        servers.append(server)
        monkeypatch.setenv("KICAD_API_SOCKET", server.socket_url)
        return server

    yield replay

    for server in reversed(servers):
        server.close()


@pytest.fixture
def mcp_integration(
    fake_kicad_socket: Callable[..., FakeKiCadSocket],
) -> Callable[..., AbstractAsyncContextManager[McpServerHarness]]:
    """Connect an MCP client to the server backed by a fake KiCad socket."""

    @asynccontextmanager
    async def connect(
        *fixture_names: str,
        verify_requests: bool = True,
    ) -> AsyncIterator[McpServerHarness]:
        socket = fake_kicad_socket(
            *fixture_names,
            verify_requests=verify_requests,
        )
        async with mcp_server(socket) as harness:
            yield harness

    return connect


@pytest.fixture
def mcp_no_kicad(
    tmp_path: Path,
) -> Callable[[], AbstractAsyncContextManager[McpServerHarness]]:
    """Connect an MCP client to a server with no KiCad IPC socket available."""

    @asynccontextmanager
    async def connect() -> AsyncIterator[McpServerHarness]:
        socket_url = f"ipc://{tmp_path / 'missing' / 'api.sock'}"
        async with mcp_server_without_kicad(socket_url) as harness:
            yield harness

    return connect
