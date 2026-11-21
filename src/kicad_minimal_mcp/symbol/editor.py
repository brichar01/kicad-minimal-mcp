"""Symbol editor adapter and atomic item transactions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any, cast

from kipy import KiCad
from kipy.proto.common.commands import editor_commands_pb2
from kipy.proto.common.types import KIID, KiCadObjectType
from kipy.schematic import Schematic
from kipy.schematic_types import SchematicField, SchematicSymbol

from kicad_minimal_mcp.symbol.items import (
    item_category,
    item_from_spec,
    item_to_dict,
    symbol_item_dicts,
)


class SymbolEditor(Schematic):
    """Wrap an open symbol document in the schematic item API.

    ``Schematic.get_items`` builds a schematic document specifier, which the
    symbol editor handler rejects, so reads are scoped to the symbol document.
    """

    def get_items(self, types: Any = None, sheet_path: Any = None) -> Sequence[Any]:
        # Symbols have no sheet hierarchy, so ``sheet_path`` does not apply.
        return cast("Sequence[Any]", self._get_items(types, self._doc))

    def get_symbol(self) -> SchematicSymbol:
        """Read the open symbol's definition, including its child items.

        The definition is the only view that carries each child's unit and body
        style, so the item readers are built on top of it.
        """
        for item in self.get_items([KiCadObjectType.KOT_LIB_SYMBOL]):
            if isinstance(item, SchematicSymbol):
                return item

        raise RuntimeError("KiCad did not return a symbol definition")


def symbol_editor(kicad: KiCad, document: Any) -> SymbolEditor:
    """Wrap an open symbol document in the editor item API."""
    return SymbolEditor(kicad._client, document)


def _guard_unit_reset(
    target: dict[str, Any],
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
    unit = target.get("unit")
    body_style = target.get("body_style")

    if (multi_unit and unit) or (multi_style and body_style):
        raise ValueError(
            f"item {target.get('id')!r} belongs to unit {unit} and body style "
            f"{body_style}; KiCad's IPC API clears those tags when an item is "
            "updated, so edit it in the symbol editor instead"
        )


def apply_item_specs(
    editor: SymbolEditor,
    specs: list[dict[str, Any]],
    *,
    replace_existing: bool = False,
    save: bool = True,
) -> dict[str, Any]:
    """Apply symbol item specifications in one commit and return change counts."""
    symbol = editor.get_symbol()
    current = symbol_item_dicts(symbol)
    by_id = {item["id"]: item for item in current if item.get("id")}
    multi_unit = symbol.unit_count > 1
    multi_style = len(symbol.body_style) > 1

    create_items: list[Any] = []
    update_items: list[Any] = []

    for spec in specs:
        if not isinstance(spec, dict):
            raise TypeError("each item specification must be an object")

        item = item_from_spec(spec)
        item_id = spec.get("id")

        if item_id is None:
            for tag in ("unit", "body_style"):
                if spec.get(tag) not in (None, 0):
                    raise ValueError(
                        f"KiCad's IPC API cannot assign a new symbol item to a "
                        f"{tag.replace('_', ' ')}; created items are common to all "
                        "units and body styles"
                    )
            create_items.append(item)
            continue

        target = by_id.get(str(item_id))
        if target is None:
            raise ValueError(f"item {item_id!r} is not part of the open symbol")
        if target.get("type") != str(spec.get("type", "")).lower():
            raise ValueError(
                f"item {item_id!r} is a {target.get('type')}, not a {spec.get('type')}"
            )

        _guard_unit_reset(target, multi_unit=multi_unit, multi_style=multi_style)
        item.id.value = str(item_id)
        update_items.append(item)

    remove_items: list[Any] = []
    if replace_existing:
        remove_items = [
            child.item
            for child in symbol.items
            if not isinstance(child.item, SchematicField)
        ]

    commit = editor.begin_commit()
    try:
        if remove_items:
            editor.remove_items(remove_items)

        if update_items:
            editor.update_items(update_items)

        created = editor.create_items(create_items) if create_items else []

        editor.push_commit(commit, "Write symbol items via API")
    except Exception:
        try:
            editor.drop_commit(commit)
        except Exception:  # noqa: BLE001, S110 - cleanup is best-effort
            pass
        raise

    saved = False
    if save:
        editor.save()
        saved = True

    final_items = symbol_item_dicts(editor.get_symbol())
    return {
        "applied": True,
        "committed": True,
        "saved": saved,
        "removed_count": len(remove_items),
        "updated_count": len(update_items),
        "created_count": len(created),
        "created_items": [item_to_dict(item) for item in created],
        "final_count": len(final_items),
        "final_summary": dict(Counter(item_category(item) for item in final_items)),
    }


def delete_items_by_id(
    editor: SymbolEditor,
    item_ids: list[str],
    *,
    save: bool = True,
) -> dict[str, Any]:
    """Delete selected symbol items by UUID in one commit.

    Symbol fields have no UUID, so only pins, graphics, text, text boxes, tables,
    and bitmaps can be addressed here.
    """
    if not item_ids:
        raise ValueError("at least one item ID is required")

    ids = [KIID(value=str(item_id)) for item_id in item_ids]
    command = editor_commands_pb2.DeleteItems()
    command.header.document.CopyFrom(editor._doc)
    command.item_ids.extend(ids)

    commit = editor.begin_commit()
    try:
        response = editor._kicad.send(command, editor_commands_pb2.DeleteItemsResponse)
        editor.push_commit(commit, "Delete symbol items via API")
    except Exception:
        try:
            editor.drop_commit(commit)
        except Exception:  # noqa: BLE001, S110 - cleanup is best-effort
            pass
        raise

    saved = False
    if save:
        editor.save()
        saved = True

    final_items = symbol_item_dicts(editor.get_symbol())
    remaining = {item["id"] for item in final_items if item.get("id")}
    results = [
        {
            "item_id": result.id.value,
            "status": editor_commands_pb2.ItemDeletionStatus.Name(result.status),
            "removed": result.id.value not in remaining,
        }
        for result in response.deleted_items
    ]
    removed = [result["item_id"] for result in results if result["removed"]]

    return {
        "applied": True,
        "committed": True,
        "saved": saved,
        "item_ids": item_ids,
        "deleted_items": results,
        "removed_count": len(removed),
        "not_removed_count": len(item_ids) - len(removed),
        "final_count": len(final_items),
        "final_summary": dict(Counter(item_category(item) for item in final_items)),
    }
