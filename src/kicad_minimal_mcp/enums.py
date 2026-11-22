"""Helpers for accepting protobuf enum names or numeric values."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class ProtobufEnum[ValueT](Protocol):
    """The surface the generated protobuf enum wrappers expose."""

    def Name(self, number: ValueT) -> str: ...

    def Value(self, name: str) -> ValueT: ...


def enum_value[ValueT](
    enum_type: ProtobufEnum[ValueT],
    value: object,
    name: str,
) -> ValueT:
    """Return the enum value ``value`` names, or pass an integer through."""
    if isinstance(value, str):
        try:
            return enum_type.Value(value)
        except ValueError:
            raise ValueError(
                f"{name} is not a valid enum name or value: {value!r}"
            ) from None

    if isinstance(value, int) and not isinstance(value, bool):
        return cast("ValueT", value)

    raise ValueError(f"{name} must be an enum name or value")


def enum_converter[ValueT](
    enum_type: ProtobufEnum[ValueT],
) -> Callable[[object, str], ValueT]:
    """Return a boundary parser accepting an enum name or a numeric value."""

    def convert(value: object, name: str) -> ValueT:
        return enum_value(enum_type, value, name)

    return convert
