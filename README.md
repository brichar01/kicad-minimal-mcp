# kicad-minimal-mcp

A minimal MCP server for authoring KiCad footprints and footprint libraries.

## Status

This repository currently contains the project setup, a review of the current
KiCad 11.0 IPC API from source, and a minimal MCP scaffold with `kicad_status`,
`get_open_documents`, `get_footprint_items`, `write_footprint_items`,
`delete_footprint_items`, and `get_symbol_items` tools.

The project is now targeting the **KiCad 11.0 IPC API only**. There is no
`.kicad_mod` file backend, no library-table editing in the MCP, and no 10.x
fallback. Anything the IPC API does not currently implement (blank footprint
creation, library registration, `.kicad_mod` serialization/parsing, some
footprint metadata) is done manually in KiCad.

See [`docs/kicad-11-ipc-review.md`](docs/kicad-11-ipc-review.md) for the
implemented/unimplemented interface inventory, binding gaps, the end-to-end
workflow, and the proposed IPC-only MCP tool surface.

## Setup

```sh
uv sync
```

Dependencies:

- `kicad-python` main / 0.9.x - official Python bindings for the 11.0 IPC API
- `mcp[cli]` 2.x - Python MCP SDK (uses `MCPServer`; `FastMCP` was removed in
  MCP SDK 2.x)

### Local bindings checkout

`pyproject.toml` uses a uv path source so the server runs against the sibling
`kicad-python` checkout rather than a released wheel:

```toml
[tool.uv.sources]
kicad-python = { path = "../kicad-python", editable = true }
```

After changing the checkout (including its `kicad` proto submodule), refresh
the environment and confirm the source location:

```sh
uv sync
uv pip show kicad-python   # Editable project location: .../kicad-python
```

The `kicad_status` tool reports the connected KiCad build, the API version the
bindings were generated from, and the open board if one is loaded.
`get_open_documents` lists the open documents and can filter by type (`pcb`,
`schematic`, `symbol`, `footprint`, `drawing_sheet`, or `project`); footprint
results include the `lib_id` needed by the item-editing commands. With the
default `all` filter, document types whose editor is not open are reported in
`unavailable_document_types` rather than failing the request.

`get_footprint_items` reads the elements of the open footprint editor document.
It returns pads, fields, text, and graphics in millimetres relative to the
footprint origin, with optional filtering by item type or item UUIDs. Pads
include their copper-layer shapes and sizes, padstack layers, and drill data;
fields include their text, visibility, layer, and text attributes.

`write_footprint_items` applies item specifications in the same shape returned
by `get_footprint_items`. It groups changes into one `BeginCommit` /
`EndCommit` transaction, optionally removes existing non-field items, updates
mandatory fields by `field_id` and other items by `id`, creates new items with
fresh UUIDs, and saves the footprint back to its library entry. Supported item
types are pads, fields, text, text boxes, and graphic segments, arcs, circles,
rectangles, and beziers.

`get_symbol_items` reads the symbol open in the symbol editor. It returns the
symbol-level definition (library id, symbol type, unit count, body styles,
keywords, footprint filters, and exclusion attributes) plus every child item:
mandatory and user fields, pins, text, text boxes, graphics, tables, and
bitmaps. Because it reads the whole definition rather than the flat item list,
each item carries the `unit` and `body_style` it belongs to (or `null` when it
is common to all units or body styles; KiCad's explicit zero is reported the
same way). Pins include their name, number,
electrical type, shape, orientation, length, alternate modes, and text sizes.
Symbol fields have no UUID in the IPC API, so their `id` is `null` and they
cannot be selected with `item_ids`.

`delete_footprint_items` removes selected items by UUID in the same atomic
commit flow and optionally saves the footprint.

`write_symbol_items` applies item specifications in the same shape returned by
`get_symbol_items`. It validates the specs against the open symbol, groups the
edit into one `BeginCommit` / `EndCommit` transaction, optionally removes all
existing non-field items, updates existing items by `id`, creates new items,
and saves the symbol back to its library entry. Writable item types are pins,
text, text boxes, and graphics (arc, circle, rectangle, bezier, polygon,
ellipse, and ellipse arc). `created_items` reports the items KiCad created,
including the UUIDs it assigned. Saving regenerates every child item UUID, so
re-read the symbol before the next edit.

Three changes are refused with an `invalid_request` result instead of being
applied silently, because the current IPC API cannot express them:

- fields are read-only, since KiCad rejects field create and update commands;
- new items cannot be assigned a `unit` or `body_style`, so they are common to
  all units and body styles;
- updating an item that belongs to a specific unit or body style in a
  multi-unit or multi-body-style symbol is refused, because KiCad clears those
  tags when an item is updated.

`delete_symbol_items` removes selected items by UUID in the same atomic commit
flow and optionally saves the symbol. Symbol fields have no UUID, so they cannot
be deleted through the API.

All tools return a consistent outcome envelope with `ok`, `status`,
`retryable`, and `error`. Connection failures report
`status: "kicad_unavailable"` and `retryable: true`; invalid requests report
`status: "invalid_request"` and `retryable: false`. Write and delete results
also include `applied` and `committed` so a caller can distinguish an IPC
failure from a successful commit that was intentionally left unsaved.

## KiCad prerequisites

KiCad 11 must be running with the API server enabled, or the MCP must start
KiCad in headless mode through `kicad-cli api-server`. In GUI mode the relevant
footprint or symbol editor must already be open. Headless mode requires a
pre-existing
footprint in an already-registered library, because the API cannot create a
blank footprint or register a library.

Set `KICAD_API_SOCKET` / `KICAD_API_TOKEN` if connecting to a non-default
instance.

## Running

```sh
uv run kicad-minimal-mcp
```

The server uses stdio transport. Example MCP client configuration:

```json
{
  "mcpServers": {
    "kicad": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/kicad-minimal-mcp", "kicad-minimal-mcp"]
    }
  }
}
```

### Verification without the GUI

A headless API server is enough to exercise the IPC connection. Inside the
KiCad 11 dev container, with the built binaries in `/install`:

```sh
kicad-cli api-server --socket /tmp/kicad/api.sock path/to/board.kicad_pcb
```

On the host, `KICAD_API_SOCKET=ipc:///tmp/kicad/api.sock` is the default Linux
socket. Calling `kicad_status` should then return `"connected": true`, the
KiCad version, and `"board_open": true` with the board name.

## Development

The review defines the IPC-only tool surface and the current gaps. The next
implementation step is a thin adapter over the 11.0 IPC protobuf commands for
the footprint editor, because `kicad-python` main does not yet expose a
dedicated footprint-editor wrapper. This remains pure IPC; there is no file
backend.

### Integration tests

The integration tests start a fake KiCad IPC socket, replay recorded
`ApiRequest`/`ApiResponse` exchanges, launch the MCP server over stdio, call its
tools through an MCP client, and verify the structured results.

```sh
just test
```

Recorded exchanges live in `tests/test_harness/ipc_recordings/`. To add a test,
record the required exchanges from the workspace nightly KiCad:

```sh
uv run python tests/test_harness/record_ipc_fixture.py \
    open-documents tests/test_harness/ipc_recordings/open_documents_footprint.bin \
    --document-type footprint
```

Then use the `mcp_integration` fixture in an async test, call the tool, and
finish with `server.assert_complete()`. See `AGENTS.md` in the workspace root
for the full workflow.
