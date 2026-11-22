"""Read/write conversions for footprint pads."""

from __future__ import annotations

from dataclasses import dataclass, field

from kipy.board_types import DrillProperties, Pad, PadStackLayer
from kipy.proto.board.board_types_pb2 import (
    BoardLayer,
    DrillShape,
    PadStackShape,
    PadStackType,
    PadType,
)

from kicad_minimal_mcp.enums import enum_converter
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import (
    converted,
    converted_list,
    mapping,
    number,
    optional,
    text,
)
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.units import PointMm, SizeMm


@dataclass(frozen=True)
class CopperLayerSpec:
    """The shape one copper layer of a padstack takes."""

    layer: BoardLayer.ValueType
    shape: PadStackShape.ValueType | None = None
    size: SizeMm | None = None
    offset: PointMm | None = None
    corner_rounding_ratio: float | None = None

    @classmethod
    def parse(cls, data: object, name: str) -> CopperLayerSpec:
        """Parse one copper layer object arriving at the MCP boundary."""
        values = mapping(data, name)

        return cls(
            layer=converted(values, "layer", enum_converter(BoardLayer), name),
            shape=optional(values, "shape", enum_converter(PadStackShape), name),
            size=optional(values, "size", SizeMm.parse, name),
            offset=optional(values, "offset", PointMm.parse, name),
            corner_rounding_ratio=optional(
                values, "corner_rounding_ratio", number, name
            ),
        )

    def apply(self, copper_layer: PadStackLayer) -> None:
        """Apply the values this specification sets."""
        if self.shape is not None:
            copper_layer.shape = self.shape
        if self.size is not None:
            copper_layer.size = self.size.to_vector()
        if self.offset is not None:
            copper_layer.offset = self.offset.to_vector()
        if self.corner_rounding_ratio is not None:
            copper_layer.corner_rounding_ratio = self.corner_rounding_ratio


@dataclass(frozen=True)
class DrillSpec:
    """The drilled hole of a padstack."""

    diameter: SizeMm | None = None
    shape: DrillShape.ValueType | None = None
    start_layer: BoardLayer.ValueType | None = None
    end_layer: BoardLayer.ValueType | None = None

    @classmethod
    def parse(cls, data: object, name: str = "drill") -> DrillSpec:
        """Parse a drill object arriving at the MCP boundary."""
        values = mapping(data, name)

        return cls(
            diameter=optional(values, "diameter", SizeMm.parse, name),
            shape=optional(values, "shape", enum_converter(DrillShape), name),
            start_layer=optional(
                values, "start_layer", enum_converter(BoardLayer), name
            ),
            end_layer=optional(values, "end_layer", enum_converter(BoardLayer), name),
        )

    def apply(self, drill: DrillProperties) -> None:
        """Apply the values this specification sets."""
        if self.diameter is not None:
            drill.diameter = self.diameter.to_vector()
        if self.shape is not None:
            drill.shape = self.shape
        if self.start_layer is not None:
            drill.start_layer = self.start_layer
        if self.end_layer is not None:
            drill.end_layer = self.end_layer


@dataclass(frozen=True)
class PadSpec:
    """A pad to create or update."""

    position: PointMm
    pad_type: PadType.ValueType = PadType.PT_SMD
    number: str = ""
    padstack_type: PadStackType.ValueType | None = None
    layers: list[BoardLayer.ValueType] = field(default_factory=list)
    copper_layers: list[CopperLayerSpec] = field(default_factory=list)
    drill: DrillSpec | None = None
    id: ItemId | None = None

    @classmethod
    def parse(cls, data: object, name: str = "pad") -> PadSpec:
        """Parse a pad object arriving at the MCP boundary."""
        values = mapping(data, name)
        pad_type = optional(values, "pad_type", enum_converter(PadType), name)
        number = optional(values, "number", text, name)

        return cls(
            position=converted(values, "position", PointMm.parse, name),
            pad_type=PadType.PT_SMD if pad_type is None else pad_type,
            number="" if number is None else number,
            padstack_type=optional(
                values, "padstack_type", enum_converter(PadStackType), name
            ),
            layers=converted_list(values, "layers", enum_converter(BoardLayer), name),
            copper_layers=converted_list(
                values, "copper_layers", CopperLayerSpec.parse, name
            ),
            drill=optional(values, "drill", DrillSpec.parse, name),
            id=optional(values, "id", text, name),
        )


def pad_to_dict(pad: Pad) -> Payload:
    padstack = pad.padstack
    copper_layers = [
        {
            "layer": BoardLayer.Name(layer.layer),
            "shape": PadStackShape.Name(layer.shape),
            "size": SizeMm.from_vector(layer.size).to_payload(),
            "offset": PointMm.from_vector(layer.offset).to_payload(),
            "corner_rounding_ratio": layer.corner_rounding_ratio,
        }
        for layer in padstack.copper_layers
    ]

    result: Payload = {
        "type": "pad",
        "id": pad.id.value,
        "number": pad.number,
        "position": PointMm.from_vector(pad.position).to_payload(),
        "pad_type": PadType.Name(pad.pad_type),
        "padstack_type": PadStackType.Name(padstack.type),
        "layers": [BoardLayer.Name(layer) for layer in padstack.layers],
        "copper_layers": copper_layers,
    }

    if copper_layers:
        result["shape"] = copper_layers[0]["shape"]
        result["size"] = copper_layers[0]["size"]

    drill = padstack.drill
    if drill.diameter.x or drill.diameter.y:
        result["drill"] = {
            "diameter": SizeMm.from_vector(drill.diameter).to_payload(),
            "shape": DrillShape.Name(drill.shape),
            "start_layer": BoardLayer.Name(drill.start_layer),
            "end_layer": BoardLayer.Name(drill.end_layer),
        }

    return result


def pad_from_spec(spec: PadSpec) -> Pad:
    pad = Pad()
    pad.number = spec.number
    pad.position = spec.position.to_vector()
    pad.pad_type = spec.pad_type

    padstack = pad.padstack
    if spec.padstack_type is not None:
        padstack.type = spec.padstack_type

    for layer_spec in spec.copper_layers:
        copper_layer = padstack.copper_layer(layer_spec.layer)
        if copper_layer is None:
            raise ValueError(
                f"pad {pad.number!r} references copper layer "
                f"{BoardLayer.Name(layer_spec.layer)!r} outside its padstack type"
            )
        layer_spec.apply(copper_layer)

    if spec.layers:
        padstack.layers = spec.layers

    if spec.drill is not None:
        spec.drill.apply(padstack.drill)

    return pad
