"""Read conversions for symbol graphic shapes."""

from __future__ import annotations

from typing import Any

from kipy.common_types import (
    Arc,
    Bezier,
    Circle,
    Ellipse,
    EllipseArc,
    Polygon,
    Rectangle,
    Segment,
)
from kipy.geometry import (
    Angle,
    ArcStartMidEnd,
    PolygonWithHoles,
    PolyLine,
    PolyLineNode,
    Vector2,
)
from kipy.proto.common.types.enums_pb2 import StrokeLineStyle
from kipy.schematic_types import SchematicGraphicShape

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.geometry import polygon_geometry_to_dict
from kicad_minimal_mcp.units import (
    millimetres_from_mm,
    mm,
    point_from_dict,
    point_to_dict,
    size_to_dict,
)


def _graphic_base_to_dict(item: SchematicGraphicShape) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": "graphic",
        "id": item.id.value,
        "shape": "unknown",
        "stroke": None,
        "filled": None,
    }

    shape = item.shape
    if shape is None:
        return result

    attributes = shape.attributes
    result["stroke"] = {
        "width_mm": mm(attributes.stroke.width),
        "style": StrokeLineStyle.Name(attributes.stroke.style),
    }
    result["filled"] = attributes.fill.filled
    return result


def graphic_to_dict(item: SchematicGraphicShape) -> dict[str, Any]:
    """Convert a symbol graphic shape to the MCP-facing dictionary shape."""
    result = _graphic_base_to_dict(item)
    shape = item.shape

    if isinstance(shape, Segment):
        result["shape"] = "segment"
        result["start"] = point_to_dict(shape.start)
        result["end"] = point_to_dict(shape.end)
    elif isinstance(shape, Arc):
        result["shape"] = "arc"
        result["start"] = point_to_dict(shape.start)
        result["mid"] = point_to_dict(shape.mid)
        result["end"] = point_to_dict(shape.end)
    elif isinstance(shape, Circle):
        result["shape"] = "circle"
        result["center"] = point_to_dict(shape.center)
        result["radius_mm"] = mm(shape.radius())
    elif isinstance(shape, Rectangle):
        result["shape"] = "rectangle"
        result["top_left"] = point_to_dict(shape.top_left)
        result["bottom_right"] = point_to_dict(shape.bottom_right)
        result["size"] = size_to_dict(shape.bottom_right - shape.top_left)
    elif isinstance(shape, Polygon):
        result["shape"] = "polygon"
        result["polygons"] = polygon_geometry_to_dict(shape)
    elif isinstance(shape, Bezier):
        result["shape"] = "bezier"
        result["start"] = point_to_dict(shape.start)
        result["control1"] = point_to_dict(shape.control1)
        result["control2"] = point_to_dict(shape.control2)
        result["end"] = point_to_dict(shape.end)
    elif isinstance(shape, EllipseArc):
        result["shape"] = "ellipse_arc"
        result["center"] = point_to_dict(shape.center)
        result["major_radius_mm"] = mm(shape.major_radius)
        result["minor_radius_mm"] = mm(shape.minor_radius)
        result["rotation_degrees"] = shape.rotation.degrees
        result["start_angle_degrees"] = shape.start_angle.degrees
        result["end_angle_degrees"] = shape.end_angle.degrees
    elif isinstance(shape, Ellipse):
        result["shape"] = "ellipse"
        result["center"] = point_to_dict(shape.center)
        result["major_radius_mm"] = mm(shape.major_radius)
        result["minor_radius_mm"] = mm(shape.minor_radius)
        result["rotation_degrees"] = shape.rotation.degrees

    return result


def apply_graphic_attributes(shape: Any, spec: dict[str, Any]) -> None:
    """Apply stroke and fill properties from an item specification."""
    stroke = spec.get("stroke") or {}
    if "width_mm" in stroke:
        shape.attributes.stroke.width = millimetres_from_mm(stroke["width_mm"])
    if "style" in stroke:
        shape.attributes.stroke.style = enum_value(StrokeLineStyle, stroke["style"])
    if "filled" in spec:
        shape.attributes.fill.filled = bool(spec["filled"])


def _polyline_from_dict(data: dict[str, Any]) -> PolyLine:
    line = PolyLine()
    line.closed = bool(data.get("closed", False))

    for node_spec in data.get("outline", []):
        if "arc" in node_spec:
            arc_spec = node_spec["arc"]
            arc = ArcStartMidEnd()
            arc.start = point_from_dict(arc_spec["start"])
            arc.mid = point_from_dict(arc_spec["mid"])
            arc.end = point_from_dict(arc_spec["end"])
            node = PolyLineNode()
            node.arc = arc
        else:
            node = PolyLineNode.from_point(point_from_dict(node_spec))

        line.append(node)

    return line


def _polygon_from_dict(data: dict[str, Any]) -> PolygonWithHoles:
    polygon = PolygonWithHoles(auto_close=False)
    polygon.outline = _polyline_from_dict(data)

    for hole in data.get("holes", []):
        polygon.holes.append(_polyline_from_dict({"outline": hole, "closed": True}))

    return polygon


def graphic_from_spec(spec: dict[str, Any]) -> SchematicGraphicShape:
    """Create a symbol graphic shape from the MCP-facing item shape."""
    shape_name = str(spec.get("shape", "")).lower()
    item = SchematicGraphicShape()

    if shape_name == "segment":
        raise ValueError(
            "symbol graphics do not support segments; use a polygon with two points"
        )
    if shape_name == "arc":
        shape: Any = Arc()
        shape.start = point_from_dict(spec["start"])
        shape.mid = point_from_dict(spec["mid"])
        shape.end = point_from_dict(spec["end"])
    elif shape_name == "circle":
        shape = Circle()
        shape.center = point_from_dict(spec["center"])
        shape.radius_point = shape.center + Vector2.from_xy_mm(
            float(spec["radius_mm"]), 0.0
        )
    elif shape_name == "rectangle":
        shape = Rectangle()
        shape.top_left = point_from_dict(spec["top_left"])
        shape.bottom_right = point_from_dict(spec["bottom_right"])
    elif shape_name == "bezier":
        shape = Bezier()
        shape.start = point_from_dict(spec["start"])
        shape.control1 = point_from_dict(spec["control1"])
        shape.control2 = point_from_dict(spec["control2"])
        shape.end = point_from_dict(spec["end"])
    elif shape_name == "polygon":
        shape = Polygon()
        for polygon_spec in spec.get("polygons", []):
            shape.polygons.append(_polygon_from_dict(polygon_spec))
    elif shape_name == "ellipse":
        shape = Ellipse()
        shape.center = point_from_dict(spec["center"])
        shape.major_radius = millimetres_from_mm(spec["major_radius_mm"])
        shape.minor_radius = millimetres_from_mm(spec["minor_radius_mm"])
        if "rotation_degrees" in spec:
            shape.rotation = Angle.from_degrees(float(spec["rotation_degrees"]))
    elif shape_name == "ellipse_arc":
        shape = EllipseArc()
        shape.center = point_from_dict(spec["center"])
        shape.major_radius = millimetres_from_mm(spec["major_radius_mm"])
        shape.minor_radius = millimetres_from_mm(spec["minor_radius_mm"])
        if "rotation_degrees" in spec:
            shape.rotation = Angle.from_degrees(float(spec["rotation_degrees"]))
        shape.start_angle = Angle.from_degrees(
            float(spec.get("start_angle_degrees", 0.0))
        )
        shape.end_angle = Angle.from_degrees(float(spec.get("end_angle_degrees", 0.0)))
    else:
        raise ValueError(f"unsupported graphic shape {shape_name!r}")

    apply_graphic_attributes(shape, spec)
    item.shape = shape
    return item
