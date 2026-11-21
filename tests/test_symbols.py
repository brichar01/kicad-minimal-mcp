"""Integration tests for symbol reads through the MCP server."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "kicad-test:TEST_OPAMP"
FIXTURE = "symbol_items_opamp.bin"

PIN_1_ID = "11111111-1111-4111-8111-111111111111"
PIN_2_ID = "22222222-2222-4222-8222-222222222222"
PIN_3_ID = "33333333-3333-4333-8333-333333333333"
RECTANGLE_ID = "44444444-4444-4444-8444-444444444444"
CIRCLE_ID = "55555555-5555-4555-8555-555555555555"
TEXT_ID = "66666666-6666-4666-8666-666666666666"

# Recorded from the workspace nightly with GENERIC_DIODE open in the symbol editor.
DIODE_LIB_ID = "benri-projects:GENERIC_DIODE"
DIODE_FIXTURE = "symbol_items_generic_diode.bin"
DIODE_PIN_K_ID = "9879f843-a667-4822-be5e-e6ab1b28c6d4"
DIODE_PIN_A_ID = "b4fcf0fc-9eab-4b3f-9804-c314876b7865"
DIODE_TRIANGLE_ID = "2e0ec950-b789-431c-b4b9-de37ec20af88"
DIODE_LEAD_ID = "9d96e507-fd65-40a7-9be2-1760c591b12a"
DIODE_BAR_ID = "194342b3-b373-4eae-8678-b1a2ff80cd92"


@pytest.mark.anyio
async def test_mcp_get_symbol_items(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool("get_symbol_items", {"lib_id": TEST_LIB_ID})

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["unit"] == "mm"

    assert result["symbol"]["type"] == "DOCTYPE_SYMBOL"
    assert result["symbol"]["lib_id"]["lib_id"] == TEST_LIB_ID

    definition = result["definition"]
    assert definition["lib_id"] == TEST_LIB_ID
    assert definition["type"] == "SST_NORMAL"
    assert definition["unit_count"] == 2
    assert definition["body_styles"] == ["Normal", "De Morgan"]
    assert definition["keywords"] == "opamp test"
    assert definition["footprint_filters"] == ["Package_SO:*"]
    assert definition["attributes"]["exclude_from_bill_of_materials"] is True
    assert definition["attributes"]["exclude_from_board"] is False

    assert result["count"] == 12
    assert result["summary"] == {
        "fields": 6,
        "pins": 3,
        "graphics": 2,
        "texts": 1,
    }
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_pins(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_type": "pin"},
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["count"] == 3
    assert result["summary"] == {"pins": 3}

    pins = {pin["name"]: pin for pin in result["items"]}
    assert set(pins) == {"IN+", "OUT", "V-"}

    assert pins["IN+"]["id"] == PIN_1_ID
    assert pins["IN+"]["number"] == "1"
    assert pins["IN+"]["position"] == {"x_mm": -7.62, "y_mm": 2.54}
    assert pins["IN+"]["length_mm"] == 2.54
    assert pins["IN+"]["orientation"] == "SPO_RIGHT"
    assert pins["IN+"]["electrical_type"] == "EPT_INPUT"
    assert pins["IN+"]["shape"] == "SPS_LINE"
    assert pins["IN+"]["visible"] is True
    assert pins["IN+"]["unit"] == 1
    assert pins["IN+"]["body_style"] is None
    assert pins["IN+"]["alternates"] == []

    assert pins["OUT"]["id"] == PIN_2_ID
    assert pins["OUT"]["shape"] == "SPS_CLOCK"
    assert pins["OUT"]["active_alternate"] == "ALT"
    assert pins["OUT"]["alternates"] == [
        {
            "name": "ALT",
            "shape": "SPS_INVERTED",
            "electrical_type": "EPT_BIDIRECTIONAL",
        }
    ]

    assert pins["V-"]["id"] == PIN_3_ID
    assert pins["V-"]["electrical_type"] == "EPT_POWER_INPUT"
    assert pins["V-"]["unit"] == 2
    assert pins["V-"]["body_style"] == 2
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_fields(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_type": "field"},
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["count"] == 6
    assert result["summary"] == {"fields": 6}

    fields = {field["name"]: field for field in result["items"]}
    assert set(fields) == {
        "Reference",
        "Value",
        "Footprint",
        "Datasheet",
        "Description",
        "MPN",
    }

    # Symbol fields have no UUID in the IPC API.
    assert {field["id"] for field in fields.values()} == {None}
    assert {field["unit"] for field in fields.values()} == {None}
    assert {field["body_style"] for field in fields.values()} == {None}

    reference = fields["Reference"]
    assert reference["field_id"] == 1
    assert reference["text"] == "U"
    assert reference["visible"] is True
    assert reference["position"] == {"x_mm": 0.0, "y_mm": 5.08}
    assert reference["attributes"]["bold"] is True
    assert reference["attributes"]["size"] == {"width_mm": 1.27, "height_mm": 1.27}

    assert fields["Value"]["field_id"] == 2
    assert fields["Value"]["text"] == TEST_LIB_ID.split(":")[1]
    assert fields["Footprint"]["field_id"] == 3
    assert fields["Footprint"]["visible"] is False
    assert fields["Datasheet"]["field_id"] == 4
    assert fields["Description"]["field_id"] == 5

    assert fields["MPN"]["field_id"] == 0
    assert fields["MPN"]["text"] == "TEST-123"
    assert fields["MPN"]["is_private"] is True
    assert fields["MPN"]["position"] == {"x_mm": 0.0, "y_mm": -7.62}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_graphics(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_type": "graphics"},
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["count"] == 2
    assert result["summary"] == {"graphics": 2}

    graphics = {item["id"]: item for item in result["items"]}
    assert set(graphics) == {RECTANGLE_ID, CIRCLE_ID}

    rectangle = graphics[RECTANGLE_ID]
    assert rectangle["shape"] == "rectangle"
    assert rectangle["top_left"] == {"x_mm": -5.08, "y_mm": 5.08}
    assert rectangle["bottom_right"] == {"x_mm": 5.08, "y_mm": -5.08}
    assert rectangle["size"] == {"width_mm": 10.16, "height_mm": 10.16}
    assert rectangle["filled"] is True
    assert rectangle["stroke"] == {"width_mm": 0.254, "style": "SLS_DEFAULT"}
    assert rectangle["unit"] == 1

    circle = graphics[CIRCLE_ID]
    assert circle["shape"] == "circle"
    assert circle["center"] == {"x_mm": 0.0, "y_mm": 2.54}
    assert circle["radius_mm"] == 1.27
    assert circle["filled"] is False
    assert circle["unit"] is None
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_text(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_type": "text"},
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["count"] == 1
    assert result["summary"] == {"texts": 1}

    text = result["items"][0]
    assert text["id"] == TEXT_ID
    assert text["text"] == "TEST"
    assert text["position"] == {"x_mm": 0.0, "y_mm": 7.62}
    assert text["attributes"]["italic"] is True
    assert text["attributes"]["size"] == {"width_mm": 1.27, "height_mm": 1.27}
    assert text["unit"] is None
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_items_by_id(mcp_integration) -> None:
    async with mcp_integration(FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": TEST_LIB_ID, "item_ids": [PIN_3_ID, CIRCLE_ID, "missing"]},
        )

    assert result["ok"] is True
    assert result["error"] is None
    assert result["count"] == 2
    assert {item["id"] for item in result["items"]} == {PIN_3_ID, CIRCLE_ID}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_symbol_items_rejects_unknown_type(mcp_no_kicad) -> None:
    async with mcp_no_kicad() as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"item_type": "not-a-real-item-type"},
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert result["retryable"] is False
    assert result["connected"] is False
    assert result["error"]
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_generic_diode_items(mcp_integration) -> None:
    """Live recording: GENERIC_DIODE from the benri-projects library."""
    async with mcp_integration(DIODE_FIXTURE) as server:
        result = await server.call_tool("get_symbol_items", {"lib_id": DIODE_LIB_ID})

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["unit"] == "mm"
    assert result["symbol"]["lib_id"]["lib_id"] == DIODE_LIB_ID

    definition = result["definition"]
    assert definition["lib_id"] == DIODE_LIB_ID
    assert definition["type"] == "SST_NORMAL"
    assert definition["unit_count"] == 1
    assert definition["body_styles"] == ["?"]
    assert definition["keywords"] == "SparkFun diode"
    assert definition["footprint_filters"] == [
        "TO-???*",
        "*_Diode_*",
        "*SingleDiode*",
        "D_*",
    ]
    assert definition["attributes"] == {
        "exclude_from_simulation": False,
        "exclude_from_bill_of_materials": False,
        "exclude_from_board": False,
        "exclude_from_position_files": False,
        "do_not_populate": False,
    }

    assert result["count"] == 11
    assert result["summary"] == {"fields": 6, "graphics": 3, "pins": 2}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_generic_diode_pins(mcp_integration) -> None:
    async with mcp_integration(DIODE_FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": DIODE_LIB_ID, "item_type": "pin"},
        )

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["summary"] == {"pins": 2}

    pins = {pin["name"]: pin for pin in result["items"]}
    assert set(pins) == {"K", "A"}

    cathode = pins["K"]
    assert cathode["id"] == DIODE_PIN_K_ID
    assert cathode["number"] == "1"
    assert cathode["position"] == {"x_mm": 2.54, "y_mm": 0.0}
    assert cathode["orientation"] == "SPO_LEFT"
    assert cathode["length_mm"] == 1.778
    assert cathode["electrical_type"] == "EPT_PASSIVE"
    assert cathode["shape"] == "SPS_LINE"
    assert cathode["visible"] is True
    assert cathode["name_text_size_mm"] == 1.27
    assert cathode["number_text_size_mm"] == 1.27
    assert cathode["unit"] == 1
    assert cathode["body_style"] == 1
    assert cathode["alternates"] == []

    anode = pins["A"]
    assert anode["id"] == DIODE_PIN_A_ID
    assert anode["number"] == "2"
    assert anode["position"] == {"x_mm": -2.54, "y_mm": 0.0}
    assert anode["orientation"] == "SPO_RIGHT"
    assert anode["length_mm"] == 1.778
    assert anode["electrical_type"] == "EPT_PASSIVE"
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_generic_diode_fields(mcp_integration) -> None:
    async with mcp_integration(DIODE_FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": DIODE_LIB_ID, "item_type": "field"},
        )

    assert result["ok"] is True
    assert result["count"] == 6
    assert result["summary"] == {"fields": 6}

    fields = {field["name"]: field for field in result["items"]}
    assert set(fields) == {
        "Reference",
        "Value",
        "Footprint",
        "Datasheet",
        "Description",
        "Component",
    }
    assert {field["id"] for field in fields.values()} == {None}

    reference = fields["Reference"]
    assert reference["field_id"] == 1
    assert reference["text"] == "D"
    assert reference["visible"] is True
    assert reference["position"] == {"x_mm": 0.0, "y_mm": -2.54}
    assert reference["attributes"]["horizontal_alignment"] == "HA_CENTER"

    assert fields["Value"]["field_id"] == 2
    assert fields["Value"]["text"] == "Val"
    assert fields["Value"]["visible"] is False
    assert fields["Value"]["position"] == {"x_mm": 0.0, "y_mm": 2.54}
    assert fields["Footprint"]["field_id"] == 3
    assert fields["Footprint"]["position"] == {"x_mm": 0.0, "y_mm": 10.16}
    assert fields["Datasheet"]["field_id"] == 4
    assert fields["Datasheet"]["position"] == {"x_mm": 0.0, "y_mm": 11.684}
    assert fields["Description"]["field_id"] == 5
    assert fields["Description"]["text"] == "Diode"
    assert fields["Component"]["field_id"] == 0
    assert fields["Component"]["text"] == ""
    assert fields["Component"]["is_private"] is False
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_generic_diode_graphics(mcp_integration) -> None:
    async with mcp_integration(DIODE_FIXTURE) as server:
        result = await server.call_tool(
            "get_symbol_items",
            {"lib_id": DIODE_LIB_ID, "item_type": "graphic"},
        )

    assert result["ok"] is True
    assert result["count"] == 3
    assert result["summary"] == {"graphics": 3}

    graphics = {item["id"]: item for item in result["items"]}
    assert set(graphics) == {DIODE_TRIANGLE_ID, DIODE_LEAD_ID, DIODE_BAR_ID}

    triangle = graphics[DIODE_TRIANGLE_ID]
    assert triangle["shape"] == "polygon"
    assert triangle["filled"] is False
    assert triangle["stroke"] == {"width_mm": 0.254, "style": "SLS_DEFAULT"}
    # KiCad serialises "common to all units" as unit 0; the reader reports None.
    assert triangle["unit"] is None
    assert triangle["body_style"] == 1
    assert triangle["polygons"] == [
        {
            "outline": [
                {"x_mm": -0.762, "y_mm": 1.016},
                {"x_mm": 0.762, "y_mm": 0.0},
                {"x_mm": -0.762, "y_mm": -1.016},
                {"x_mm": -0.762, "y_mm": 1.016},
            ],
            "closed": False,
            "holes": [],
        }
    ]

    lead = graphics[DIODE_LEAD_ID]
    assert lead["polygons"] == [
        {
            "outline": [
                {"x_mm": 0.762, "y_mm": 0.0},
                {"x_mm": -0.762, "y_mm": 0.0},
            ],
            "closed": False,
            "holes": [],
        }
    ]
    assert lead["stroke"] == {"width_mm": 0.0, "style": "SLS_DEFAULT"}

    bar = graphics[DIODE_BAR_ID]
    assert bar["polygons"] == [
        {
            "outline": [
                {"x_mm": 0.762, "y_mm": 1.016},
                {"x_mm": 0.762, "y_mm": -1.016},
            ],
            "closed": False,
            "holes": [],
        }
    ]
    server.assert_complete()
