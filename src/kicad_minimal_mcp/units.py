"""Millimetre and KiCad geometry conversions.

The IPC API carries positions, sizes, and radii as integer nanometres. Every
conversion in this package goes through the helpers below, so readers and
writers share one rounding rule and one coordinate representation.
"""

from __future__ import annotations

from dataclasses import dataclass

from kipy.geometry import Vector2
from kipy.util.units import from_mm, to_mm

from kicad_minimal_mcp.parsing import converted, mapping, number
from kicad_minimal_mcp.results import Payload


def mm_from_api(value: float) -> float:
    """Convert API nanometres to millimetres, rounded for display."""
    return round(to_mm(int(value)), 6)


def api_from_mm(value: float) -> int:
    return from_mm(float(value))


@dataclass(frozen=True)
class PointMm:
    x_mm: float
    y_mm: float

    @classmethod
    def from_vector(cls, point: Vector2) -> PointMm:
        return cls(x_mm=mm_from_api(point.x), y_mm=mm_from_api(point.y))

    @classmethod
    def parse(cls, data: object, name: str = "position") -> PointMm:
        values = mapping(data, name)

        return cls(
            x_mm=converted(values, "x_mm", number, name),
            y_mm=converted(values, "y_mm", number, name),
        )

    def to_vector(self) -> Vector2:
        return Vector2.from_xy_mm(self.x_mm, self.y_mm)

    def to_payload(self) -> Payload:
        return {"x_mm": self.x_mm, "y_mm": self.y_mm}


@dataclass(frozen=True)
class SizeMm:
    width_mm: float
    height_mm: float

    @classmethod
    def from_vector(cls, size: Vector2) -> SizeMm:
        """Convert an API size vector, reporting both dimensions as positive."""
        return cls(
            width_mm=mm_from_api(abs(size.x)), height_mm=mm_from_api(abs(size.y))
        )

    @classmethod
    def parse(cls, data: object, name: str = "size") -> SizeMm:
        values = mapping(data, name)

        return cls(
            width_mm=converted(values, "width_mm", number, name),
            height_mm=converted(values, "height_mm", number, name),
        )

    def to_vector(self) -> Vector2:
        return Vector2.from_xy_mm(self.width_mm, self.height_mm)

    def to_payload(self) -> Payload:
        return {"width_mm": self.width_mm, "height_mm": self.height_mm}
