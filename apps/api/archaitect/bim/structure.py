"""Structural repairs run first in ``logic.complete``: whatever the model (or the user's edit) drew, volumes, openings and attachments must be buildable.

audit.audit() is the matching checker (scripts/construction_bench.py measures both). Every repair appends a German note for the user.
"""
from __future__ import annotations

from shapely.geometry import box
from shapely.ops import unary_union

from .geom import side_length
from .audit import MIN_OVERLAP_M2, _fp, _sh, _zr, attach_dims

ATTACH = ("terrace", "steps", "ramp", "carport", "stair_ext", "loggia")
MARGIN = 0.15            # distance of an opening to the wall end
HIGH = 1.2               # base_z above which a volume needs something below it (lower = Hochparterre / entrance lift)


def _volumes(spec, notes):
    vols = spec.get("volumes", [])
    _push_apart(spec, notes)
    if _unfloat(spec, notes):          # a volume put on the ground may now clash with the one it was supposed to sit on
        _push_apart(spec, notes)


def _push_apart(spec, notes):
    vols = spec.get("volumes", [])
    # 1. clashes: the smaller volume is pushed out of the larger one along the axis with the least movement
    for _ in range(6):
        moved = False
        for i, a in enumerate(vols):
            for b in vols[i + 1:]:
                za, zb = _zr(spec, a), _zr(spec, b)
                if min(za[1], zb[1]) - max(za[0], zb[0]) < 0.4:
                    continue
                fa, fb = _fp(a), _fp(b)
                if fa.intersection(fb).area <= MIN_OVERLAP_M2:
                    continue
                big, small = (a, b) if fa.area >= fb.area else (b, a)
                fbig = _fp(big)
                sx, sy = small["size"]
                ox, oy = small["origin"]
                bx0, by0, bx1, by1 = fbig.bounds
                cands = [(abs(bx1 - ox), (bx1, oy)), (abs(ox + sx - bx0), (bx0 - sx, oy)), (abs(by1 - oy), (ox, by1)), (abs(oy + sy - by0), (ox, by0 - sy))]
                # do not push it into a third volume
                others = [_fp(w) for w in vols if w is not big and w is not small]
                best = None
                for dist, (nx, ny) in sorted(cands, key=lambda t: t[0]):
                    r = box(nx, ny, nx + sx, ny + sy)
                    if all(r.intersection(o).area <= MIN_OVERLAP_M2 for o in others):
                        best = (nx, ny)
                        break
                if best is None:
                    best = sorted(cands, key=lambda t: t[0])[0][1]
                small["origin"] = [round(best[0], 3), round(best[1], 3)]
                notes.append(f"Baukörper {small['id']} durchdrang {big['id']}: neben den Baukörper verschoben")
                moved = True
        if not moved:
            break


def _unfloat(spec, notes) -> bool:
    """An elevated volume needs a supporting volume below it, else it stands on the ground."""
    vols = spec.get("volumes", [])
    changed = False
    for v in vols:
        z0 = float(v.get("base_z", 0.0))
        if z0 <= HIGH:
            continue
        fp = _fp(v)
        below = [w for w in vols if w is not v and _zr(spec, w)[1] >= z0 - 0.35 and _zr(spec, w)[0] < z0 - 0.2]
        share = fp.intersection(unary_union([_fp(w) for w in below])).area / fp.area if below else 0.0
        if share < 0.6:
            v["base_z"] = 0.0
            changed = True
            notes.append(f"Baukörper {v['id']} schwebte ohne Unterbau: auf das Gelände gestellt")
    return changed


def _openings(spec, notes):
    V = {v["id"]: v for v in spec.get("volumes", [])}
    keep = []
    for o in spec.get("openings", []):
        v = V.get(o.get("volume"))
        if v is None:
            notes.append("Öffnung ohne Baukörper entfernt")
            continue
        n = int(v.get("storeys", 1))
        st = int(o.get("storey", 0))
        if st >= n + (1 if v.get("roof") else 0):
            notes.append(f"Öffnung {v['id']}-{o['side']} auf Geschoss {st + 1} entfernt (Baukörper hat {n})")
            continue
        L = side_length(o["side"], *v["size"])
        w = float(o["width"])
        if w > L - 2 * MARGIN:
            w = L - 2 * MARGIN
        if w < 0.4:
            notes.append(f"Öffnung {v['id']}-{o['side']} G{st}: Wand zu kurz, entfernt")
            continue
        off = min(max(float(o["offset"]), MARGIN), L - w - MARGIN)
        if abs(w - float(o["width"])) > 0.01 or abs(off - float(o["offset"])) > 0.01:
            notes.append(f"Öffnung {v['id']}-{o['side']} G{st}: in die Wand gesetzt ({off:.2f}–{off + w:.2f} m)")
        o = dict(o, width=round(w, 3), offset=round(off, 3))
        if st == n:       # Giebelfenster: only a gable roof has an attic wall, and the window must fit inside the triangle
            roof = v.get("roof") or {}
            ridge = roof.get("ridge", "x")
            if roof.get("type") != "gable" or o["side"] not in (("W", "E") if ridge == "x" else ("S", "N")):
                notes.append(f"Öffnung {v['id']}-{o['side']} im Dachgeschoss entfernt (dort gibt es keinen Giebel)")
                continue
            import math
            pitch = math.radians(float(roof.get("pitch_deg", 45)))
            span = v["size"][1] if ridge == "x" else v["size"][0]
            rise = span / 2 * math.tan(pitch) - 0.2 / math.cos(pitch) - 0.03
            f = lambda uu: rise * (1 - abs(2 * uu / L - 1))  # noqa: E731
            top = min(f(off), f(off + w)) - 0.05
            sill = max(0.0, float(o.get("sill", 0.0)))
            hgt = min(float(o["height"]), top - sill)
            if hgt < 0.5:
                notes.append(f"Öffnung {v['id']}-{o['side']} im Giebel entfernt (zu wenig Platz im Dreieck)")
                continue
            if abs(hgt - float(o["height"])) > 0.01:
                notes.append(f"Öffnung {v['id']}-{o['side']} im Giebel auf {hgt:.2f} m Höhe gekürzt")
            o["height"], o["sill"] = round(hgt, 3), round(sill, 3)
            keep.append(o)
            continue
        if st < n:
            sh = _sh(spec, v)
            sill, hgt = max(0.0, float(o.get("sill", 0.0))), float(o["height"])
            if sill + hgt > sh - 0.1:
                if hgt > sh - 0.1:
                    hgt, sill = sh - 0.1, 0.0
                else:
                    sill = sh - 0.1 - hgt
                notes.append(f"Öffnung {v['id']}-{o['side']} G{st}: unter die Geschossdecke gesetzt")
            if hgt < 0.5:
                continue
            o["sill"], o["height"] = round(sill, 3), round(hgt, 3)
        keep.append(o)
    spec["openings"] = keep


def _attachments(spec, notes):
    V = {v["id"]: v for v in spec.get("volumes", [])}
    out = []
    for c in spec.get("components", []):
        t = c.get("type")
        v = V.get(c.get("volume"))
        if c.get("volume") is not None and v is None:
            notes.append(f"{t} ohne Baukörper ({c.get('volume')}) entfernt")
            continue
        if v is None or c.get("side") not in ("S", "N", "E", "W") or t not in ATTACH:
            out.append(c)
            continue
        side = c["side"]
        ox, oy = v["origin"]
        W, D = v["size"]
        L = side_length(side, W, D)
        c = dict(c)
        w, dp = attach_dims(c)
        if w > L:
            c["width"] = w = round(L, 2)
            notes.append(f"{t} {v['id']}-{side} auf Wandbreite gekürzt")
        u = float(c["u"]) if c.get("u") is not None else L / 2
        u2 = min(max(u, w / 2 + 0.25), L - w / 2 - 0.25) if w <= L - 0.4 else L / 2
        if abs(u2 - u) > 0.01:
            c["u"] = round(u2, 3)
            notes.append(f"{t} {v['id']}-{side} an die Wand geschoben")
        a, b = u2 - w / 2, u2 + w / 2
        rect = {"S": box(ox + a, oy - dp, ox + b, oy), "N": box(ox + a, oy + D, ox + b, oy + D + dp),
                "W": box(ox - dp, oy + a, ox, oy + b), "E": box(ox + W, oy + a, ox + W + dp, oy + b)}[side]
        z0 = float(v.get("base_z", 0.0))
        clash = [w2 for w2 in spec["volumes"] if w2 is not v and _zr(spec, w2)[0] <= z0 + 1.2 and rect.intersection(_fp(w2)).area > 0.3]
        if clash:
            notes.append(f"{t} {v['id']}-{side} stand im Baukörper {clash[0]['id']}: entfernt")
            continue
        out.append(c)
    spec["components"] = out


def _params(spec, notes):
    """Component parameters the catalogue would reject (out of range, unknown name, wrong enum, storey that does not exist) are corrected instead of failing the whole build."""
    from . import catalog
    V = {v["id"]: v for v in spec.get("volumes", [])}
    for c in spec.get("components", []):
        t = c.get("type")
        if t not in catalog.C:
            continue
        ps = catalog.C[t]["params"]
        for k in [k for k in c if k not in ps and k not in ("type", "volume", "note", "id")]:
            del c[k]
            notes.append(f"{t}: Parameter „{k}“ gibt es nicht, ignoriert")
        for k, (ty, default, lo, hi, _txt) in ps.items():
            val = c.get(k)
            if val is None:
                continue
            if ty in ("n", "i") and isinstance(val, (int, float)) and not isinstance(val, bool):
                nv = val
                if lo is not None and nv < lo:
                    nv = lo
                if hi is not None and nv > hi:
                    nv = hi
                if nv != val:
                    c[k] = int(nv) if ty == "i" else round(nv, 3)
                    notes.append(f"{t}.{k}: {val} auf {c[k]} begrenzt (erlaubt {lo}..{hi})")
            elif ty == "e" and val not in lo:
                c[k] = default
                notes.append(f"{t}.{k}: {val!r} nicht erlaubt, {default!r} gesetzt")
        v = V.get(c.get("volume"))
        if t == "technical_box" and v is not None:       # roof plant must stand inside the roof area (volume was resized / moved)
            W, D = v["size"]
            w, d = min(float(c.get("width", 1.5)), W - 0.8), min(float(c.get("depth", 1.5)), D - 0.8)
            if w > 0.3 and d > 0.3:
                c["width"], c["depth"] = round(w, 2), round(d, 2)
                for k, ext, dim in (("x", W, w), ("y", D, d)):
                    if c.get(k) is not None:
                        c[k] = round(min(max(float(c[k]), 0.35), ext - dim - 0.35), 2)
            else:
                c["_drop"] = True
        if t == "loggia" and v is not None:
            n = int(v.get("storeys", 1))
            if int(c.get("storey", ps["storey"][1] if "storey" in ps else 0)) >= n:
                c["storey"] = n - 1
                notes.append(f"loggia {v['id']}: auf das oberste Geschoss gesetzt")
            L = side_length(c.get("side", "S"), *v["size"])
            w = float(c.get("width", 3.0))
            if w > L - 0.4:
                c["width"] = w = round(max(1.5, L - 0.6), 2)
            u = float(c["u"]) if c.get("u") is not None else L / 2
            c["u"] = round(min(max(u, w / 2 + 0.25), L - w / 2 - 0.25), 3)


def _dormers(spec, notes):
    """Dormers must sit on an existing slope, inside the roof length and below the main ridge; otherwise they are shrunk, lowered or removed."""
    import math
    V = {v["id"]: v for v in spec.get("volumes", [])}
    keep = []
    for dm in spec.get("dormers", []):
        v = V.get(dm.get("volume"))
        roof = (v or {}).get("roof") or {}
        if v is None or roof.get("type") != "gable":
            notes.append("Gaube ohne Satteldach entfernt")
            continue
        ridge = roof.get("ridge", "x")
        slopes = ("W", "E") if ridge == "y" else ("S", "N")
        dm = dict(dm)
        if dm.get("slope") not in slopes:
            dm["slope"] = slopes[0]
            notes.append(f"Gaube: Dachseite auf {slopes[0]} gesetzt")
        W, D = v["size"]
        Lr = W if ridge == "x" else D
        span = D if ridge == "x" else W
        tn = math.tan(math.radians(float(roof.get("pitch_deg", 45))))
        pd = math.radians(float(dm.get("pitch_deg", roof.get("pitch_deg", 45))))
        t = float(v.get("wall_thickness", 0.3)) + 0.1
        w, inset, wh = float(dm["width"]), float(dm.get("inset", 0.8)), float(dm.get("wall_height", 1.4))
        w = min(w, Lr - 2 * t - 0.2)
        ok = False
        for _ in range(12):
            reach = (inset * tn + wh + (w / 2 + 0.25) * math.tan(pd)) / tn if tn > 0 else 99
            if reach < span / 2 - 0.1 and w >= 0.8:
                ok = True
                break
            if wh > 0.95:
                wh = max(0.95, wh - 0.2)
            elif w > 0.8:
                w = max(0.8, w - 0.2)
            elif inset > 0.3:
                inset = max(0.3, inset - 0.2)
            else:
                break
        if not ok:
            notes.append(f"Gaube auf {v['id']} entfernt (passt nicht unter den First)")
            continue
        off = min(max(float(dm.get("offset", (Lr - w) / 2)), t + 0.05), Lr - w - t - 0.05)
        if (w, wh, inset, off) != (float(dm["width"]), float(dm.get("wall_height", 1.4)), float(dm.get("inset", 0.8)), float(dm.get("offset", off))):
            notes.append(f"Gaube auf {v['id']} angepasst (Breite {w:.1f} m, Wandhöhe {wh:.2f} m)")
        dm.update(width=round(w, 2), wall_height=round(wh, 2), inset=round(inset, 2), offset=round(off, 2))
        keep.append(dm)
    if "dormers" in spec:
        spec["dormers"] = keep


def clamp_params(spec: dict, notes: list[str]) -> None:
    """Re-run after the plausibility repairs added components of their own (canopy, lamps ...)."""
    _params(spec, notes)
    spec["components"] = [c for c in spec.get("components", []) if not c.get("_drop")]


def repair(spec: dict, notes: list[str]) -> None:
    """In place; order matters: volumes (positions) -> openings (walls) -> attachments (need final positions)."""
    _volumes(spec, notes)
    _openings(spec, notes)
    _params(spec, notes)
    _dormers(spec, notes)
    _attachments(spec, notes)
    spec["components"] = [c for c in spec.get("components", []) if not c.get("_drop")]
