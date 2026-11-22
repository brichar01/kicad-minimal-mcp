"""Footprint item write tools."""

from __future__ import annotations

from typing import Any

from kipy import KiCad

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.documents import document_to_dict, find_footprint_document
from kicad_minimal_mcp.footprint.editor import (
    apply_item_specs,
    delete_items_by_id,
    footprint_editor,
)
from kicad_minimal_mcp.footprint.items import parse_item_spec
from kicad_minimal_mcp.results import Status, ToolResult
from kicad_minimal_mcp.tools.runner import (
    open_document,
    requested_library_id,
    run_tool,
)


@mcp.tool()
def delete_footprint_items(
    item_ids: list[str],
    lib_id: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Delete footprint items by UUID using an atomic IPC commit.

    ``item_ids`` are the ``id`` values returned by :func:`get_footprint_items`.
    The deletion is grouped into one commit and saved to the library entry by
    default. Mandatory footprint fields cannot be deleted; KiCad rejects those
    deletions at the IPC layer. Every requested ID is reported in
    ``deleted_items`` with the status KiCad returned and whether the item is
    actually gone afterwards, because a field can report ``IDS_OK`` and still
    remain in the footprint.
    """
    result = ToolResult(
        body={
            "applied": False,
            "committed": False,
            "footprint": None,
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
            find_footprint_document,
            requested_library_id(lib_id),
            noun="footprint",
            unavailable_status=Status.FOOTPRINT_UNAVAILABLE,
        )
        result.connected = True
        result.body["footprint"] = document_to_dict(document)

        editor = footprint_editor(kicad, document)
        result.body.update(delete_items_by_id(editor, item_ids, save=save).to_payload())

    return run_tool(result, delete)


@mcp.tool()
def write_footprint_items(
    items: list[dict[str, Any]],
    lib_id: str | None = None,
    replace_existing: bool = False,
    save: bool = True,
) -> dict[str, Any]:
    """Write items into an open footprint using an atomic IPC commit.

    ``items`` uses the same shape as the ``items`` returned by
    :func:`get_footprint_items`. Supported item types are ``pad``, ``field``,
    ``text``, ``text_box``, and ``graphic`` (segment, arc, circle, rectangle, or
    bezier). Existing mandatory fields are updated by ``field_id`` or, when no
    ``field_id`` is given, by ``name``; the KiCad field ids are 1 Reference,
    2 Value, 4 Datasheet, and 5 Description. ``USER`` fields use id 0. Other
    specs that include an ``id`` update that existing item; specs without an
    ``id`` are created with new UUIDs. Pad ``copper_layers`` entries accept
    ``shape`` (``PSS_CIRCLE``, ``PSS_RECTANGLE``, ``PSS_OVAL``, ``PSS_ROUNDRECT``,
    ``PSS_CHAMFEREDRECT``, ``PSS_TRAPEZOID``, ``PSS_CUSTOM``), ``size``,
    ``offset``, and ``corner_rounding_ratio`` for the rect shapes. When
    ``replace_existing`` is true, all existing non-field items are removed first.
    The edit is grouped into one commit and saved to the library entry by default.

    The operation is transactional at the commit level: if validation or any
    IPC command fails before the commit is pushed, the pending commit is dropped.
    """
    result = ToolResult(
        body={
            "applied": False,
            "committed": False,
            "footprint": None,
            "replace_existing": replace_existing,
            "saved": False,
            "removed_count": 0,
            "updated_count": 0,
            "created_count": 0,
            "final_count": 0,
            "final_summary": {},
        }
    )

    def write(kicad: KiCad) -> None:
        document = open_document(
            kicad,
            find_footprint_document,
            requested_library_id(lib_id),
            noun="footprint",
            unavailable_status=Status.FOOTPRINT_UNAVAILABLE,
        )
        result.connected = True
        result.body["footprint"] = document_to_dict(document)

        specs = [parse_item_spec(item) for item in items]
        editor = footprint_editor(kicad, document)
        result.body.update(
            apply_item_specs(
                editor,
                specs,
                replace_existing=replace_existing,
                save=save,
            ).to_payload()
        )

    return run_tool(result, write)
