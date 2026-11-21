"""Shared geometry conversions for board and symbol graphic shapes."""

from __future__ import annotations

from typing import Any

from kicad_minimal_mcp.units import point_to_dict


def polygon_geometry_to_dict(item: Any) -> list[dict[str, Any]]:
    """Convert a shape's ``polygons`` view to outlines, holes, and closed flags."""
    polygons = []
    for polygon in item.polygons:
        outline = []
        for node in polygon.outline.nodes:
            if node.has_point:
                outline.append(point_to_dict(node.point))
            else:
                outline.append(
                    {
                        "arc": {
                            "start": point_to_dict(node.arc.start),
                            "mid": point_to_dict(node.arc.mid),
                            "end": point_to_dict(node.arc.end),
                        }
                    }
                )

        holes = []
        for hole in polygon.holes:
            holes.append(
                [point_to_dict(node.point) for node in hole.nodes if node.has_point]
            )

        polygons.append(
            {"outline": outline, "closed": polygon.outline.closed, "holes": holes}
        )

    return polygons
