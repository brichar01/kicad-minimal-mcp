"""Symbol editor adapter and atomic item transactions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from typing import cast

from kipy import KiCad
from kipy.common_types import SheetPath
from kipy.proto.common.types import DocumentSpecifier, KiCadObjectType
from kipy.schematic import Schematic
from kipy.schematic_types import (
    SchematicField,
    SchematicItem,
    SchematicSymbol,
    SheetInstance,
)

from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.symbol.items import (
    SymbolItem,
    SymbolItemSpec,
    item_from_spec,
    item_to_dict,
    spec_item_type,
    symbol_item_records,
)
from kicad_minimal_mcp.transactions import (
    DeleteSummary,
    WriteSummary,
    apply_in_commit,
    delete_in_commit,
)


class SymbolEditor(Schematic):
    """Wrap an open symbol document in the schematic item API.

    ``Schematic.get_items`` builds a schematic document specifier, which the
    symbol editor handler rejects, so reads are scoped to the symbol document.
    """

    def get_items(
        self,
        types: KiCadObjectType.ValueType
        | Sequence[KiCadObjectType.ValueType]
        | None = None,
        sheet_path: SheetPath | SheetInstance | None = None,
    ) -> Sequence[SchematicItem]:
        # Symbols have no sheet hierarchy, so ``sheet_path`` does not apply.
        return self._get_items(types, self._doc)

    def get_symbol(self) -> SchematicSymbol:
        """Read the open symbol's definition, including its child items.

        The definition is the only view that carries each child's unit and body
        style, so the item readers are built on top of it.
        """
        for item in self.get_items([KiCadObjectType.KOT_LIB_SYMBOL]):
            if isinstance(item, SchematicSymbol):
                return item

        raise RuntimeError("KiCad did not return a symbol definition")


def symbol_editor(kicad: KiCad, document: DocumentSpecifier) -> SymbolEditor:
    return SymbolEditor(kicad._client, document)


def _update_clears_tags(
    target: SymbolItem,
    *,
    multi_unit: bool,
    multi_style: bool,
) -> bool:
    """Return whether updating ``target`` would clear its unit or body style."""
    unit_is_tagged = multi_unit and target.unit
    style_is_tagged = multi_style and target.body_style

    return bool(unit_is_tagged or style_is_tagged)


def _guard_unit_reset(
    target: SymbolItem,
    *,
    multi_unit: bool,
    multi_style: bool,
) -> None:
    """Refuse updates that KiCad would move to another unit or body style.

    Symbol item messages carry no unit or body-style fields, and KiCad swaps the
    freshly deserialized item's tags into the existing one, which clears them to
    "common to all units and body styles". That is harmless for a symbol with a
    single unit and body style, but it would silently reassign items in a
    multi-unit or De Morgan symbol.
    """
    if not _update_clears_tags(target, multi_unit=multi_unit, multi_style=multi_style):
        return

    raise ValueError(
        f"item {target.item_id!r} belongs to unit {target.unit} and body style "
        f"{target.body_style}; KiCad's IPC API clears those tags when an item is "
        "updated, so edit it in the symbol editor instead"
    )


def _check_new_item_tags(spec: SymbolItemSpec) -> None:
    for tag, value in (("unit", spec.unit), ("body_style", spec.body_style)):
        if value in (None, 0):
            continue

        name = tag.replace("_", " ")
        raise ValueError(
            f"KiCad's IPC API cannot assign a new symbol item to a {name}; "
            "created items are common to all units and body styles"
        )


def apply_item_specs(
    editor: SymbolEditor,
    symbol: SchematicSymbol,
    specs: Sequence[SymbolItemSpec],
    *,
    replace_existing: bool = False,
    save: bool = True,
) -> WriteSummary:
    """Apply symbol item specifications in one commit and return change counts.

    ``symbol`` is the definition the editor returned for the open document; the
    caller reads it before the specifications are parsed, so a rejected
    specification leaves the document untouched.
    """
    current = symbol_item_records(symbol)
    by_id = {item.item_id: item for item in current if item.item_id is not None}
    multi_unit = symbol.unit_count > 1
    multi_style = len(symbol.body_style) > 1

    create_items: list[SchematicItem] = []
    update_items: list[SchematicItem] = []

    for spec in specs:
        item = item_from_spec(spec)
        item_id = spec.id

        if item_id is None:
            _check_new_item_tags(spec)
            create_items.append(item)
            continue

        target = by_id.get(item_id)
        if target is None:
            raise ValueError(f"item {item_id!r} is not part of the open symbol")

        item_type = spec_item_type(spec)
        if target.item_type != item_type:
            raise ValueError(
                f"item {item_id!r} is a {target.item_type}, not a {item_type}"
            )

        _guard_unit_reset(target, multi_unit=multi_unit, multi_style=multi_style)
        item.id.value = str(item_id)
        update_items.append(item)

    remove_items: list[SchematicItem] = []
    if replace_existing:
        remove_items = [
            cast("SchematicItem", child.item)
            for child in symbol.items
            if not isinstance(child.item, SchematicField)
        ]

    def commit() -> list[SchematicItem]:
        if remove_items:
            editor.remove_items(remove_items)

        if update_items:
            editor.update_items(update_items)

        if create_items:
            return editor.create_items(create_items)

        return []

    created, saved = apply_in_commit(
        editor,
        "Write symbol items via API",
        commit,
        save=save,
    )

    final_items = symbol_item_records(editor.get_symbol())

    return WriteSummary(
        saved=saved,
        removed_count=len(remove_items),
        updated_count=len(update_items),
        created_count=len(created),
        final_count=len(final_items),
        final_summary=dict(Counter(item.category for item in final_items)),
        created_items=[item_to_dict(item) for item in created],
    )


def delete_items_by_id(
    editor: SymbolEditor,
    item_ids: Sequence[ItemId],
    *,
    save: bool = True,
) -> DeleteSummary:
    """Delete selected symbol items by UUID in one commit.

    Symbol fields have no UUID, so only pins, graphics, text, text boxes, tables,
    and bitmaps can be addressed here.
    """
    report, saved = delete_in_commit(
        editor,
        item_ids,
        "Delete symbol items via API",
        save=save,
    )

    final_items = symbol_item_records(editor.get_symbol())
    remaining = {item.item_id for item in final_items if item.item_id is not None}
    deleted_items = [
        replace(deletion, removed=deletion.item_id not in remaining)
        for deletion in report
    ]

    return DeleteSummary(
        saved=saved,
        item_ids=item_ids,
        deleted_items=deleted_items,
        final_count=len(final_items),
        final_summary=dict(Counter(item.category for item in final_items)),
    )
