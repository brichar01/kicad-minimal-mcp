"""Read/write conversions for symbol graphic shapes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from kipy.common_types import (
    Arc,
    Bezier,
    Circle,
    Ellipse,
    EllipseArc,
    Polygon,
    Rectangle,
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

from kicad_minimal_mcp.geometry import (
    GraphicAppearance,
    StrokeSpec,
    polygon_geometry_to_dict,
)
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    boolean,
    converted,
    converted_list,
    integer,
    mapping,
    number,
    optional,
    sequence,
    text,
)
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import PointMm, SizeMm, api_from_mm, mm_from_api


@dataclass(frozen=True)
class ArcNode:
    start: PointMm
    mid: PointMm
    end: PointMm

    @classmethod
    def parse(cls, data: object, name: str) -> ArcNode:
        values = mapping(data, name)

        return cls(
            start=converted(values, "start", PointMm.parse, name),
            mid=converted(values, "mid", PointMm.parse, name),
            end=converted(values, "end", PointMm.parse, name),
        )


#: A point or an arc segment in a polygon outline.
PolygonNode = PointMm | ArcNode


@dataclass(frozen=True)
class PolygonOutline:
    outline: list[PolygonNode] = field(default_factory=list)
    closed: bool = False
    holes: list[list[PointMm]] = field(default_factory=list)

    @classmethod
    def parse(cls, data: object, name: str = "polygon") -> PolygonOutline:
        values = mapping(data, name)
        closed = optional(values, "closed", boolean, name)

        return cls(
            outline=converted_list(values, "outline", _parse_node, name),
            closed=False if closed is None else closed,
            holes=converted_list(values, "holes", _parse_hole, name),
        )

    def to_geometry(self) -> PolygonWithHoles:
        polygon = PolygonWithHoles(auto_close=False)
        polygon.outline = _polyline(self.outline, closed=self.closed)

        for hole in self.holes:
            polygon.holes.append(_polyline(hole, closed=True))

        return polygon


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


@dataclass(frozen=True)
class PolygonShape:
    polygons: list[PolygonOutline] = field(default_factory=list)


@dataclass(frozen=True)
class EllipseShape:
    center: PointMm
    major_radius_mm: float
    minor_radius_mm: float
    rotation_degrees: float = 0.0


@dataclass(frozen=True)
class EllipseArcShape:
    center: PointMm
    major_radius_mm: float
    minor_radius_mm: float
    rotation_degrees: float = 0.0
    start_angle_degrees: float = 0.0
    end_angle_degrees: float = 0.0


#: The shapes a symbol graphic can draw.
SymbolShape = (
    ArcShape
    | CircleShape
    | RectangleShape
    | BezierShape
    | PolygonShape
    | EllipseShape
    | EllipseArcShape
)


@dataclass(frozen=True)
class GraphicSpec(GraphicAppearance):
    shape: SymbolShape
    id: ItemId | None = None
    unit: int | None = None
    body_style: int | None = None

    @classmethod
    def parse(cls, data: object, name: str = "graphic") -> GraphicSpec:
        values = mapping(data, name)
        shape = converted(values, "shape", text, name)

        if shape.lower() == "segment":
            raise ValueError(
                "symbol graphics do not support segments; use a polygon with two points"
            )

        return cls(
            shape=_parse_shape(shape, values, name),
            stroke=optional(values, "stroke", StrokeSpec.parse, name),
            filled=optional(values, "filled", boolean, name),
            id=optional(values, "id", text, name),
            unit=optional(values, "unit", integer, name),
            body_style=optional(values, "body_style", integer, name),
        )


def _parse_shape(
    shape: str,
    values: Mapping[str, object],
    name: str,
) -> SymbolShape:
    match shape.lower():
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
        case "polygon":
            return PolygonShape(
                polygons=converted_list(values, "polygons", PolygonOutline.parse, name),
            )
        case "ellipse":
            return EllipseShape(
                center=converted(values, "center", PointMm.parse, name),
                major_radius_mm=converted(values, "major_radius_mm", number, name),
                minor_radius_mm=converted(values, "minor_radius_mm", number, name),
                rotation_degrees=optional(values, "rotation_degrees", number, name)
                or 0.0,
            )
        case "ellipse_arc":
            return EllipseArcShape(
                center=converted(values, "center", PointMm.parse, name),
                major_radius_mm=converted(values, "major_radius_mm", number, name),
                minor_radius_mm=converted(values, "minor_radius_mm", number, name),
                rotation_degrees=optional(values, "rotation_degrees", number, name)
                or 0.0,
                start_angle_degrees=optional(
                    values, "start_angle_degrees", number, name
                )
                or 0.0,
                end_angle_degrees=optional(values, "end_angle_degrees", number, name)
                or 0.0,
            )

    raise ValueError(f"unsupported graphic shape {shape!r}")


def graphic_base_to_dict(item: SchematicGraphicShape) -> Payload:
    result: Payload = {
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
        "width_mm": mm_from_api(attributes.stroke.width),
        "style": StrokeLineStyle.Name(attributes.stroke.style),
    }
    result["filled"] = attributes.fill.filled

    return result


def graphic_to_dict(item: SchematicGraphicShape) -> Payload:
    result = graphic_base_to_dict(item)
    shape = item.shape

    if isinstance(shape, Arc):
        result["shape"] = "arc"
        result["start"] = PointMm.from_vector(shape.start).to_payload()
        result["mid"] = PointMm.from_vector(shape.mid).to_payload()
        result["end"] = PointMm.from_vector(shape.end).to_payload()
    elif isinstance(shape, Circle):
        result["shape"] = "circle"
        result["center"] = PointMm.from_vector(shape.center).to_payload()
        result["radius_mm"] = mm_from_api(shape.radius())
    elif isinstance(shape, Rectangle):
        result["shape"] = "rectangle"
        result["top_left"] = PointMm.from_vector(shape.top_left).to_payload()
        result["bottom_right"] = PointMm.from_vector(shape.bottom_right).to_payload()
        result["size"] = SizeMm.from_vector(
            shape.bottom_right - shape.top_left
        ).to_payload()
    elif isinstance(shape, Polygon):
        result["shape"] = "polygon"
        result["polygons"] = polygon_geometry_to_dict(shape)
    elif isinstance(shape, Bezier):
        result["shape"] = "bezier"
        result["start"] = PointMm.from_vector(shape.start).to_payload()
        result["control1"] = PointMm.from_vector(shape.control1).to_payload()
        result["control2"] = PointMm.from_vector(shape.control2).to_payload()
        result["end"] = PointMm.from_vector(shape.end).to_payload()
    elif isinstance(shape, EllipseArc):
        result["shape"] = "ellipse_arc"
        result["center"] = PointMm.from_vector(shape.center).to_payload()
        result["major_radius_mm"] = mm_from_api(shape.major_radius)
        result["minor_radius_mm"] = mm_from_api(shape.minor_radius)
        result["rotation_degrees"] = shape.rotation.degrees
        result["start_angle_degrees"] = shape.start_angle.degrees
        result["end_angle_degrees"] = shape.end_angle.degrees
    elif isinstance(shape, Ellipse):
        result["shape"] = "ellipse"
        result["center"] = PointMm.from_vector(shape.center).to_payload()
        result["major_radius_mm"] = mm_from_api(shape.major_radius)
        result["minor_radius_mm"] = mm_from_api(shape.minor_radius)
        result["rotation_degrees"] = shape.rotation.degrees

    return result


def graphic_from_spec(spec: GraphicSpec) -> SchematicGraphicShape:
    shape = _graphic_shape(spec.shape)
    spec.apply(shape.attributes)

    item = SchematicGraphicShape()
    item.shape = shape

    return item


def _graphic_shape(
    shape: SymbolShape,
) -> Arc | Circle | Rectangle | Bezier | Polygon | Ellipse | EllipseArc:
    match shape:
        case ArcShape():
            graphic = Arc()
            graphic.start = shape.start.to_vector()
            graphic.mid = shape.mid.to_vector()
            graphic.end = shape.end.to_vector()
            return graphic
        case CircleShape():
            graphic = Circle()
            graphic.center = shape.center.to_vector()
            graphic.radius_point = graphic.center + Vector2.from_xy_mm(
                shape.radius_mm, 0.0
            )
            return graphic
        case RectangleShape():
            graphic = Rectangle()
            graphic.top_left = shape.top_left.to_vector()
            graphic.bottom_right = shape.bottom_right.to_vector()
            return graphic
        case BezierShape():
            graphic = Bezier()
            graphic.start = shape.start.to_vector()
            graphic.control1 = shape.control1.to_vector()
            graphic.control2 = shape.control2.to_vector()
            graphic.end = shape.end.to_vector()
            return graphic
        case PolygonShape():
            graphic = Polygon()
            for outline in shape.polygons:
                graphic.polygons.append(outline.to_geometry())
            return graphic
        case EllipseShape():
            graphic = Ellipse()
            graphic.center = shape.center.to_vector()
            graphic.major_radius = api_from_mm(shape.major_radius_mm)
            graphic.minor_radius = api_from_mm(shape.minor_radius_mm)
            graphic.rotation = Angle.from_degrees(shape.rotation_degrees)
            return graphic
        case EllipseArcShape():
            graphic = EllipseArc()
            graphic.center = shape.center.to_vector()
            graphic.major_radius = api_from_mm(shape.major_radius_mm)
            graphic.minor_radius = api_from_mm(shape.minor_radius_mm)
            graphic.rotation = Angle.from_degrees(shape.rotation_degrees)
            graphic.start_angle = Angle.from_degrees(shape.start_angle_degrees)
            graphic.end_angle = Angle.from_degrees(shape.end_angle_degrees)
            return graphic

    raise ValueError("unsupported symbol graphic shape")


def _parse_node(data: object, name: str) -> PolygonNode:
    values = mapping(data, name)
    arc = values.get("arc")

    if arc is not None:
        return ArcNode.parse(arc, f"{name}.arc")

    return PointMm.parse(data, name)


def _parse_hole(data: object, name: str) -> list[PointMm]:
    return [PointMm.parse(point, f"{name}[]") for point in sequence(data, name)]


def _polyline(nodes: Sequence[PolygonNode], *, closed: bool) -> PolyLine:
    line = PolyLine()
    line.closed = closed

    for node in nodes:
        if isinstance(node, ArcNode):
            arc = ArcStartMidEnd()
            arc.start = node.start.to_vector()
            arc.mid = node.mid.to_vector()
            arc.end = node.end.to_vector()
            polyline_node = PolyLineNode()
            polyline_node.arc = arc
        else:
            polyline_node = PolyLineNode.from_point(node.to_vector())

        line.append(polyline_node)

    return line
