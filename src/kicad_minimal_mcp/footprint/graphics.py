"""Read/write conversions for footprint graphic shapes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from kipy.board_types import (
    BoardArc,
    BoardBezier,
    BoardCircle,
    BoardPolygon,
    BoardRectangle,
    BoardSegment,
    BoardShape,
)
from kipy.geometry import Vector2
from kipy.proto.board.board_types_pb2 import BoardLayer
from kipy.proto.common.types.enums_pb2 import StrokeLineStyle

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.geometry import (
    GraphicAppearance,
    StrokeSpec,
    polygon_geometry_to_dict,
)
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    boolean,
    converted,
    mapping,
    number,
    optional,
    text,
)
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import PointMm, SizeMm, mm_from_api


@dataclass(frozen=True)
class SegmentShape:
    start: PointMm
    end: PointMm


@dataclass(frozen=True)
class ArcShape:
    start: PointMm
    mid: PointMm
    end: PointMm


@dataclass(frozen=True)
class CircleShape:
    center: PointMm
    radius_mm: float


@dataclass(frozen=True)
class RectangleShape:
    top_left: PointMm
    bottom_right: PointMm


@dataclass(frozen=True)
class BezierShape:
    start: PointMm
    control1: PointMm
    control2: PointMm
    end: PointMm


#: The shapes a footprint graphic can draw.
FootprintShape = SegmentShape | ArcShape | CircleShape | RectangleShape | BezierShape


@dataclass(frozen=True)
class GraphicSpec(GraphicAppearance):
    layer: BoardLayer.ValueType
    shape: FootprintShape
    id: ItemId | None = None

    @classmethod
    def parse(cls, data: object, name: str = "graphic") -> GraphicSpec:
        values = mapping(data, name)

        return cls(
            layer=converted(values, "layer", enum_converter(BoardLayer), name),
            shape=_parse_shape(values, name),
            stroke=optional(values, "stroke", StrokeSpec.parse, name),
            filled=optional(values, "filled", boolean, name),
            id=optional(values, "id", text, name),
        )


def _parse_shape(values: Mapping[str, object], name: str) -> FootprintShape:
    shape = converted(values, "shape", text, name)

    match shape.lower():
        case "segment":
            return SegmentShape(
                start=converted(values, "start", PointMm.parse, name),
                end=converted(values, "end", PointMm.parse, name),
            )
        case "arc":
            return ArcShape(
                start=converted(values, "start", PointMm.parse, name),
                mid=converted(values, "mid", PointMm.parse, name),
                end=converted(values, "end", PointMm.parse, name),
            )
        case "circle":
            return CircleShape(
                center=converted(values, "center", PointMm.parse, name),
                radius_mm=converted(values, "radius_mm", number, name),
            )
        case "rectangle":
            return RectangleShape(
                top_left=converted(values, "top_left", PointMm.parse, name),
                bottom_right=converted(values, "bottom_right", PointMm.parse, name),
            )
        case "bezier":
            return BezierShape(
                start=converted(values, "start", PointMm.parse, name),
                control1=converted(values, "control1", PointMm.parse, name),
                control2=converted(values, "control2", PointMm.parse, name),
                end=converted(values, "end", PointMm.parse, name),
            )

    raise ValueError(f"unsupported graphic shape {shape!r}")


def graphic_base_to_dict(item: BoardShape) -> Payload:
    attributes = item.attributes

    return {
        "type": "graphic",
        "id": item.id.value,
        "layer": BoardLayer.Name(item.layer),
        "stroke": {
            "width_mm": mm_from_api(attributes.stroke.width),
            "style": StrokeLineStyle.Name(attributes.stroke.style),
        },
        "filled": attributes.fill.filled,
    }


def graphic_to_dict(item: BoardShape) -> Payload:
    result = graphic_base_to_dict(item)

    if isinstance(item, BoardSegment):
        result["shape"] = "segment"
        result["start"] = PointMm.from_vector(item.start).to_payload()
        result["end"] = PointMm.from_vector(item.end).to_payload()
    elif isinstance(item, BoardArc):
        result["shape"] = "arc"
        result["start"] = PointMm.from_vector(item.start).to_payload()
        result["mid"] = PointMm.from_vector(item.mid).to_payload()
        result["end"] = PointMm.from_vector(item.end).to_payload()
    elif isinstance(item, BoardCircle):
        result["shape"] = "circle"
        result["center"] = PointMm.from_vector(item.center).to_payload()
        result["radius_mm"] = mm_from_api(item.radius())
    elif isinstance(item, BoardRectangle):
        result["shape"] = "rectangle"
        result["top_left"] = PointMm.from_vector(item.top_left).to_payload()
        result["bottom_right"] = PointMm.from_vector(item.bottom_right).to_payload()
        result["size"] = SizeMm.from_vector(
            item.bottom_right - item.top_left
        ).to_payload()
    elif isinstance(item, BoardPolygon):
        result["shape"] = "polygon"
        result["polygons"] = polygon_geometry_to_dict(item)
    elif isinstance(item, BoardBezier):
        result["shape"] = "bezier"
        result["start"] = PointMm.from_vector(item.start).to_payload()
        result["control1"] = PointMm.from_vector(item.control1).to_payload()
        result["control2"] = PointMm.from_vector(item.control2).to_payload()
        result["end"] = PointMm.from_vector(item.end).to_payload()
    else:
        result["shape"] = "unknown"

    return result


def graphic_from_spec(spec: GraphicSpec) -> BoardShape:
    item = _board_shape(spec.shape)
    item.layer = spec.layer
    spec.apply(item.attributes)

    return item


def _board_shape(shape: FootprintShape) -> BoardShape:
    match shape:
        case SegmentShape():
            item = BoardSegment()
            item.start = shape.start.to_vector()
            item.end = shape.end.to_vector()
            return item
        case ArcShape():
            item = BoardArc()
            item.start = shape.start.to_vector()
            item.mid = shape.mid.to_vector()
            item.end = shape.end.to_vector()
            return item
        case CircleShape():
            item = BoardCircle()
            item.center = shape.center.to_vector()
            item.radius_point = item.center + Vector2.from_xy_mm(shape.radius_mm, 0.0)
            return item
        case RectangleShape():
            item = BoardRectangle()
            item.top_left = shape.top_left.to_vector()
            item.bottom_right = shape.bottom_right.to_vector()
            return item
        case BezierShape():
            item = BoardBezier()
            item.start = shape.start.to_vector()
            item.control1 = shape.control1.to_vector()
            item.control2 = shape.control2.to_vector()
            item.end = shape.end.to_vector()
            return item

    raise ValueError("unsupported footprint graphic shape")
