"""Minimal KiCad MCP server.

At this stage the server only exposes a connection/diagnostics tool. Footprint
and library authoring will use the KiCad 11.0 IPC API only; see
``docs/kicad-11-ipc-review.md`` for the implemented surface and manual gaps.
"""

from __future__ import annotations

from typing import Any

from kipy import KiCad
from kipy.errors import ApiError, ConnectionError, FutureVersionError
from mcp.server.mcpserver import MCPServer

SERVER_NAME = "kicad-minimal-mcp"
SERVER_VERSION = "0.1.0"

mcp = MCPServer(
    SERVER_NAME,
    version=SERVER_VERSION,
    instructions=(
        "KiCad footprint authoring tools. The IPC backend requires a running "
        "KiCad 10 GUI with the API server enabled; library authoring is handled "
        "by the file-based backend."
    ),
)


@mcp.tool()
def kicad_status() -> dict[str, Any]:
    """Report whether the KiCad IPC API is reachable and which version is running.

    This never raises for an unavailable KiCad instance; inspect the ``connected``
    field in the result instead.
    """
    result: dict[str, Any] = {
        "connected": False,
        "server_version": SERVER_VERSION,
        "board_open": False,
        "board_name": None,
        "kicad_version": None,
        "api_version": None,
        "version_check_ok": None,
        "error": None,
    }

    kicad = KiCad(timeout_ms=2000)

    try:
        version = kicad.get_version()
        result["connected"] = True
        result["kicad_version"] = version.full_version
        result["api_version"] = str(kicad.get_api_version())

        # kicad-python 0.8.0 was built against 10.0.6 and treats a newer
        # connected version as a FutureVersionError. Report it without making
        # connectivity depend on an exact patch match.
        try:
            result["version_check_ok"] = kicad.check_version()
        except FutureVersionError as exc:
            result["version_check_ok"] = False
            result["version_check_error"] = str(exc)

        try:
            board = kicad.get_board()
            result["board_open"] = True
            result["board_name"] = board.name
        except (ApiError, ConnectionError) as exc:
            result["board_error"] = str(exc)

    except (ApiError, ConnectionError) as exc:
        result["error"] = str(exc)
    except Exception as exc:  # pragma: no cover - defensive at the MCP boundary
        result["error"] = f"{type(exc).__name__}: {exc}"

    return result


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
