"""Minimal KiCad MCP server.

The server exposes connection, diagnostics, and open-document discovery tools.
Footprint and symbol authoring use the KiCad 11.0 IPC API only; see
``docs/kicad-11-ipc-review.md`` for the implemented surface and manual gaps.
"""

from __future__ import annotations

from kicad_minimal_mcp.app import SERVER_NAME, SERVER_VERSION, mcp
from kicad_minimal_mcp.tools.footprint_read import get_footprint_items
from kicad_minimal_mcp.tools.footprint_write import (
    delete_footprint_items,
    write_footprint_items,
)
from kicad_minimal_mcp.tools.open_documents import get_open_documents
from kicad_minimal_mcp.tools.status import kicad_status
from kicad_minimal_mcp.tools.symbol_read import get_symbol_items
from kicad_minimal_mcp.tools.symbol_write import (
    delete_symbol_items,
    write_symbol_items,
)

__all__ = [
    "SERVER_NAME",
    "SERVER_VERSION",
    "delete_footprint_items",
    "delete_symbol_items",
    "get_footprint_items",
    "get_open_documents",
    "get_symbol_items",
    "kicad_status",
    "main",
    "mcp",
    "write_footprint_items",
    "write_symbol_items",
]


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
