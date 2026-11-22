"""Footprint editor adapter and atomic item transactions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from uuid import uuid4

from kipy import KiCad
from kipy.board import Board
from kipy.board_types import BoardItem, Field
from kipy.proto.common.types import DocumentSpecifier

from kicad_minimal_mcp.footprint.items import (
    ItemSpec,
    item_category,
    item_from_spec,
    item_uuid,
)
from kicad_minimal_mcp.footprint.text import FieldSpec, field_from_spec
from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.transactions import (
    DeleteSummary,
    WriteSummary,
    apply_in_commit,
    delete_in_commit,
)


def footprint_editor(kicad: KiCad, document: DocumentSpecifier) -> Board:
    """Wrap an open footprint document in the board/editor item API."""
    return Board(kicad._client, document)


def footprint_parent_id(items: Sequence[BoardItem]) -> ItemId:
    """Return the UUID of the footprint that owns ``items``."""
    for item in items:
        if isinstance(item, Field) and item.proto.text.HasField("parent"):
            return item.proto.text.parent.value

        parent = getattr(item, "parent", None)
        if parent is not None:
            return parent.value

    raise ValueError("could not determine the open footprint's UUID")


def _prepare_new_item(item: BoardItem, parent_id: ItemId) -> None:
    if isinstance(item, Field):
        item.proto.text.id.value = str(uuid4())
        item.proto.text.parent.value = parent_id
        return

    item.proto.id.value = str(uuid4())
    item.proto.parent.value = parent_id


def _prepare_field_update(field: Field, target: Field, parent_id: ItemId) -> None:
    field.proto.text.id.value = target.text.id.value
    field.proto.text.parent.value = parent_id


def _prepare_item_update(item: BoardItem, target: BoardItem, parent_id: ItemId) -> None:
    item.proto.id.value = target.id.value
    item.proto.parent.value = parent_id


def _append_field_spec(
    spec: FieldSpec,
    *,
    target_fields: dict[int, Field],
    target_fields_by_name: dict[str, Field],
    parent_id: ItemId,
    create_items: list[BoardItem],
    update_items: list[BoardItem],
) -> None:
    """Route a field specification to a create or to the field it updates."""
    # Mandatory fields use the KiCad FIELD_T values (REFERENCE=1, VALUE=2,
    # FOOTPRINT=3, DATASHEET=4, DESCRIPTION=5) and USER=0 for custom ones.
    # A spec that omits or zeroes field_id falls back to the field name, so
    # naming a mandatory field updates it instead of creating a duplicate.
    new_item = field_from_spec(spec)
    target = target_fields.get(new_item.field_id)

    if target is None and new_item.field_id == 0:
        target = target_fields_by_name.get(new_item.name)
        if target is not None:
            new_item.proto.id.id = target.field_id

    if target is None:
        _prepare_new_item(new_item, parent_id)
        create_items.append(new_item)
        return

    _prepare_field_update(new_item, target, parent_id)
    update_items.append(new_item)


def apply_item_specs(
    editor: Board,
    specs: Sequence[ItemSpec],
    *,
    replace_existing: bool = False,
    save: bool = True,
) -> WriteSummary:
    """Apply item specifications in one commit and return change counts."""
    target_items = list(editor.get_items())
    parent_id = footprint_parent_id(target_items)
    target_fields = {
        item.field_id: item for item in target_items if isinstance(item, Field)
    }
    target_fields_by_name = {
        item.name: item for item in target_items if isinstance(item, Field)
    }
    target_by_id = {
        item_uuid(item): item
        for item in target_items
        if getattr(getattr(item, "id", None), "value", None)
    }

    create_items: list[BoardItem] = []
    update_items: list[BoardItem] = []

    for spec in specs:
        if isinstance(spec, FieldSpec):
            _append_field_spec(
                spec,
                target_fields=target_fields,
                target_fields_by_name=target_fields_by_name,
                parent_id=parent_id,
                create_items=create_items,
                update_items=update_items,
            )
            continue

        new_item = item_from_spec(spec)
        item_id = spec.id
        target = target_by_id.get(item_id) if item_id is not None else None

        if target is None:
            _prepare_new_item(new_item, parent_id)
            create_items.append(new_item)
            continue

        if item_category(target) != item_category(new_item):
            raise ValueError(
                f"item {item_id!r} is a {item_category(target)[:-1]}, "
                f"not a {item_category(new_item)[:-1]}"
            )

        _prepare_item_update(new_item, target, parent_id)
        update_items.append(new_item)

    remove_items: list[BoardItem] = []
    if replace_existing:
        remove_items = [item for item in target_items if not isinstance(item, Field)]

    def commit() -> None:
        if remove_items:
            editor.remove_items(remove_items)

        if update_items:
            updated = editor.update_items(update_items)
            if len(updated) != len(update_items):
                raise RuntimeError(
                    f"KiCad updated {len(updated)} of {len(update_items)} items"
                )

        if create_items:
            created = editor.create_items(create_items)
            if len(created) != len(create_items):
                raise RuntimeError(
                    f"KiCad created {len(created)} of {len(create_items)} items"
                )

    _, saved = apply_in_commit(
        editor,
        "Write footprint items via API",
        commit,
        save=save,
    )

    final_items = list(editor.get_items())

    return WriteSummary(
        saved=saved,
        removed_count=len(remove_items),
        updated_count=len(update_items),
        created_count=len(create_items),
        final_count=len(final_items),
        final_summary=dict(Counter(item_category(item) for item in final_items)),
    )


def delete_items_by_id(
    editor: Board,
    item_ids: Sequence[ItemId],
    *,
    save: bool = True,
) -> DeleteSummary:
    """Delete selected footprint items by UUID in one commit.

    KiCad answers ``DeleteItems`` with a status per item. Fields resolve but are
    not removed in the current 11.0 source, so the result reports both the
    per-item status and what is actually missing afterwards.
    """
    report, saved = delete_in_commit(
        editor,
        item_ids,
        "Delete footprint items via API",
        save=save,
    )

    final_items = list(editor.get_items())
    remaining = {item_uuid(item) for item in final_items}
    deleted_items = [
        replace(deletion, removed=deletion.item_id not in remaining)
        for deletion in report
    ]

    return DeleteSummary(
        saved=saved,
        item_ids=item_ids,
        deleted_items=deleted_items,
        final_count=len(final_items),
        final_summary=dict(Counter(item_category(item) for item in final_items)),
    )
