"""Footprint item read tool."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kipy.errors import ApiError, ConnectionError
from kipy.proto.common import ApiStatusCode
from kipy.proto.common.types import KIID

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.documents import document_to_dict, find_footprint_document
from kicad_minimal_mcp.footprint.editor import footprint_editor
from kicad_minimal_mcp.footprint.items import (
    ITEM_TYPES,
    item_category,
    item_matches_type,
    item_to_dict,
    normalise_item_type,
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
    try:
        requested_type = normalise_item_type(item_type)
    except ValueError as exc:
        return complete_result(
            {
                "ok": False,
                "status": STATUS_INVALID_REQUEST,
                "retryable": False,
                "connected": False,
                "footprint": None,
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
                "footprint": None,
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
        "footprint": None,
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

        # kicad-python has no footprint-editor wrapper yet. The Board wrapper
        # provides the shared GetItems implementation for any editor document.
        editor = footprint_editor(kicad, document)
        if item_ids is not None:
            items = list(
                editor.get_items_by_id(
                    [KIID(value=str(item_id)) for item_id in item_ids]
                )
            )
            items = [item for item in items if item_matches_type(item, requested_type)]
        else:
            proto_type = None if requested_type == "all" else ITEM_TYPES[requested_type]
            items = list(editor.get_items(proto_type))
        result["items"] = [item_to_dict(item) for item in items]
        result["count"] = len(result["items"])
        result["summary"] = dict(Counter(item_category(item) for item in items))

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
