"""Footprint item type catalog and read/write dispatch."""

from __future__ import annotations

from enum import StrEnum

from kipy.board_types import BoardItem, BoardShape, BoardText, BoardTextBox, Field, Pad
from kipy.proto.common.types import KiCadObjectType

from kicad_minimal_mcp.footprint.graphics import (
    GraphicSpec,
    graphic_from_spec,
    graphic_to_dict,
)
from kicad_minimal_mcp.footprint.pads import PadSpec, pad_from_spec, pad_to_dict
from kicad_minimal_mcp.footprint.text import (
    FieldSpec,
    TextBoxSpec,
    TextSpec,
    field_from_spec,
    field_to_dict,
    text_box_from_spec,
    text_box_to_dict,
    text_from_spec,
    text_to_dict,
)
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.parsing import mapping, required, text
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.type_filters import Category, TypeFilter


class FootprintItemType(StrEnum):
    BARCODE = "barcode"
    DIMENSION = "dimension"
    FIELD = "field"
    GRAPHIC = "graphic"
    GROUP = "group"
    OTHER = "other"
    PAD = "pad"
    TABLE = "table"
    TEXT = "text"
    TEXT_BOX = "text_box"
    ZONE = "zone"


ITEM_TYPES = TypeFilter(
    noun="item type",
    prefix="kot_pcb_",
    values={
        FootprintItemType.PAD: KiCadObjectType.KOT_PCB_PAD,
        FootprintItemType.FIELD: KiCadObjectType.KOT_PCB_FIELD,
        FootprintItemType.TEXT: KiCadObjectType.KOT_PCB_TEXT,
        FootprintItemType.TEXT_BOX: KiCadObjectType.KOT_PCB_TEXTBOX,
        FootprintItemType.GRAPHIC: KiCadObjectType.KOT_PCB_SHAPE,
        FootprintItemType.ZONE: KiCadObjectType.KOT_PCB_ZONE,
        FootprintItemType.TABLE: KiCadObjectType.KOT_PCB_TABLE,
        FootprintItemType.BARCODE: KiCadObjectType.KOT_PCB_BARCODE,
        FootprintItemType.DIMENSION: KiCadObjectType.KOT_PCB_DIMENSION,
        FootprintItemType.GROUP: KiCadObjectType.KOT_PCB_GROUP,
    },
    aliases={
        "barcodes": FootprintItemType.BARCODE,
        "board_shape": FootprintItemType.GRAPHIC,
        "board_shapes": FootprintItemType.GRAPHIC,
        "dimensions": FootprintItemType.DIMENSION,
        "fields": FootprintItemType.FIELD,
        "graphics": FootprintItemType.GRAPHIC,
        "groups": FootprintItemType.GROUP,
        "pads": FootprintItemType.PAD,
        "shape": FootprintItemType.GRAPHIC,
        "shapes": FootprintItemType.GRAPHIC,
        "tables": FootprintItemType.TABLE,
        "text_boxes": FootprintItemType.TEXT_BOX,
        "textbox": FootprintItemType.TEXT_BOX,
        "textboxes": FootprintItemType.TEXT_BOX,
        "texts": FootprintItemType.TEXT,
        "zones": FootprintItemType.ZONE,
    },
    plurals={
        FootprintItemType.PAD: Category.PADS,
        FootprintItemType.FIELD: Category.FIELDS,
        FootprintItemType.TEXT: Category.TEXTS,
        FootprintItemType.TEXT_BOX: Category.TEXT_BOXES,
        FootprintItemType.GRAPHIC: Category.GRAPHICS,
    },
)


def normalise_item_type(item_type: str) -> FootprintItemType | None:
    return ITEM_TYPES.normalise(item_type)


def item_type_of(item: BoardItem) -> FootprintItemType:
    if isinstance(item, Pad):
        return FootprintItemType.PAD
    if isinstance(item, Field):
        return FootprintItemType.FIELD
    if isinstance(item, BoardText):
        return FootprintItemType.TEXT
    if isinstance(item, BoardTextBox):
        return FootprintItemType.TEXT_BOX
    if isinstance(item, BoardShape):
        return FootprintItemType.GRAPHIC

    return FootprintItemType.OTHER


def item_category(item: BoardItem) -> Category:
    category = ITEM_TYPES.plural(item_type_of(item))
    if category is None:
        return Category.OTHER

    return category


def item_matches_type(item: BoardItem, item_type: FootprintItemType) -> bool:
    category = ITEM_TYPES.plural(item_type)
    if category is not None:
        return item_category(item) == category

    return item_type_of(item) == item_type


def item_uuid(item: BoardItem) -> ItemId:
    """Return the UUID KiCad uses to address ``item``.

    Footprint fields are addressed by the UUID of their text, not by ``Field.id``,
    which is the ``FieldId`` enum for mandatory field types.
    """
    if isinstance(item, Field):
        return item.text.id.value

    return item.id.value


def item_to_dict(item: BoardItem) -> Payload:
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

    identifier = getattr(getattr(item, "id", None), "value", None)

    return {"type": str(item_type_of(item)), "id": identifier}


#: The item specifications a footprint writer accepts.
ItemSpec = PadSpec | FieldSpec | TextSpec | TextBoxSpec | GraphicSpec


def item_from_spec(spec: ItemSpec) -> BoardItem:
    match spec:
        case PadSpec():
            return pad_from_spec(spec)
        case FieldSpec():
            return field_from_spec(spec)
        case TextSpec():
            return text_from_spec(spec)
        case TextBoxSpec():
            return text_box_from_spec(spec)
        case GraphicSpec():
            return graphic_from_spec(spec)

    raise ValueError("unsupported item specification")


def parse_item_spec(data: object) -> ItemSpec:
    values = mapping(data, "item specification")
    kind = text(required(values, "type", "item specification"), "item.type").lower()

    match kind:
        case "pad":
            return PadSpec.parse(values)
        case "field":
            return FieldSpec.parse(values)
        case "text":
            return TextSpec.parse(values)
        case "text_box":
            return TextBoxSpec.parse(values)
        case "graphic":
            return GraphicSpec.parse(values)

    raise ValueError(f"unsupported item type {kind!r}")
