"""Shared geometry conversions for board and symbol graphic shapes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from kipy.common_types import GraphicAttributes
from kipy.geometry import PolygonWithHoles
from kipy.proto.common.types.enums_pb2 import StrokeLineStyle

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.parsing import mapping, number, optional
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import PointMm, api_from_mm


class HasPolygons(Protocol):
    """The ``polygons`` view shared by the board and symbol polygon shapes."""

    @property
    def polygons(self) -> Sequence[PolygonWithHoles]: ...


@dataclass(frozen=True)
class StrokeSpec:
    width_mm: float | None = None
    style: StrokeLineStyle.ValueType | None = None

    @classmethod
    def parse(cls, data: object, name: str = "stroke") -> StrokeSpec:
        values = mapping(data, name)

        return cls(
            width_mm=optional(values, "width_mm", number, name),
            style=optional(values, "style", enum_converter(StrokeLineStyle), name),
        )


@dataclass(frozen=True, kw_only=True)
class GraphicAppearance:
    """The stroke and fill shared by every writable graphic shape."""

    stroke: StrokeSpec | None = None
    filled: bool | None = None

    def apply(self, attributes: GraphicAttributes) -> None:
        if self.stroke is not None:
            if self.stroke.width_mm is not None:
                attributes.stroke.width = api_from_mm(self.stroke.width_mm)
            if self.stroke.style is not None:
                attributes.stroke.style = self.stroke.style

        if self.filled is not None:
            attributes.fill.filled = self.filled


def polygon_geometry_to_dict(shape: HasPolygons) -> list[Payload]:
    """Convert a shape's ``polygons`` view to outlines, holes, and closed flags."""
    polygons: list[Payload] = []

    for polygon in shape.polygons:
        outline: list[Payload] = []
        for node in polygon.outline.nodes:
            if node.has_point:
                outline.append(PointMm.from_vector(node.point).to_payload())
                continue

            outline.append(
                {
                    "arc": {
                        "start": PointMm.from_vector(node.arc.start).to_payload(),
                        "mid": PointMm.from_vector(node.arc.mid).to_payload(),
                        "end": PointMm.from_vector(node.arc.end).to_payload(),
                    }
                }
            )

        holes = [
            [
                PointMm.from_vector(node.point).to_payload()
                for node in hole.nodes
                if node.has_point
            ]
            for hole in polygon.holes
        ]

        polygons.append(
            {"outline": outline, "closed": polygon.outline.closed, "holes": holes}
        )

    return polygons
