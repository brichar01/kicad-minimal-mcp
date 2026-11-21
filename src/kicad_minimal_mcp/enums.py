"""Helpers for accepting protobuf enum names or numeric values."""

from __future__ import annotations

from typing import Any


def enum_value(enum_type: Any, value: Any) -> Any:
    """Return a numeric enum value from a name, or pass an integer through."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return enum_type.Value(value)
    raise ValueError(f"expected an enum name or value, got {value!r}")
