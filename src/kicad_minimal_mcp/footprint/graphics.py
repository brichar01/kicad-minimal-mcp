"""Read/write conversions for footprint graphic shapes."""

from __future__ import annotations

from typing import Any

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

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.geometry import polygon_geometry_to_dict
from kicad_minimal_mcp.units import (
    millimetres_from_mm,
    mm,
    point_from_dict,
    point_to_dict,
    size_to_dict,
)


def graphic_base_to_dict(item: BoardShape) -> dict[str, Any]:
    attributes = item.attributes
    return {
        "type": "graphic",
        "id": item.id.value,
        "layer": BoardLayer.Name(item.layer),
        "stroke": {
            "width_mm": mm(attributes.stroke.width),
            "style": StrokeLineStyle.Name(attributes.stroke.style),
        },
        "filled": attributes.fill.filled,
    }


def graphic_to_dict(item: BoardShape) -> dict[str, Any]:
    result = graphic_base_to_dict(item)

    if isinstance(item, BoardSegment):
        result["shape"] = "segment"
        result["start"] = point_to_dict(item.start)
        result["end"] = point_to_dict(item.end)
    elif isinstance(item, BoardArc):
        result["shape"] = "arc"
        result["start"] = point_to_dict(item.start)
        result["mid"] = point_to_dict(item.mid)
        result["end"] = point_to_dict(item.end)
    elif isinstance(item, BoardCircle):
        result["shape"] = "circle"
        result["center"] = point_to_dict(item.center)
        result["radius_mm"] = mm(item.radius())
    elif isinstance(item, BoardRectangle):
        result["shape"] = "rectangle"
        result["top_left"] = point_to_dict(item.top_left)
        result["bottom_right"] = point_to_dict(item.bottom_right)
        result["size"] = size_to_dict(item.bottom_right - item.top_left)
    elif isinstance(item, BoardPolygon):
        result["shape"] = "polygon"
        result["polygons"] = polygon_geometry_to_dict(item)
    elif isinstance(item, BoardBezier):
        result["shape"] = "bezier"
        result["start"] = point_to_dict(item.start)
        result["control1"] = point_to_dict(item.control1)
        result["control2"] = point_to_dict(item.control2)
        result["end"] = point_to_dict(item.end)
    else:
        result["shape"] = "unknown"

    return result


def apply_graphic_attributes(item: BoardShape, spec: dict[str, Any]) -> None:
    attributes = item.attributes
    stroke = spec.get("stroke", {})
    if "width_mm" in stroke:
        attributes.stroke.width = millimetres_from_mm(stroke["width_mm"])
    if "style" in stroke:
        attributes.stroke.style = enum_value(StrokeLineStyle, stroke["style"])
    if "filled" in spec:
        attributes.fill.filled = bool(spec["filled"])


def graphic_from_spec(spec: dict[str, Any]) -> BoardShape:
    shape = str(spec.get("shape", "")).lower()
    shape_classes = {
        "segment": BoardSegment,
        "arc": BoardArc,
        "circle": BoardCircle,
        "rectangle": BoardRectangle,
        "bezier": BoardBezier,
    }
    shape_class = shape_classes.get(shape)
    if shape_class is None:
        raise ValueError(f"unsupported graphic shape {shape!r}")

    item = shape_class()
    item.layer = enum_value(BoardLayer, spec["layer"])
    apply_graphic_attributes(item, spec)

    if shape == "segment":
        item.start = point_from_dict(spec["start"])
        item.end = point_from_dict(spec["end"])
    elif shape == "arc":
        item.start = point_from_dict(spec["start"])
        item.mid = point_from_dict(spec["mid"])
        item.end = point_from_dict(spec["end"])
    elif shape == "circle":
        item.center = point_from_dict(spec["center"])
        item.radius_point = item.center + Vector2.from_xy_mm(
            float(spec["radius_mm"]), 0.0
        )
    elif shape == "rectangle":
        item.top_left = point_from_dict(spec["top_left"])
        item.bottom_right = point_from_dict(spec["bottom_right"])
    elif shape == "bezier":
        item.start = point_from_dict(spec["start"])
        item.control1 = point_from_dict(spec["control1"])
        item.control2 = point_from_dict(spec["control2"])
        item.end = point_from_dict(spec["end"])

    return item
