# kicad-minimal-mcp

A minimal MCP server for authoring KiCad footprints and footprint libraries.

## Status

This repository currently contains the project setup, a review of the current
KiCad 11.0 IPC API from source, and a minimal MCP scaffold whose only tool is
`kicad_status`.

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

**Note:** the current `pyproject.toml` still pins `kicad-python>=0.8,<0.9` from
the initial 10.x setup. That pin must move to the 11.0 development version
before implementation; the review is written against `kicad-python` `main`
(`0.9.0.dev0`).

## KiCad prerequisites

KiCad 11 must be running with the API server enabled, or the MCP must start
KiCad in headless mode through `kicad-cli api-server`. In GUI mode the relevant
footprint editor must already be open. Headless mode requires a pre-existing
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
      "args": ["run", "--directory", "/home/benri/src/kicad-minimal-mcp", "kicad-minimal-mcp"]
    }
  }
}
```

## Development

The review defines the IPC-only tool surface and the current gaps. The next
implementation step is a thin adapter over the 11.0 IPC protobuf commands for
the footprint editor, because `kicad-python` main does not yet expose a
dedicated footprint-editor wrapper. This remains pure IPC; there is no file
backend.
