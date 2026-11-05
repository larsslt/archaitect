"""Garden pond: a natural, irregular outline inside the component's bounding box (x, y = lower-left corner, width x depth).
The same outline drives the terrain (basin) and the IFC (water, rim stones), so both always agree."""
from __future__ import annotations

import math


def outline(c: dict, n: int = 18) -> list[tuple[float, float]]:
    x, y, w, d = float(c["x"]), float(c["y"]), float(c.get("width", 8.0)), float(c.get("depth", 5.5))
    cx, cy, rx, ry = x + w / 2, y + d / 2, w / 2 * 0.94, d / 2 * 0.94
    p1 = (int(x * 13 + y * 7) % 628) / 100.0           # deterministic per position: a moved pond keeps a natural but stable shape
    p2 = (int(x * 5 + y * 11) % 628) / 100.0
    pts = []
    for k in range(n):
        t = 2 * math.pi * k / n
        m = 1.0 + 0.13 * math.sin(2 * t + p1) + 0.08 * math.sin(3 * t + p2)
        m = min(m, 1.0 / 0.94) * 0.94
        pts.append((round(cx + rx * m * math.cos(t), 3), round(cy + ry * m * math.sin(t), 3)))
    return pts


def polygon(c: dict):
    from shapely.geometry import Polygon
    return Polygon(outline(c))
