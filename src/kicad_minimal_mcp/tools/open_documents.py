"""Open-document discovery tool."""

from __future__ import annotations

from typing import Any

from kipy.errors import ApiError, ConnectionError
from kipy.proto.common import ApiStatusCode

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.documents import (
    DOCUMENT_TYPES,
    document_to_dict,
    normalise_document_type,
)
from kicad_minimal_mcp.results import (
    STATUS_ERROR,
    STATUS_INVALID_REQUEST,
    STATUS_KICAD_ERROR,
    STATUS_KICAD_UNAVAILABLE,
    complete_result,
)


@mcp.tool()
def get_open_documents(document_type: str = "all") -> dict[str, Any]:
    """List documents currently open in KiCad.

    ``document_type`` accepts ``all`` (the default), ``pcb``, ``schematic``,
    ``symbol``, ``footprint``, ``drawing_sheet``, or ``project``. The
    ``DOCTYPE_*`` enum names used by the IPC API are also accepted. Footprint
    documents are identified by their ``lib_id``; use that specifier with the
    footprint item-editing commands.

    Not every document type has a handler registered in every KiCad state; for
    example, footprint documents are only discoverable while the footprint
    editor is open. Types that KiCad cannot handle are listed in
    ``unavailable_document_types`` instead of failing the whole request.

    This never raises for an unavailable KiCad instance; inspect the
    ``connected`` field in the result instead.
    """
    try:
        requested_type = normalise_document_type(document_type)
    except ValueError as exc:
        return complete_result(
            {
                "ok": False,
                "status": STATUS_INVALID_REQUEST,
                "retryable": False,
                "connected": False,
                "document_type": document_type,
                "count": 0,
                "documents": [],
                "unavailable_document_types": [],
                "error": str(exc),
            },
            status=STATUS_INVALID_REQUEST,
        )

    result: dict[str, Any] = {
        "ok": False,
        "status": "ok",
        "retryable": False,
        "connected": False,
        "document_type": requested_type,
        "count": 0,
        "documents": [],
        "unavailable_document_types": [],
        "error": None,
    }

    kicad = kicad_client()

    try:
        types = (
            DOCUMENT_TYPES.items()
            if requested_type == "all"
            else [(requested_type, DOCUMENT_TYPES[requested_type])]
        )
        documents: list[dict[str, Any]] = []
        for type_name, proto_type in types:
            try:
                open_documents = kicad.get_open_documents(proto_type)
            except ApiError as exc:
                # KiCad returns AS_UNHANDLED when no open editor of that type
                # has registered a GetOpenDocuments handler. That is an
                # expected state, not a failure of the whole query.
                if exc.code != ApiStatusCode.AS_UNHANDLED:
                    raise
                result["unavailable_document_types"].append(type_name)
                continue

            documents.extend(document_to_dict(document) for document in open_documents)
        result["connected"] = True
        result["documents"] = documents
        result["count"] = len(documents)

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
