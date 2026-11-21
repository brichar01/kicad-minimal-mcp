"""Shared outcome envelope for MCP tool results."""

from __future__ import annotations

from typing import Any

STATUS_OK = "ok"
STATUS_INVALID_REQUEST = "invalid_request"
STATUS_KICAD_UNAVAILABLE = "kicad_unavailable"
STATUS_FOOTPRINT_UNAVAILABLE = "footprint_unavailable"
STATUS_SYMBOL_UNAVAILABLE = "symbol_unavailable"
STATUS_KICAD_ERROR = "kicad_error"
STATUS_ERROR = "error"


def complete_result(
    result: dict[str, Any],
    *,
    status: str = STATUS_OK,
    retryable: bool = False,
) -> dict[str, Any]:
    """Add the standard ``ok``/``status``/``retryable`` outcome fields.

    A result with no ``error`` is always successful, regardless of the status
    passed by the caller.
    """
    if result.get("error") is None:
        result["ok"] = True
        result["status"] = STATUS_OK
        result["retryable"] = False
    else:
        result["ok"] = False
        result["status"] = STATUS_ERROR if status == STATUS_OK else status
        result["retryable"] = retryable
    return result
