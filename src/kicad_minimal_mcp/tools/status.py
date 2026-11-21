"""KiCad connection status tool."""

from __future__ import annotations

from typing import Any

from kipy.errors import ApiError, ConnectionError, FutureVersionError

from kicad_minimal_mcp.app import SERVER_VERSION, mcp
from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.results import (
    STATUS_ERROR,
    STATUS_KICAD_ERROR,
    STATUS_KICAD_UNAVAILABLE,
    complete_result,
)


@mcp.tool()
def kicad_status() -> dict[str, Any]:
    """Report whether the KiCad IPC API is reachable and which version is running.

    This never raises for an unavailable KiCad instance; inspect the ``connected``
    field in the result instead.
    """
    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "connected": False,
        "server_version": SERVER_VERSION,
        "board_open": False,
        "board_name": None,
        "kicad_version": None,
        "api_version": None,
        "version_check_ok": None,
        "error": None,
    }

    kicad = kicad_client()

    try:
        version = kicad.get_version()
        result["connected"] = True
        result["kicad_version"] = version.full_version
        result["api_version"] = str(kicad.get_api_version())

        # The development bindings treat a connected KiCad newer than the API
        # version they were generated from as a FutureVersionError. Report it
        # without making connectivity depend on an exact patch match.
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

    except ConnectionError as exc:
        result["error"] = str(exc)
        return complete_result(
            result,
            status=STATUS_KICAD_UNAVAILABLE,
            retryable=True,
        )
    except ApiError as exc:
        result["error"] = str(exc)
        return complete_result(result, status=STATUS_KICAD_ERROR)
    except Exception as exc:  # noqa: BLE001 - defensive at the MCP boundary
        result["error"] = f"{type(exc).__name__}: {exc}"
        return complete_result(result, status=STATUS_ERROR)

    return complete_result(result)
