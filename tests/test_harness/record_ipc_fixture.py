"""Record raw KiCad IPC request/response exchanges into a binary fixture.

The integration tests use this script to capture what the MCP tools send to a
real KiCad instance.  The fake test transport replays the recorded replies over
an ``ipc://`` socket without needing KiCad running.

Usage::

    # Point at a running KiCad GUI (or a headless api-server) with the
    # footprint editor open, then record a read-only call:
    uv run python tests/test_harness/record_ipc_fixture.py \
        --socket /tmp/kicad/api.sock \
        footprint-items tests/test_harness/ipc_recordings/footprint_items_all.bin

    # The socket is auto-detected when --socket/KICAD_API_SOCKET is not set.
    uv run python tests/test_harness/record_ipc_fixture.py \
        open-documents tests/test_harness/ipc_recordings/open_documents_footprint.bin \
        --document-type footprint

Fixture format (little-endian)::

    magic      8 bytes   b"KCMIPCF1"
    count      u32       number of request/response exchanges
    repeated count times:
        req_len   u32
        request   req_len bytes   raw serialized ApiRequest
        rsp_len   u32
        response  rsp_len bytes   raw serialized ApiResponse

Each exchange is exactly what kipy's transport sends and receives, so a fake
server can return ``response`` byte-for-byte after reading the corresponding
``request``.  The request is retained so tests can also assert that the MCP
functions generated the expected IPC command.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kipy.client import KiCadClient

from kicad_minimal_mcp.connection import kicad_client
from kicad_minimal_mcp.documents import find_footprint_document, find_symbol_document
from kicad_minimal_mcp.footprint.editor import footprint_editor
from kicad_minimal_mcp.identifiers import LibraryId
from kicad_minimal_mcp.server import (
    delete_footprint_items,
    delete_symbol_items,
    get_footprint_items,
    get_open_documents,
    get_symbol_items,
    kicad_status,
    write_footprint_items,
    write_symbol_items,
)
from kicad_minimal_mcp.symbol.editor import symbol_editor

MAGIC = b"KCMIPCF1"
_U32 = struct.Struct("<I")


@dataclass(frozen=True)
class Exchange:
    """One raw IPC round trip."""

    request: bytes
    response: bytes


def write_recording(path: Path, exchanges: list[Exchange]) -> None:
    """Write exchanges to ``path`` atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")

    with temporary.open("wb") as fixture:
        fixture.write(MAGIC)
        fixture.write(_U32.pack(len(exchanges)))
        for exchange in exchanges:
            fixture.write(_U32.pack(len(exchange.request)))
            fixture.write(exchange.request)
            fixture.write(_U32.pack(len(exchange.response)))
            fixture.write(exchange.response)

    temporary.replace(path)


def read_recording(path: Path) -> list[Exchange]:
    """Read a fixture written by :func:`write_recording`."""
    with path.open("rb") as fixture:
        if fixture.read(len(MAGIC)) != MAGIC:
            raise ValueError(f"{path} is not a KiCad IPC fixture")

        (count,) = _U32.unpack(_read_exact(fixture, _U32.size, path))
        exchanges = []
        for _ in range(count):
            (request_length,) = _U32.unpack(_read_exact(fixture, _U32.size, path))
            request = _read_exact(fixture, request_length, path)
            (response_length,) = _U32.unpack(_read_exact(fixture, _U32.size, path))
            response = _read_exact(fixture, response_length, path)
            exchanges.append(Exchange(request=request, response=response))

        if fixture.read(1):
            raise ValueError(f"{path} has trailing data after the last exchange")

    return exchanges


def _read_exact(fixture: Any, size: int, path: Path) -> bytes:
    data = fixture.read(size)
    if len(data) != size:
        raise ValueError(f"{path} is truncated")
    return data


class _RecordingConnection:
    """Wrap a pynng request socket and capture each raw round trip."""

    def __init__(self, connection: Any, exchanges: list[Exchange]) -> None:
        self._connection = connection
        self._exchanges = exchanges
        self._pending_request: bytes | None = None

    def send(self, data: Any, *args: Any, **kwargs: Any) -> Any:
        result = self._connection.send(data, *args, **kwargs)
        self._pending_request = bytes(data)
        return result

    def recv_msg(self) -> Any:
        message = self._connection.recv_msg()
        if self._pending_request is None:
            raise RuntimeError("received an IPC reply without a recorded request")
        self._exchanges.append(
            Exchange(
                request=self._pending_request,
                response=bytes(message.bytes),
            )
        )
        self._pending_request = None
        return message

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


@contextmanager
def record_exchanges() -> Iterator[list[Exchange]]:
    """Capture raw traffic for every KiCad client created in the block.

    ``KiCadClient`` connects lazily, so patching its ``_connect`` method is
    enough to wrap the underlying pynng socket for any ``KiCad()`` instance the
    MCP tool creates.
    """
    exchanges: list[Exchange] = []
    original_connect = KiCadClient._connect

    def recording_connect(client: KiCadClient) -> None:
        original_connect(client)
        client._conn = _RecordingConnection(  # pyright: ignore[reportAttributeAccessIssue]
            client._conn, exchanges
        )

    KiCadClient._connect = recording_connect  # type: ignore[method-assign]
    try:
        yield exchanges
    finally:
        KiCadClient._connect = original_connect  # type: ignore[method-assign]


def run_scenario(
    scenario: str,
    *,
    document_type: str,
    lib_id: str | None,
    item_type: str,
    item_ids: list[str],
    items: list[dict[str, Any]],
    save: bool,
) -> dict[str, Any]:
    """Invoke one MCP tool and return its result."""
    if scenario == "status":
        return kicad_status()
    if scenario == "open-documents":
        return get_open_documents(document_type)
    if scenario == "footprint-items":
        return get_footprint_items(lib_id=lib_id, item_type=item_type)
    if scenario == "footprint-items-by-id":
        return get_footprint_items(
            lib_id=lib_id,
            item_type=item_type,
            item_ids=item_ids,
        )
    if scenario == "write-footprint-items":
        return write_footprint_items(items=items, lib_id=lib_id, save=save)
    if scenario == "delete-footprint-items":
        return delete_footprint_items(item_ids=item_ids, lib_id=lib_id, save=save)
    if scenario == "symbol-items":
        return get_symbol_items(
            lib_id=lib_id,
            item_type=item_type,
            item_ids=item_ids or None,
        )
    if scenario == "write-symbol-items":
        return write_symbol_items(items=items, lib_id=lib_id, save=save)
    if scenario == "delete-symbol-items":
        return delete_symbol_items(item_ids=item_ids, lib_id=lib_id, save=save)
    raise ValueError(f"unknown scenario {scenario!r}")


def _revert(scenario: str, lib_id: str | None) -> None:
    """Discard unsaved recording edits and restore the open document."""
    kicad = kicad_client()
    library_id = LibraryId.parse(lib_id) if lib_id is not None else None

    if scenario.startswith("symbol"):
        document = find_symbol_document(kicad, library_id)
        editor = symbol_editor(kicad, document)
    else:
        document = find_footprint_document(kicad, library_id)
        editor = footprint_editor(kicad, document)

    editor.revert()


def _candidate_sockets() -> list[Path]:
    candidates: list[Path] = []

    configured = os.environ.get("KICAD_API_SOCKET")
    if configured:
        candidates.append(Path(configured.removeprefix("ipc://")))

    candidates.append(Path("/tmp/kicad/api.sock"))

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        candidates.append(Path(runtime_dir) / "kicad" / "api.sock")

    for pattern in (
        "/tmp/nix-shell.*/kicad/api.sock",
        "/proc/[0-9]*/root/tmp/nix-shell.*/kicad/api.sock",
        "/proc/[0-9]*/root/tmp/kicad/api.sock",
    ):
        candidates.extend(Path(path) for path in glob.glob(pattern))

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_socket():
            unique.append(candidate)

    # Prefer the most recently created/updated socket, which is normally the
    # live KiCad instance rather than a leftover from a previous run.
    unique.sort(key=lambda path: path.stat().st_mtime_ns, reverse=True)
    return unique


def _socket_is_live(socket_path: Path) -> bool:
    previous = os.environ.get("KICAD_API_SOCKET")
    os.environ["KICAD_API_SOCKET"] = f"ipc://{socket_path}"
    try:
        kicad_client().get_version()
        return True
    except Exception:  # noqa: BLE001 - probing an arbitrary socket
        return False
    finally:
        if previous is None:
            os.environ.pop("KICAD_API_SOCKET", None)
        else:
            os.environ["KICAD_API_SOCKET"] = previous


def _select_socket(explicit: str | None) -> None:
    """Set KICAD_API_SOCKET to an explicit or auto-detected live socket."""
    if explicit:
        path = Path(explicit.removeprefix("ipc://"))
        os.environ["KICAD_API_SOCKET"] = f"ipc://{path}"
        return

    if os.environ.get("KICAD_API_SOCKET"):
        return

    for candidate in _candidate_sockets():
        if _socket_is_live(candidate):
            os.environ["KICAD_API_SOCKET"] = f"ipc://{candidate}"
            return

    raise SystemExit(
        "no live KiCad IPC server found; set KICAD_API_SOCKET or pass --socket"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        choices=(
            "status",
            "open-documents",
            "footprint-items",
            "footprint-items-by-id",
            "write-footprint-items",
            "delete-footprint-items",
            "symbol-items",
            "write-symbol-items",
            "delete-symbol-items",
        ),
    )
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--socket",
        help="KiCad IPC socket path (defaults to KICAD_API_SOCKET or auto-detect)",
    )
    parser.add_argument(
        "--document-type",
        default="all",
        help="document type for open-documents (default: all)",
    )
    parser.add_argument(
        "--lib-id",
        default=None,
        help="footprint or symbol library ID for the item scenarios"
        " (default: the open one)",
    )
    parser.add_argument(
        "--item-type",
        default="all",
        help="item type filter for the item scenarios (default: all)",
    )
    parser.add_argument(
        "--item-id",
        action="append",
        default=[],
        help="item UUID to read or delete; may be repeated",
    )
    parser.add_argument(
        "--items-file",
        type=Path,
        help="JSON file containing item specifications for write-footprint-items",
    )
    parser.add_argument(
        "--no-save",
        action="store_false",
        dest="save",
        help="leave the edited footprint unsaved",
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="revert unsaved edits after recording a write scenario",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing fixture",
    )
    parser.add_argument(
        "--print-result",
        action="store_true",
        help="print the full MCP tool result",
    )
    return parser.parse_args(argv)


def load_items(items_file: Path | None) -> list[dict[str, Any]]:
    """Return the item specifications stored in ``items_file``."""
    if items_file is None:
        return []

    with items_file.open(encoding="utf-8") as source:
        loaded = json.load(source)

    if isinstance(loaded, dict):
        return [loaded]
    if isinstance(loaded, list):
        return loaded

    raise ValueError("--items-file must contain an object or a list")


def record_scenario(
    scenario: str,
    *,
    document_type: str,
    lib_id: str | None,
    item_type: str,
    item_ids: list[str],
    items: list[dict[str, Any]],
    save: bool,
) -> tuple[list[Exchange], dict[str, Any]]:
    """Invoke one MCP tool and capture the IPC exchanges it produces."""
    with record_exchanges() as exchanges:
        result = run_scenario(
            scenario,
            document_type=document_type,
            lib_id=lib_id,
            item_type=item_type,
            item_ids=item_ids,
            items=items,
            save=save,
        )

    return list(exchanges), result


def main(
    scenario: str,
    output: Path,
    *,
    socket: str | None,
    document_type: str,
    lib_id: str | None,
    item_type: str,
    item_ids: list[str],
    items_file: Path | None,
    save: bool,
    revert: bool,
    force: bool,
    print_result: bool,
) -> int:
    """Record one scenario's raw IPC exchanges into ``output``."""
    if output.exists() and not force:
        print(
            f"error: {output} already exists; pass --force to overwrite",
            file=sys.stderr,
        )
        return 2

    try:
        items = load_items(items_file)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    _select_socket(socket)

    try:
        exchanges, result = record_scenario(
            scenario,
            document_type=document_type,
            lib_id=lib_id,
            item_type=item_type,
            item_ids=item_ids,
            items=items,
            save=save,
        )
    finally:
        if revert:
            _revert(scenario, lib_id)

    if not exchanges:
        print(
            "error: no IPC exchanges were recorded; the tool may have failed "
            "before connecting to KiCad",
            file=sys.stderr,
        )
        if result.get("error"):
            print(f"tool error: {result['error']}", file=sys.stderr)
        return 1

    write_recording(output, exchanges)

    print(f"recorded {len(exchanges)} IPC exchange(s) for {scenario!r} to {output}")
    if result.get("error") is not None:
        print(f"tool error: {result['error']}")
    if print_result:
        print(json.dumps(result, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(
        main(
            arguments.scenario,
            arguments.output,
            socket=arguments.socket,
            document_type=arguments.document_type,
            lib_id=arguments.lib_id,
            item_type=arguments.item_type,
            item_ids=arguments.item_id,
            items_file=arguments.items_file,
            save=arguments.save,
            revert=arguments.revert,
            force=arguments.force,
            print_result=arguments.print_result,
        )
    )
