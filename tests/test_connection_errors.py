"""Integration tests for graceful handling of an unavailable KiCad instance."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

TEST_LIB_ID = "benri-projects:MOLEX_22232021_C"
TEST_ITEM_ID = "add0bb5c-52b7-4e43-b867-c5b9c8291b3c"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("kicad_status", {}),
        ("get_open_documents", {"document_type": "footprint"}),
        ("get_footprint_items", {"lib_id": TEST_LIB_ID}),
        ("get_symbol_items", {"lib_id": "kicad-test:TEST_OPAMP"}),
        (
            "write_symbol_items",
            {"lib_id": "kicad-test:TEST_OPAMP", "items": [], "save": False},
        ),
        (
            "delete_symbol_items",
            {
                "lib_id": "kicad-test:TEST_OPAMP",
                "item_ids": [TEST_ITEM_ID],
                "save": False,
            },
        ),
        (
            "write_footprint_items",
            {"lib_id": TEST_LIB_ID, "items": [], "save": False},
        ),
        (
            "delete_footprint_items",
            {"lib_id": TEST_LIB_ID, "item_ids": [TEST_ITEM_ID], "save": False},
        ),
    ],
)
async def test_tool_reports_unavailable_kicad(
    mcp_no_kicad,
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    async with mcp_no_kicad() as server:
        result = await server.call_tool(tool_name, arguments)

    assert result["ok"] is False
    assert result["status"] == "kicad_unavailable"
    assert result["retryable"] is True
    assert result["connected"] is False
    assert isinstance(result["error"], str)
    assert result["error"]
    if tool_name in {
        "write_footprint_items",
        "delete_footprint_items",
        "write_symbol_items",
        "delete_symbol_items",
    }:
        assert result["applied"] is False
        assert result["committed"] is False
    server.assert_complete()


@pytest.mark.anyio
async def test_invalid_request_has_non_retryable_status(mcp_no_kicad) -> None:
    async with mcp_no_kicad() as server:
        result = await server.call_tool(
            "get_footprint_items",
            {"item_type": "not-a-real-item-type"},
        )

    assert result["ok"] is False
    assert result["status"] == "invalid_request"
    assert result["retryable"] is False
    assert result["connected"] is False
    assert result["error"]
    server.assert_complete()
