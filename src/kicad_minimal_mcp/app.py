"""MCP application instance and server metadata."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

SERVER_NAME = "kicad-minimal-mcp"
SERVER_VERSION = "0.1.0"

mcp = MCPServer(
    SERVER_NAME,
    version=SERVER_VERSION,
    instructions=(
        "KiCad footprint and symbol authoring tools over the KiCad 11.0 IPC API. "
        "The backend requires a running KiCad 11 GUI with the IPC API server "
        "enabled, or a headless `kicad-cli api-server`. There is no file-based "
        "backend."
    ),
)
