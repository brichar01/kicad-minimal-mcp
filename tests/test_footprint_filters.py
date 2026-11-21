"""Integration tests for filtered footprint item reads and writes."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "benri-projects:JST_SM04B-SR_R"
PAD_ID = "5901c8dd-c8ff-4d4a-b5bd-8876bf2bb8aa"
GRAPHIC_ID = "efac83a1-1bcd-46ea-ac9f-d38a58e3b443"

PAD_SPEC = {
    "type": "pad",
    "id": PAD_ID,
    "number": "1",
    "position": {"x_mm": -2.45, "y_mm": -1.5},
    "pad_type": "PT_SMD",
    "padstack_type": "PST_NORMAL",
    "layers": ["BL_F_Cu", "BL_F_Mask", "BL_F_Paste"],
    "copper_layers": [
        {
            "layer": "BL_F_Cu",
            "shape": "PSS_RECTANGLE",
            "size": {"width_mm": 1.55, "height_mm": 0.6},
            "offset": {"x_mm": 0.0, "y_mm": 0.0},
        }
    ],
}


@pytest.mark.anyio
async def test_mcp_get_footprint_items_by_id(mcp_integration) -> None:
    async with mcp_integration("footprint_items_by_id.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {
                "lib_id": TEST_LIB_ID,
                "item_ids": [PAD_ID, GRAPHIC_ID],
            },
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 2
    assert result["summary"] == {"pads": 1, "graphics": 1}
    assert {item["id"] for item in result["items"]} == {PAD_ID, GRAPHIC_ID}
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_update_footprint_item_by_id(mcp_integration) -> None:
    async with mcp_integration("write_footprint_items_update.bin") as server:
        result = await server.call_tool(
            "write_footprint_items",
            {
                "lib_id": TEST_LIB_ID,
                "items": [PAD_SPEC],
                "save": False,
            },
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["applied"] is True
    assert result["committed"] is True
    assert result["saved"] is False
    assert result["created_count"] == 0
    assert result["updated_count"] == 1
    assert result["removed_count"] == 0
    assert result["final_count"] == 26
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_delete_footprint_item_by_id(mcp_integration) -> None:
    async with mcp_integration("delete_footprint_items.bin") as server:
        result = await server.call_tool(
            "delete_footprint_items",
            {
                "lib_id": TEST_LIB_ID,
                "item_ids": [GRAPHIC_ID],
                "save": False,
            },
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["applied"] is True
    assert result["committed"] is True
    assert result["saved"] is False
    assert result["removed_count"] == 1
    assert result["final_count"] == 25
    assert result["final_summary"] == {
        "pads": 6,
        "graphics": 14,
        "fields": 4,
        "texts": 1,
    }
    server.assert_complete()
