"""Terrain for the BIM pipeline: official DGM1 heights of the plot -> graded ground around the building (Geländemodell mit Bauplateau).

Inputs come from the site pack (``terrain.grid``: heights on a regular grid in the project's local frame, x East, y North, z above NHN).
The building spec has its own frame (origin near the house, floor level = 0). ``placement`` maps spec -> site frame:
    site = R(rot_deg) * spec + (x, y)
The output ``site.terrain`` section of the spec is expressed in the SPEC frame with heights relative to the building pad (pad = 0),
so renderer, 360° viewer and IFC all agree: the finished floor is at z = 0 and the ground rises or falls around it.

Grading rule (Böschung): inside the pad the ground is level at ``pad_z``; outside, the new ground follows the natural terrain but never
deviates from the pad level by more than ``distance_to_pad * slope`` (slope 0.5 = 1:2). Where the natural terrain is steeper than that,
the difference is cut (Abtrag) or filled (Auftrag). Volumes are computed from the same grid and reported, never hidden.

Nothing here is a permit-grade earthwork design; the numbers come from a 1 m terrain model (bare earth) and are for planning and rendering.
"""
from __future__ import annotations

from .ifc_garden2 import TYPES as G2_TYPES

import math
from dataclasses import dataclass

from shapely import affinity
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

DEFAULT_SLOPE = 0.5          # rise/run of the embankment, 1:2
PAD_DROP_M = 0.04            # ground a hair below the floor slab: door thresholds / plinths never get buried by the terrain mesh
DEFAULT_PAD_MARGIN_M = 1.5   # level ground around the building and garden objects
MAX_FILL_WARN_M = 1.5        # embankments higher than this are called out
MAX_MESH_CELLS = 120         # per side, keeps GLB/JSON and the Blender mesh small


@dataclass
class Placement:
    x: float = 0.0
    y: float = 0.0
    rotation_deg: float = 0.0

    @classmethod
    def from_spec(cls, spec: dict) -> "Placement":
        p = (spec.get("site") or {}).get("placement") or {}
        return cls(float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("rotation_deg", 0.0)))

    def to_site(self, x: float, y: float) -> tuple[float, float]:
        a = math.radians(self.rotation_deg)
        c, s = math.cos(a), math.sin(a)
        return self.x + c * x - s * y, self.y + s * x + c * y

    def to_spec(self, x: float, y: float) -> tuple[float, float]:
        a = math.radians(self.rotation_deg)
        c, s = math.cos(a), math.sin(a)
        dx, dy = x - self.x, y - self.y
        return c * dx + s * dy, -s * dx + c * dy

    def poly_to_site(self, poly: Polygon) -> Polygon:
        return affinity.translate(affinity.rotate(poly, self.rotation_deg, origin=(0, 0)), self.x, self.y)

    def poly_to_spec(self, poly: Polygon) -> Polygon:
        return affinity.rotate(affinity.translate(poly, -self.x, -self.y), -self.rotation_deg, origin=(0, 0))


class Heights:
    """Bilinear sampler over the site pack's terrain grid (site frame). Missing cells are filled from their neighbours."""

    def __init__(self, grid: dict, native_m: float = 1.0):
        rows = grid["heights_m"]
        self.step = float(grid["cell_m"])
        self.nx = max((len(r) for r in rows), default=0)
        self.ny = len(rows)
        self.x0 = float(grid["x_west_local"]) + native_m / 2
        self.y0 = float(grid["y_north_local"]) - native_m / 2
        self.z = [[None if v is None else float(v) for v in r] + [None] * (self.nx - len(r)) for r in rows]
        self._fill()

    @property
    def valid(self) -> bool:
        return self.nx >= 2 and self.ny >= 2 and any(v is not None for r in self.z for v in r)

    def _fill(self) -> None:
        if not any(v is not None for r in self.z for v in r):
            return
        for _ in range(self.nx + self.ny):
            missing = [(i, j) for j in range(self.ny) for i in range(self.nx) if self.z[j][i] is None]
            if not missing:
                return
            upd = {}
            for i, j in missing:
                nb = [self.z[jj][ii] for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                      if 0 <= ii < self.nx and 0 <= jj < self.ny and self.z[jj][ii] is not None]
                if nb:
                    upd[(i, j)] = sum(nb) / len(nb)
            for (i, j), v in upd.items():
                self.z[j][i] = v

    def at(self, x: float, y: float) -> float:
        """Terrain height at a site-frame point; outside the grid the nearest edge value is used."""
        fx = (x - self.x0) / self.step
        fy = (self.y0 - y) / self.step          # row 0 is north
        fx = min(max(fx, 0.0), self.nx - 1.0)
        fy = min(max(fy, 0.0), self.ny - 1.0)
        i, j = min(int(fx), self.nx - 2), min(int(fy), self.ny - 2)
        tx, ty = fx - i, fy - j
        z = self.z
        return (z[j][i] * (1 - tx) * (1 - ty) + z[j][i + 1] * tx * (1 - ty)
                + z[j + 1][i] * (1 - tx) * ty + z[j + 1][i + 1] * tx * ty)


def heights_from_pack(pack: dict) -> Heights | None:
    t = (pack or {}).get("terrain") or {}
    if t.get("status") != "OK" or not t.get("grid"):
        return None
    h = Heights(t["grid"], float(t.get("cell_m_native") or 1.0))
    return h if h.valid else None


# ------------------------------------------------------------------------------------------------ footprints
def _rect(origin, size, rot=0.0) -> Polygon:
    r = box(origin[0], origin[1], origin[0] + size[0], origin[1] + size[1])
    return affinity.rotate(r, rot, origin=tuple(origin)) if rot else r


def dressing_polygon(spec: dict, margin: float = DEFAULT_PAD_MARGIN_M) -> Polygon | None:
    """Area that must be level because IFC elements stand on z = 0 there: building volumes, curtain walls and garden components with fixed position."""
    parts: list[Polygon] = []
    for v in spec.get("volumes", []):
        if float(v.get("base_z", 0.0)) <= 1.0:      # incl. raised ground floor (entrance steps)
            parts.append(_rect(v["origin"], v["size"], float(v.get("rotation_deg", 0.0))))
    for cw in spec.get("curtain_walls", []):
        parts.append(_rect(cw["origin"], cw["size"]))
    for key in ("paving", "pools", "paths"):
        for r in (spec.get("site") or {}).get(key, []):
            parts.append(_rect(r["origin"], r["size"]))
    vols = {v["id"]: v for v in spec.get("volumes", [])}
    for c in spec.get("components", []):
        t = c.get("type")
        v = vols.get(c.get("volume"))
        if v is not None and c.get("side") in ("S", "N", "E", "W") and t in ("terrace", "steps", "ramp", "carport", "stair_ext", "loggia"):
            # attached to a facade: its footprint must stand on the same level pad, otherwise terraces hover over a sloping site
            ox, oy = v["origin"]
            W, D = v["size"]
            side = c["side"]
            L = W if side in "SN" else D
            u = float(c["u"]) if c.get("u") is not None else L / 2
            w = float(c.get("width", 4.0 if t in ("terrace", "carport") else 1.8))
            dp = float(c.get("depth") or c.get("projection") or (3.0 if t in ("terrace", "carport") else 1.6))
            a, b = u - w / 2, u + w / 2
            rect = {"S": (ox + a, oy - dp, ox + b, oy), "N": (ox + a, oy + D, ox + b, oy + D + dp),
                    "W": (ox - dp, oy + a, ox, oy + b), "E": (ox + W, oy + a, ox + W + dp, oy + b)}[side]
            parts.append(box(*rect))
            continue
        if t == "path" and c.get("points"):
            pts = c["points"]
            hw = float(c.get("width", 1.2)) / 2
            for a, b in zip(pts, pts[1:]):
                parts.append(box(min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw))
            continue
        if c.get("x") is None or c.get("y") is None:
            continue
        w, d = float(c.get("width", 3.0)), float(c.get("depth", 3.0))
        if t in ("pool", "flowerbed", "parking", "terrace", "carport", "ramp", "garden_set", "bench") or t in G2_TYPES:
            parts.append(box(c["x"], c["y"], c["x"] + w, c["y"] + d))
        elif t in ("tree", "shrub", "garden_light"):
            parts.append(Point(c["x"], c["y"]).buffer(1.0))
        elif t == "path" and c.get("points"):
            pts = c["points"]
            for a, b in zip(pts, pts[1:]):
                hw = float(c.get("width", 1.2)) / 2
                parts.append(box(min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw))
    parts = [p for p in parts if p is not None and not p.is_empty]
    if not parts:
        return None
    return unary_union(parts).buffer(margin, join_style=2)


# ------------------------------------------------------------------------------------------------ grading
@dataclass
class Grading:
    pad_z_abs: float
    cut_m3: float
    fill_m3: float
    max_cut_m: float
    max_fill_m: float
    natural_slope_pct: float | None


def _find_depression(nats: dict, x0: float, y0: float, step: float, ref: tuple[float, float] | None = None) -> dict | None:
    """Largest connected hollow (Senke, Graben, Mulde) of the parcel: cells clearly lower than the parcel's median once the overall slope is removed.
    ``x/y`` = bottom, ``near_x/near_y`` = the point of the hollow closest to ``ref`` (the building) at half depth, a good spot for a pond."""
    if len(nats) < 12:
        return None
    import numpy as np
    keys = list(nats)
    A = np.array([[1.0, k[0] * step, k[1] * step] for k in keys])
    y = np.array([nats[k] for k in keys])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)          # remove the plane (overall slope): only genuine hollows remain
    res = dict(zip(keys, (y - A @ coef).tolist()))
    med = sorted(res.values())[len(res) // 2]
    low = {k for k, v in res.items() if v < med - 0.6}
    best: list = []
    seen: set = set()
    for k in low:
        if k in seen:
            continue
        stack, comp = [k], []
        seen.add(k)
        while stack:
            a = stack.pop()
            comp.append(a)
            for b in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if b in low and b not in seen:
                    seen.add(b)
                    stack.append(b)
        if len(comp) > len(best):
            best = comp
    area = len(best) * step * step
    if area < 12.0 or len(best) > 0.35 * len(nats):       # tiny noise, or a whole slope side rather than a hollow
        return None
    xy = lambda c: (x0 + c[0] * step, y0 + c[1] * step)  # noqa: E731
    bottom = min(best, key=lambda c: res[c])
    depth = med - res[bottom]
    mid = [c for c in best if res[c] <= med - 0.45 * depth] or best
    if ref is not None:
        near = min(mid, key=lambda c: (xy(c)[0] - ref[0]) ** 2 + (xy(c)[1] - ref[1]) ** 2)
    else:
        near = bottom
    xs = [xy(c)[0] for c in best]
    ys = [xy(c)[1] for c in best]
    return {"x": round(xy(bottom)[0], 1), "y": round(xy(bottom)[1], 1), "near_x": round(xy(near)[0], 1), "near_y": round(xy(near)[1], 1),
            "area_m2": round(area, 1), "depth_m": round(depth, 2), "bbox": [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]}


def _flood_lake(nat: dict, x0: float, y0: float, step: float, nx: int, ny: int, ax: float, ay: float, fill: float,
                parcel, dress) -> dict | None:
    """Fill the hollow around (ax, ay) with water: the water level rises ``fill`` of the way from the lowest point to the lowest spill point
    (capped), the lake is every connected cell below it. Returns {'level', 'ring', 'area_m2'} in the spec frame (pad = 0) or None."""
    from shapely.geometry import MultiPolygon
    near = [k for k in nat if math.hypot(x0 + k[0] * step - ax, y0 + k[1] * step - ay) <= max(8.0, 3 * step)]
    if not near:
        return None
    seed = min(near, key=lambda k: nat[k])
    low = nat[seed]
    def region(lv):
        comp, stack, seen = [], [seed], {seed}
        while stack:
            a = stack.pop()
            comp.append(a)
            for b in ((a[0] + 1, a[1]), (a[0] - 1, a[1]), (a[0], a[1] + 1), (a[0], a[1] - 1)):
                if b in nat and b not in seen and nat[b] < lv:
                    seen.add(b)
                    stack.append(b)
        return comp

    cap = 0.3 * len(nat)
    spill = low
    for lv in sorted({round(v, 2) for v in nat.values() if low < v <= low + 4.0}):
        comp = region(lv)
        if len(comp) > cap or any(c[0] in (0, nx - 1) or c[1] in (0, ny - 1) for c in comp):
            break
        spill = lv
    if spill - low < 0.3:
        return None
    lv = low + max(0.3, fill * (spill - low))
    comp = region(lv)
    sq = unary_union([box(x0 + i * step - step / 2, y0 + j * step - step / 2, x0 + i * step + step / 2, y0 + j * step + step / 2) for i, j in comp])
    sq = sq.buffer(step * 0.6).buffer(-step * 0.9).buffer(step * 0.3)
    if dress is not None:
        sq = sq.difference(dress.buffer(2.0))
    if sq.is_empty:
        return None
    if isinstance(sq, MultiPolygon):
        sq = max(sq.geoms, key=lambda g: g.area)
    sq = sq.simplify(step * 0.25)
    if sq.area < 12.0:
        return None
    return {"level": round(lv, 3), "ring": [[round(x, 2), round(y, 2)] for x, y in sq.exterior.coords], "area_m2": round(sq.area, 1)}


def build_terrain(pack: dict, spec: dict, pad_z_abs: float | None = None, slope: float = DEFAULT_SLOPE,
                  margin: float = DEFAULT_PAD_MARGIN_M, extent_pad_m: float = 25.0) -> dict:
    """Return the ``site.terrain`` section for ``spec`` (frame: spec, heights relative to the pad) or {'status': 'UNAVAILABLE', ...}."""
    hs = heights_from_pack(pack)
    if hs is None:
        return {"status": "UNAVAILABLE", "note_de": "Kein Geländemodell vorhanden: der Boden bleibt eben."}
    pl = Placement.from_spec(spec)
    dress = dressing_polygon(spec, margin)
    if dress is None:
        return {"status": "UNAVAILABLE", "note_de": "Keine Gebäudefläche für ein Plateau."}
    dress_site = pl.poly_to_site(dress)
    if pad_z_abs is None:
        # level at the mean natural height under the building (equal cut and fill under the house)
        pad_z_abs = _mean_height(hs, dress_site)
    ring_site = ((pack.get("site") or {}).get("ring_local")) or []
    parcel_spec = pl.poly_to_spec(Polygon(ring_site)) if len(ring_site) >= 3 else None
    area = unary_union([p for p in (dress, parcel_spec) if p is not None])
    x0, y0, x1, y1 = area.buffer(extent_pad_m).bounds
    step = max(1.0, math.ceil(max(x1 - x0, y1 - y0) / MAX_MESH_CELLS))
    nx, ny = int(math.ceil((x1 - x0) / step)) + 1, int(math.ceil((y1 - y0) / step)) + 1
    from . import pond as _pond
    ponds = []        # (component index, outline in spec frame, water level relative to the pad)
    for ci, c in enumerate(spec.get("components", [])):
        if c.get("type") == "pond" and c.get("x") is not None and c.get("y") is not None:
            pg = _pond.polygon(c)
            minx, miny, maxx, maxy = pg.bounds
            vals = []
            gx = minx
            while gx <= maxx:
                gy = miny
                while gy <= maxy:
                    if pg.contains(Point(gx, gy)):
                        sx, sy = pl.to_site(gx, gy)
                        vals.append(hs.at(sx, sy) - pad_z_abs)
                    gy += 0.5
                gx += 0.5
            c0 = pg.centroid
            if not vals:
                sx, sy = pl.to_site(c0.x, c0.y)
                vals = [hs.at(sx, sy) - pad_z_abs]
            ponds.append((ci, pg, round(min(vals), 3)))
    lake_specs = [(ci, c) for ci, c in enumerate(spec.get("components", [])) if c.get("type") == "lake" and c.get("x") is not None and c.get("y") is not None]
    allnat: dict[tuple[int, int], float] = {}
    z: list[float] = []
    cut = fill = 0.0
    max_cut = max_fill = 0.0
    cell = step * step
    nats: dict[tuple[int, int], float] = {}
    inside = parcel_spec.buffer(0.01) if parcel_spec is not None else None
    for j in range(ny):
        for i in range(nx):
            px, py = x0 + i * step, y0 + j * step
            sx, sy = pl.to_site(px, py)
            nat = hs.at(sx, sy) - pad_z_abs
            d = dress.distance(Point(px, py))
            new = -PAD_DROP_M if d <= 0.0 else max(-d * slope, min(d * slope, nat)) if abs(nat) > d * slope else nat
            for _ci, _pg, _lv in ponds:
                dp = _pg.distance(Point(px, py))
                if dp < d:
                    B = _lv + 0.1
                    new = (_lv - 0.6) if dp <= 0.0 else (_lv - 0.1 + 0.2 * dp if dp <= 1.0 else B + max(-dp * slope, min(dp * slope, nat - B)))
            z.append(round(new, 3))
            if lake_specs:
                allnat[(i, j)] = nat
            if d > 1.0 and (parcel_spec is None or parcel_spec.contains(Point(px, py))):
                nats[(i, j)] = nat
            if inside is None or inside.contains(Point(px, py)):
                diff = (0.0 if d <= 0.0 else new) - nat      # the 4 cm threshold drop is not earthwork
                if diff > 0:
                    fill += diff * cell
                    max_fill = max(max_fill, diff)
                else:
                    cut += -diff * cell
                    max_cut = max(max_cut, -diff)
    lakes = []
    for ci, c in lake_specs:
        lk = _flood_lake(allnat, x0, y0, step, nx, ny, float(c["x"]), float(c["y"]), float(c.get("fill", 0.55)), parcel_spec, dress)
        if lk:
            lakes.append({"i": ci, **lk})
    nat_slope = _natural_slope_pct(hs, dress_site)
    notes = []
    c0 = dress.centroid
    depression = _find_depression(nats, x0, y0, step, (c0.x, c0.y))
    if depression:
        notes.append(f"Geländesenke (bis {depression['depth_m']:.1f} m tief, {depression['area_m2']:.0f} m²) um x={depression['x']:.0f}, y={depression['y']:.0f}; "
                     f"nächster Punkt zum Haus x={depression['near_x']:.0f}, y={depression['near_y']:.0f}: geeignet für einen Teich.")
    if max_fill > MAX_FILL_WARN_M:
        notes.append(f"Auftrag bis {max_fill:.1f} m: hohe Anschüttung, Stützmauer oder Gebäude tiefer setzen prüfen.")
    if max_cut > MAX_FILL_WARN_M:
        notes.append(f"Abtrag bis {max_cut:.1f} m: tiefe Baugrube/Einschnitt, Stützmauer oder Gebäude höher setzen prüfen.")
    return {"status": "OK", "frame": "spec", "step_m": step, "x0": round(x0, 3), "y0": round(y0, 3), "nx": nx, "ny": ny, "z": z,
            "pad_z_abs_m": round(pad_z_abs, 2), "height_reference": "DHHN2016 (NHN), m", "slope": slope,
            "pad_ring": [[round(x, 2), round(y, 2)] for x, y in dress.exterior.coords] if dress.geom_type == "Polygon" else None,
            "parcel_ring": [[round(x, 2), round(y, 2)] for x, y in parcel_spec.exterior.coords] if parcel_spec is not None and parcel_spec.geom_type == "Polygon" else None,
            "cut_m3": round(cut, 1), "fill_m3": round(fill, 1), "max_cut_m": round(max_cut, 2), "max_fill_m": round(max_fill, 2),
            "natural_slope_pct": nat_slope, "notes_de": notes, "depression": depression,
            "ponds": [{"i": ci, "level": lv} for ci, _pg, lv in ponds], "lakes": lakes,
            "source": "DGM1 Hessen (bare earth), planerische Näherung, keine Erdbauplanung"}


def _mean_height(hs: Heights, poly_site: Polygon) -> float:
    minx, miny, maxx, maxy = poly_site.bounds
    n = 12
    vals = [hs.at(minx + (maxx - minx) * (i + 0.5) / n, miny + (maxy - miny) * (j + 0.5) / n)
            for i in range(n) for j in range(n)
            if poly_site.contains(Point(minx + (maxx - minx) * (i + 0.5) / n, miny + (maxy - miny) * (j + 0.5) / n))]
    if not vals:
        c = poly_site.centroid
        return hs.at(c.x, c.y)
    return sum(vals) / len(vals)


def _natural_slope_pct(hs: Heights, poly_site: Polygon) -> float | None:
    minx, miny, maxx, maxy = poly_site.buffer(5).bounds
    n = 10
    sl = []
    for i in range(n):
        for j in range(n):
            x, y = minx + (maxx - minx) * (i + 0.5) / n, miny + (maxy - miny) * (j + 0.5) / n
            h = 1.0
            gx = (hs.at(x + h, y) - hs.at(x - h, y)) / (2 * h)
            gy = (hs.at(x, y + h) - hs.at(x, y - h)) / (2 * h)
            sl.append(math.hypot(gx, gy))
    return round(100 * sum(sl) / len(sl), 1) if sl else None


# ------------------------------------------------------------------------------------------------ sampling for renderers
class SpecTerrain:
    """Sampler for the ``site.terrain`` section (spec frame, pad = 0)."""

    def __init__(self, t: dict):
        self.ok = bool(t) and t.get("status") == "OK"
        if not self.ok:
            return
        self.x0, self.y0, self.step = t["x0"], t["y0"], t["step_m"]
        self.nx, self.ny, self.z = t["nx"], t["ny"], t["z"]
        self._ponds = {int(p["i"]): float(p["level"]) for p in (t.get("ponds") or [])}
        self._lakes = {int(p["i"]): p for p in (t.get("lakes") or [])}

    def lake(self, i: int):
        return self._lakes.get(int(i))

    def pond_level(self, i: int) -> float:
        return self._ponds.get(int(i), 0.0)

    def at(self, x: float, y: float) -> float:
        if not self.ok:
            return 0.0
        fx = min(max((x - self.x0) / self.step, 0.0), self.nx - 1.0)
        fy = min(max((y - self.y0) / self.step, 0.0), self.ny - 1.0)
        i, j = min(int(fx), self.nx - 2), min(int(fy), self.ny - 2)
        tx, ty = fx - i, fy - j
        z, nx = self.z, self.nx
        return (z[j * nx + i] * (1 - tx) * (1 - ty) + z[j * nx + i + 1] * tx * (1 - ty)
                + z[(j + 1) * nx + i] * (1 - tx) * ty + z[(j + 1) * nx + i + 1] * tx * ty)


def terrain_mesh(t: dict) -> dict | None:
    """Triangles of the graded ground for the 360° viewer: {'positions': [x,y,z,...], 'indices': [...]} (spec frame, z up, pad = 0)."""
    if not t or t.get("status") != "OK":
        return None
    nx, ny, step, x0, y0, z = t["nx"], t["ny"], t["step_m"], t["x0"], t["y0"], t["z"]
    pos: list[float] = []
    for j in range(ny):
        for i in range(nx):
            pos += [round(x0 + i * step, 3), round(y0 + j * step, 3), z[j * nx + i]]
    idx: list[int] = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i
            idx += [a, b, c, a, c, d]
    return {"positions": pos, "indices": idx}
