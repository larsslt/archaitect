"""Plausibility checks that do not block a version (returned as warnings).

envelope_gaps: every face plane of a curtain wall must be closed by glass or by an adjacent volume
(wall incl. parapet). Open areas show up as holes in the render (e.g. an offset between two volumes).
"""
from __future__ import annotations

from shapely.geometry import box as _sbox
from shapely.ops import unary_union

from .geom import facade_xy, side_length

CELL = 0.1      # sampling grid in metres
TOL = 0.06      # contact tolerance between a glass plane and a neighbouring volume
MIN_AREA = 0.05  # m2, smaller leftovers are ignored
SIDE_NAME = {"S": "Süd", "N": "Nord", "E": "Ost", "W": "West"}


def _volume_tops(spec: dict):
    d = spec.get("defaults", {})
    sh = float(spec.get("storey_height", 3.0))
    par = float(d.get("parapet_height", 0.6))
    for v in spec.get("volumes", []):
        x0, y0 = v["origin"]
        W, D = v["size"]
        z0 = float(v.get("base_z", 0.0))
        z1 = z0 + int(v.get("storeys", 1)) * float(v.get("storey_height", sh))
        yield (x0, y0, x0 + W, y0 + D, z0, z1 + float(v.get("parapet_height", par)))


def envelope_gaps(spec: dict) -> list[str]:
    vols = list(_volume_tops(spec))
    out: list[str] = []
    for cw in spec.get("curtain_walls", []):
        ox, oy = cw["origin"]
        W, D = cw["size"]
        top = float(cw["top_z"])
        for side in ("S", "N", "E", "W"):
            L = side_length(side, W, D)
            glass = [(f.get("span", (0.0, L)), float(f["z0"]), float(f["z1"]))
                     for f in cw.get("faces", []) if f["side"] == side]
            nu, nz = round(L / CELL), round(top / CELL)
            open_cells = []
            for i in range(nu):
                u = (i + 0.5) * L / nu
                x, y = facade_xy(side, ox, oy, W, D, u, 0.0)
                for j in range(nz):
                    z = (j + 0.5) * top / nz
                    if any(a <= u <= b and za <= z <= zb for (a, b), za, zb in glass):
                        continue
                    if any(vx0 - TOL <= x <= vx1 + TOL and vy0 - TOL <= y <= vy1 + TOL and vz0 <= z <= vz1
                           for vx0, vy0, vx1, vy1, vz0, vz1 in vols):
                        continue
                    open_cells.append(_sbox(u - CELL / 2, z - CELL / 2, u + CELL / 2, z + CELL / 2))
            if not open_cells:
                continue
            # grow slightly so touching cells fuse into one region (no sliver seams)
            merged = unary_union([c.buffer(0.001, join_style=2) for c in open_cells]).buffer(-0.001, join_style=2)
            for g in getattr(merged, "geoms", [merged]):
                if g.area < MIN_AREA:
                    continue
                u0, z0, u1, z1 = g.bounds
                out.append(f"Lücke in {cw.get('name', cw.get('id', 'Glaswand'))} {SIDE_NAME[side]}: "
                           f"entlang {u0:.1f}–{u1:.1f} m, Höhe {z0:.1f}–{z1:.1f} m ({g.area:.1f} m²) "
                           f"weder Glas noch anliegender Baukörper")
    return out


def warnings(spec: dict) -> list[str]:
    lim = [f"Nicht abgebildet: {x}" for x in spec.get("limitations", [])]
    lim += [f"Automatisch ergänzt: {x}" for x in spec.get("auto_notes", [])]
    try:
        from .logic import audit
        lim += audit(spec)
    except Exception as e:
        lim.append(f"Logikprüfung nicht möglich: {e}")
    try:
        return lim + envelope_gaps(spec)
    except Exception as e:  # a check must never break the workflow
        return [f"Dichtheitsprüfung nicht möglich: {e}"]
