"""Read/write conversions for footprint text, text boxes, and fields."""

from __future__ import annotations

from typing import Any

from kipy.board_types import BoardText, BoardTextBox, Field
from kipy.proto.board.board_types_pb2 import BoardLayer
from kipy.proto.common.types.enums_pb2 import (
    HorizontalAlignment,
    VerticalAlignment,
)

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.units import (
    millimetres_from_mm,
    mm,
    point_from_dict,
    point_to_dict,
    size_from_dict,
    size_to_dict,
)


def text_attributes_to_dict(attributes: Any) -> dict[str, Any]:
    return {
        "size": size_to_dict(attributes.size),
        "thickness_mm": mm(attributes.stroke_width),
        "angle_degrees": attributes.angle,
        "bold": attributes.bold,
        "italic": attributes.italic,
        "mirrored": attributes.mirrored,
        "keep_upright": attributes.keep_upright,
        "horizontal_alignment": HorizontalAlignment.Name(
            attributes.horizontal_alignment
        ),
        "vertical_alignment": VerticalAlignment.Name(attributes.vertical_alignment),
    }


def apply_text_attributes(attributes: Any, spec: dict[str, Any]) -> None:
    if "size" in spec:
        attributes.size = size_from_dict(spec["size"])
    if "thickness_mm" in spec:
        attributes.stroke_width = millimetres_from_mm(spec["thickness_mm"])
    if "angle_degrees" in spec:
        attributes.angle = float(spec["angle_degrees"])
    if "bold" in spec:
        attributes.bold = bool(spec["bold"])
    if "italic" in spec:
        attributes.italic = bool(spec["italic"])
    if "mirrored" in spec:
        attributes.mirrored = bool(spec["mirrored"])
    if "keep_upright" in spec:
        attributes.keep_upright = bool(spec["keep_upright"])
    if "horizontal_alignment" in spec:
        attributes.horizontal_alignment = enum_value(
            HorizontalAlignment, spec["horizontal_alignment"]
        )
    if "vertical_alignment" in spec:
        attributes.vertical_alignment = enum_value(
            VerticalAlignment, spec["vertical_alignment"]
        )


def field_to_dict(field: Field) -> dict[str, Any]:
    text = field.text
    return {
        "type": "field",
        "id": field.text.id.value,
        "field_id": field.field_id,
        "name": field.name,
        "text": text.value,
        "visible": field.visible,
        "layer": BoardLayer.Name(field.layer),
        "position": point_to_dict(text.position),
        "attributes": text_attributes_to_dict(text.attributes),
    }


def text_to_dict(item: BoardText) -> dict[str, Any]:
    return {
        "type": "text",
        "id": item.id.value,
        "text": item.value,
        "layer": BoardLayer.Name(item.layer),
        "position": point_to_dict(item.position),
        "attributes": text_attributes_to_dict(item.attributes),
    }


def text_box_to_dict(item: BoardTextBox) -> dict[str, Any]:
    return {
        "type": "text_box",
        "id": item.id.value,
        "text": item.value,
        "layer": BoardLayer.Name(item.layer),
        "top_left": point_to_dict(item.top_left),
        "bottom_right": point_to_dict(item.bottom_right),
        "attributes": text_attributes_to_dict(item.attributes),
    }


def field_from_spec(spec: dict[str, Any]) -> Field:
    field = Field()
    field.proto.id.id = int(spec.get("field_id", 0))
    field.name = str(spec.get("name", ""))
    field.visible = bool(spec.get("visible", True))
    field.layer = enum_value(BoardLayer, spec.get("layer", "BL_F_Fab"))
    text = field.text
    text.value = str(spec.get("text", ""))
    text.position = point_from_dict(spec["position"])
    apply_text_attributes(text.attributes, spec.get("attributes", {}))
    return field


def text_from_spec(spec: dict[str, Any]) -> BoardText:
    item = BoardText()
    item.layer = enum_value(BoardLayer, spec.get("layer", "BL_F_Fab"))
    item.value = str(spec.get("text", ""))
    item.position = point_from_dict(spec["position"])
    apply_text_attributes(item.attributes, spec.get("attributes", {}))
    return item


def text_box_from_spec(spec: dict[str, Any]) -> BoardTextBox:
    item = BoardTextBox()
    item.layer = enum_value(BoardLayer, spec.get("layer", "BL_F_Fab"))
    item.value = str(spec.get("text", ""))
    item.top_left = point_from_dict(spec["top_left"])
    item.bottom_right = point_from_dict(spec["bottom_right"])
    apply_text_attributes(item.attributes, spec.get("attributes", {}))
    return item
