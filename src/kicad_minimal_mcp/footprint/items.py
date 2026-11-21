"""Footprint item type catalog and read/write dispatch."""

from __future__ import annotations

from typing import Any

from kipy.board_types import (
    BoardShape,
    BoardText,
    BoardTextBox,
    Field,
    Pad,
)
from kipy.proto.common.types import KiCadObjectType

from kicad_minimal_mcp.footprint.graphics import graphic_from_spec, graphic_to_dict
from kicad_minimal_mcp.footprint.pads import pad_from_spec, pad_to_dict
from kicad_minimal_mcp.footprint.text import (
    field_from_spec,
    field_to_dict,
    text_box_from_spec,
    text_box_to_dict,
    text_from_spec,
    text_to_dict,
)

ITEM_TYPES = {
    "pad": KiCadObjectType.KOT_PCB_PAD,
    "field": KiCadObjectType.KOT_PCB_FIELD,
    "text": KiCadObjectType.KOT_PCB_TEXT,
    "text_box": KiCadObjectType.KOT_PCB_TEXTBOX,
    "graphic": KiCadObjectType.KOT_PCB_SHAPE,
    "zone": KiCadObjectType.KOT_PCB_ZONE,
    "table": KiCadObjectType.KOT_PCB_TABLE,
    "barcode": KiCadObjectType.KOT_PCB_BARCODE,
    "dimension": KiCadObjectType.KOT_PCB_DIMENSION,
    "group": KiCadObjectType.KOT_PCB_GROUP,
}

_ITEM_TYPE_ALIASES = {
    "pads": "pad",
    "fields": "field",
    "texts": "text",
    "textbox": "text_box",
    "text-box": "text_box",
    "textboxes": "text_box",
    "text_boxes": "text_box",
    "graphics": "graphic",
    "shape": "graphic",
    "shapes": "graphic",
    "board_shape": "graphic",
    "board_shapes": "graphic",
    "zones": "zone",
    "tables": "table",
    "barcodes": "barcode",
    "dimensions": "dimension",
    "groups": "group",
}


def normalise_item_type(item_type: str) -> str:
    """Return the canonical name for a footprint item-type filter."""
    value = item_type.strip().lower().replace(" ", "_").replace("-", "_")
    if value.startswith("kot_pcb_"):
        value = value.removeprefix("kot_pcb_")
    value = _ITEM_TYPE_ALIASES.get(value, value)
    if value not in {"all", *ITEM_TYPES}:
        supported = ", ".join(("all", *ITEM_TYPES))
        raise ValueError(
            f"Unsupported item type {item_type!r}; expected one of: {supported}"
        )
    return value


def item_category(item: Any) -> str:
    """Return the summary category used for a footprint item."""
    if isinstance(item, Pad):
        return "pads"
    if isinstance(item, Field):
        return "fields"
    if isinstance(item, BoardText):
        return "texts"
    if isinstance(item, BoardTextBox):
        return "text_boxes"
    if isinstance(item, BoardShape):
        return "graphics"
    return "other"


_ITEM_CATEGORIES = {
    "pad": "pads",
    "field": "fields",
    "text": "texts",
    "text_box": "text_boxes",
    "graphic": "graphics",
}


def item_matches_type(item: Any, item_type: str) -> bool:
    """Return whether an item matches a canonical item-type filter."""
    if item_type == "all":
        return True

    category = _ITEM_CATEGORIES.get(item_type)
    if category is not None:
        return item_category(item) == category

    value = item_to_dict(item).get("type")
    return isinstance(value, str) and value.lower() == item_type


def item_to_dict(item: Any) -> dict[str, Any]:
    """Convert a footprint item to the MCP-facing dictionary shape."""
    if isinstance(item, Pad):
        return pad_to_dict(item)
    if isinstance(item, Field):
        return field_to_dict(item)
    if isinstance(item, BoardText):
        return text_to_dict(item)
    if isinstance(item, BoardTextBox):
        return text_box_to_dict(item)
    if isinstance(item, BoardShape):
        return graphic_to_dict(item)
    return {
        "type": type(item).__name__,
        "id": getattr(getattr(item, "id", None), "value", None),
    }


def item_from_spec(spec: dict[str, Any]) -> Any:
    """Create a KiCad footprint item from the MCP-facing item shape."""
    item_type = str(spec.get("type", "")).lower()

    if item_type == "pad":
        return pad_from_spec(spec)
    if item_type == "field":
        return field_from_spec(spec)
    if item_type == "text":
        return text_from_spec(spec)
    if item_type == "text_box":
        return text_box_from_spec(spec)
    if item_type == "graphic":
        return graphic_from_spec(spec)

    raise ValueError(f"unsupported item type {item_type!r}")
