"""Facade coordinate helpers.

Conventions: x = east, y = north, z = up, metres.
For a rectangle (ox, oy, W, D) every side has a local frame:
  u = distance along the facade from its LEFT end as seen from outside,
  d = depth into the building from the exterior face (negative = outside).
"""
from __future__ import annotations

SIDES = ("S", "N", "E", "W")


def side_length(side: str, W: float, D: float) -> float:
    return W if side in ("S", "N") else D


def facade_xy(side: str, ox: float, oy: float, W: float, D: float, u: float, d: float):
    if side == "S":
        return ox + u, oy + d
    if side == "N":
        return ox + W - u, oy + D - d
    if side == "E":
        return ox + W - d, oy + u
    if side == "W":
        return ox + d, oy + D - u
    raise ValueError(f"unknown side {side!r}")


def facade_box(side, ox, oy, W, D, u0, u1, d0, d1, z0, z1):
    """Axis-aligned box (x0, y0, z0, dx, dy, dz) from facade-local ranges."""
    pts = [facade_xy(side, ox, oy, W, D, u, d) for u in (u0, u1) for d in (d0, d1)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    return (x0, y0, min(z0, z1), max(xs) - x0, max(ys) - y0, abs(z1 - z0))


def subtract_intervals(span, cuts, eps=1e-6):
    """span (a, b) minus list of (a, b) intervals -> list of remaining intervals."""
    out = [tuple(span)]
    for c0, c1 in sorted(cuts):
        nxt = []
        for a, b in out:
            if c1 <= a + eps or c0 >= b - eps:
                nxt.append((a, b))
                continue
            if c0 > a + eps:
                nxt.append((a, c0))
            if c1 < b - eps:
                nxt.append((c1, b))
        out = nxt
    return [(a, b) for a, b in out if b - a > 0.01]
