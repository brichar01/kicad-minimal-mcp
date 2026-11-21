"""Run the MCP server against a fake KiCad socket and call its tools."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from tests.test_harness.fake_kicad_socket import FakeKiCadSocket

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class McpServerHarness:
    """A connected MCP client plus the optional fake KiCad socket it uses."""

    socket: FakeKiCadSocket | None
    client: Client

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call an MCP tool and return its structured result."""
        result = await self.client.call_tool(name, arguments)

        if result.is_error:
            raise AssertionError(f"MCP tool {name!r} returned an error result")

        if not isinstance(result.structured_content, dict):
            raise AssertionError(  # noqa: TRY004 - this is a test assertion
                f"MCP tool {name!r} did not return a structured object"
            )

        return result.structured_content

    def assert_complete(self) -> None:
        """Assert that the fake KiCad socket consumed the recording cleanly."""
        if self.socket is not None:
            self.socket.assert_complete()


@asynccontextmanager
async def _mcp_server(
    socket_url: str,
    socket: FakeKiCadSocket | None,
) -> AsyncIterator[McpServerHarness]:
    """Start the MCP server over stdio with the supplied KiCad socket URL."""
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from kicad_minimal_mcp import main; main()"],
        env={"KICAD_API_SOCKET": socket_url},
        cwd=PROJECT_ROOT,
    )

    async with Client(parameters) as client:
        yield McpServerHarness(socket=socket, client=client)


@asynccontextmanager
async def mcp_server(
    socket: FakeKiCadSocket,
) -> AsyncIterator[McpServerHarness]:
    """Start the MCP server connected to a fake KiCad socket."""
    async with _mcp_server(socket.socket_url, socket) as harness:
        yield harness


@asynccontextmanager
async def mcp_server_without_kicad(
    socket_url: str,
) -> AsyncIterator[McpServerHarness]:
    """Start the MCP server pointed at a KiCad socket that does not exist."""
    async with _mcp_server(socket_url, None) as harness:
        yield harness
