"""Shared outcome envelope for MCP tool results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

Payload = dict[str, Any]
"""The presentation body of a tool result, serialised as JSON for the client."""


class Status(StrEnum):
    """The outcome codes the tools report."""

    ERROR = "error"
    FOOTPRINT_UNAVAILABLE = "footprint_unavailable"
    INVALID_REQUEST = "invalid_request"
    KICAD_ERROR = "kicad_error"
    KICAD_UNAVAILABLE = "kicad_unavailable"
    OK = "ok"
    SYMBOL_UNAVAILABLE = "symbol_unavailable"


@dataclass
class ToolResult:
    """The outcome of one tool call and the body the tool returns."""

    body: Payload
    status: Status = Status.OK
    retryable: bool = False
    error: str | None = None
    connected: bool = False

    def fail(
        self,
        message: str,
        *,
        status: Status,
        retryable: bool = False,
        connected: bool | None = None,
    ) -> None:
        """Record a failed outcome, leaving ``connected`` alone when unspecified."""
        self.error = message
        self.status = status
        self.retryable = retryable

        if connected is not None:
            self.connected = connected

    def to_payload(self) -> Payload:
        """Return the envelope with the standard outcome fields."""
        if self.error is None:
            return {
                "ok": True,
                "status": str(Status.OK),
                "retryable": False,
                "connected": self.connected,
                **self.body,
                "error": None,
            }

        status = Status.ERROR if self.status is Status.OK else self.status

        return {
            "ok": False,
            "status": str(status),
            "retryable": self.retryable,
            "connected": self.connected,
            **self.body,
            "error": self.error,
        }
