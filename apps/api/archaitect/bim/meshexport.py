"""Mesh export for the browser 360° view: IFC geometry + graded terrain as compact JSON (no Blender, no GLB parser needed).

Format (all coordinates in the spec frame, metres, z up, finished floor = 0):
  {"parts": [{"name", "color": [r,g,b], "opacity", "positions": [x,y,z,...], "indices": [...]}], "bounds": [minx,miny,minz,maxx,maxy,maxz]}
Parts are merged per surface colour so a whole house is a few dozen draw calls. Render-only vegetation (lawn hair, tree crowns) is not part
of it; trees and hedges from the IFC are kept as simple volumes.
"""
from __future__ import annotations

import math
from pathlib import Path

from . import terrain as T

TERRAIN_COLOR = [0.30, 0.42, 0.22]
FILL_COLOR = [0.36, 0.30, 0.22]


def _rgb(d) -> tuple:
    """ifcopenshell colour object (r/g/b as methods or attributes) or sequence -> (r, g, b) rounded; grey if unknown."""
    if d is None:
        return (0.7, 0.7, 0.7)
    try:
        vals = [getattr(d, k) for k in "rgb"]
        vals = [v() if callable(v) else v for v in vals]
        if not all(math.isfinite(float(v)) for v in vals):
            return (0.7, 0.7, 0.7)
    except AttributeError:
        try:
            vals = [d[k] for k in range(3)]
        except (TypeError, IndexError):
            return (0.7, 0.7, 0.7)
    return tuple(round(float(v), 2) for v in vals)


def ifc_parts(ifc_path: str | Path, spec: dict | None = None) -> list[dict]:
    """Parts merged per (object, colour). ``obj`` is the selectable object (bim/objects.py): the element's Tag, else guessed from its name."""
    import ifcopenshell
    import ifcopenshell.geom as geom
    from . import objects as O
    model = ifcopenshell.open(str(ifc_path))
    obj_cache: dict[int, str | None] = {}

    def obj_of(eid: int):
        if eid not in obj_cache:
            tag = name = None
            try:
                el = model.by_id(eid)
                tag, name = getattr(el, "Tag", None), getattr(el, "Name", None)
            except Exception:  # noqa: BLE001
                pass
            obj_cache[eid] = tag if (tag and str(tag).startswith(("bld:", "site.", "comp."))) else (O.object_of_element(name or "", spec) if spec else None)
        return obj_cache[eid]
    from shapely.geometry import Point
    from . import objects as OB
    vols = []
    for v in (spec or {}).get("volumes", []):
        try:
            h = float(v.get("storey_height") or (spec or {}).get("storey_height") or 2.9)
            z0 = float(v.get("base_z", 0.0))
            vols.append((str(v["id"]), OB._vpoly(v), z0 - 0.3, z0 + int(v.get("storeys", 1)) * h + 4.0, z0))
        except (KeyError, TypeError, ValueError):
            continue
    vol_cache: dict[int, str | None] = {}

    def vol_of(eid: int, verts):
        """Volume of an element by its centre (xy inside the footprint, z inside the volume's height; the highest base wins for stacked volumes)."""
        if eid not in vol_cache:
            r = None
            if vols and verts:
                n = len(verts) // 3
                cx, cy, cz = (sum(verts[k::3]) / n for k in range(3))
                pt = Point(cx, cy)
                hit = [(poly.distance(pt), -z0, vid) for vid, poly, zlo, zhi, z0 in vols if zlo <= cz <= zhi and poly.distance(pt) < 0.9]
                r = min(hit)[2] if hit else None
            vol_cache[eid] = r
        return vol_cache[eid]
    settings = geom.settings()
    settings.set("use-world-coords", True)
    skip = [e for t in ("IfcOpeningElement", "IfcSpace") for e in model.by_type(t)]      # Aussparungen sind keine Bauteile: sonst verdecken graue Quader Türen und Fenster
    try:
        it = geom.iterator(settings, model, 2, exclude=skip) if skip else geom.iterator(settings, model, 2)
    except TypeError:
        it = geom.iterator(settings, model, 2)
    buckets: dict[tuple, dict] = {}
    if it.initialize():
        while True:
            sh = it.get()
            g = sh.geometry
            verts, faces = list(g.verts), list(g.faces)
            if verts and faces:
                mats = list(g.materials)
                ids = list(g.material_ids)
                for fi in range(len(faces) // 3):
                    m = mats[ids[fi]] if ids and 0 <= ids[fi] < len(mats) else None
                    d = getattr(m, "diffuse", None)
                    col = _rgb(d)
                    tr = getattr(m, "transparency", 0.0) if m is not None else 0.0
                    tr = tr() if callable(tr) else tr
                    try:
                        op = 1.0 - float(tr or 0.0)
                    except (TypeError, ValueError):
                        op = 1.0
                    if not math.isfinite(op):           # ifcopenshell reports NaN for an unset transparency; NaN is not valid JSON
                        op = 1.0
                    op = min(1.0, max(0.05, op))
                    key = (obj_of(sh.id), vol_of(sh.id, verts), col, round(op, 2))
                    b = buckets.setdefault(key, {"pos": [], "idx": [], "map": {}})
                    tri = faces[3 * fi:3 * fi + 3]
                    out = []
                    for v in tri:
                        k = (sh.id, v)
                        if k not in b["map"]:
                            b["map"][k] = len(b["pos"]) // 3
                            b["pos"] += [round(verts[3 * v], 3), round(verts[3 * v + 1], 3), round(verts[3 * v + 2], 3)]
                        out.append(b["map"][k])
                    b["idx"] += out
            if not it.next():
                break
    parts = []
    for (obj, vol, col, op), b in buckets.items():
        parts.append({"name": f"ifc_{len(parts)}", "obj": obj, "vol": vol, "color": list(col), "opacity": op, "positions": b["pos"], "indices": b["idx"]})
    return parts


def terrain_part(t: dict | None) -> dict | None:
    m = T.terrain_mesh(t) if t else None
    if m is None:
        return None
    return {"name": "terrain", "color": TERRAIN_COLOR, "opacity": 1.0, **m}


def bounds(parts: list[dict]) -> list[float] | None:
    lo, hi = [1e18] * 3, [-1e18] * 3
    seen = False
    for p in parts:
        pos = p["positions"]
        for i in range(0, len(pos), 3):
            seen = True
            for k in range(3):
                lo[k] = min(lo[k], pos[i + k])
                hi[k] = max(hi[k], pos[i + k])
    return [round(v, 2) for v in lo + hi] if seen else None


def O_public(spec):
    from . import objects as O
    return O.public(spec) if spec else []


def build(ifc_path: str | Path, terrain: dict | None = None, spec: dict | None = None) -> dict:
    parts = ifc_parts(ifc_path, spec)
    tp = terrain_part(terrain)
    if tp:
        parts.append(tp)
    return {"parts": parts, "objects": O_public(spec), "bounds": bounds(parts), "terrain": None if not terrain or terrain.get("status") != "OK" else
            {k: terrain.get(k) for k in ("pad_z_abs_m", "cut_m3", "fill_m3", "max_cut_m", "max_fill_m", "natural_slope_pct", "notes_de", "source")}}
