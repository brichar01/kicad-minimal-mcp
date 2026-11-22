"""Shared envelope and error mapping for the MCP tools.

Every tool builds the same result envelope, resolves the open document the same
way, and maps the same exception types onto the same status codes. That
mechanical work lives here so each tool body carries only its own logic.
"""

from __future__ import annotations

from collections.abc import Callable

from kipy import KiCad
from kipy.errors import ApiError, ConnectionError
from kipy.proto.common import ApiStatusCode
from kipy.proto.common.types import DocumentSpecifier

from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.identifiers import LibraryId
from kicad_minimal_mcp.results import Payload, Status, ToolResult


class ToolError(Exception):
    """A tool outcome reported through the result envelope instead of raised."""

    def __init__(
        self,
        message: str,
        *,
        status: Status,
        retryable: bool = False,
        connected: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.connected = connected


def run_tool(result: ToolResult, body: Callable[[KiCad], None]) -> Payload:
    """Run ``body`` against a fresh client and complete ``result``.

    ``body`` records its output on ``result``. Whatever it raises is mapped onto
    the shared status codes here, so an unavailable KiCad instance, a rejected
    request, and an API failure never escape as exceptions at the MCP boundary.
    """
    kicad = kicad_client()

    try:
        body(kicad)
    except ToolError as exc:
        result.fail(
            str(exc),
            status=exc.status,
            retryable=exc.retryable,
            connected=exc.connected,
        )
    except ValueError as exc:
        result.fail(str(exc), status=Status.INVALID_REQUEST)
    except ConnectionError as exc:
        result.fail(str(exc), status=Status.KICAD_UNAVAILABLE, retryable=True)
    except ApiError as exc:
        result.fail(str(exc), status=Status.KICAD_ERROR)
    except Exception as exc:  # noqa: BLE001 - defensive at the MCP boundary
        result.fail(f"{type(exc).__name__}: {exc}", status=Status.ERROR)

    return result.to_payload()


def requested_library_id(lib_id: str | None) -> LibraryId | None:
    """Parse the optional ``lib_id`` tool argument."""
    if lib_id is None:
        return None

    return LibraryId.parse(lib_id)


def open_document(
    kicad: KiCad,
    finder: Callable[[KiCad, LibraryId | None], DocumentSpecifier],
    lib_id: LibraryId | None,
    *,
    noun: str,
    unavailable_status: Status,
) -> DocumentSpecifier:
    """Return the open document ``finder`` selects, or raise a ``ToolError``.

    A missing or ambiguous document is reported as ``unavailable_status`` and is
    retryable: opening the right editor is a step the caller can take. KiCad
    answering ``AS_UNHANDLED`` still proves the connection works, so that path
    marks the result connected.
    """
    try:
        return finder(kicad, lib_id)
    except ValueError as exc:
        raise ToolError(str(exc), status=unavailable_status, retryable=True) from exc
    except ApiError as exc:
        if exc.code != ApiStatusCode.AS_UNHANDLED:
            raise

        raise ToolError(
            f"no {noun} editor is open in KiCad",
            status=unavailable_status,
            retryable=True,
            connected=True,
        ) from exc
