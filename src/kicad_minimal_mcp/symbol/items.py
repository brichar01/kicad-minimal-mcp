"""Symbol item catalog and read dispatch."""

from __future__ import annotations

from typing import Any

from google.protobuf.any_pb2 import Any as AnyMessage
from kipy.proto.common.types import KiCadObjectType
from kipy.proto.schematic.schematic_types_pb2 import SchematicSymbolType
from kipy.schematic_types import (
    SchematicField,
    SchematicGraphicShape,
    SchematicImage,
    SchematicPin,
    SchematicSymbol,
    SchematicTable,
    SchematicText,
    SchematicTextBox,
)
from kipy.util.proto import unpack_any

from kicad_minimal_mcp.symbol.graphics import graphic_from_spec, graphic_to_dict
from kicad_minimal_mcp.symbol.pins import pin_from_spec, pin_to_dict
from kicad_minimal_mcp.symbol.text import (
    field_to_dict,
    text_box_from_spec,
    text_box_to_dict,
    text_from_spec,
    text_to_dict,
)
from kicad_minimal_mcp.units import point_to_dict

#: Canonical item names mapped to the IPC object type the symbol editor accepts.
SYMBOL_ITEM_TYPES = {
    "pin": KiCadObjectType.KOT_SCH_PIN,
    "field": KiCadObjectType.KOT_SCH_FIELD,
    "text": KiCadObjectType.KOT_SCH_TEXT,
    "text_box": KiCadObjectType.KOT_SCH_TEXTBOX,
    "graphic": KiCadObjectType.KOT_SCH_SHAPE,
    "table": KiCadObjectType.KOT_SCH_TABLE,
    "bitmap": KiCadObjectType.KOT_SCH_BITMAP,
}

_ITEM_TYPE_ALIASES = {
    "pins": "pin",
    "fields": "field",
    "texts": "text",
    "textbox": "text_box",
    "text-box": "text_box",
    "textboxes": "text_box",
    "text_boxes": "text_box",
    "graphics": "graphic",
    "shape": "graphic",
    "shapes": "graphic",
    "sch_shape": "graphic",
    "tables": "table",
    "bitmaps": "bitmap",
    "image": "bitmap",
    "images": "bitmap",
}

#: Categories used in the result summary, keyed by item type.
_ITEM_CATEGORIES = {
    "pin": "pins",
    "field": "fields",
    "text": "texts",
    "text_box": "text_boxes",
    "graphic": "graphics",
    "table": "tables",
    "bitmap": "bitmaps",
}

#: Protobuf message names for child items kipy does not wrap yet.
_KIND_TO_TYPE = {
    "SchematicPin": "pin",
    "SchematicField": "field",
    "SchematicText": "text",
    "SchematicTextBox": "text_box",
    "SchematicGraphicShape": "graphic",
    "SchematicTable": "table",
    "SchematicImage": "bitmap",
}

#: Attributes on ``SchematicSymbol`` that hold the mandatory fields.
MANDATORY_FIELD_ATTRS = (
    "reference_field",
    "value_field",
    "footprint_field",
    "datasheet_field",
    "description_field",
)

#: Item types that can be created or updated through the symbol editor API.
WRITABLE_ITEM_TYPES = ("pin", "text", "text_box", "graphic")


def normalise_item_type(item_type: str) -> str:
    """Return the canonical name for a symbol item-type filter."""
    value = item_type.strip().lower().replace(" ", "_").replace("-", "_")
    if value.startswith("kot_sch_"):
        value = value.removeprefix("kot_sch_")
    value = _ITEM_TYPE_ALIASES.get(value, value)
    if value not in {"all", *SYMBOL_ITEM_TYPES}:
        supported = ", ".join(("all", *SYMBOL_ITEM_TYPES))
        raise ValueError(
            f"Unsupported item type {item_type!r}; expected one of: {supported}"
        )
    return value


def item_category(item: dict[str, Any]) -> str:
    """Return the summary category for an MCP-facing item dictionary."""
    return _ITEM_CATEGORIES.get(str(item.get("type")), "other")


def item_matches_type(item: dict[str, Any], item_type: str) -> bool:
    """Return whether an item dictionary matches a canonical item-type filter."""
    return item_type == "all" or item.get("type") == item_type


def _raw_item_to_dict(item: AnyMessage, kind: str | None) -> dict[str, Any]:
    """Convert a child item kipy returns as a raw ``Any`` protobuf."""
    result: dict[str, Any] = {"type": _KIND_TO_TYPE.get(kind or "", "other")}

    try:
        proto = unpack_any(item)
    except (NotImplementedError, ValueError):
        return result

    id_value = getattr(getattr(proto, "id", None), "value", None)
    if id_value:
        result["id"] = id_value

    return result


def item_to_dict(item: Any, kind: str | None = None) -> dict[str, Any]:
    """Convert a symbol child item to the MCP-facing dictionary shape."""
    if isinstance(item, SchematicPin):
        return pin_to_dict(item)
    if isinstance(item, SchematicField):
        return field_to_dict(item)
    if isinstance(item, SchematicText):
        return text_to_dict(item)
    if isinstance(item, SchematicTextBox):
        return text_box_to_dict(item)
    if isinstance(item, SchematicGraphicShape):
        return graphic_to_dict(item)
    if isinstance(item, SchematicImage):
        return {
            "type": "bitmap",
            "id": item.id.value,
            "position": point_to_dict(item.position),
            "scale": item.image_scale,
        }
    if isinstance(item, SchematicTable):
        return {
            "type": "table",
            "id": item.id.value,
            "column_count": item.column_count,
        }
    if isinstance(item, AnyMessage):
        return _raw_item_to_dict(item, kind)

    return {"type": "other", "id": getattr(getattr(item, "id", None), "value", None)}


def symbol_definition_to_dict(symbol: SchematicSymbol) -> dict[str, Any]:
    """Convert the symbol-level metadata to the MCP-facing dictionary shape."""
    attributes = symbol.attributes
    return {
        "lib_id": str(symbol.id),
        "type": SchematicSymbolType.Name(symbol.type),
        "unit_count": symbol.unit_count,
        "body_styles": [body_style.name for body_style in symbol.body_style],
        "keywords": symbol.keywords,
        "footprint_filters": list(symbol.footprint_filters),
        "attributes": {
            "exclude_from_simulation": attributes.exclude_from_simulation,
            "exclude_from_bill_of_materials": attributes.exclude_from_bill_of_materials,
            "exclude_from_board": attributes.exclude_from_board,
            "exclude_from_position_files": attributes.exclude_from_position_files,
            "do_not_populate": attributes.do_not_populate,
        },
    }


def symbol_item_dicts(symbol: SchematicSymbol) -> list[dict[str, Any]]:
    """Flatten a symbol definition into mandatory fields and child items.

    Child items keep the unit, body style, and privacy tags from their
    ``SchematicSymbolChild`` wrapper; mandatory fields are common to all units
    and body styles, so their tags are ``None``.
    """
    items: list[dict[str, Any]] = []

    for attribute in MANDATORY_FIELD_ATTRS:
        result = field_to_dict(getattr(symbol, attribute))
        result["unit"] = None
        result["body_style"] = None
        items.append(result)

    for child in symbol.items:
        result = item_to_dict(child.item, kind=child.kind)
        # KiCad writes 0 for "common to all units / body styles"; report both
        # the absent and zero forms as ``None`` so callers see one convention.
        result["unit"] = child.unit or None
        result["body_style"] = child.body_style or None
        result["is_private"] = bool(child.is_private or result.get("is_private", False))
        items.append(result)

    return items


def item_from_spec(spec: dict[str, Any]) -> Any:
    """Create a KiCad symbol item from the MCP-facing item shape.

    Only pins, text, text boxes, and graphics are writable. Symbol fields are
    owned by the parent symbol and cannot be created or updated through the item
    commands, and tables and bitmaps are not supported yet.
    """
    item_type = str(spec.get("type", "")).lower()

    if item_type == "pin":
        return pin_from_spec(spec)
    if item_type == "text":
        return text_from_spec(spec)
    if item_type == "text_box":
        return text_box_from_spec(spec)
    if item_type == "graphic":
        return graphic_from_spec(spec)

    if item_type == "field":
        raise ValueError(
            "symbol fields cannot be created or updated through the IPC API; edit "
            "them in the symbol editor"
        )
    if item_type in {"table", "bitmap"}:
        raise ValueError(f"symbol {item_type} items are read-only through this tool")

    supported = ", ".join(WRITABLE_ITEM_TYPES)
    raise ValueError(
        f"unsupported item type {item_type!r}; expected one of: {supported}"
    )
