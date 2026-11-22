"""KiCad open-document metadata and lookup helpers."""

from __future__ import annotations

from enum import StrEnum

from kipy import KiCad
from kipy.proto.common.types import DocumentSpecifier, DocumentType

from kicad_minimal_mcp.identifiers import LibraryId
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.type_filters import TypeFilter


class DocumentTypeName(StrEnum):
    """The canonical document type names the tools accept and report."""

    DRAWING_SHEET = "drawing_sheet"
    FOOTPRINT = "footprint"
    PCB = "pcb"
    PROJECT = "project"
    SCHEMATIC = "schematic"
    SYMBOL = "symbol"


DOCUMENT_TYPES = TypeFilter(
    noun="document type",
    prefix="doctype_",
    values={
        DocumentTypeName.SCHEMATIC: DocumentType.DOCTYPE_SCHEMATIC,
        DocumentTypeName.SYMBOL: DocumentType.DOCTYPE_SYMBOL,
        DocumentTypeName.PCB: DocumentType.DOCTYPE_PCB,
        DocumentTypeName.FOOTPRINT: DocumentType.DOCTYPE_FOOTPRINT,
        DocumentTypeName.DRAWING_SHEET: DocumentType.DOCTYPE_DRAWING_SHEET,
        DocumentTypeName.PROJECT: DocumentType.DOCTYPE_PROJECT,
    },
    aliases={
        "board": DocumentTypeName.PCB,
        "boards": DocumentTypeName.PCB,
        "drawingsheet": DocumentTypeName.DRAWING_SHEET,
        "drawing_sheets": DocumentTypeName.DRAWING_SHEET,
        "footprints": DocumentTypeName.FOOTPRINT,
        "fp": DocumentTypeName.FOOTPRINT,
        "pcbnew": DocumentTypeName.PCB,
        "projects": DocumentTypeName.PROJECT,
        "schematics": DocumentTypeName.SCHEMATIC,
        "symbols": DocumentTypeName.SYMBOL,
    },
)


def normalise_document_type(document_type: str) -> DocumentTypeName | None:
    """Return the canonical name for an open-document type filter."""
    return DOCUMENT_TYPES.normalise(document_type)


def document_to_dict(document: DocumentSpecifier) -> Payload:
    """Convert a DocumentSpecifier protobuf into an MCP-friendly dictionary."""
    result: Payload = {
        "type": DocumentType.Name(document.type),
    }

    identifier = document.WhichOneof("identifier")
    library_id = LibraryId.from_document(document)

    if library_id is not None:
        result["lib_id"] = {
            "library_nickname": library_id.library_nickname,
            "entry_name": library_id.entry_name,
            "lib_id": str(library_id),
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
    lib_id: LibraryId | None,
    *,
    noun: str,
) -> DocumentSpecifier:
    """Find an open library-item document, optionally selected by ``lib_id``."""
    documents = kicad.get_open_documents(document_type)
    if lib_id is None:
        if not documents:
            raise ValueError(f"no {noun} is open in the {noun} editor")
        return documents[0]

    for document in documents:
        if LibraryId.from_document(document) == lib_id:
            return document

    open_documents = [
        str(opened)
        for opened in (LibraryId.from_document(document) for document in documents)
        if opened is not None
    ]
    raise ValueError(
        f"open {noun} {str(lib_id)!r} was not found; open {noun}s: {open_documents}"
    )


def find_footprint_document(
    kicad: KiCad, lib_id: LibraryId | None
) -> DocumentSpecifier:
    """Find an open footprint document, optionally selected by ``lib_id``."""
    return _find_library_document(
        kicad, DocumentType.DOCTYPE_FOOTPRINT, lib_id, noun="footprint"
    )


def find_symbol_document(kicad: KiCad, lib_id: LibraryId | None) -> DocumentSpecifier:
    """Find an open symbol document, optionally selected by ``lib_id``."""
    return _find_library_document(
        kicad, DocumentType.DOCTYPE_SYMBOL, lib_id, noun="symbol"
    )
