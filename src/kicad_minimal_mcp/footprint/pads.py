"""Read/write conversions for footprint pads."""

from __future__ import annotations

from typing import Any

from kipy.board_types import Pad
from kipy.proto.board.board_types_pb2 import (
    BoardLayer,
    DrillShape,
    PadStackShape,
    PadStackType,
    PadType,
)

from kicad_minimal_mcp.enums import enum_value
from kicad_minimal_mcp.units import (
    point_from_dict,
    point_to_dict,
    size_from_dict,
    size_to_dict,
)


def pad_to_dict(pad: Pad) -> dict[str, Any]:
    padstack = pad.padstack
    copper_layers = [
        {
            "layer": BoardLayer.Name(layer.layer),
            "shape": PadStackShape.Name(layer.shape),
            "size": size_to_dict(layer.size),
            "offset": point_to_dict(layer.offset),
            "corner_rounding_ratio": layer.corner_rounding_ratio,
        }
        for layer in padstack.copper_layers
    ]

    result: dict[str, Any] = {
        "type": "pad",
        "id": pad.id.value,
        "number": pad.number,
        "position": point_to_dict(pad.position),
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
            "diameter": size_to_dict(drill.diameter),
            "shape": DrillShape.Name(drill.shape),
            "start_layer": BoardLayer.Name(drill.start_layer),
            "end_layer": BoardLayer.Name(drill.end_layer),
        }

    return result


def pad_from_spec(spec: dict[str, Any]) -> Pad:
    pad = Pad()
    pad.number = str(spec.get("number", ""))
    pad.position = point_from_dict(spec["position"])
    pad.pad_type = enum_value(PadType, spec.get("pad_type", "PT_SMD"))
    padstack = pad.padstack
    if "padstack_type" in spec:
        padstack.type = enum_value(PadStackType, spec["padstack_type"])

    for layer_spec in spec.get("copper_layers", []):
        layer = enum_value(BoardLayer, layer_spec["layer"])
        copper_layer = padstack.copper_layer(layer)
        if copper_layer is None:
            raise ValueError(
                f"pad {pad.number!r} references copper layer "
                f"{layer_spec['layer']!r} outside its padstack type"
            )
        if "shape" in layer_spec:
            copper_layer.shape = enum_value(PadStackShape, layer_spec["shape"])
        if "size" in layer_spec:
            copper_layer.size = size_from_dict(layer_spec["size"])
        if "offset" in layer_spec:
            copper_layer.offset = point_from_dict(layer_spec["offset"])
        if "corner_rounding_ratio" in layer_spec:
            copper_layer.corner_rounding_ratio = float(
                layer_spec["corner_rounding_ratio"]
            )

    if "layers" in spec:
        padstack.layers = [enum_value(BoardLayer, layer) for layer in spec["layers"]]

    if "drill" in spec:
        drill_spec = spec["drill"]
        drill = padstack.drill
        if "diameter" in drill_spec:
            drill.diameter = size_from_dict(drill_spec["diameter"])
        if "shape" in drill_spec:
            drill.shape = enum_value(DrillShape, drill_spec["shape"])
        if "start_layer" in drill_spec:
            drill.start_layer = enum_value(BoardLayer, drill_spec["start_layer"])
        if "end_layer" in drill_spec:
            drill.end_layer = enum_value(BoardLayer, drill_spec["end_layer"])

    return pad
