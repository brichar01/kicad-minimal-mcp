"""Integration tests for symbol writes through the MCP server."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "kicad-test:TEST_DIODE"
PIN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
RECTANGLE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
TEXT_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

# Multi-unit symbol used by the rejection tests.
MULTI_LIB_ID = "kicad-test:TEST_OPAMP"
MULTI_PIN_ID = "11111111-1111-4111-8111-111111111111"

# Live-recording pair: two small updates to the large EZURIO-BL54L15 symbol,
# followed by a read of the modified (unsaved) symbol.
EZURIO_LIB_ID = "benri-projects:EZURIO-BL54L15"
EZURIO_PIN_ID = "10ff77a6-29b4-4321-8833-678be117e010"
EZURIO_RECT_ID = "580b3d60-4c7d-4eac-b0c3-9437e6c56045"
EZURIO_PIN_SPEC = {
    "type": "pin",
    "id": EZURIO_PIN_ID,
    "name": "P2.09",
    "number": "2",
    "position": {"x_mm": 21.59, "y_mm": 10.16},
    "length_mm": 1.27,
    "orientation": "SPO_LEFT",
    "electrical_type": "EPT_BIDIRECTIONAL",
    "shape": "SPS_INVERTED",
    "visible": True,
    "name_text_size_mm": 1.27,
    "number_text_size_mm": 1.27,
}
EZURIO_RECT_SPEC = {
    "type": "graphic",
    "id": EZURIO_RECT_ID,
    "shape": "rectangle",
    "top_left": {"x_mm": -19.05, "y_mm": -33.02},
    "bottom_right": {"x_mm": 19.05, "y_mm": 20.32},
    "stroke": {"width_mm": 0.508, "style": "SLS_DEFAULT"},
    "filled": False,
}

# Second live pass: update the rectangle, create a text, and save the library.
EZURIO_SAVE_RECT_ID = "78991413-6dbd-4931-acd9-1abc13903c1d"
EZURIO_SAVE_RECT_SPEC = {
    "type": "graphic",
    "id": EZURIO_SAVE_RECT_ID,
    "shape": "rectangle",
    "top_left": {"x_mm": -19.05, "y_mm": -33.02},
    "bottom_right": {"x_mm": 19.05, "y_mm": 20.32},
    "stroke": {"width_mm": 0.381, "style": "SLS_DEFAULT"},
    "filled": False,
}
EZURIO_TEXT_SPEC = {
    "type": "text",
    "text": "REV A",
    "position": {"x_mm": 0.0, "y_mm": -38.1},
    "attributes": {"size": {"width_mm": 1.27, "height_mm": 1.27}},
}
EZURIO_CREATED_TEXT_ID = "110d61f2-c98e-49a2-ad14-72f8a714d626"
EZURIO_SAVED_TEXT_ID = "08115973-dece-40ab-8237-992c1526358d"


@pytest.mark.anyio
async def test_mcp_write_symbol_items_creates_items(mcp_integration) -> None:
    async with mcp_integration("write_symbol_items_create.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": TEST_LIB_ID,
                "items": [
                    {
                        "type": "pin",
                        "name": "A",
                        "number": "2",
                        "position": {"x_mm": 3.81, "y_mm": 0.0},
                        "length_mm": 2.54,
                        "orientation": "SPO_LEFT",
                        "electrical_type": "EPT_PASSIVE",
                        "shape": "SPS_LINE",
                        "visible": True,
                        "name_text_size_mm": 1.27,
                        "number_text_size_mm": 1.27,
                    },
                    {
                        "type": "text",
                        "text": "A-K",
                        "position": {"x_mm": 0.0, "y_mm": -3.81},
                        "attributes": {"size": {"width_mm": 1.0, "height_mm": 1.0}},
                    },
                ],
                "save": False,
            },
        )
        followup = await server.call_tool(
            "get_symbol_items", {"lib_id": TEST_LIB_ID, "item_type": "pin"}
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["applied"] is True
    assert result["committed"] is True
    assert result["saved"] is False
    assert result["created_count"] == 2
    assert result["updated_count"] == 0
    assert result["removed_count"] == 0
    assert result["final_count"] == 10
    assert result["final_summary"] == {
        "fields": 5,
        "pins": 2,
        "graphics": 1,
        "texts": 2,
    }

    created = {item["type"]: item for item in result["created_items"]}
    assert set(created) == {"pin", "text"}
    assert created["pin"]["name"] == "A"
    assert created["pin"]["number"] == "2"
    assert created["pin"]["id"]
    assert created["text"]["text"] == "A-K"
    assert created["text"]["id"]

    pins = {pin["name"]: pin for pin in followup["items"]}
    assert set(pins) == {"K", "A"}
    # Existing items keep their unit; new items are common to all units.
    assert pins["K"]["unit"] == 1
    assert pins["K"]["body_style"] == 1
    assert pins["A"]["unit"] is None
    assert pins["A"]["body_style"] is None
    assert pins["A"]["position"] == {"x_mm": 3.81, "y_mm": 0.0}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_updates_item(mcp_integration) -> None:
    async with mcp_integration("write_symbol_items_update.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": TEST_LIB_ID,
                "items": [
                    {
                        "type": "pin",
                        "id": PIN_ID,
                        "name": "K",
                        "number": "1",
                        "position": {"x_mm": -5.08, "y_mm": 0.0},
                        "length_mm": 3.81,
                        "orientation": "SPO_RIGHT",
                        "electrical_type": "EPT_INPUT",
                        "shape": "SPS_CLOCK",
                        "visible": True,
                    }
                ],
                "save": False,
            },
        )
        followup = await server.call_tool(
            "get_symbol_items", {"lib_id": TEST_LIB_ID, "item_type": "pin"}
        )

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["committed"] is True
    assert result["updated_count"] == 1
    assert result["created_count"] == 0
    assert result["final_summary"]["pins"] == 1

    assert followup["count"] == 1
    pin = followup["items"][0]
    assert pin["id"] == PIN_ID
    assert pin["position"] == {"x_mm": -5.08, "y_mm": 0.0}
    assert pin["length_mm"] == 3.81
    assert pin["electrical_type"] == "EPT_INPUT"
    assert pin["shape"] == "SPS_CLOCK"
    # KiCad clears the unit and body-style tags when an item is updated.
    assert pin["unit"] is None
    assert pin["body_style"] is None
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_replaces_existing(mcp_integration) -> None:
    async with mcp_integration("write_symbol_items_replace.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": TEST_LIB_ID,
                "items": [
                    {
                        "type": "graphic",
                        "shape": "rectangle",
                        "top_left": {"x_mm": -2.54, "y_mm": 2.54},
                        "bottom_right": {"x_mm": 2.54, "y_mm": -2.54},
                        "stroke": {"width_mm": 0.254, "style": "SLS_DEFAULT"},
                        "filled": False,
                    }
                ],
                "replace_existing": True,
                "save": False,
            },
        )
        followup = await server.call_tool("get_symbol_items", {"lib_id": TEST_LIB_ID})

    assert result["ok"] is True
    assert result["replace_existing"] is True
    assert result["removed_count"] == 3
    assert result["created_count"] == 1
    assert result["final_count"] == 6
    assert result["final_summary"] == {"fields": 5, "graphics": 1}
    assert result["created_items"][0]["shape"] == "rectangle"
    assert result["created_items"][0]["filled"] is False

    assert followup["count"] == 6
    assert {item["type"] for item in followup["items"]} == {"field", "graphic"}
    rectangle = next(item for item in followup["items"] if item["type"] == "graphic")
    assert rectangle["size"] == {"width_mm": 5.08, "height_mm": 5.08}
    assert rectangle["unit"] is None
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_delete_symbol_items(mcp_integration) -> None:
    async with mcp_integration("delete_symbol_items.bin") as server:
        result = await server.call_tool(
            "delete_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_ids": [RECTANGLE_ID], "save": True},
        )
        followup = await server.call_tool("get_symbol_items", {"lib_id": TEST_LIB_ID})

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["committed"] is True
    assert result["saved"] is True
    assert result["removed_count"] == 1
    assert result["not_removed_count"] == 0
    assert result["deleted_items"] == [
        {"item_id": RECTANGLE_ID, "status": "IDS_OK", "removed": True}
    ]
    assert result["final_count"] == 7
    assert result["final_summary"] == {"fields": 5, "pins": 1, "texts": 1}

    assert {item.get("id") for item in followup["items"]} == {PIN_ID, TEXT_ID, None}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_rejects_fields(mcp_integration) -> None:
    async with mcp_integration("symbol_write_reject.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": TEST_LIB_ID,
                "items": [{"type": "field", "name": "MPN", "text": "NOPE"}],
                "save": False,
            },
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert result["retryable"] is False
    assert result["applied"] is False
    assert result["committed"] is False
    assert "fields cannot be created" in result["error"]
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_rejects_unit_assignment(mcp_integration) -> None:
    async with mcp_integration("symbol_items_opamp.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": MULTI_LIB_ID,
                "items": [
                    {
                        "type": "pin",
                        "name": "X",
                        "number": "9",
                        "position": {"x_mm": 0.0, "y_mm": 0.0},
                        "unit": 2,
                    }
                ],
                "save": False,
            },
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert "cannot assign a new symbol item to a unit" in result["error"]
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_rejects_multi_unit_update(
    mcp_integration,
) -> None:
    async with mcp_integration("symbol_items_opamp.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": MULTI_LIB_ID,
                "items": [
                    {
                        "type": "pin",
                        "id": MULTI_PIN_ID,
                        "name": "IN+",
                        "number": "1",
                        "position": {"x_mm": -7.62, "y_mm": 2.54},
                    }
                ],
                "save": False,
            },
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert "belongs to unit 1" in result["error"]
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_symbol_items_rejects_unknown_id(mcp_integration) -> None:
    async with mcp_integration("symbol_items_opamp.bin") as server:
        result = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": MULTI_LIB_ID,
                "items": [
                    {
                        "type": "pin",
                        "id": "99999999-9999-4999-8999-999999999999",
                        "name": "X",
                        "number": "9",
                        "position": {"x_mm": 0.0, "y_mm": 0.0},
                    }
                ],
                "save": False,
            },
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert "is not part of the open symbol" in result["error"]
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_large_symbol_items(mcp_integration) -> None:
    """Live recording: two small updates to the 45-item EZURIO-BL54L15 symbol."""
    async with mcp_integration(
        "write_symbol_items_ezurio.bin",
        "symbol_items_ezurio_modified.bin",
    ) as server:
        write = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": EZURIO_LIB_ID,
                "items": [EZURIO_PIN_SPEC, EZURIO_RECT_SPEC],
                "save": False,
            },
        )
        read = await server.call_tool("get_symbol_items", {"lib_id": EZURIO_LIB_ID})

    assert write["ok"] is True
    assert write["status"] == "ok"
    assert write["applied"] is True
    assert write["committed"] is True
    assert write["saved"] is False
    assert write["updated_count"] == 2
    assert write["created_count"] == 0
    assert write["removed_count"] == 0
    assert write["final_count"] == 45
    assert write["final_summary"] == {"fields": 5, "graphics": 1, "pins": 39}

    assert read["ok"] is True
    assert read["count"] == 45
    assert read["summary"] == {"fields": 5, "graphics": 1, "pins": 39}

    pins = {pin["number"]: pin for pin in read["items"] if pin["type"] == "pin"}
    assert len(pins) == 39

    updated = pins["2"]
    assert updated["id"] == EZURIO_PIN_ID
    assert updated["name"] == "P2.09"
    assert updated["position"] == {"x_mm": 21.59, "y_mm": 10.16}
    assert updated["length_mm"] == 1.27
    assert updated["shape"] == "SPS_INVERTED"
    # Updating an item clears its unit and body-style tags.
    assert updated["unit"] is None
    assert updated["body_style"] is None

    untouched = pins["3"]
    assert untouched["name"] == "P2.08"
    assert untouched["length_mm"] == 2.54
    assert untouched["shape"] == "SPS_LINE"
    assert untouched["unit"] == 1
    assert untouched["body_style"] == 1

    rectangle = next(item for item in read["items"] if item["type"] == "graphic")
    assert rectangle["id"] == EZURIO_RECT_ID
    assert rectangle["shape"] == "rectangle"
    assert rectangle["size"] == {"width_mm": 38.1, "height_mm": 53.34}
    assert rectangle["stroke"] == {"width_mm": 0.508, "style": "SLS_DEFAULT"}
    assert rectangle["unit"] is None
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_write_large_symbol_items_and_save(mcp_integration) -> None:
    """Live recording: update + create, then save the EZURIO library symbol."""
    async with mcp_integration(
        "write_symbol_items_ezurio_save.bin",
        "symbol_items_ezurio_saved.bin",
    ) as server:
        write = await server.call_tool(
            "write_symbol_items",
            {
                "lib_id": EZURIO_LIB_ID,
                "items": [EZURIO_SAVE_RECT_SPEC, EZURIO_TEXT_SPEC],
                "save": True,
            },
        )
        read = await server.call_tool("get_symbol_items", {"lib_id": EZURIO_LIB_ID})

    assert write["ok"] is True
    assert write["applied"] is True
    assert write["committed"] is True
    assert write["saved"] is True
    assert write["updated_count"] == 1
    assert write["created_count"] == 1
    assert write["removed_count"] == 0
    assert write["final_count"] == 46
    assert write["final_summary"] == {
        "fields": 5,
        "graphics": 1,
        "pins": 39,
        "texts": 1,
    }

    created = write["created_items"]
    assert len(created) == 1
    assert created[0]["type"] == "text"
    assert created[0]["text"] == "REV A"
    assert created[0]["id"] == EZURIO_CREATED_TEXT_ID

    assert read["ok"] is True
    assert read["count"] == 46
    assert read["summary"] == {
        "fields": 5,
        "graphics": 1,
        "pins": 39,
        "texts": 1,
    }

    text = next(item for item in read["items"] if item["type"] == "text")
    assert text["text"] == "REV A"
    assert text["position"] == {"x_mm": 0.0, "y_mm": -38.1}
    assert text["attributes"]["size"] == {"width_mm": 1.27, "height_mm": 1.27}
    assert text["unit"] is None
    assert text["body_style"] is None
    # Saving the symbol regenerates item UUIDs, so the read-back ID is not the
    # one reported in created_items.
    assert text["id"] == EZURIO_SAVED_TEXT_ID
    assert text["id"] != EZURIO_CREATED_TEXT_ID

    rectangle = next(item for item in read["items"] if item["type"] == "graphic")
    assert rectangle["shape"] == "rectangle"
    assert rectangle["stroke"] == {"width_mm": 0.381, "style": "SLS_DEFAULT"}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_delete_large_symbol_item(mcp_integration) -> None:
    """Live recording: delete the saved text item and save the symbol."""
    async with mcp_integration(
        "delete_symbol_items_ezurio.bin",
        "symbol_items_ezurio_deleted.bin",
    ) as server:
        delete = await server.call_tool(
            "delete_symbol_items",
            {
                "lib_id": EZURIO_LIB_ID,
                "item_ids": [EZURIO_SAVED_TEXT_ID],
                "save": True,
            },
        )
        read = await server.call_tool("get_symbol_items", {"lib_id": EZURIO_LIB_ID})

    assert delete["ok"] is True
    assert delete["applied"] is True
    assert delete["committed"] is True
    assert delete["saved"] is True
    assert delete["removed_count"] == 1
    assert delete["not_removed_count"] == 0
    assert delete["deleted_items"] == [
        {
            "item_id": EZURIO_SAVED_TEXT_ID,
            "status": "IDS_OK",
            "removed": True,
        }
    ]
    assert delete["final_count"] == 45
    assert delete["final_summary"] == {"fields": 5, "graphics": 1, "pins": 39}

    assert read["ok"] is True
    assert read["count"] == 45
    assert read["summary"] == {"fields": 5, "graphics": 1, "pins": 39}
    assert [item for item in read["items"] if item["type"] == "text"] == []

    rectangle = next(item for item in read["items"] if item["type"] == "graphic")
    assert rectangle["stroke"] == {"width_mm": 0.381, "style": "SLS_DEFAULT"}
    server.assert_complete()
