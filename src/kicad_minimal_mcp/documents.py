"""KiCad open-document metadata and lookup helpers."""

from __future__ import annotations

from typing import Any

from kipy import KiCad
from kipy.proto.common.types import DocumentType

DOCUMENT_TYPES = {
    "schematic": DocumentType.DOCTYPE_SCHEMATIC,
    "symbol": DocumentType.DOCTYPE_SYMBOL,
    "pcb": DocumentType.DOCTYPE_PCB,
    "footprint": DocumentType.DOCTYPE_FOOTPRINT,
    "drawing_sheet": DocumentType.DOCTYPE_DRAWING_SHEET,
    "project": DocumentType.DOCTYPE_PROJECT,
}

_DOCUMENT_TYPE_ALIASES = {
    "board": "pcb",
    "boards": "pcb",
    "pcbnew": "pcb",
    "footprints": "footprint",
    "fp": "footprint",
    "schematics": "schematic",
    "symbols": "symbol",
    "drawingsheet": "drawing_sheet",
    "drawing-sheet": "drawing_sheet",
    "drawing_sheets": "drawing_sheet",
    "projects": "project",
}


def normalise_document_type(document_type: str) -> str:
    """Return the canonical name for an open-document type filter."""
    value = document_type.strip().lower().replace(" ", "_").replace("-", "_")
    if value.startswith("doctype_"):
        value = value.removeprefix("doctype_")

    value = _DOCUMENT_TYPE_ALIASES.get(value, value)
    if value not in {"all", *DOCUMENT_TYPES}:
        supported = ", ".join(("all", *DOCUMENT_TYPES))
        raise ValueError(
            f"Unsupported document type {document_type!r}; expected one of: {supported}"
        )
    return value


def document_to_dict(document: Any) -> dict[str, Any]:
    """Convert a DocumentSpecifier protobuf into an MCP-friendly dictionary."""
    result: dict[str, Any] = {
        "type": DocumentType.Name(document.type),
    }

    identifier = document.WhichOneof("identifier")
    if identifier == "lib_id":
        lib_id = document.lib_id
        result["lib_id"] = {
            "library_nickname": lib_id.library_nickname,
            "entry_name": lib_id.entry_name,
            "lib_id": f"{lib_id.library_nickname}:{lib_id.entry_name}",
        }
    elif identifier == "sheet_path":
        sheet_path = document.sheet_path
        result["sheet_path"] = {
            "path": [kiid.value for kiid in sheet_path.path],
            "path_human_readable": sheet_path.path_human_readable,
        }
    elif identifier == "board_filename":
        result["board_filename"] = document.board_filename

    if document.HasField("project"):
        result["project"] = {
            "name": document.project.name,
            "path": document.project.path,
        }

    return result


def _find_library_document(
    kicad: KiCad,
    document_type: DocumentType.ValueType,
    lib_id: str | None,
    *,
    noun: str,
) -> Any:
    """Find an open library-item document, optionally selected by ``lib_id``."""
    documents = kicad.get_open_documents(document_type)
    if lib_id is None:
        if not documents:
            raise ValueError(f"no {noun} is open in the {noun} editor")
        return documents[0]

    wanted = lib_id.strip()
    for document in documents:
        if document.WhichOneof("identifier") != "lib_id":
            continue
        current = f"{document.lib_id.library_nickname}:{document.lib_id.entry_name}"
        if current == wanted:
            return document

    available = [
        f"{document.lib_id.library_nickname}:{document.lib_id.entry_name}"
        for document in documents
        if document.WhichOneof("identifier") == "lib_id"
    ]
    raise ValueError(f"open {noun} {wanted!r} was not found; open {noun}s: {available}")


def find_footprint_document(kicad: KiCad, lib_id: str | None) -> Any:
    """Find an open footprint document, optionally selected by ``lib_id``."""
    return _find_library_document(
        kicad, DocumentType.DOCTYPE_FOOTPRINT, lib_id, noun="footprint"
    )


def find_symbol_document(kicad: KiCad, lib_id: str | None) -> Any:
    """Find an open symbol document, optionally selected by ``lib_id``."""
    return _find_library_document(
        kicad, DocumentType.DOCTYPE_SYMBOL, lib_id, noun="symbol"
    )
