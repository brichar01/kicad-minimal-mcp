# ruff: noqa: TRY004 - malformed tool arguments are invalid requests, not bugs.
"""Validation helpers for the JSON payloads the MCP tools accept.

The MCP boundary is the one place where values arrive untyped. Every tool parses
its arguments into the dataclasses this package uses internally as soon as it
receives them, and these helpers do the mechanical part of that: checking the
JSON shape and naming the offending field in the error message.

Malformed arguments are rejected with ``ValueError``, which the tool runner maps
to the ``invalid_request`` status.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence


def mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a JSON object")

    return value


def sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be an array")

    return value


def required(values: Mapping[str, object], key: str, name: str) -> object:
    """Return ``values[key]``, or raise a ``ValueError`` naming ``name``."""
    if values.get(key) is None:
        raise ValueError(f"{name} requires {key}")

    return values[key]


def converted[T](
    values: Mapping[str, object],
    key: str,
    convert: Callable[[object, str], T],
    name: str,
) -> T:
    """Return ``values[key]`` converted, or raise a ``ValueError`` when absent."""
    return convert(required(values, key, name), f"{name}.{key}")


def optional[T](
    values: Mapping[str, object],
    key: str,
    convert: Callable[[object, str], T],
    name: str,
) -> T | None:
    """Return ``values[key]`` converted, or ``None`` when it is absent."""
    value = values.get(key)
    if value is None:
        return None

    return convert(value, f"{name}.{key}")


def converted_list[T](
    values: Mapping[str, object],
    key: str,
    convert: Callable[[object, str], T],
    name: str,
) -> list[T]:
    """Return ``values[key]`` converted element by element, empty when absent."""
    value = values.get(key)
    if value is None:
        return []

    name = f"{name}.{key}"

    return [convert(item, f"{name}[]") for item in sequence(value, name)]


def text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")

    return value


def boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")

    return value


def number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a number")

    return float(value)


def integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")

    return value
