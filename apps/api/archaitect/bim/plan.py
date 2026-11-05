"""Floor plans (SVG) cut from the IFC model: one horizontal section per storey.

The plan comes from the generated IFC itself (not from the spec), so what is drawn is what is modelled.
Walls/columns black, glass blue, doors brown, rails grey; floor slabs, stairs and furniture as light
footprints below the cut plane. Dimensions: overall extents only. No rooms yet (see README).
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import numpy as np
import ifcopenshell
import ifcopenshell.geom
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

CUT_HEIGHT = 1.10    # m above storey elevation (usual plan cut)
PX_PER_M = 40.0
MARGIN_M = 3.0
WALL_CLASSES = {"IfcWall", "IfcWallStandardCase", "IfcColumn"}
FLOOR_CLASSES = {"IfcSlab", "IfcCovering"}
SKIP = {"IfcOpeningElement", "IfcSpace", "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcCurtainWall"}


def _settings():
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    return s


def _triangles(shape) -> np.ndarray:
    v = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
    f = np.array(shape.geometry.faces, dtype=int).reshape(-1, 3)
    return v[f]  # (n, 3, 3)


def _section(tris: np.ndarray, z: float):
    """Polygons where the horizontal plane z cuts the triangle mesh."""
    z = z + 1e-4  # avoid exact vertex/plane coincidences
    above = tris[:, :, 2] > z
    n_above = above.sum(axis=1)
    lines = []
    for t, a in zip(tris[(n_above == 1) | (n_above == 2)], above[(n_above == 1) | (n_above == 2)]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if a[i] != a[j]:
                s = (z - t[i, 2]) / (t[j, 2] - t[i, 2])
                # rounded so the shared diagonal point of two triangles matches exactly (closed loops)
                pts.append((round(t[i, 0] + s * (t[j, 0] - t[i, 0]), 4), round(t[i, 1] + s * (t[j, 1] - t[i, 1]), 4)))
        if len(pts) == 2 and pts[0] != pts[1]:
            lines.append(LineString(pts))
    if not lines:
        return None
    polys = list(polygonize(unary_union(lines)))
    return unary_union(polys) if polys else None


def _footprint(tris: np.ndarray):
    polys = []
    for t in tris:
        p = Polygon(t[:, :2])
        if p.is_valid and p.area > 1e-8:
            polys.append(p)
    return unary_union(polys) if polys else None


def _group(el) -> str | None:
    c = el.is_a()
    if c in SKIP:
        return None
    if c in WALL_CLASSES:
        return "wall"
    if c == "IfcWindow":
        return "glass"
    if c == "IfcPlate":
        return "glass"
    if c == "IfcMember":
        return "frame"
    if c == "IfcDoor":
        return "door"
    if c == "IfcRailing":
        return "rail"
    if c in ("IfcStair", "IfcStairFlight"):
        return "stair"
    if c in FLOOR_CLASSES:
        return "floor"
    if c == "IfcFurniture":
        return "furn"
    return None


def _path(geom) -> str:
    out = []
    for p in getattr(geom, "geoms", [geom]):
        if not isinstance(p, Polygon) or p.is_empty:
            continue
        for ring in [p.exterior, *p.interiors]:
            out.append("M" + " L".join(f"{x:.3f},{y:.3f}" for x, y in ring.coords) + " Z")
    return " ".join(out)


def storeys(ifc) -> list[tuple[str, float]]:
    return sorted(((s.Name, float(s.Elevation or 0.0)) for s in ifc.by_type("IfcBuildingStorey")), key=lambda t: t[1])


def build_plans(ifc_path: str | Path, out_dir: str | Path, title: str = "", prefix: str = "plan", spec: dict | None = None) -> list[dict]:
    """Write one SVG per storey that contains cut walls; returns [{storey, elevation, svg, ...}]."""
    ifc = ifcopenshell.open(str(ifc_path))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    st = storeys(ifc)
    settings = _settings()
    elems = []  # (group, tris, zmin, zmax, name)
    for el in ifc.by_type("IfcProduct"):
        g = _group(el)
        if not g or not getattr(el, "Representation", None):
            continue
        try:
            tris = _triangles(ifcopenshell.geom.create_shape(settings, el))
        except Exception:
            continue
        if len(tris):
            elems.append((g, tris, float(tris[:, :, 2].min()), float(tris[:, :, 2].max()), el.Name or ""))
    results = []
    from . import rooms as R
    analysis = R.analyze(spec) if spec else []
    for k, (name, elev) in enumerate(st):
        upper = st[k + 1][1] if k + 1 < len(st) else elev + 3.0
        cut = elev + min(CUT_HEIGHT, (upper - elev) * 0.5)
        layers: dict[str, list] = {g: [] for g in ("floor", "furn", "stair", "wall", "glass", "frame", "door", "rail")}
        for g, tris, z0, z1, _n in elems:
            if g in ("wall", "glass", "frame", "door", "rail"):
                if z0 < cut < z1:
                    sec = _section(tris, cut)
                    if sec is not None:
                        layers[g].append(sec)
            elif g == "floor":
                if elev - 0.5 <= z1 <= elev + 0.3:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
            elif g == "stair":
                if z0 >= elev - 0.2 and z0 < upper - 0.5:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
            elif g == "furn":
                if z0 >= elev - 0.2 and z0 < cut:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
        if not layers["wall"] and not layers["glass"]:
            continue  # no building at this level (e.g. roof level)
        u = {g: unary_union(v) for g, v in layers.items() if v}
        # building extents for the dimension lines: connected wall bodies > 0.3 m2 (drops pergola posts) + glass
        parts = [p for g in (u.get("wall"),) if g is not None for p in getattr(g, "geoms", [g]) if p.area > 0.3]
        parts += [u[g] for g in ("glass", "frame") if g in u]
        shell = unary_union(parts)
        lvl_rooms = [a for a in analysis if a["level"] == name]
        svg, meta = _svg(u, shell, f"{name}  ·  +{elev:.2f} m", f"Schnitt in {cut - elev:.2f} m Höhe", title, lvl_rooms)
        path = out_dir / f"{prefix}_{re.sub(r'[^A-Za-z0-9_-]', '_', name)}.svg"
        path.write_text(svg, encoding="utf-8")
        meta.update(level=name, elevation=elev, inner=[f["rect"] for f in R.footprints(spec, name)] if spec else [])
        path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        minx, miny, maxx, maxy = shell.bounds
        results.append({"storey": name, "elevation": elev, "svg": str(path), "file": path.name,
                        "width_m": round(maxx - minx, 2), "depth_m": round(maxy - miny, 2)})
    return results


def _svg(u: dict, shell, label: str, sub: str, title: str, rooms: list | None = None):
    minx, miny, maxx, maxy = shell.bounds            # building (dimension lines)
    ax0, ay0, ax1, ay1 = unary_union(list(u.values())).bounds   # everything drawn (canvas)
    ax0, ay0, ax1, ay1 = min(ax0, minx), min(ay0, miny), max(ax1, maxx), max(ay1, maxy)
    S = PX_PER_M
    x0, y1 = ax0 - MARGIN_M, ay1 + MARGIN_M
    W = (ax1 - ax0 + 2 * MARGIN_M) * S
    H = (ay1 - ay0 + 2 * MARGIN_M) * S + 70

    def tx(g):
        from shapely import affinity
        return affinity.affine_transform(g, [S, 0, 0, -S, -x0 * S, y1 * S])

    def px(x):  # world x -> px
        return (x - x0) * S

    def py(y):
        return (y1 - y) * S

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
         f'font-family="-apple-system, Helvetica, Arial, sans-serif"><rect width="100%" height="100%" fill="#ffffff"/>']
    style = {
        "floor": ('#fbfbfc', '#d9d9de', 0.8),
        "furn": ('#f1f1f4', '#bdbdc4', 0.9),
        "stair": ('#e6e6ea', '#8a8a92', 1.0),
        "wall": ('#2a2a2f', '#2a2a2f', 0.4),
        "glass": ('#e9f2fb', '#4d86b3', 1.2),
        "frame": ('#2a2a2f', '#2a2a2f', 0.4),
        "door": ('#d8cbb8', '#6d5a43', 0.9),
        "rail": ('#8a8a92', '#8a8a92', 0.7),
    }
    from . import rooms as R
    analysis = R.analyze(spec) if spec else []
    for k, (name, elev) in enumerate(st):
        upper = st[k + 1][1] if k + 1 < len(st) else elev + 3.0
        cut = elev + min(CUT_HEIGHT, (upper - elev) * 0.5)
        layers: dict[str, list] = {g: [] for g in ("floor", "furn", "stair", "wall", "glass", "frame", "door", "rail")}
        for g, tris, z0, z1, _n in elems:
            if g in ("wall", "glass", "frame", "door", "rail"):
                if z0 < cut < z1:
                    sec = _section(tris, cut)
                    if sec is not None:
                        layers[g].append(sec)
            elif g == "floor":
                if elev - 0.5 <= z1 <= elev + 0.3:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
            elif g == "stair":
                if z0 >= elev - 0.2 and z0 < upper - 0.5:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
            elif g == "furn":
                if z0 >= elev - 0.2 and z0 < cut:
                    fp = _footprint(tris)
                    if fp is not None:
                        layers[g].append(fp)
        if not layers["wall"] and not layers["glass"]:
            continue  # no building at this level (e.g. roof level)
        u = {g: unary_union(v) for g, v in layers.items() if v}
        # building extents for the dimension lines: connected wall bodies > 0.3 m2 (drops pergola posts) + glass
        parts = [p for g in (u.get("wall"),) if g is not None for p in getattr(g, "geoms", [g]) if p.area > 0.3]
        parts += [u[g] for g in ("glass", "frame") if g in u]
        shell = unary_union(parts)
        lvl_rooms = [a for a in analysis if a["level"] == name]
        svg, meta = _svg(u, shell, f"{name}  ·  +{elev:.2f} m", f"Schnitt in {cut - elev:.2f} m Höhe", title, lvl_rooms)
        path = out_dir / f"{prefix}_{re.sub(r'[^A-Za-z0-9_-]', '_', name)}.svg"
        path.write_text(svg, encoding="utf-8")
        meta.update(level=name, elevation=elev, inner=[f["rect"] for f in R.footprints(spec, name)] if spec else [])
        path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        minx, miny, maxx, maxy = shell.bounds
        results.append({"storey": name, "elevation": elev, "svg": str(path), "file": path.name,
                        "width_m": round(maxx - minx, 2), "depth_m": round(maxy - miny, 2)})
    return results


def _svg(u: dict, shell, label: str, sub: str, title: str, rooms: list | None = None):
    minx, miny, maxx, maxy = shell.bounds            # building (dimension lines)
    ax0, ay0, ax1, ay1 = unary_union(list(u.values())).bounds   # everything drawn (canvas)
    ax0, ay0, ax1, ay1 = min(ax0, minx), min(ay0, miny), max(ax1, maxx), max(ay1, maxy)
    S = PX_PER_M
    x0, y1 = ax0 - MARGIN_M, ay1 + MARGIN_M
    W = (ax1 - ax0 + 2 * MARGIN_M) * S
    H = (ay1 - ay0 + 2 * MARGIN_M) * S + 70

    def tx(g):
        from shapely import affinity
        return affinity.affine_transform(g, [S, 0, 0, -S, -x0 * S, y1 * S])

    def px(x):  # world x -> px
        return (x - x0) * S

    def py(y):
        return (y1 - y) * S

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}" '
         f'font-family="Helvetica, Arial, sans-serif"><rect width="100%" height="100%" fill="#ffffff"/>']
    style = {
        "floor": ('#ececec', '#b5b5b5', 1.0),
        "furn": ('#f7f7f7', '#8a8a8a', 1.0),
        "stair": ('#dcdcdc', '#6e6e6e', 1.2),
        "wall": ('#1b1b1b', '#1b1b1b', 0.5),
        "glass": ('#cfe6f7', '#2f78b7', 1.4),
        "frame": ('#3a3a3a', '#3a3a3a', 0.5),
        "door": ('#b0713a', '#6b4220', 1.0),
        "rail": ('#6a6a6a', '#6a6a6a', 0.8),
    }
    from . import rooms as R
    if "floor" in u:
        f, s_, w = style["floor"]
        o.append(f'<path d="{_path(tx(u["floor"]))}" fill="{f}" stroke="{s_}" stroke-width="{w}" fill-rule="evenodd"/>')
    for rm in rooms or []:
        x0r, y0r, x1r, y1r = rm["rect"]
        o.append(f'<rect x="{px(x0r):.1f}" y="{py(y1r):.1f}" width="{(x1r - x0r) * S:.1f}" height="{(y1r - y0r) * S:.1f}" '
                 f'fill="{R.FUNCTIONS[rm["function"]][1]}" opacity="0.55"/>')
    for g in ("furn", "stair", "glass", "wall", "frame", "door", "rail"):
        if g in u:
            f, s, w = style[g]
            o.append(f'<path d="{_path(tx(u[g]))}" fill="{f}" stroke="{s}" stroke-width="{w}" fill-rule="evenodd"/>')
    for rm in rooms or []:
        x0r, y0r, x1r, y1r = rm["rect"]
        cx, cy = px((x0r + x1r) / 2), py((y0r + y1r) / 2)
        warn = " ⚠" if rm["hints"] else ""
        sub2 = f'{rm["area"]:.1f} m²' + (f' · Fenster {rm["glass_area"]:.1f} m²' if rm["glass_area"] else "")
        o.append(f'<g text-anchor="middle" fill="#111" style="paint-order:stroke" stroke="#fff" stroke-width="3" '
                 f'stroke-linejoin="round"><text x="{cx:.1f}" y="{cy - 2:.1f}" font-size="14" font-weight="700">'
                 f'{html.escape(rm["name"])}{warn}</text><text x="{cx:.1f}" y="{cy + 14:.1f}" font-size="11">{sub2}</text></g>')
    # overall dimensions
    dy = py(ay0) + 1.2 * S
    o.append(f'<g stroke="#444" stroke-width="1" fill="#444" font-size="13" text-anchor="middle">'
             f'<line x1="{px(minx):.1f}" y1="{dy:.1f}" x2="{px(maxx):.1f}" y2="{dy:.1f}"/>'
             f'<line x1="{px(minx):.1f}" y1="{dy - 5:.1f}" x2="{px(minx):.1f}" y2="{dy + 5:.1f}"/>'
             f'<line x1="{px(maxx):.1f}" y1="{dy - 5:.1f}" x2="{px(maxx):.1f}" y2="{dy + 5:.1f}"/>'
             f'<text x="{(px(minx) + px(maxx)) / 2:.1f}" y="{dy + 18:.1f}" stroke="none">{maxx - minx:.2f} m</text>')
    dx = px(ax0) - 1.2 * S
    o.append(f'<line x1="{dx:.1f}" y1="{py(miny):.1f}" x2="{dx:.1f}" y2="{py(maxy):.1f}"/>'
             f'<line x1="{dx - 5:.1f}" y1="{py(miny):.1f}" x2="{dx + 5:.1f}" y2="{py(miny):.1f}"/>'
             f'<line x1="{dx - 5:.1f}" y1="{py(maxy):.1f}" x2="{dx + 5:.1f}" y2="{py(maxy):.1f}"/>'
             f'<text transform="translate({dx - 8:.1f},{(py(miny) + py(maxy)) / 2:.1f}) rotate(-90)" stroke="none">'
             f'{maxy - miny:.2f} m</text></g>')
    # north arrow + scale bar + caption
    ax, ay = W - 50, 60
    o.append(f'<g fill="#222"><polygon points="{ax},{ay - 28} {ax - 9},{ay + 8} {ax},{ay} {ax + 9},{ay + 8}"/>'
             f'<text x="{ax}" y="{ay - 34}" font-size="14" text-anchor="middle">N</text></g>')
    bx, by = 24, H - 28
    o.append(f'<g stroke="#222" stroke-width="2"><line x1="{bx}" y1="{by}" x2="{bx + 5 * S:.0f}" y2="{by}"/>'
             f'<line x1="{bx}" y1="{by - 5}" x2="{bx}" y2="{by + 5}"/><line x1="{bx + 5 * S:.0f}" y1="{by - 5}" '
             f'x2="{bx + 5 * S:.0f}" y2="{by + 5}"/></g><text x="{bx + 5 * S + 10:.0f}" y="{by + 5}" font-size="13" '
             f'fill="#222">5 m</text>')
    o.append(f'<text x="24" y="34" font-size="22" font-weight="700" fill="#111">{html.escape(label)}</text>'
             f'<text x="24" y="56" font-size="13" fill="#555">{html.escape(sub)}'
             f'</text>')
    o.append("</svg>")
    return "".join(o), {"x0": x0, "y1": y1, "S": S, "W": W, "H": H}
