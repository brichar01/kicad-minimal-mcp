# KiCad 11.0 IPC API review for a footprint-authoring MCP

Reviewed 2026-10-25 against the current KiCad 11.0 development source
(`master`) and the current `kicad-python` `main` branch (`0.9.0.dev0`). KiCad
11.0 has not been released from this source yet, so this is a moving target.

## Scope and assumptions

This review assumes:

- The MCP targets **KiCad 11.0+ only**. The 10.x API is out of scope.
- **All KiCad interaction goes through the IPC API.** There is no
  `.kicad_mod` writer/parser, no `fp-lib-table` editing, and no other
  file-backend fallback in the MCP.
- Anything the IPC API does not implement is done **manually by the user** in
  the KiCad GUI or through normal KiCad workflows.
- Protobuf commands sent directly through `kicad-python`'s client are still IPC
  API usage. They are not considered file-backend workarounds.
- The MCP runs against `kicad-python` `main`/0.9.x. The repository uses an
  editable path source to the sibling `kicad-python` checkout.

## Bottom line

KiCad 11 turns footprint editing into a first-class IPC document type. Once a
footprint exists in a registered library, the API can:

- enumerate and read footprint libraries;
- open an existing footprint in the footprint editor (GUI or headless);
- create, update, and delete pads and graphical/text/field items;
- save back to the same library item;
- save a copy as a new footprint name and/or a different registered library;
- run all of this headlessly through `kicad-cli api-server`.

It still does **not** provide:

- creation of a blank footprint document from scratch;
- creation of a new `.pretty` library directory;
- insertion/deletion of library-table rows (the messages exist in the protobuf
  but are not implemented in the current source);
- library search (`SearchLibraries` is also protobuf-only);
- a clean `.kicad_mod` string serializer/parser;
- editing of some footprint-level metadata such as attributes and the classic
  3D model list.

So the MCP can own the **edit → save** workflow for existing footprints. The
**create blank footprint / create library / register library** steps remain
manual.

## Implemented API surface in current 11.0 source

### Connection and execution modes

| Interface | Status | Notes |
| --- | --- | --- |
| `KiCad()` | Available | Connects to a running GUI instance with the API server enabled. |
| `KiCad(headless=True, kicad_cli_path=..., file_path=...)` | Available | Starts and connects to `kicad-cli api-server`. |
| `get_version()`, `get_api_version()`, `check_version()` | Available | Version checking is useful, but treat it as informational in a moving 11.0 development tree. |
| `get_paths()` | Available | Returns KiCad path locations, including stock footprint and 3D-model paths. |
| GUI plugins | Available | 11 expands API plugin support to the schematic editor as well as the PCB editor. Not required for an external MCP. |

### Document lifecycle

| Interface | Status | Notes |
| --- | --- | --- |
| `get_open_documents(type)` | Available | Supports `DOCTYPE_FOOTPRINT`. |
| `open_library_item(library, name, DOCTYPE_FOOTPRINT)` | Available, GUI only | Loads an existing library item into the footprint editor. The footprint editor must already be open. |
| `open_document("Lib:Name", DOCTYPE_FOOTPRINT)` | Available, headless only | Opens an existing library footprint into a headless footprint context. |
| `close_document()` | Available | Closes the open footprint document. |
| `create_document()` | Available for PCB and schematic only | `CreateDocument` explicitly rejects footprint/symbol types. |
| `create_document()` for footprint | **Not implemented** | There is no blank-footprint document creation path. |

The headless footprint context is backed by a real `FOOTPRINT` loaded from a
library, with the footprint as the default item container. It is not an empty
scratch document.

### Library APIs

Implemented in the current C++ handler and wrapped by `kicad-python` main:

| Interface | Status | Notes |
| --- | --- | --- |
| `get_library_items(type, nicknames)` | Implemented | Lists identifiers in registered libraries. |
| `get_library_footprints(nicknames)` | Implemented | Footprint wrapper around `get_library_items`. |
| `get_library_footprint(lib_id)` | Implemented | Returns the full `Footprint` definition. |
| `get_library_statuses()` | Implemented | Reports per-library load status. |
| `reload_library()` | Implemented | Asynchronous; wait for completion. |
| `load_all_libraries()` | Implemented | Headless bootstrap; no-op in GUI because the GUI preloads. |
| `wait_for_libraries()` | Implemented | Polls status until loading completes. |
| `Board.place_footprint_from_library()` | Implemented | Board placement, not footprint-editor authoring. |
| `open_library_item()` / headless `open_document()` | Implemented | Opens an existing footprint item. |
| `SearchLibraries` | **Protobuf only** | No handler registered in current source and no `kicad-python` wrapper. |
| `GetLibraryTable` | **Protobuf only** | No handler registered. |
| `AddLibraryTableEntry` | **Protobuf only** | No handler registered; cannot register a library through IPC yet. |
| `UpdateLibraryTableEntry` | **Protobuf only** | No handler registered. |
| `DeleteLibraryTableEntry` | **Protobuf only** | No handler registered. |
| Create a new `.pretty` directory | **No API** | Filesystem/GUI operation only. |

Library loading is asynchronous. In headless mode, call `load_all_libraries()`
and/or `wait_for_libraries()` before enumerating or opening items. In GUI mode,
the user must have the library registered and loaded.

### Footprint editor commands

The footprint editor inherits the common editor and board-editor command sets.
The default item container is the open footprint.

| Command / binding | Status | Notes |
| --- | --- | --- |
| `get_items(types=None)` | Implemented | Returns footprint children. No argument means the footprint handler's allowed type set. |
| `get_items_by_id()` | Implemented | Base board-editor handler. |
| `create_items()` | Implemented | Creates items in the open footprint by default. |
| `update_items()` | Implemented | Updates existing children by UUID. |
| `remove_items()` / `remove_items_by_id()` | Implemented | Mandatory fields cannot be deleted. |
| `begin_commit()` / `push_commit()` / `drop_commit()` | Implemented | Groups edits into one undo step. |
| `save()` | Implemented | Saves the footprint back to its library item. |
| `save_as()` | Implemented at protocol level | `SaveCopyOfDocument` with `"NewName"` or `"Lib:NewName"` saves a copy into a registered library. |
| `revert()` | Implemented | Reloads from the library. |
| `is_document_modified()` | Implemented | Reports unsaved state. |
| `get_as_string()` | Implemented, but board-format | The shared board handler serializes with `CLIPBOARD_IO::SaveBoard`, producing `(kicad_pcb ...)` text, not `.kicad_mod`. |
| `get_selection_as_string()` | GUI only | Selection serialization; headless mode rejects it. Not a full-footprint serializer. |
| `ParseAndCreateItemsFromString` | **Not implemented** | Still a stub in current source: returns an empty response. |

## Footprint child items supported by the API

The current board handler explicitly allows these item types inside a footprint
container:

- pads (`Pad`, `PadStack`, `PadStackLayer`, `PadStackOuterLayer`,
  `DrillProperties`, `PostMachiningProperties`, `PadTeardropSettings`)
- footprint fields (`Field`), including custom fields
- free text and text boxes (`BoardText`, `BoardTextBox`)
- graphical shapes (`BoardSegment`, `BoardArc`, `BoardCircle`,
  `BoardRectangle`, `BoardPolygon`, `BoardBezier`)
- barcodes
- tables and table cells
- zones
- groups
- constraints
- reference points
- dimensions (`AlignedDimension`, `OrthogonalDimension`, `RadialDimension`,
  `LeaderDimension`, `CenterDimension`)
- reference images
- 3D bodies

Pads are rejected unless the target container is a footprint.

Pad support in current 11.0 bindings includes:

- pad type (SMD, PTH, NPTH, edge connector)
- padstack type and per-layer shapes/sizes/offsets
- roundrect corner ratio, chamfer ratio/corners, trapezoid delta
- custom pad shapes and custom anchor shape
- drill shape, diameter, start/end layers, capped/filled state
- secondary and tertiary drills
- front/back post-machining (counterbore/countersink)
- solder mask and paste modes plus per-pad margins/ratios
- zone connection and thermal spoke settings
- teardrop settings
- pad-to-die length and delay
- fabrication property, simulation electrical type, custom properties
- symbol-pin association metadata (read/write fields)

All distances use KiCad internal nanometres. `kipy.util.units` and
`Vector2.from_xy_mm()` are the intended conversion helpers.

### Item retrieval caveat

The footprint `GetItems` handler's default list is slightly narrower than the
creation allow-list. Reference images, constraints, and reference points are
creatable but not returned by the footprint `GetItems` switch. `GetItemsById`
can still retrieve an item if its UUID is known. Plan the MCP around the
creation/retrieval asymmetry rather than assuming both lists are identical.

### Footprint-level metadata

The `Footprint` data model exposes attributes, design-rule overrides, net ties,
private layers, jumpers, anchor, mandatory fields, 3D models, and embedded
files. `get_library_footprint()` can read the full definition.

Editing those footprint-level properties on an **open** footprint is not
exposed as a normal child-item update: the footprint itself is the container,
and `CreateItems`/`UpdateItems` accept child item types only. The MCP should
treat footprint attributes, the classic 3D model list, net ties, and jumper
settings as read-only/manual for now unless a future command is added.

Mandatory fields (`Reference`, `Value`, `Datasheet`, `Description`) are
protected from deletion. They can be read and their text/position/etc. updated
as fields, but they cannot be removed.

## Symbol editor support

KiCad 11 also registers an `API_HANDLER_SYMBOL` for `DOCTYPE_SYMBOL`, in both
the symbol editor frame and the headless symbol context. Headless mode can load
a library symbol directly by `LIB_ID`, so no pre-opened document is needed.

Registered commands: `OpenLibraryItem`, `GetOpenDocuments`, `SaveDocument`,
`SaveCopyOfDocument`, `RevertDocument`, `GetItems`, `GetItemsById`, plus the
shared `BeginCommit`/`EndCommit`, `CreateItems`, `UpdateItems`, `DeleteItems`,
and modified-state commands.

The handler's allowed child types are pins, fields, graphic shapes, text, text
boxes, tables, table cells, bitmaps, and the whole `LIB_SYMBOL`. Reading is
straightforward: `GetItems` with `KOT_LIB_SYMBOL` returns the full
`SchematicSymbol` definition, whose children carry the unit and body style they
belong to. The flat item list does not carry those tags, so the MCP reads the
definition instead.

Write-side limits in the current source:

- `CreateItems`/`UpdateItems` reject the whole `LIB_SYMBOL` and every
  `SCH_FIELD`, so symbol-level properties and all fields are read-only.
- Individual item messages have no unit or body-style fields, and updating an
  item swaps in the freshly deserialized item, which resets those tags to
  "common to all units / body styles". Creating items has the same result.
- Symbol fields have no UUID in the protobuf (the field is commented out as
  reserved), so they cannot be addressed by `item_ids`.
- `SaveDocument` requires the symbol to have a library nickname;
  `SaveCopyOfDocument` takes a `.kicad_sym` path plus an overwrite flag rather
  than a `Lib:Name` identifier.
- Saving a symbol regenerates its child item UUIDs. The IDs returned by
  `created_items` or read before a save are stale afterwards, so re-read the
  symbol before the next edit.

The MCP implements pin, text, text box, and graphic create/update/delete on top
of the commands that work, and refuses the rest with an `invalid_request`
result: field specs, `table`/`bitmap` writes, assigning a new item to a unit or
body style, and updating an item that carries a unit or body-style tag in a
multi-unit or multi-body-style symbol. A KiCad patch that preserved `m_unit`,
`m_bodyStyle`, and `m_private` across `SwapItemData` would remove the last two
restrictions, but that changes KiCad itself and is out of scope for the MCP.

## Current end-to-end workflow

### Interactive/GUI mode

1. User manually registers the target `.pretty` library and opens the footprint
   editor.
2. MCP connects to the GUI.
3. MCP enumerates the library and opens an existing footprint by `LIB_ID`.
4. MCP reads its children, then creates/updates/deletes pads, graphics, text,
   and fields inside a commit.
5. MCP calls `save()` to overwrite the library item, or `save_as("Lib:NewName")`
   to create a new item.

Creating the initial blank footprint and registering the library are manual
steps outside the MCP.

### Headless mode

1. User manually registers the library and ensures an existing footprint exists
   to open. This is the key manual prerequisite: headless mode cannot create a
   blank footprint.
2. MCP starts `KiCad(headless=True)`, opens/loads the project or libraries, and
   calls `load_all_libraries()` / `wait_for_libraries()`.
3. MCP calls `open_document("Lib:Name", DOCTYPE_FOOTPRINT)`.
4. MCP edits children and commits.
5. MCP calls `save()` or sends `SaveCopyOfDocument` with `"Lib:NewName"`.

Headless mode gives the same edit/save capabilities, but still lacks blank
footprint creation, library creation, and library-table mutation.

## Gaps and manual operations

| Capability | Current 11.0 source | Manual step |
| --- | --- | --- |
| Create a blank footprint | No API | Create it in the GUI footprint editor. |
| Create a new `.pretty` library | No API | Create the directory in the filesystem/GUI. |
| Register a library | Protobuf messages exist but no handler | Add it through the GUI library manager / `fp-lib-table`. |
| Unregister/update a library row | Protobuf messages exist but no handler | GUI library manager. |
| Search libraries | Protobuf only, no handler | Enumerate with `get_library_items()` or use GUI. |
| Open a footprint by raw file path | No | Register the library and open by `LIB_ID`. |
| Serialize the open footprint to `.kicad_mod` text | No clean API | Save via API, or export manually. |
| Parse/paste `.kicad_mod` text into the editor | `ParseAndCreateItemsFromString` is a stub | Use normal GUI paste/import. |
| Edit footprint-level attributes | No child-item update path | GUI footprint properties dialog. |
| Edit classic 3D model list | No obvious update path | GUI footprint properties dialog. |
| Edit net ties / jumper settings | No obvious update path | GUI footprint properties dialog. |
| Delete mandatory fields | Blocked by `IDS_IMMUTABLE` | Not normally desirable. |

## `kicad-python` binding gaps

The C++ API is ahead of the Python ergonomics in a few places:

1. **No dedicated footprint-editor wrapper.** `main` has a generic
   `EditorCommandsHandler`, plus `Board` and `Schematic`, but no
   `FootprintEditor` class. An MCP will either construct a `Board`-like wrapper
   around the footprint `DocumentSpecifier` or send the protobuf commands
   directly. Neither is a file-backend hack, but both should be isolated behind
   a small adapter.

2. **`save_as()` path handling.** The generic `save_as()` resolves its argument
   with `pathlib.Path.resolve()`. That is correct for file documents but breaks
   the footprint-specific `"NewName"` / `"Lib:NewName"` syntax expected by
   `SaveCopyOfDocument`. The MCP should send the raw `SaveCopyOfDocument`
   command for footprint saves until this is fixed.

3. **No library-table wrappers.** Even after the C++ handlers land, the Python
   bindings will need wrappers for `GetLibraryTable`,
   `Add/Update/DeleteLibraryTableEntry`, and `SearchLibraries`.

4. **No footprint serializer.** `get_as_string()` is inherited from the board
   handler and emits a board document. Do not treat it as a `.kicad_mod`
   serializer.

5. **Dependency source.** The project now resolves `kicad-python` from the
   editable sibling checkout (`0.9.0.dev0` or later). Keep that checkout and its
   `kicad` proto submodule aligned with the KiCad build under test.

## Proposed MCP tool surface (IPC only)

These tools are implementable with the current 11.0 source:

| Tool | Backend call |
| --- | --- |
| `kicad_status` | `get_version`, `get_open_documents`, mode/headless info |
| `library_list` | `get_library_statuses`, `get_library_footprints` |
| `footprint_list` | `get_library_footprints` |
| `footprint_read_definition` | `get_library_footprint` |
| `footprint_open` | GUI `open_library_item` or headless `open_document` |
| `footprint_get_items` | `get_items` / `get_items_by_id` |
| `footprint_add_pad` | `create_items([Pad])` |
| `footprint_update_pad` | `update_items([Pad])` |
| `footprint_delete_item` | `remove_items` / `remove_items_by_id` |
| `footprint_add_graphic` | `create_items([BoardShape])` |
| `footprint_add_text` / `add_field` | `create_items([BoardText/TextBox/Field])` |
| `footprint_commit` | `begin_commit` / `push_commit` / `drop_commit` |
| `footprint_save` | `save` |
| `footprint_save_as` | raw `SaveCopyOfDocument` with `"Lib:NewName"` |
| `board_place_from_library` | `place_footprint_from_library` (optional) |
| `get_symbol_items` (implemented) | `get_items([KOT_LIB_SYMBOL])` on the open symbol document |
| `write_symbol_items` (implemented) | `BeginCommit`, `CreateItems`/`UpdateItems`, `DeleteItems`, `EndCommit`, `SaveDocument` |
| `delete_symbol_items` (implemented) | `BeginCommit`, `DeleteItems`, `EndCommit`, `SaveDocument` |

These must **not** be offered as API tools because the API does not implement
them. The MCP should return an explicit “manual step required” message instead:

- create blank footprint;
- create `.pretty` library;
- register/unregister library;
- search libraries;
- serialize/parse `.kicad_mod`;
- edit footprint attributes/3D models/net ties/jumpers;
- delete mandatory fields.

## Suggested implementation order

1. Pin `kicad-python` to the 11.0 development version.
2. Build a thin adapter over the raw protobuf commands for the footprint
   editor, because the Python bindings have no footprint wrapper yet.
3. Implement library enumeration/status/open/save flows.
4. Implement pad and graphic/text/field create/update/delete with commit
   grouping.
5. Add explicit manual-step errors for the unimplemented gaps.
6. Add headless tests using `kicad-cli api-server` and a manually prepared
   registered library containing a seed footprint.

## Open questions

- Will the MCP run primarily in GUI mode or headless mode? Headless requires a
  pre-existing footprint and pre-registered library.
- Which subset of pad features and graphic item types is required for v1?
- Should the MCP expose one generic `footprint_apply_ops` batch tool or
  fine-grained pad/graphic tools?
- How should the MCP handle a user opening the wrong footprint or leaving unsaved
  changes in the editor? Use `is_document_modified()`, `revert()`, and explicit
  commit semantics.
- Do we need board placement preview via `place_footprint_from_library`, or is
  footprint-editor editing sufficient?

## Sources

- KiCad 11.0 development source, footprint editor handler:
  <https://github.com/KiCad/kicad-source-mirror/blob/master/pcbnew/api/api_handler_footprint.cpp>
- Footprint child type allow-list and create/update/delete:
  <https://github.com/KiCad/kicad-source-mirror/blob/master/pcbnew/api/api_handler_board.cpp>
- Common editor commands:
  <https://github.com/KiCad/kicad-source-mirror/blob/master/common/api/api_handler_editor.cpp>
- Library command handler (implemented subset):
  <https://github.com/KiCad/kicad-source-mirror/blob/master/common/api/api_handler_libraries.cpp>
- Library protobuf definitions:
  <https://github.com/KiCad/kicad-source-mirror/blob/master/api/proto/common/commands/library_commands.proto>
- Headless API server and footprint opening:
  <https://github.com/KiCad/kicad-source-mirror/blob/master/kicad/cli/command_api_server.cpp>
  and
  <https://github.com/KiCad/kicad-source-mirror/blob/master/pcbnew/pcbnew.cpp>
- `kicad-python` main:
  <https://gitlab.com/kicad/code/kicad-python/-/blob/main/kipy/kicad.py>
  and
  <https://gitlab.com/kicad/code/kicad-python/-/blob/main/kipy/editor.py>
- Development API documentation:
  <https://docs.kicad.org/kicad-python/>
