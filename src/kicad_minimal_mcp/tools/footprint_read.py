"""Footprint item read tool."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kipy import KiCad
from kipy.proto.common.types import KIID

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.documents import document_to_dict, find_footprint_document
from kicad_minimal_mcp.footprint.editor import footprint_editor
from kicad_minimal_mcp.footprint.items import (
    ITEM_TYPES,
    item_category,
    item_matches_type,
    item_to_dict,
    normalise_item_type,
)
from kicad_minimal_mcp.results import Status, ToolResult
from kicad_minimal_mcp.tools.runner import (
    ToolError,
    open_document,
    requested_library_id,
    run_tool,
)
from kicad_minimal_mcp.type_filters import ALL_TYPES, summary_payload


@mcp.tool()
def get_footprint_items(
    lib_id: str | None = None,
    item_type: str = "all",
    item_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Read the elements of an open footprint in the footprint editor.

    ``lib_id`` optionally selects a footprint as ``Library:Name``. If omitted, the
    single open footprint is used. ``item_type`` accepts ``all`` (the default),
    ``pad``, ``field``, ``text``, ``text_box``, ``graphic``, ``zone``, ``table``,
    ``barcode``, ``dimension``, or ``group``; plural and ``KOT_PCB_*`` names are
    also accepted. Graphics include segments, arcs, circles, rectangles,
    polygons, and beziers.

    ``item_ids`` optionally restricts the read to specific item UUIDs, using the
    ``get_items_by_id`` IPC command. When both filters are supplied, only items
    matching ``item_type`` are returned.

    Positions and sizes are returned in millimetres, relative to the footprint
    origin. Pads include their copper-layer shapes and sizes, padstack layers,
    and drill data when present. Fields include their text, visibility, layer,
    and text attributes. This never raises for an unavailable KiCad instance;
    inspect the ``connected`` field in the result instead.
    """
    result = ToolResult(
        body={
            "footprint": None,
            "item_type": item_type,
            "item_ids": item_ids,
            "unit": "mm",
            "count": 0,
            "summary": {},
            "items": [],
        }
    )

    def read(kicad: KiCad) -> None:
        requested_type = normalise_item_type(item_type)
        if requested_type is None:
            result.body["item_type"] = ALL_TYPES
        else:
            result.body["item_type"] = str(requested_type)

        if item_ids is not None and not item_ids:
            raise ToolError("item_ids must not be empty", status=Status.INVALID_REQUEST)

        document = open_document(
            kicad,
            find_footprint_document,
            requested_library_id(lib_id),
            noun="footprint",
            unavailable_status=Status.FOOTPRINT_UNAVAILABLE,
        )
        result.connected = True
        result.body["footprint"] = document_to_dict(document)

        # kicad-python has no footprint-editor wrapper yet. The Board wrapper
        # provides the shared GetItems implementation for any editor document.
        editor = footprint_editor(kicad, document)

        if item_ids is not None:
            wanted = [KIID(value=str(item_id)) for item_id in item_ids]
            items = list(editor.get_items_by_id(wanted))
            if requested_type is not None:
                items = [
                    item for item in items if item_matches_type(item, requested_type)
                ]
        else:
            proto_type = None if requested_type is None else ITEM_TYPES[requested_type]
            items = list(editor.get_items(proto_type))

        result.body["items"] = [item_to_dict(item) for item in items]
        result.body["count"] = len(items)
        result.body["summary"] = summary_payload(
            Counter(item_category(item) for item in items)
        )

    return run_tool(result, read)
