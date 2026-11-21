"""Footprint editor adapter and atomic item transactions."""

from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import uuid4

from kipy import KiCad
from kipy.board import Board
from kipy.board_types import Field
from kipy.proto.common.commands import editor_commands_pb2
from kipy.proto.common.types import KIID

from kicad_minimal_mcp.footprint.items import item_category, item_from_spec


def footprint_editor(kicad: KiCad, document: Any) -> Board:
    """Wrap an open footprint document in the board/editor item API."""
    return Board(kicad._client, document)


def footprint_parent_id(items: list[Any]) -> str:
    """Return the UUID of the footprint that owns ``items``."""
    for item in items:
        if isinstance(item, Field) and item.proto.text.HasField("parent"):
            return item.proto.text.parent.value
        parent = getattr(item, "parent", None)
        if parent is not None:
            return parent.value
    raise ValueError("could not determine the open footprint's UUID")


def _prepare_new_item(item: Any, parent_id: str) -> None:
    if isinstance(item, Field):
        item.proto.text.id.value = str(uuid4())
        item.proto.text.parent.value = parent_id
        return

    item.proto.id.value = str(uuid4())
    item.proto.parent.value = parent_id


def _prepare_field_update(field: Field, target: Field, parent_id: str) -> None:
    field.proto.text.id.value = target.text.id.value
    field.proto.text.parent.value = parent_id


def _prepare_item_update(item: Any, target: Any, parent_id: str) -> None:
    item.proto.id.value = target.id.value
    item.proto.parent.value = parent_id


def item_uuid(item: Any) -> str:
    """Return the UUID KiCad uses to address ``item``.

    Footprint fields are addressed by the UUID of their text, not by ``Field.id``,
    which is the ``FieldId`` enum for mandatory field types.
    """
    if isinstance(item, Field):
        return item.text.id.value
    return item.id.value


def delete_items_by_id(
    editor: Board,
    item_ids: list[str],
    *,
    save: bool = True,
) -> dict[str, Any]:
    """Delete selected footprint items by UUID in one commit.

    KiCad answers ``DeleteItems`` with a status per item. Fields resolve but are
    not removed in the current 11.0 source, so the result reports both the
    per-item status and what is actually missing afterwards.
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
        editor.push_commit(commit, "Delete footprint items via API")
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

    final_items = list(editor.get_items())
    remaining = {item_uuid(item) for item in final_items}
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


def apply_item_specs(
    editor: Board,
    specs: list[dict[str, Any]],
    *,
    replace_existing: bool = False,
    save: bool = True,
) -> dict[str, Any]:
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

    create_items = []
    update_items = []
    for spec in specs:
        if not isinstance(spec, dict):
            raise TypeError("each item specification must be an object")

        new_item = item_from_spec(spec)
        if isinstance(new_item, Field):
            # Mandatory fields use the KiCad FIELD_T values (REFERENCE=1, VALUE=2,
            # FOOTPRINT=3, DATASHEET=4, DESCRIPTION=5) and USER=0 for custom ones.
            # A spec that omits or zeroes field_id falls back to the field name, so
            # naming a mandatory field updates it instead of creating a duplicate.
            target = target_fields.get(new_item.field_id)
            if target is None and new_item.field_id == 0:
                target = target_fields_by_name.get(new_item.name)
                if target is not None:
                    new_item.proto.id.id = target.field_id

            if target is None:
                _prepare_new_item(new_item, parent_id)
                create_items.append(new_item)
            else:
                _prepare_field_update(new_item, target, parent_id)
                update_items.append(new_item)
            continue

        item_id = spec.get("id")
        target = target_by_id.get(str(item_id)) if item_id is not None else None
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

    remove_items = []
    if replace_existing:
        remove_items = [item for item in target_items if not isinstance(item, Field)]

    commit = editor.begin_commit()
    try:
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

        editor.push_commit(commit, "Write footprint items via API")
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

    final_items = list(editor.get_items())
    return {
        "applied": True,
        "committed": True,
        "saved": saved,
        "removed_count": len(remove_items),
        "updated_count": len(update_items),
        "created_count": len(create_items),
        "final_count": len(final_items),
        "final_summary": dict(Counter(item_category(item) for item in final_items)),
    }
