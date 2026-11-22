"""Symbol item read tool."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kipy import KiCad

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.documents import document_to_dict, find_symbol_document
from kicad_minimal_mcp.results import Status, ToolResult
from kicad_minimal_mcp.symbol.editor import symbol_editor
from kicad_minimal_mcp.symbol.items import (
    item_matches_type,
    normalise_item_type,
    symbol_definition_to_dict,
    symbol_item_records,
)
from kicad_minimal_mcp.tools.runner import (
    ToolError,
    open_document,
    requested_library_id,
    run_tool,
)
from kicad_minimal_mcp.type_filters import ALL_TYPES, summary_payload


@mcp.tool()
def get_symbol_items(
    lib_id: str | None = None,
    item_type: str = "all",
    item_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Read the elements of an open symbol in the symbol editor.

    ``lib_id`` optionally selects a symbol as ``Library:Name``. If omitted, the
    single open symbol is used. ``item_type`` accepts ``all`` (the default),
    ``pin``, ``field``, ``text``, ``text_box``, ``graphic``, ``table``, or
    ``bitmap``; plural and ``KOT_SCH_*`` names are also accepted. Graphics
    include segments, arcs, circles, rectangles, polygons, beziers, ellipses,
    and ellipse arcs.

    ``item_ids`` optionally restricts the read to specific item UUIDs.

    The symbol definition is read as a whole, so every item carries the
    ``unit`` and ``body_style`` it belongs to (``null`` means common to all
    units or body styles; KiCad's explicit zero is reported the same way).
    Positions and sizes are returned in millimetres in
    the symbol definition's local coordinate frame, as reported by the IPC API.
    Mandatory fields (Reference, Value, Footprint, Datasheet, Description) are
    returned alongside the other items with their ``field_id``. This never
    raises for an unavailable KiCad instance; inspect the ``connected`` field in
    the result instead.
    """
    result = ToolResult(
        body={
            "symbol": None,
            "definition": None,
            "item_type": item_type,
            "item_id": item_ids,
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
            find_symbol_document,
            requested_library_id(lib_id),
            noun="symbol",
            unavailable_status=Status.SYMBOL_UNAVAILABLE,
        )
        result.connected = True
        result.body["symbol"] = document_to_dict(document)

        # kicad-python has no symbol-editor wrapper yet. The adapter scopes the
        # shared editor commands to the symbol document.
        symbol = symbol_editor(kicad, document).get_symbol()
        result.body["definition"] = symbol_definition_to_dict(symbol)

        records = symbol_item_records(symbol)
        if requested_type is not None:
            records = [
                record
                for record in records
                if item_matches_type(record, requested_type)
            ]
        if item_ids is not None:
            wanted = set(item_ids)
            records = [record for record in records if record.item_id in wanted]

        items = [record.to_payload() for record in records]
        result.body["items"] = items
        result.body["count"] = len(items)
        result.body["summary"] = summary_payload(
            Counter(record.category for record in records)
        )

    return run_tool(result, read)
