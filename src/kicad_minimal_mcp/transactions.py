"""Atomic commit bookkeeping shared by the footprint and symbol editors.

Both editors drive the same IPC pattern: open a commit, mutate through item
commands, push the commit, then optionally save the document. Duplicating that
sequence per command made it easy for one path to forget the drop-on-failure
cleanup, so it lives here once.

The editor is any kipy ``EditorCommandsHandler``: the board and schematic
editors expose the same commit, save, and delete commands.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from kipy.board_types import BoardItem
from kipy.editor import EditorCommandsHandler
from kipy.proto.common.commands import editor_commands_pb2
from kipy.proto.common.types import KIID
from kipy.schematic_types import SchematicItem

from kicad_minimal_mcp.identifiers import ItemId
from kicad_minimal_mcp.results import Payload
from kicad_minimal_mcp.type_filters import Category, summary_payload

Editor = EditorCommandsHandler[BoardItem] | EditorCommandsHandler[SchematicItem]


def apply_in_commit[T](
    editor: Editor,
    message: str,
    body: Callable[[], T],
    *,
    save: bool,
) -> tuple[T, bool]:
    """Run ``body`` inside one commit, push it, and optionally save.

    Returns the body's value and whether the document was saved. If ``body``
    raises, the pending commit is dropped and the exception propagates, so no
    partial edit reaches the library.
    """
    commit = editor.begin_commit()

    try:
        value = body()
        editor.push_commit(commit, message)
    except Exception:
        try:
            editor.drop_commit(commit)
        except Exception:  # noqa: BLE001, S110 - cleanup is best-effort
            pass
        raise

    if save:
        editor.save()

    return value, save


@dataclass(frozen=True)
class ItemDeletion:
    """KiCad's answer for one item in a delete command."""

    item_id: ItemId
    status: editor_commands_pb2.ItemDeletionStatus.ValueType
    removed: bool = False

    def to_payload(self) -> Payload:
        """Return the JSON form the tools report."""
        return {
            "item_id": self.item_id,
            "status": editor_commands_pb2.ItemDeletionStatus.Name(self.status),
            "removed": self.removed,
        }


def delete_in_commit(
    editor: Editor,
    item_ids: Sequence[ItemId],
    message: str,
    *,
    save: bool,
) -> tuple[list[ItemDeletion], bool]:
    """Delete items by UUID in one commit and report each item's status.

    The ``removed`` flag is left false for the caller to fill in: only it knows
    how to read the document back and see which items are actually gone.
    """
    if not item_ids:
        raise ValueError("at least one item ID is required")

    command = editor_commands_pb2.DeleteItems()
    command.header.document.CopyFrom(editor._doc)
    command.item_ids.extend(KIID(value=str(item_id)) for item_id in item_ids)

    def send() -> editor_commands_pb2.DeleteItemsResponse:
        return editor._kicad.send(command, editor_commands_pb2.DeleteItemsResponse)

    response, saved = apply_in_commit(editor, message, send, save=save)
    report = [
        ItemDeletion(item_id=result.id.value, status=result.status)
        for result in response.deleted_items
    ]

    return report, saved


@dataclass(frozen=True)
class WriteSummary:
    """The counts and saved state of an applied item write."""

    saved: bool
    removed_count: int
    updated_count: int
    created_count: int
    final_count: int
    final_summary: Mapping[Category, int]
    created_items: list[Payload] | None = None

    def to_payload(self) -> Payload:
        """Return the JSON form the tools report."""
        payload: Payload = {
            "applied": True,
            "committed": True,
            "saved": self.saved,
            "removed_count": self.removed_count,
            "updated_count": self.updated_count,
            "created_count": self.created_count,
        }

        if self.created_items is not None:
            payload["created_items"] = self.created_items

        payload["final_count"] = self.final_count
        payload["final_summary"] = summary_payload(self.final_summary)

        return payload


@dataclass(frozen=True)
class DeleteSummary:
    """The item counts and saved state of an applied item deletion."""

    saved: bool
    item_ids: Sequence[ItemId]
    deleted_items: list[ItemDeletion]
    final_count: int
    final_summary: Mapping[Category, int]

    def to_payload(self) -> Payload:
        """Return the JSON form the tools report."""
        removed = [deletion for deletion in self.deleted_items if deletion.removed]

        return {
            "applied": True,
            "committed": True,
            "saved": self.saved,
            "item_ids": list(self.item_ids),
            "deleted_items": [deletion.to_payload() for deletion in self.deleted_items],
            "removed_count": len(removed),
            "not_removed_count": len(self.item_ids) - len(removed),
            "final_count": self.final_count,
            "final_summary": summary_payload(self.final_summary),
        }
