"""Read conversions for symbol text, text boxes, and fields."""

from __future__ import annotations

from typing import Any

from kipy.proto.common.types.enums_pb2 import HorizontalAlignment, VerticalAlignment
from kipy.schematic_types import SchematicField, SchematicText, SchematicTextBox

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.units import (
    millimetres_from_mm,
    mm,
    point_from_dict,
    point_to_dict,
    size_from_dict,
    size_to_dict,
)

#: KiCad FIELD_T values for the mandatory fields of a symbol definition.
MANDATORY_FIELD_IDS = {
    "Reference": 1,
    "Value": 2,
    "Footprint": 3,
    "Datasheet": 4,
    "Description": 5,
}


def text_attributes_to_dict(attributes: Any) -> dict[str, Any]:
    """Convert shared text attributes to the MCP-facing dictionary shape."""
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


def field_to_dict(field: SchematicField) -> dict[str, Any]:
    """Convert a symbol field to the MCP-facing dictionary shape.

    Symbol fields have no unique identifier in the IPC API, so ``id`` is always
    ``None`` and fields cannot be addressed by ``item_ids``.
    """
    text = field.text
    return {
        "type": "field",
        "id": None,
        "field_id": MANDATORY_FIELD_IDS.get(field.name, 0),
        "name": field.name,
        "text": text.value,
        "visible": field.visible,
        "show_name": field.show_name,
        "allow_auto_place": field.allow_auto_place,
        "is_private": field.is_private,
        "position": point_to_dict(text.position),
        "attributes": text_attributes_to_dict(text.attributes),
    }


def text_to_dict(item: SchematicText) -> dict[str, Any]:
    """Convert a symbol text item to the MCP-facing dictionary shape."""
    return {
        "type": "text",
        "id": item.id.value,
        "text": item.value,
        "position": point_to_dict(item.position),
        "attributes": text_attributes_to_dict(item.text.attributes),
    }


def text_box_to_dict(item: SchematicTextBox) -> dict[str, Any]:
    """Convert a symbol text box to the MCP-facing dictionary shape."""
    return {
        "type": "text_box",
        "id": item.id.value,
        "text": item.value,
        "top_left": point_to_dict(item.top_left),
        "bottom_right": point_to_dict(item.bottom_right),
        "attributes": text_attributes_to_dict(item.textbox.attributes),
    }


def apply_text_attributes(attributes: Any, spec: dict[str, Any]) -> None:
    """Apply text attributes from an item specification."""
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


def text_from_spec(spec: dict[str, Any]) -> SchematicText:
    """Create a symbol text item from the MCP-facing item shape."""
    if "position" not in spec:
        raise ValueError("a text specification requires position")

    item = SchematicText()
    item.value = str(spec.get("text", ""))
    item.position = point_from_dict(spec["position"])
    apply_text_attributes(item.text.attributes, spec.get("attributes", {}))
    return item


def text_box_from_spec(spec: dict[str, Any]) -> SchematicTextBox:
    """Create a symbol text box from the MCP-facing item shape."""
    for key in ("top_left", "bottom_right"):
        if key not in spec:
            raise ValueError(f"a text box specification requires {key}")

    item = SchematicTextBox()
    item.value = str(spec.get("text", ""))
    item.top_left = point_from_dict(spec["top_left"])
    item.bottom_right = point_from_dict(spec["bottom_right"])
    apply_text_attributes(item.textbox.attributes, spec.get("attributes", {}))
    return item
