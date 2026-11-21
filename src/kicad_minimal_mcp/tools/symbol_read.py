"""Symbol item read tool."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kipy.errors import ApiError, ConnectionError
from kipy.proto.common import ApiStatusCode

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.documents import document_to_dict, find_symbol_document
from kicad_minimal_mcp.results import (
    STATUS_ERROR,
    STATUS_INVALID_REQUEST,
    STATUS_KICAD_ERROR,
    STATUS_KICAD_UNAVAILABLE,
    STATUS_SYMBOL_UNAVAILABLE,
    complete_result,
)
from kicad_minimal_mcp.symbol.editor import symbol_editor
from kicad_minimal_mcp.symbol.items import (
    item_category,
    item_matches_type,
    normalise_item_type,
    symbol_definition_to_dict,
    symbol_item_dicts,
)


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
    try:
        requested_type = normalise_item_type(item_type)
    except ValueError as exc:
        return complete_result(
            {
                "ok": False,
                "status": STATUS_INVALID_REQUEST,
                "retryable": False,
                "connected": False,
                "symbol": None,
                "definition": None,
                "item_type": item_type,
                "item_ids": item_ids,
                "unit": "mm",
                "count": 0,
                "summary": {},
                "items": [],
                "error": str(exc),
            },
            status=STATUS_INVALID_REQUEST,
        )

    if item_ids is not None and not item_ids:
        return complete_result(
            {
                "ok": False,
                "status": STATUS_INVALID_REQUEST,
                "retryable": False,
                "connected": False,
                "symbol": None,
                "definition": None,
                "item_type": requested_type,
                "item_ids": item_ids,
                "unit": "mm",
                "count": 0,
                "summary": {},
                "items": [],
                "error": "item_ids must not be empty",
            },
            status=STATUS_INVALID_REQUEST,
        )

    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "connected": False,
        "symbol": None,
        "definition": None,
        "item_type": requested_type,
        "item_ids": item_ids,
        "unit": "mm",
        "count": 0,
        "summary": {},
        "items": [],
        "error": None,
    }

    kicad = kicad_client()

    try:
        try:
            document = find_symbol_document(kicad, lib_id)
        except ValueError as exc:
            result["error"] = str(exc)
            return complete_result(
                result,
                status=STATUS_SYMBOL_UNAVAILABLE,
                retryable=True,
            )
        except ApiError as exc:
            if exc.code != ApiStatusCode.AS_UNHANDLED:
                raise
            result["connected"] = True
            result["error"] = "no symbol editor is open in KiCad"
            return complete_result(
                result,
                status=STATUS_SYMBOL_UNAVAILABLE,
                retryable=True,
            )

        result["connected"] = True
        result["symbol"] = document_to_dict(document)

        # kicad-python has no symbol-editor wrapper yet. The adapter scopes the
        # shared editor commands to the symbol document.
        symbol = symbol_editor(kicad, document).get_symbol()
        result["definition"] = symbol_definition_to_dict(symbol)

        items = symbol_item_dicts(symbol)
        if requested_type != "all":
            items = [item for item in items if item_matches_type(item, requested_type)]
        if item_ids is not None:
            wanted = set(item_ids)
            items = [item for item in items if item.get("id") in wanted]

        result["items"] = items
        result["count"] = len(items)
        result["summary"] = dict(Counter(item_category(item) for item in items))

    except ConnectionError as exc:
        result["error"] = str(exc)
        return complete_result(
            result,
            status=STATUS_KICAD_UNAVAILABLE,
            retryable=True,
        )
    except ApiError as exc:
        result["error"] = str(exc)
        return complete_result(result, status=STATUS_KICAD_ERROR)
    except Exception as exc:  # noqa: BLE001 - defensive at the MCP boundary
        result["error"] = f"{type(exc).__name__}: {exc}"
        return complete_result(result, status=STATUS_ERROR)

    return complete_result(result)
