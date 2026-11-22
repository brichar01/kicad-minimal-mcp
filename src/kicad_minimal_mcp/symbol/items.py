"""Symbol item catalog and read dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum

from google.protobuf.any_pb2 import Any as AnyMessage
from kipy.proto.common.types import KiCadObjectType
from kipy.proto.schematic.schematic_types_pb2 import SchematicSymbolType
from kipy.schematic_types import (
    SchematicField,
    SchematicGraphicShape,
    SchematicImage,
    SchematicItem,
    SchematicPin,
    SchematicSymbol,
    SchematicTable,
    SchematicText,
    SchematicTextBox,
)
from kipy.util.proto import unpack_any

from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import mapping, required, text
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.symbol.graphics import (
    GraphicSpec,
    graphic_from_spec,
    graphic_to_dict,
)
from kicad_minimal_mcp.symbol.pins import PinSpec, pin_from_spec, pin_to_dict
from kicad_minimal_mcp.symbol.text import (
    TextBoxSpec,
    TextSpec,
    field_to_dict,
    text_box_from_spec,
    text_box_to_dict,
    text_from_spec,
    text_to_dict,
)
from kicad_minimal_mcp.type_filters import Category, TypeFilter
from kicad_minimal_mcp.units import PointMm


class SymbolItemType(StrEnum):
    BITMAP = "bitmap"
    FIELD = "field"
    GRAPHIC = "graphic"
    OTHER = "other"
    PIN = "pin"
    TABLE = "table"
    TEXT = "text"
    TEXT_BOX = "text_box"


#: Canonical item names mapped to the IPC object type the symbol editor accepts.
SYMBOL_ITEM_TYPES = TypeFilter(
    noun="item type",
    prefix="kot_sch_",
    values={
        SymbolItemType.PIN: KiCadObjectType.KOT_SCH_PIN,
        SymbolItemType.FIELD: KiCadObjectType.KOT_SCH_FIELD,
        SymbolItemType.TEXT: KiCadObjectType.KOT_SCH_TEXT,
        SymbolItemType.TEXT_BOX: KiCadObjectType.KOT_SCH_TEXTBOX,
        SymbolItemType.GRAPHIC: KiCadObjectType.KOT_SCH_SHAPE,
        SymbolItemType.TABLE: KiCadObjectType.KOT_SCH_TABLE,
        SymbolItemType.BITMAP: KiCadObjectType.KOT_SCH_BITMAP,
    },
    aliases={
        "bitmaps": SymbolItemType.BITMAP,
        "fields": SymbolItemType.FIELD,
        "graphics": SymbolItemType.GRAPHIC,
        "image": SymbolItemType.BITMAP,
        "images": SymbolItemType.BITMAP,
        "pins": SymbolItemType.PIN,
        "sch_shape": SymbolItemType.GRAPHIC,
        "shape": SymbolItemType.GRAPHIC,
        "shapes": SymbolItemType.GRAPHIC,
        "tables": SymbolItemType.TABLE,
        "text_boxes": SymbolItemType.TEXT_BOX,
        "textbox": SymbolItemType.TEXT_BOX,
        "textboxes": SymbolItemType.TEXT_BOX,
        "texts": SymbolItemType.TEXT,
    },
    plurals={
        SymbolItemType.PIN: Category.PINS,
        SymbolItemType.FIELD: Category.FIELDS,
        SymbolItemType.TEXT: Category.TEXTS,
        SymbolItemType.TEXT_BOX: Category.TEXT_BOXES,
        SymbolItemType.GRAPHIC: Category.GRAPHICS,
        SymbolItemType.TABLE: Category.TABLES,
        SymbolItemType.BITMAP: Category.BITMAPS,
    },
)

#: Protobuf message names for child items kipy does not wrap yet.
_KIND_TO_TYPE: Mapping[str, SymbolItemType] = {
    "SchematicPin": SymbolItemType.PIN,
    "SchematicField": SymbolItemType.FIELD,
    "SchematicText": SymbolItemType.TEXT,
    "SchematicTextBox": SymbolItemType.TEXT_BOX,
    "SchematicGraphicShape": SymbolItemType.GRAPHIC,
    "SchematicTable": SymbolItemType.TABLE,
    "SchematicImage": SymbolItemType.BITMAP,
}

#: Item types that can be created or updated through the symbol editor API.
WRITABLE_ITEM_TYPES = (
    SymbolItemType.PIN,
    SymbolItemType.TEXT,
    SymbolItemType.TEXT_BOX,
    SymbolItemType.GRAPHIC,
)


@dataclass(frozen=True)
class SymbolItem:
    """A symbol item: its typed identity and tags, plus the payload to show.

    The payload is the JSON form the tools report. Nothing in this package looks
    inside it; the editor works from ``item_type``, ``item_id``, ``unit``, and
    ``body_style``.
    """

    item_type: SymbolItemType
    item_id: ItemId | None
    payload: Payload
    unit: int | None = None
    body_style: int | None = None
    is_private: bool | None = None

    @property
    def category(self) -> Category:
        category = SYMBOL_ITEM_TYPES.plural(self.item_type)
        if category is None:
            return Category.OTHER

        return category

    def to_payload(self) -> Payload:
        result = dict(self.payload)
        result["unit"] = self.unit
        result["body_style"] = self.body_style

        if self.is_private is not None:
            result["is_private"] = self.is_private

        return result


def normalise_item_type(item_type: str) -> SymbolItemType | None:
    return SYMBOL_ITEM_TYPES.normalise(item_type)


def item_matches_type(item: SymbolItem, item_type: SymbolItemType) -> bool:
    """Return whether a symbol item matches a canonical item-type filter."""
    category = SYMBOL_ITEM_TYPES.plural(item_type)
    if category is not None:
        return item.category == category

    return item.item_type == item_type


def item_id_of(item: SchematicItem | AnyMessage) -> ItemId | None:
    if isinstance(item, AnyMessage):
        try:
            proto = unpack_any(item)
        except (NotImplementedError, ValueError):
            return None

        identifier = getattr(getattr(proto, "id", None), "value", None)
    else:
        identifier = getattr(getattr(item, "id", None), "value", None)

    return identifier or None


def _raw_item_to_dict(item: AnyMessage, kind: str | None) -> Payload:
    """Convert a child item kipy returns as a raw ``Any`` protobuf."""
    result: Payload = {"type": str(_KIND_TO_TYPE.get(kind or "", SymbolItemType.OTHER))}

    try:
        proto = unpack_any(item)
    except (NotImplementedError, ValueError):
        return result

    id_value = getattr(getattr(proto, "id", None), "value", None)
    if id_value:
        result["id"] = id_value

    return result


def symbol_item(
    item: SchematicItem | AnyMessage,
    kind: str | None = None,
) -> SymbolItem:
    """Convert a symbol child item into its typed record and payload."""
    if isinstance(item, SchematicPin):
        item_type, payload = SymbolItemType.PIN, pin_to_dict(item)
    elif isinstance(item, SchematicField):
        item_type, payload = SymbolItemType.FIELD, field_to_dict(item)
    elif isinstance(item, SchematicText):
        item_type, payload = SymbolItemType.TEXT, text_to_dict(item)
    elif isinstance(item, SchematicTextBox):
        item_type, payload = SymbolItemType.TEXT_BOX, text_box_to_dict(item)
    elif isinstance(item, SchematicGraphicShape):
        item_type, payload = SymbolItemType.GRAPHIC, graphic_to_dict(item)
    elif isinstance(item, SchematicImage):
        item_type = SymbolItemType.BITMAP
        payload = {
            "type": "bitmap",
            "id": item.id.value,
            "position": PointMm.from_vector(item.position).to_payload(),
            "scale": item.image_scale,
        }
    elif isinstance(item, SchematicTable):
        item_type = SymbolItemType.TABLE
        payload = {
            "type": "table",
            "id": item.id.value,
            "column_count": item.column_count,
        }
    elif isinstance(item, AnyMessage):
        item_type = _KIND_TO_TYPE.get(kind or "", SymbolItemType.OTHER)
        payload = _raw_item_to_dict(item, kind)
    else:
        identifier = item_id_of(item)
        item_type = SymbolItemType.OTHER
        payload = {"type": "other", "id": identifier}

    return SymbolItem(
        item_type=item_type,
        item_id=item_id_of(item),
        payload=payload,
    )


def item_to_dict(item: SchematicItem | AnyMessage, kind: str | None = None) -> Payload:
    return symbol_item(item, kind).payload


def symbol_definition_to_dict(symbol: SchematicSymbol) -> Payload:
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


def _mandatory_fields(symbol: SchematicSymbol) -> tuple[SchematicField, ...]:
    return (
        symbol.reference_field,
        symbol.value_field,
        symbol.footprint_field,
        symbol.datasheet_field,
        symbol.description_field,
    )


def symbol_item_records(symbol: SchematicSymbol) -> list[SymbolItem]:
    """Flatten a symbol definition into mandatory fields and child items.

    Child items keep the unit, body style, and privacy tags from their
    ``SchematicSymbolChild`` wrapper; mandatory fields are common to all units
    and body styles, so their tags are ``None``.
    """
    records = [
        SymbolItem(
            item_type=SymbolItemType.FIELD,
            item_id=None,
            payload=field_to_dict(item),
        )
        for item in _mandatory_fields(symbol)
    ]

    for child in symbol.items:
        record = symbol_item(child.item, kind=child.kind)
        is_private = bool(child.is_private or record.payload.get("is_private", False))
        records.append(
            replace(
                record,
                unit=child.unit or None,
                body_style=child.body_style or None,
                is_private=is_private,
            )
        )

    return records


#: The item specifications a symbol writer accepts.
SymbolItemSpec = PinSpec | TextSpec | TextBoxSpec | GraphicSpec


def spec_item_type(spec: SymbolItemSpec) -> SymbolItemType:
    match spec:
        case PinSpec():
            return SymbolItemType.PIN
        case TextSpec():
            return SymbolItemType.TEXT
        case TextBoxSpec():
            return SymbolItemType.TEXT_BOX

    return SymbolItemType.GRAPHIC


def item_from_spec(spec: SymbolItemSpec) -> SchematicItem:
    match spec:
        case PinSpec():
            return pin_from_spec(spec)
        case TextSpec():
            return text_from_spec(spec)
        case TextBoxSpec():
            return text_box_from_spec(spec)
        case GraphicSpec():
            return graphic_from_spec(spec)

    raise ValueError("unsupported item specification")


def parse_item_spec(data: object) -> SymbolItemSpec:
    """Parse the MCP-facing item shape into a typed specification.

    Only pins, text, text boxes, and graphics are writable. Symbol fields are
    owned by the parent symbol and cannot be created or updated through the item
    commands, and tables and bitmaps are not supported yet.
    """
    values = mapping(data, "item specification")
    kind = text(required(values, "type", "item specification"), "item.type").lower()

    match kind:
        case "pin":
            return PinSpec.parse(values)
        case "text":
            return TextSpec.parse(values)
        case "text_box":
            return TextBoxSpec.parse(values)
        case "graphic":
            return GraphicSpec.parse(values)
        case "field":
            raise ValueError(
                "symbol fields cannot be created or updated through the IPC API; "
                "edit them in the symbol editor"
            )
        case "table" | "bitmap":
            raise ValueError(f"symbol {kind} items are read-only through this tool")

    supported = ", ".join(str(item_type) for item_type in WRITABLE_ITEM_TYPES)
    raise ValueError(f"unsupported item type {kind!r}; expected one of: {supported}")
