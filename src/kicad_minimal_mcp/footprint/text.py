"""Read/write conversions for footprint text, text boxes, and fields."""

from __future__ import annotations

from dataclasses import dataclass, field

from kipy.board_types import BoardText, BoardTextBox, Field
from kipy.proto.board.board_types_pb2 import BoardLayer

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    boolean,
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


@dataclass(frozen=True)
class FieldSpec:
    position: PointMm
    value: str = ""
    field_id: int = 0
    name: str = ""
    visible: bool = True
    layer: BoardLayer.ValueType = BoardLayer.BL_F_Fab
    attributes: TextAttributesSpec = field(default_factory=TextAttributesSpec)
    id: ItemId | None = None

    @classmethod
    def parse(cls, data: object, name: str = "field") -> FieldSpec:
        values = mapping(data, name)
        layer = optional(values, "layer", enum_converter(BoardLayer), name)
        visible = optional(values, "visible", boolean, name)

        return cls(
            position=converted(values, "position", PointMm.parse, name),
            value=optional(values, "text", text, name) or "",
            field_id=optional(values, "field_id", integer, name) or 0,
            name=optional(values, "name", text, name) or "",
            visible=True if visible is None else visible,
            layer=BoardLayer.BL_F_Fab if layer is None else layer,
            attributes=optional(values, "attributes", TextAttributesSpec.parse, name)
            or TextAttributesSpec(),
            id=optional(values, "id", text, name),
        )


@dataclass(frozen=True)
class TextSpec:
    position: PointMm
    value: str = ""
    layer: BoardLayer.ValueType = BoardLayer.BL_F_Fab
    attributes: TextAttributesSpec = field(default_factory=TextAttributesSpec)
    id: ItemId | None = None

    @classmethod
    def parse(cls, data: object, name: str = "text") -> TextSpec:
        values = mapping(data, name)
        layer = optional(values, "layer", enum_converter(BoardLayer), name)

        return cls(
            position=converted(values, "position", PointMm.parse, name),
            value=optional(values, "text", text, name) or "",
            layer=BoardLayer.BL_F_Fab if layer is None else layer,
            attributes=optional(values, "attributes", TextAttributesSpec.parse, name)
            or TextAttributesSpec(),
            id=optional(values, "id", text, name),
        )


@dataclass(frozen=True)
class TextBoxSpec:
    top_left: PointMm
    bottom_right: PointMm
    value: str = ""
    layer: BoardLayer.ValueType = BoardLayer.BL_F_Fab
    attributes: TextAttributesSpec = field(default_factory=TextAttributesSpec)
    id: ItemId | None = None

    @classmethod
    def parse(cls, data: object, name: str = "text box") -> TextBoxSpec:
        values = mapping(data, name)
        layer = optional(values, "layer", enum_converter(BoardLayer), name)

        return cls(
            top_left=converted(values, "top_left", PointMm.parse, name),
            bottom_right=converted(values, "bottom_right", PointMm.parse, name),
            value=optional(values, "text", text, name) or "",
            layer=BoardLayer.BL_F_Fab if layer is None else layer,
            attributes=optional(values, "attributes", TextAttributesSpec.parse, name)
            or TextAttributesSpec(),
            id=optional(values, "id", text, name),
        )


def field_to_dict(item: Field) -> Payload:
    item_text = item.text

    return {
        "type": "field",
        "id": item.text.id.value,
        "field_id": item.field_id,
        "name": item.name,
        "text": item_text.value,
        "visible": item.visible,
        "layer": BoardLayer.Name(item.layer),
        "position": PointMm.from_vector(item_text.position).to_payload(),
        "attributes": text_attributes_to_dict(item_text.attributes),
    }


def text_to_dict(item: BoardText) -> Payload:
    return {
        "type": "text",
        "id": item.id.value,
        "text": item.value,
        "layer": BoardLayer.Name(item.layer),
        "position": PointMm.from_vector(item.position).to_payload(),
        "attributes": text_attributes_to_dict(item.attributes),
    }


def text_box_to_dict(item: BoardTextBox) -> Payload:
    return {
        "type": "text_box",
        "id": item.id.value,
        "text": item.value,
        "layer": BoardLayer.Name(item.layer),
        "top_left": PointMm.from_vector(item.top_left).to_payload(),
        "bottom_right": PointMm.from_vector(item.bottom_right).to_payload(),
        "attributes": text_attributes_to_dict(item.attributes),
    }


def field_from_spec(spec: FieldSpec) -> Field:
    item = Field()
    item.proto.id.id = spec.field_id
    item.name = spec.name
    item.visible = spec.visible
    item.layer = spec.layer

    item_text = item.text
    item_text.value = spec.value
    item_text.position = spec.position.to_vector()
    spec.attributes.apply(item_text.attributes)

    return item


def text_from_spec(spec: TextSpec) -> BoardText:
    item = BoardText()
    item.layer = spec.layer
    item.value = spec.value
    item.position = spec.position.to_vector()
    spec.attributes.apply(item.attributes)

    return item


def text_box_from_spec(spec: TextBoxSpec) -> BoardTextBox:
    item = BoardTextBox()
    item.layer = spec.layer
    item.value = spec.value
    item.top_left = spec.top_left.to_vector()
    item.bottom_right = spec.bottom_right.to_vector()
    spec.attributes.apply(item.attributes)

    return item
