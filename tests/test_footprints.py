"""Integration tests driven through the MCP server over a fake KiCad socket."""

from __future__ import annotations

from itertools import pairwise

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "benri-projects:EZURIO-BL54L15_T"


@pytest.mark.anyio
async def test_mcp_get_open_documents(mcp_integration) -> None:
    async with mcp_integration("open_documents_footprint.bin") as server:
        result = await server.call_tool(
            "get_open_documents",
            {"document_type": "footprint"},
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 1
    assert result["documents"][0]["lib_id"]["lib_id"] == TEST_LIB_ID
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_footprint_items(mcp_integration) -> None:
    async with mcp_integration("footprint_items_all.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_type": "all"},
        )

    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 52
    assert result["summary"] == {
        "pads": 39,
        "graphics": 7,
        "fields": 4,
        "texts": 2,
    }
    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_footprint_pads(mcp_integration) -> None:
    async with mcp_integration("footprint_items_pad.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_type": "pad"},
        )

    assert result["ok"] is True
    assert result["status"] == "ok"
    assert result["retryable"] is False
    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 39
    assert result["summary"] == {"pads": 39}

    pads = {int(item["number"]): item for item in result["items"]}
    assert set(pads) == set(range(1, 40))

    rows = [
        (range(1, 17), "y_mm", 4.497, {"width_mm": 0.5, "height_mm": 0.55}),
        (range(17, 28), "x_mm", -6.497, {"width_mm": 0.55, "height_mm": 0.5}),
        (range(28, 40), "y_mm", -4.497, {"width_mm": 0.5, "height_mm": 0.55}),
    ]
    for numbers, position_axis, position_mm, size_mm in rows:
        row = [pads[number] for number in numbers]
        for pad in row:
            assert pad["pad_type"] == "PT_SMD"
            assert pad["layers"] == ["BL_F_Cu", "BL_F_Mask", "BL_F_Paste"]
            assert pad["size"] == size_mm
            assert pad["position"][position_axis] == position_mm

        other_axis = "x_mm" if position_axis == "y_mm" else "y_mm"
        positions = sorted(pad["position"][other_axis] for pad in row)
        deltas = [round(right - left, 6) for left, right in pairwise(positions)]
        assert deltas
        assert set(deltas) == {0.75}

    server.assert_complete()


@pytest.mark.anyio
async def test_mcp_get_footprint_graphics(mcp_integration) -> None:
    async with mcp_integration("footprint_items_graphic.bin") as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_type": "graphic"},
        )

    assert result["connected"] is True
    assert result["error"] is None
    assert result["count"] == 7
    assert result["summary"] == {"graphics": 7}

    graphics = result["items"]
    fab_rectangles = [
        item
        for item in graphics
        if item["shape"] == "rectangle" and item["layer"] == "BL_F_Fab"
    ]
    assert any(
        item["size"] == {"width_mm": 14.0, "height_mm": 10.0} for item in fab_rectangles
    )

    keepouts = [
        item
        for item in graphics
        if item["shape"] == "rectangle"
        and item["layer"] == "BL_Cmts_User"
        and item["size"] == {"width_mm": 5.0, "height_mm": 8.5}
    ]
    assert len(keepouts) == 1
    assert keepouts[0]["top_left"] == {"x_mm": 2.0, "y_mm": -4.85}
    assert keepouts[0]["bottom_right"] == {"x_mm": 7.0, "y_mm": 3.65}

    pin_one_markers = [
        item
        for item in graphics
        if item["shape"] == "circle"
        and item["layer"] == "BL_F_SilkS"
        and item["center"] == {"x_mm": 5.45, "y_mm": 4.497}
        and item["radius_mm"] == 0.25
    ]
    assert len(pin_one_markers) == 1

    server.assert_complete()
