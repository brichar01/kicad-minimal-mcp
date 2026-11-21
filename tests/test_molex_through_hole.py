"""Integration tests for a through-hole footprint with both solder-mask sides."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "benri-projects:MOLEX_22232021_C"

PAD_1_ID = "add0bb5c-52b7-4e43-b867-c5b9c8291b3c"
PAD_2_ID = "176a78b3-e41b-4f6b-af25-87f0df5c3db5"


@pytest.mark.anyio
async def test_mcp_get_molex_footprint_items(mcp_integration) -> None:
    async with mcp_integration("footprint_items_molex_all.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_type": "all"},
        )

    assert result["connected"] is True
    assert result["error"] is None
    assert result["footprint"]["lib_id"]["lib_id"] == TEST_LIB_ID
    assert result["count"] == 40
    assert result["summary"] == {
        "pads": 2,
        "graphics": 32,
        "fields": 4,
        "texts": 2,
    }
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_molex_through_hole_pads(mcp_integration) -> None:
    async with mcp_integration("footprint_items_molex_pad.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_type": "pad"},
        )

    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 2
    assert result["summary"] == {"pads": 2}

    pads = {pad["number"]: pad for pad in result["items"]}
    assert set(pads) == {"1", "2"}
    assert {pad["id"] for pad in pads.values()} == {PAD_1_ID, PAD_2_ID}

    for pad in pads.values():
        assert pad["pad_type"] == "PT_PTH"
        assert pad["padstack_type"] == "PST_NORMAL"
        assert pad["shape"] == "PSS_CIRCLE"
        assert pad["size"] == {"width_mm": 1.7, "height_mm": 1.7}

        assert "BL_F_Mask" in pad["layers"]
        assert "BL_B_Mask" in pad["layers"]
        assert pad["layers"].count("BL_F_Mask") == 1
        assert pad["layers"].count("BL_B_Mask") == 1

        assert "BL_F_Cu" in pad["layers"]
        assert "BL_B_Cu" in pad["layers"]
        assert "BL_In1_Cu" in pad["layers"]
        assert "BL_In30_Cu" in pad["layers"]

        assert pad["drill"] == {
            "diameter": {"width_mm": 1.0, "height_mm": 1.0},
            "shape": "DS_CIRCLE",
            "start_layer": "BL_F_Cu",
            "end_layer": "BL_B_Cu",
        }

    assert pads["1"]["position"] == {"x_mm": 0.0, "y_mm": -1.27}
    assert pads["2"]["position"] == {"x_mm": 0.0, "y_mm": 1.27}
    server.assert_complete()
