"""Read/write conversions for symbol text, text boxes, and fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from kipy.schematic_types import SchematicField, SchematicText, SchematicTextBox

from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    converted,
    integer,
    mapping,
    optional,
    text,
)
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.text_attributes import (
    TextAttributesSpec,
    text_attributes_to_dict,
)
from kicad_minimal_mcp.units import PointMm

#: KiCad FIELD_T values for the mandatory fields of a symbol definition.
MANDATORY_FIELD_IDS = {
    "Reference": 1,
    "Value": 2,
    "Footprint": 3,
    "Datasheet": 4,
    "Description": 5,
}


@dataclass(frozen=True)
class TextSpec:
    position: PointMm
    value: str = ""
    attributes: TextAttributesSpec = field(default_factory=TextAttributesSpec)
    id: ItemId | None = None
    unit: int | None = None
    body_style: int | None = None

    @classmethod
    def parse(cls, data: object, name: str = "text") -> TextSpec:
        values = mapping(data, name)

        return cls(
            position=converted(values, "position", PointMm.parse, name),
            value=optional(values, "text", text, name) or "",
            attributes=optional(values, "attributes", TextAttributesSpec.parse, name)
            or TextAttributesSpec(),
            id=optional(values, "id", text, name),
            unit=optional(values, "unit", integer, name),
            body_style=optional(values, "body_style", integer, name),
        )


@dataclass(frozen=True)
class TextBoxSpec:
    top_left: PointMm
    bottom_right: PointMm
    value: str = ""
    attributes: TextAttributesSpec = field(default_factory=TextAttributesSpec)
    id: ItemId | None = None
    unit: int | None = None
    body_style: int | None = None

    @classmethod
    def parse(cls, data: object, name: str = "text box") -> TextBoxSpec:
        values = mapping(data, name)

        return cls(
            top_left=converted(values, "top_left", PointMm.parse, name),
            bottom_right=converted(values, "bottom_right", PointMm.parse, name),
            value=optional(values, "text", text, name) or "",
            attributes=optional(values, "attributes", TextAttributesSpec.parse, name)
            or TextAttributesSpec(),
            id=optional(values, "id", text, name),
            unit=optional(values, "unit", integer, name),
            body_style=optional(values, "body_style", integer, name),
        )


def field_to_dict(item: SchematicField) -> Payload:
    """Symbol fields have no unique identifier in the IPC API, so ``id`` is always
    ``None`` and fields cannot be addressed by ``item_ids``.
    """
    item_text = item.text

    return {
        "type": "field",
        "id": None,
        "field_id": MANDATORY_FIELD_IDS.get(item.name, 0),
        "name": item.name,
        "text": item_text.value,
        "visible": item.visible,
        "show_name": item.show_name,
        "allow_auto_place": item.allow_auto_place,
        "is_private": item.is_private,
        "position": PointMm.from_vector(item_text.position).to_payload(),
        "attributes": text_attributes_to_dict(item_text.attributes),
    }


def text_to_dict(item: SchematicText) -> Payload:
    return {
        "type": "text",
        "id": item.id.value,
        "text": item.value,
        "position": PointMm.from_vector(item.position).to_payload(),
        "attributes": text_attributes_to_dict(item.text.attributes),
    }


def text_box_to_dict(item: SchematicTextBox) -> Payload:
    return {
        "type": "text_box",
        "id": item.id.value,
        "text": item.value,
        "top_left": PointMm.from_vector(item.top_left).to_payload(),
        "bottom_right": PointMm.from_vector(item.bottom_right).to_payload(),
        "attributes": text_attributes_to_dict(item.textbox.attributes),
    }


def text_from_spec(spec: TextSpec) -> SchematicText:
    item = SchematicText()
    item.value = spec.value
    item.position = spec.position.to_vector()
    spec.attributes.apply(item.text.attributes)

    return item


def text_box_from_spec(spec: TextBoxSpec) -> SchematicTextBox:
    item = SchematicTextBox()
    item.value = spec.value
    item.top_left = spec.top_left.to_vector()
    item.bottom_right = spec.bottom_right.to_vector()
    spec.attributes.apply(item.textbox.attributes)

    return item
