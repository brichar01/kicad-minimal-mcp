"""KiCad IPC connection helpers."""

from __future__ import annotations

from kipy import KiCad

DEFAULT_TIMEOUT_MS = 2000


def kicad_client() -> KiCad:
    """Create a lazily connected KiCad client with the server's timeout."""
    return KiCad(timeout_ms=DEFAULT_TIMEOUT_MS)
