"""KiCad connection status tool."""

from __future__ import annotations

from typing import Any

from kipy import KiCad
from kipy.errors import ApiError, ConnectionError, FutureVersionError

from kicad_minimal_mcp.app import SERVER_VERSION, mcp
from kicad_minimal_mcp.results import ToolResult
from kicad_minimal_mcp.tools.runner import run_tool


@mcp.tool()
def kicad_status() -> dict[str, Any]:
    """Report whether the KiCad IPC API is reachable and which version is running."""
    result = ToolResult(
        body={
            "server_version": SERVER_VERSION,
            "board_open": False,
            "board_name": None,
            "kicad_version": None,
            "api_version": None,
            "version_check_ok": None,
        }
    )

    def status(kicad: KiCad) -> None:
        version = kicad.get_version()
        result.connected = True
        result.body["kicad_version"] = version.full_version
        result.body["api_version"] = str(kicad.get_api_version())

        # The development bindings treat a connected KiCad newer than the API
        # version they were generated from as a FutureVersionError. Report it
        # without making connectivity depend on an exact patch match.
        try:
            result.body["version_check_ok"] = kicad.check_version()
        except FutureVersionError as exc:
            result.body["version_check_ok"] = False
            result.body["version_check_error"] = str(exc)

        try:
            board = kicad.get_board()
            result.body["board_open"] = True
            result.body["board_name"] = board.name
        except (ApiError, ConnectionError) as exc:
            result.body["board_error"] = str(exc)

    return run_tool(result, status)
