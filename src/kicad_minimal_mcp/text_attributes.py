"""Shared text attribute conversions.

Footprint text, text boxes, and fields and their symbol counterparts expose the
same text attributes through different protobuf messages, so the conversion
lives here rather than in either editor package.
"""

from __future__ import annotations

from dataclasses import dataclass

from kipy.common_types import TextAttributes
from kipy.proto.common.types.enums_pb2 import HorizontalAlignment, VerticalAlignment

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.parsing import boolean, mapping, number, optional
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import SizeMm, api_from_mm, mm_from_api


@dataclass(frozen=True)
class TextAttributesSpec:
    size: SizeMm | None = None
    thickness_mm: float | None = None
    angle_degrees: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    mirrored: bool | None = None
    keep_upright: bool | None = None
    horizontal_alignment: HorizontalAlignment.ValueType | None = None
    vertical_alignment: VerticalAlignment.ValueType | None = None

    @classmethod
    def parse(cls, data: object, name: str = "attributes") -> TextAttributesSpec:
        values = mapping(data, name)

        return cls(
            size=optional(values, "size", SizeMm.parse, name),
            thickness_mm=optional(values, "thickness_mm", number, name),
            angle_degrees=optional(values, "angle_degrees", number, name),
            bold=optional(values, "bold", boolean, name),
            italic=optional(values, "italic", boolean, name),
            mirrored=optional(values, "mirrored", boolean, name),
            keep_upright=optional(values, "keep_upright", boolean, name),
            horizontal_alignment=optional(
                values,
                "horizontal_alignment",
                enum_converter(HorizontalAlignment),
                name,
            ),
            vertical_alignment=optional(
                values, "vertical_alignment", enum_converter(VerticalAlignment), name
            ),
        )

    def apply(self, attributes: TextAttributes) -> None:
        """Apply the attributes this specification sets."""
        if self.size is not None:
            attributes.size = self.size.to_vector()
        if self.thickness_mm is not None:
            attributes.stroke_width = api_from_mm(self.thickness_mm)
        if self.angle_degrees is not None:
            attributes.angle = self.angle_degrees
        if self.bold is not None:
            attributes.bold = self.bold
        if self.italic is not None:
            attributes.italic = self.italic
        if self.mirrored is not None:
            attributes.mirrored = self.mirrored
        if self.keep_upright is not None:
            attributes.keep_upright = self.keep_upright
        if self.horizontal_alignment is not None:
            attributes.horizontal_alignment = self.horizontal_alignment
        if self.vertical_alignment is not None:
            attributes.vertical_alignment = self.vertical_alignment


def text_attributes_to_dict(attributes: TextAttributes) -> Payload:
    return {
        "size": SizeMm.from_vector(attributes.size).to_payload(),
        "thickness_mm": mm_from_api(attributes.stroke_width),
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
