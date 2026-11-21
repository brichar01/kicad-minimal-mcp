"""Symbol item write tools."""

from __future__ import annotations

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
from kicad_minimal_mcp.symbol.editor import (
    apply_item_specs,
    delete_items_by_id,
    symbol_editor,
)


@mcp.tool()
def delete_symbol_items(
    item_ids: list[str],
    lib_id: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Delete symbol items by UUID using an atomic IPC commit.

    ``item_ids`` are the ``id`` values returned by :func:`get_symbol_items`.
    The deletion is grouped into one commit and saved to the library entry by
    default. Symbol fields have no UUID in the IPC API, so they cannot be
    addressed here; mandatory fields are not deletable anyway. Every requested
    ID is reported in ``deleted_items`` with the status KiCad returned and
    whether the item is actually gone afterwards.
    """
    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "applied": False,
        "committed": False,
        "connected": False,
        "symbol": None,
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
        editor = symbol_editor(kicad, document)
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
    existing item; specs without an ``id`` are created. When
    ``replace_existing`` is true, all existing non-field items are removed
    first. The edit is grouped into one commit and saved to the library entry
    by default.

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
    assigned. The operation is transactional at the commit level: if validation
    or any IPC command fails before the commit is pushed, the pending commit is
    dropped.
    """
    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "applied": False,
        "committed": False,
        "connected": False,
        "symbol": None,
        "replace_existing": replace_existing,
        "saved": False,
        "removed_count": 0,
        "updated_count": 0,
        "created_count": 0,
        "created_items": [],
        "final_count": 0,
        "final_summary": {},
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
        editor = symbol_editor(kicad, document)
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
