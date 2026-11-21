"""Read conversions for symbol pins."""

from __future__ import annotations

from typing import Any

from kipy.proto.common.types.base_types_pb2 import ElectricalPinType
from kipy.proto.schematic.schematic_types_pb2 import (
    SchematicPinOrientation,
    SchematicPinShape,
)
from kipy.schematic_types import SchematicPin, SchematicPinAlternate

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.units import (
    millimetres_from_mm,
    mm,
    point_from_dict,
    point_to_dict,
)


def pin_to_dict(pin: SchematicPin) -> dict[str, Any]:
    """Convert a symbol pin to the MCP-facing dictionary shape.

    Positions and sizes are millimetres in the symbol definition's local
    coordinate frame, as reported by the IPC API.
    """
    return {
        "type": "pin",
        "id": pin.id.value,
        "name": pin.name,
        "number": pin.number,
        "position": point_to_dict(pin.position),
        "length_mm": mm(pin.length),
        "orientation": SchematicPinOrientation.Name(pin.orientation),
        "electrical_type": ElectricalPinType.Name(pin.electrical_type),
        "shape": SchematicPinShape.Name(pin.shape),
        "visible": pin.visible,
        "name_text_size_mm": mm(pin.name_text_size),
        "number_text_size_mm": mm(pin.number_text_size),
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


def pin_from_spec(spec: dict[str, Any]) -> SchematicPin:
    """Create a symbol pin from the MCP-facing item shape."""
    if "position" not in spec:
        raise ValueError("a pin specification requires position")

    pin = SchematicPin()
    pin.name = str(spec.get("name", ""))
    pin.number = str(spec.get("number", ""))
    pin.position = point_from_dict(spec["position"])

    if "length_mm" in spec:
        pin.length = millimetres_from_mm(spec["length_mm"])
    if "orientation" in spec:
        pin.orientation = enum_value(SchematicPinOrientation, spec["orientation"])
    if "electrical_type" in spec:
        pin.electrical_type = enum_value(ElectricalPinType, spec["electrical_type"])
    if "shape" in spec:
        pin.shape = enum_value(SchematicPinShape, spec["shape"])
    if "visible" in spec:
        pin.visible = bool(spec["visible"])
    if "name_text_size_mm" in spec:
        pin.name_text_size = millimetres_from_mm(spec["name_text_size_mm"])
    if "number_text_size_mm" in spec:
        pin.number_text_size = millimetres_from_mm(spec["number_text_size_mm"])

    alternates = []
    for alternate_spec in spec.get("alternates", []):
        alternate = SchematicPinAlternate()
        alternate.name = str(alternate_spec.get("name", ""))
        if "shape" in alternate_spec:
            alternate.shape = enum_value(SchematicPinShape, alternate_spec["shape"])
        if "electrical_type" in alternate_spec:
            alternate.electrical_type = enum_value(
                ElectricalPinType, alternate_spec["electrical_type"]
            )
        alternates.append(alternate)
    if alternates:
        pin.alternates = alternates

    if "active_alternate" in spec:
        pin.active_alternate = spec["active_alternate"]

    return pin
