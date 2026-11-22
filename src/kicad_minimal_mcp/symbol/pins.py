"""Read/write conversions for symbol pins."""

from __future__ import annotations

from dataclasses import dataclass, field

from kipy.proto.common.types.base_types_pb2 import ElectricalPinType
from kipy.proto.schematic.schematic_types_pb2 import (
    SchematicPinOrientation,
    SchematicPinShape,
)
from kipy.schematic_types import SchematicPin, SchematicPinAlternate

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    boolean,
    converted,
    converted_list,
    integer,
    mapping,
    number,
    optional,
    text,
)
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import PointMm, api_from_mm, mm_from_api


@dataclass(frozen=True)
class PinAlternateSpec:
    """An alternate function of a symbol pin."""

    name: str = ""
    shape: SchematicPinShape.ValueType | None = None
    electrical_type: ElectricalPinType.ValueType | None = None

    @classmethod
    def parse(cls, data: object, name: str = "alternate") -> PinAlternateSpec:
        """Parse an alternate pin object arriving at the MCP boundary."""
        values = mapping(data, name)

        return cls(
            name=optional(values, "name", text, name) or "",
            shape=optional(values, "shape", enum_converter(SchematicPinShape), name),
            electrical_type=optional(
                values, "electrical_type", enum_converter(ElectricalPinType), name
            ),
        )


@dataclass(frozen=True)
class PinSpec:
    """A symbol pin to create or update."""

    position: PointMm
    name: str = ""
    number: str = ""
    length_mm: float | None = None
    orientation: SchematicPinOrientation.ValueType | None = None
    electrical_type: ElectricalPinType.ValueType | None = None
    shape: SchematicPinShape.ValueType | None = None
    visible: bool | None = None
    name_text_size_mm: float | None = None
    number_text_size_mm: float | None = None
    active_alternate: str | None = None
    alternates: list[PinAlternateSpec] = field(default_factory=list)
    id: ItemId | None = None
    unit: int | None = None
    body_style: int | None = None

    @classmethod
    def parse(cls, data: object, name: str = "pin") -> PinSpec:
        """Parse a pin object arriving at the MCP boundary."""
        values = mapping(data, name)

        return cls(
            position=converted(values, "position", PointMm.parse, name),
            name=optional(values, "name", text, name) or "",
            number=optional(values, "number", text, name) or "",
            length_mm=optional(values, "length_mm", number, name),
            orientation=optional(
                values, "orientation", enum_converter(SchematicPinOrientation), name
            ),
            electrical_type=optional(
                values, "electrical_type", enum_converter(ElectricalPinType), name
            ),
            shape=optional(values, "shape", enum_converter(SchematicPinShape), name),
            visible=optional(values, "visible", boolean, name),
            name_text_size_mm=optional(values, "name_text_size_mm", number, name),
            number_text_size_mm=optional(values, "number_text_size_mm", number, name),
            active_alternate=optional(values, "active_alternate", text, name),
            alternates=converted_list(
                values, "alternates", PinAlternateSpec.parse, name
            ),
            id=optional(values, "id", text, name),
            unit=optional(values, "unit", integer, name),
            body_style=optional(values, "body_style", integer, name),
        )


def pin_to_dict(pin: SchematicPin) -> Payload:
    """Convert a symbol pin to the MCP-facing dictionary shape.

    Positions and sizes are millimetres in the symbol definition's local
    coordinate frame, as reported by the IPC API.
    """
    return {
        "type": "pin",
        "id": pin.id.value,
        "name": pin.name,
        "number": pin.number,
        "position": PointMm.from_vector(pin.position).to_payload(),
        "length_mm": mm_from_api(pin.length),
        "orientation": SchematicPinOrientation.Name(pin.orientation),
        "electrical_type": ElectricalPinType.Name(pin.electrical_type),
        "shape": SchematicPinShape.Name(pin.shape),
        "visible": pin.visible,
        "name_text_size_mm": mm_from_api(pin.name_text_size),
        "number_text_size_mm": mm_from_api(pin.number_text_size),
        "active_alternate": pin.active_alternate,
        "alternates": [
            {
                "name": alternate.name,
                "shape": SchematicPinShape.Name(alternate.shape),
                "electrical_type": ElectricalPinType.Name(alternate.electrical_type),
            }
            for alternate in pin.alternates
        ],
    }


def pin_from_spec(spec: PinSpec) -> SchematicPin:
    """Create a symbol pin from a parsed pin specification."""
    pin = SchematicPin()
    pin.name = spec.name
    pin.number = spec.number
    pin.position = spec.position.to_vector()

    if spec.length_mm is not None:
        pin.length = api_from_mm(spec.length_mm)
    if spec.orientation is not None:
        pin.orientation = spec.orientation
    if spec.electrical_type is not None:
        pin.electrical_type = spec.electrical_type
    if spec.shape is not None:
        pin.shape = spec.shape
    if spec.visible is not None:
        pin.visible = spec.visible
    if spec.name_text_size_mm is not None:
        pin.name_text_size = api_from_mm(spec.name_text_size_mm)
    if spec.number_text_size_mm is not None:
        pin.number_text_size = api_from_mm(spec.number_text_size_mm)

    alternates = [_alternate_from_spec(alternate) for alternate in spec.alternates]
    if alternates:
        pin.alternates = alternates

    if spec.active_alternate is not None:
        pin.active_alternate = spec.active_alternate

    return pin


def _alternate_from_spec(spec: PinAlternateSpec) -> SchematicPinAlternate:
    alternate = SchematicPinAlternate()
    alternate.name = spec.name

    if spec.shape is not None:
        alternate.shape = spec.shape
    if spec.electrical_type is not None:
        alternate.electrical_type = spec.electrical_type

    return alternate
