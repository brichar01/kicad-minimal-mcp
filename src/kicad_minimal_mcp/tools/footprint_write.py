"""Footprint item write tool."""

from __future__ import annotations

from typing import Any

from kipy.errors import ApiError, ConnectionError
from kipy.proto.common import ApiStatusCode

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.documents import document_to_dict, find_footprint_document
from kicad_minimal_mcp.footprint.editor import (
    apply_item_specs,
    delete_items_by_id,
    footprint_editor,
)
from kicad_minimal_mcp.results import (
    STATUS_ERROR,
    STATUS_FOOTPRINT_UNAVAILABLE,
    STATUS_INVALID_REQUEST,
    STATUS_KICAD_ERROR,
    STATUS_KICAD_UNAVAILABLE,
    complete_result,
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
    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "applied": False,
        "committed": False,
        "connected": False,
        "footprint": None,
        "item_ids": item_ids,
        "saved": False,
        "removed_count": 0,
        "not_removed_count": 0,
        "deleted_items": [],
        "final_count": 0,
        "final_summary": {},
        "error": None,
    }

    kicad = kicad_client()

    try:
        try:
            document = find_footprint_document(kicad, lib_id)
        except ValueError as exc:
            result["error"] = str(exc)
            return complete_result(
                result,
                status=STATUS_FOOTPRINT_UNAVAILABLE,
                retryable=True,
            )
        except ApiError as exc:
            if exc.code != ApiStatusCode.AS_UNHANDLED:
                raise
            result["connected"] = True
            result["error"] = "no footprint editor is open in KiCad"
            return complete_result(
                result,
                status=STATUS_FOOTPRINT_UNAVAILABLE,
                retryable=True,
            )

        result["connected"] = True
        result["footprint"] = document_to_dict(document)
        editor = footprint_editor(kicad, document)
        result.update(delete_items_by_id(editor, item_ids, save=save))

    except ValueError as exc:
        result["error"] = str(exc)
        return complete_result(result, status=STATUS_INVALID_REQUEST)
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
    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "applied": False,
        "committed": False,
        "connected": False,
        "footprint": None,
        "replace_existing": replace_existing,
        "saved": False,
        "removed_count": 0,
        "updated_count": 0,
        "created_count": 0,
        "final_count": 0,
        "final_summary": {},
        "error": None,
    }

    kicad = kicad_client()

    try:
        try:
            document = find_footprint_document(kicad, lib_id)
        except ValueError as exc:
            result["error"] = str(exc)
            return complete_result(
                result,
                status=STATUS_FOOTPRINT_UNAVAILABLE,
                retryable=True,
            )
        except ApiError as exc:
            if exc.code != ApiStatusCode.AS_UNHANDLED:
                raise
            result["connected"] = True
            result["error"] = "no footprint editor is open in KiCad"
            return complete_result(
                result,
                status=STATUS_FOOTPRINT_UNAVAILABLE,
                retryable=True,
            )

        result["connected"] = True
        result["footprint"] = document_to_dict(document)
        editor = footprint_editor(kicad, document)
        result.update(
            apply_item_specs(
                editor,
                items,
                replace_existing=replace_existing,
                save=save,
            )
        )

    except ValueError as exc:
        result["error"] = str(exc)
        return complete_result(result, status=STATUS_INVALID_REQUEST)
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
