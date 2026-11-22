"""Symbol item write tools."""

from __future__ import annotations

from typing import Any

from kipy import KiCad

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.documents import document_to_dict, find_symbol_document
from kicad_minimal_mcp.results import Status, ToolResult
from kicad_minimal_mcp.symbol.editor import (
    apply_item_specs,
    delete_items_by_id,
    symbol_editor,
)
from kicad_minimal_mcp.symbol.items import parse_item_spec
from kicad_minimal_mcp.tools.runner import (
    open_document,
    requested_library_id,
    run_tool,
)


@mcp.tool()
def delete_symbol_items(
    item_ids: list[str],
    lib_id: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Delete symbol items by UUID using an atomic IPC commit.

    ``item_ids`` are the ``id`` values returned by :func:`get_symbol_items`.
    Symbol fields have no UUID in the IPC API, so they cannot be addressed here;
    mandatory fields are not deletable anyway. Every requested ID is reported in
    ``deleted_items`` with the status KiCad returned and whether the item is
    actually gone afterwards.
    """
    result = ToolResult(
        body={
            "applied": False,
            "committed": False,
            "symbol": None,
            "item_ids": item_ids,
            "saved": False,
            "removed_count": 0,
            "not_removed_count": 0,
            "deleted_items": [],
            "final_count": 0,
            "final_summary": {},
        }
    )

    def delete(kicad: KiCad) -> None:
        document = open_document(
            kicad,
            find_symbol_document,
            requested_library_id(lib_id),
            noun="symbol",
            unavailable_status=Status.SYMBOL_UNAVAILABLE,
        )
        result.connected = True
        result.body["symbol"] = document_to_dict(document)

        editor = symbol_editor(kicad, document)
        result.body.update(delete_items_by_id(editor, item_ids, save=save).to_payload())

    return run_tool(result, delete)


@mcp.tool()
def write_symbol_items(
    items: list[dict[str, Any]],
    lib_id: str | None = None,
    replace_existing: bool = False,
    save: bool = True,
) -> dict[str, Any]:
    """Write items into an open symbol using an atomic IPC commit.

    ``items`` uses the same shape as the ``items`` returned by
    :func:`get_symbol_items`. Writable item types are ``pin``, ``text``,
    ``text_box``, and ``graphic`` (arc, circle, rectangle, bezier, polygon,
    ellipse, or ellipse arc; symbol graphics have no segment type, so use a
    two-point polygon for a line). Specs that include an ``id`` update that
    existing item; specs without an ``id`` are created.

    Some changes are not possible through the current IPC API and are refused
    with an ``invalid_request`` result rather than applied silently:

    - Fields are read-only, because KiCad rejects field create/update commands.
    - Tables and bitmaps are read-only here.
    - New items cannot be assigned a ``unit`` or ``body_style``; they are common
      to all units and body styles.
    - Updating an item that belongs to a specific unit or body style in a
      multi-unit or multi-body-style symbol is refused, because KiCad clears
      those tags when an item is updated. Edit such items in the symbol editor.
      Common items (``unit``/``body_style`` of ``null`` or ``0``) can be updated.

    ``created_items`` reports the items KiCad created, including the UUIDs it
    assigned.
    """
    result = ToolResult(
        body={
            "applied": False,
            "committed": False,
            "symbol": None,
            "replace_existing": replace_existing,
            "saved": False,
            "removed_count": 0,
            "updated_count": 0,
            "created_count": 0,
            "created_items": [],
            "final_count": 0,
            "final_summary": {},
        }
    )

    def write(kicad: KiCad) -> None:
        document = open_document(
            kicad,
            find_symbol_document,
            requested_library_id(lib_id),
            noun="symbol",
            unavailable_status=Status.SYMBOL_UNAVAILABLE,
        )
        result.connected = True
        result.body["symbol"] = document_to_dict(document)

        editor = symbol_editor(kicad, document)
        symbol = editor.get_symbol()

        specs = [parse_item_spec(item) for item in items]
        result.body.update(
            apply_item_specs(
                editor,
                symbol,
                specs,
                replace_existing=replace_existing,
                save=save,
            ).to_payload()
        )

    return run_tool(result, write)
