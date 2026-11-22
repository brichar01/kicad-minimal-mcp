"""Canonical names for the type filters the MCP tools accept.

Each filter table stays with the module that owns it: document types with
``documents``, footprint item types with ``footprint.items``, and symbol item
types with ``symbol.items``. This module holds the normalisation they share, so
``pcbnew``, ``KOT_PCB_PAD``, and ``pads`` all resolve the same way, and so does
``DOCTYPE_SYMBOL`` against ``symbols``.
"""

from __future__ import annotations

from collections.abc import ItemsView, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

ALL_TYPES = "all"


class Category(StrEnum):
    """The plural categories the per-item summaries count."""

    BITMAPS = "bitmaps"
    FIELDS = "fields"
    GRAPHICS = "graphics"
    OTHER = "other"
    PADS = "pads"
    PINS = "pins"
    TABLES = "tables"
    TEXTS = "texts"
    TEXT_BOXES = "text_boxes"


@dataclass(frozen=True)
class TypeFilter[TypeNameT: StrEnum, ValueT]:
    """A filterable type table, the spellings that alias it, and its plurals."""

    noun: str
    prefix: str
    values: Mapping[TypeNameT, ValueT]
    aliases: Mapping[str, TypeNameT]
    plurals: Mapping[TypeNameT, Category] = field(default_factory=dict)
    names: Mapping[str, TypeNameT] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        names = {str(name): name for name in self.values}
        names.update(self.aliases)
        object.__setattr__(self, "names", names)

    def normalise(self, name: str) -> TypeNameT | None:
        """Return the canonical type for a user filter, or ``None`` for all types."""
        value = self._simplify(name)
        if value == ALL_TYPES:
            return None

        canonical = self.names.get(value)
        if canonical is not None:
            return canonical

        supported = ", ".join([ALL_TYPES, *(str(item) for item in self.values)])
        raise ValueError(
            f"Unsupported {self.noun} {name!r}; expected one of: {supported}"
        )

    def plural(self, item_type: TypeNameT) -> Category | None:
        """Return the summary category for a canonical item type."""
        return self.plurals.get(item_type)

    def items(self) -> ItemsView[TypeNameT, ValueT]:
        """Return the canonical name and IPC value pairs."""
        return self.values.items()

    def __getitem__(self, name: TypeNameT) -> ValueT:
        return self.values[name]

    def _simplify(self, name: str) -> str:
        value = name.strip().lower().replace(" ", "_").replace("-", "_")

        return value.removeprefix(self.prefix)


def summary_payload(counts: Mapping[Category, int]) -> dict[str, int]:
    """Return the JSON summary of per-category item counts."""
    return {str(category): count for category, count in counts.items()}
