"""Construction audit: structural / geometric defects of a (completed) spec that the plausibility repairs in ``logic`` should have removed.

Pure geometry on the spec (no IFC, no language model), so it can be run over thousands of generated variants (scripts/construction_bench.py).
Every issue is a (code, message) pair; an empty list means "buildable as drawn".
"""
from __future__ import annotations

from shapely.geometry import box
from shapely.ops import unary_union

from .geom import side_length

HIGH = 1.2               # base_z above which a volume needs something below it
MIN_SUPPORT = 0.6        # share of an elevated volume's footprint that must stand on something below
MIN_OVERLAP_M2 = 0.35    # footprint overlap of two volumes at the same height that counts as a clash


def _sh(spec, v):
    return float(v.get("storey_height", spec.get("storey_height", 3.0)))


def _fp(v):
    x, y = v["origin"]
    W, D = v["size"]
    return box(x, y, x + W, y + D)


def _zr(spec, v):
    z0 = float(v.get("base_z", 0.0))
    return z0, z0 + int(v.get("storeys", 1)) * _sh(spec, v)


def attach_dims(c: dict, fallback_w: float = 1.8) -> tuple[float, float]:
    """(width, depth) of a facade attachment with the catalogue defaults filled in."""
    from . import catalog
    ps = catalog.C.get(c.get("type"), {}).get("params", {})
    w = c.get("width", ps["width"][1] if "width" in ps and ps["width"][1] is not None else fallback_w)
    d = c.get("depth") or c.get("projection") or (ps["depth"][1] if "depth" in ps else None) or (ps["projection"][1] if "projection" in ps else None) or 1.6
    return float(w), float(d)


def audit(spec: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    vols = spec.get("volumes", [])
    V = {v["id"]: v for v in vols}
    # 1. volumes: floating and clashing
    for v in vols:
        z0, z1 = _zr(spec, v)
        fp = _fp(v)
        if z0 > HIGH:
            below = [w for w in vols if w is not v and _zr(spec, w)[1] >= z0 - 0.35 and _zr(spec, w)[0] < z0 - 0.2]
            share = fp.intersection(unary_union([_fp(w) for w in below])).area / fp.area if below else 0.0
            if share < MIN_SUPPORT:
                out.append(("floating_volume", f"Baukörper {v['id']} schwebt (Auflage {share:.0%} < {MIN_SUPPORT:.0%})"))
    for i, a in enumerate(vols):
        for b in vols[i + 1:]:
            za, zb = _zr(spec, a), _zr(spec, b)
            if min(za[1], zb[1]) - max(za[0], zb[0]) < 0.4:
                continue
            ov = _fp(a).intersection(_fp(b)).area
            if ov > MIN_OVERLAP_M2:
                out.append(("volume_overlap", f"Baukörper {a['id']} und {b['id']} überlappen sich um {ov:.1f} m²"))
    # 2. openings: inside the wall, not overlapping, not through floors
    by: dict = {}
    for o in spec.get("openings", []):
        v = V.get(o.get("volume"))
        if not v:
            out.append(("opening_orphan", f"Öffnung ohne Baukörper ({o.get('volume')})"))
            continue
        L = side_length(o["side"], *v["size"])
        a, b = float(o["offset"]), float(o["offset"]) + float(o["width"])
        sill, hgt = float(o.get("sill", 0.0)), float(o["height"])
        if a < -0.01 or b > L + 0.01:
            out.append(("opening_outside_wall", f"Öffnung {v['id']}-{o['side']} G{o['storey']} ragt aus der Wand ({a:.2f}–{b:.2f} von {L:.2f} m)"))
        if int(o["storey"]) < int(v.get("storeys", 1)) and (sill < -0.01 or sill + hgt > _sh(spec, v) + 0.01):
            out.append(("opening_through_floor", f"Öffnung {v['id']}-{o['side']} G{o['storey']} reicht über die Geschosshöhe ({sill:.2f}+{hgt:.2f} m)"))
        if int(o["storey"]) >= int(v.get("storeys", 1)) + (1 if v.get("roof") else 0):
            out.append(("opening_no_storey", f"Öffnung {v['id']}-{o['side']} auf nicht vorhandenem Geschoss {o['storey']}"))
        by.setdefault((v["id"], o["side"], int(o["storey"])), []).append((a, b, sill, sill + hgt))
    for key, lst in by.items():
        lst.sort()
        for p, q in zip(lst, lst[1:]):
            if q[0] < p[1] - 0.02 and min(p[3], q[3]) - max(p[2], q[2]) > 0.05:
                out.append(("opening_overlap", f"Öffnungen {key[0]}-{key[1]} G{key[2]} überlappen ({p[0]:.2f}–{p[1]:.2f} / {q[0]:.2f}–{q[1]:.2f})"))
    # 3. facade attachments: must not stand inside another volume, must hang on an existing wall
    for c in spec.get("components", []):
        t = c.get("type")
        v = V.get(c.get("volume"))
        if c.get("volume") is not None and v is None:
            out.append(("component_orphan", f"{t}: Baukörper {c.get('volume')} existiert nicht"))
            continue
        if v is None or c.get("side") not in ("S", "N", "E", "W") or t not in ("terrace", "steps", "ramp", "carport", "stair_ext", "loggia"):
            continue
        ox, oy = v["origin"]
        W, D = v["size"]
        side = c["side"]
        L = side_length(side, W, D)
        u = float(c["u"]) if c.get("u") is not None else L / 2
        w, dp = attach_dims(c)
        a, b = u - w / 2, u + w / 2
        if a < -0.05 or b > L + 0.05:
            out.append(("attachment_off_wall", f"{t} {v['id']}-{side} ragt seitlich über die Wand ({a:.2f}–{b:.2f} von {L:.2f} m)"))
        rect = {"S": box(ox + a, oy - dp, ox + b, oy), "N": box(ox + a, oy + D, ox + b, oy + D + dp),
                "W": box(ox - dp, oy + a, ox, oy + b), "E": box(ox + W, oy + a, ox + W + dp, oy + b)}[side]
        z0 = float(v.get("base_z", 0.0))
        for w2 in vols:
            if w2 is v or _zr(spec, w2)[0] > z0 + 1.2:
                continue
            ov = rect.intersection(_fp(w2)).area
            if ov > 0.3:
                out.append(("attachment_in_volume", f"{t} {v['id']}-{side} steht {ov:.1f} m² im Baukörper {w2['id']}"))
    return out
