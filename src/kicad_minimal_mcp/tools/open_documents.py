"""Open-document discovery tool."""

from __future__ import annotations

from typing import Any

from kipy import KiCad
from kipy.errors import ApiError
from kipy.proto.common import ApiStatusCode

from kicad_minimal_mcp.app import mcp
from kicad_minimal_mcp.documents import (
    DOCUMENT_TYPES,
    document_to_dict,
    normalise_document_type,
)
from kicad_minimal_mcp.results import Payload, ToolResult
from kicad_minimal_mcp.tools.runner import run_tool
from kicad_minimal_mcp.type_filters import ALL_TYPES


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
    result = ToolResult(
        body={
            "document_type": document_type,
            "count": 0,
            "documents": [],
            "unavailable_document_types": [],
        }
    )

    def list_documents(kicad: KiCad) -> None:
        requested = normalise_document_type(document_type)
        if requested is None:
            candidates = list(DOCUMENT_TYPES.items())
            result.body["document_type"] = ALL_TYPES
        else:
            candidates = [(requested, DOCUMENT_TYPES[requested])]
            result.body["document_type"] = str(requested)

        documents: list[Payload] = []
        unavailable: list[str] = []

        for type_name, proto_type in candidates:
            try:
                open_documents = kicad.get_open_documents(proto_type)
            except ApiError as exc:
                # KiCad returns AS_UNHANDLED when no open editor of that type
                # has registered a GetOpenDocuments handler. That is an
                # expected state, not a failure of the whole query.
                if exc.code != ApiStatusCode.AS_UNHANDLED:
                    raise
                unavailable.append(str(type_name))
                continue

            documents.extend(document_to_dict(document) for document in open_documents)

        result.connected = True
        result.body["documents"] = documents
        result.body["count"] = len(documents)
        result.body["unavailable_document_types"] = unavailable

    return run_tool(result, list_documents)
