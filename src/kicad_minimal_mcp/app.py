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
        "backend. "
        "Tool calls never raise for an unavailable KiCad instance; inspect the "
        "`connected` field in the result instead. Type filters accept canonical "
        "names, their plurals, and the `KOT_*` and `DOCTYPE_*` enum spellings. "
        "Edits are grouped into one commit and saved to the library entry unless "
        "`save` is false, and are transactional at the commit level: if "
        "validation or any IPC command fails before the commit is pushed, the "
        "pending commit is dropped. A write with `replace_existing` removes all "
        "existing non-field items first."
    ),
)
