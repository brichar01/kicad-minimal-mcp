"""Millimetre and KiCad geometry conversions."""

from __future__ import annotations

from typing import Any

from kipy.geometry import Vector2
from kipy.util.units import from_mm, to_mm


def mm(value: float) -> float:
    """Convert API nanometres to millimetres, rounded for display."""
    return round(to_mm(int(value)), 6)


def point_to_dict(point: Any) -> dict[str, float]:
    """Convert a KiCad point or vector to millimetres."""
    return {"x_mm": mm(point.x), "y_mm": mm(point.y)}


def size_to_dict(size: Any) -> dict[str, float]:
    """Convert a KiCad size vector to positive millimetre dimensions."""
    return {"width_mm": mm(abs(size.x)), "height_mm": mm(abs(size.y))}


def point_from_dict(point: dict[str, Any]) -> Vector2:
    """Convert an ``x_mm``/``y_mm`` mapping to a KiCad point."""
    return Vector2.from_xy_mm(float(point["x_mm"]), float(point["y_mm"]))


def size_from_dict(size: dict[str, Any]) -> Vector2:
    """Convert a ``width_mm``/``height_mm`` mapping to a KiCad size vector."""
    return Vector2.from_xy_mm(float(size["width_mm"]), float(size["height_mm"]))


def millimetres_from_mm(value: Any) -> int:
    """Convert millimetres to API nanometres."""
    return from_mm(float(value))
