"""Identifier types shared by the reader and writer paths."""

from __future__ import annotations

from dataclasses import dataclass

from kipy.proto.common.types import DocumentSpecifier

#: A KiCad item UUID. It is structured, but none of its parts are used here.
ItemId = str


@dataclass(frozen=True)
class LibraryId:
    """A ``Library:Name`` reference to a library symbol or footprint."""

    library_nickname: str
    entry_name: str

    @classmethod
    def parse(cls, value: str) -> LibraryId:
        nickname, separator, entry = value.strip().partition(":")
        complete = bool(separator) and bool(nickname) and bool(entry)
        if not complete:
            raise ValueError(f"library ID {value!r} must be written as 'Library:Name'")

        return cls(nickname, entry)

    @classmethod
    def from_document(cls, document: DocumentSpecifier) -> LibraryId | None:
        if document.WhichOneof("identifier") != "lib_id":
            return None

        lib_id = document.lib_id

        return cls(lib_id.library_nickname, lib_id.entry_name)

    def __str__(self) -> str:
        return f"{self.library_nickname}:{self.entry_name}"
