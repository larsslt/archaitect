"""Architectural plausibility rules that complete or flag a spec (deterministic, idempotent).

complete(spec) -> (spec', notes): repairs what is unambiguous
  - a balcony / terrace / external stair / entrance steps / ramp needs a door onto it: an overlapping window is converted
    to a french door, otherwise a door is inserted (overlapping windows removed)
  - external stair landing snaps to the nearest floor level
  - a canopy is raised above the door beneath it
audit(spec) -> warnings for what cannot be repaired without guessing (overlaps, covered windows, missing entrance ...).
Automatic changes are recorded in spec["auto_notes"] and shown as warnings.
"""
from __future__ import annotations

from .ifc_garden2 import TYPES as G2_TYPES

import copy
import math

from . import structure
from .geom import facade_xy, side_length

WIN_ONLY = {"sashes", "bars", "window_type", "transom", "shutters", "flower_box", "sill_material", "glass", "surround", "arch_rise"}


def _vol(spec):
    return {v["id"]: v for v in spec.get("volumes", [])}


def _sh(spec, v):
    return float(v.get("storey_height", spec.get("storey_height", 3.0)))


def _span(o):
    return float(o["offset"]), float(o["offset"]) + float(o["width"])


def _overlap(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])


def _at(spec, vid, side, storey):
    return [o for o in spec.get("openings", []) if o["volume"] == vid and o["side"] == side and int(o["storey"]) == storey]


def _door_like(o):
    return o.get("kind", "window") == "door"


def _make_door(spec, v, side, storey, span, kind_note, w=1.4, french=True, h=2.25):
    """Ensure a door overlapping `span` exists on (v, side, storey). Returns note or None."""
    vid = v["id"]
    L = side_length(side, *v["size"])
    ops = _at(spec, vid, side, storey)
    existing = next((o for o in ops if _door_like(o) and _overlap(_span(o), span) > 0.3), None)
    if existing:
        if french and storey > 0 and existing.get('door_type') == 'panel':
            existing['door_type'] = 'french'
            return f"Balkontür {vid}-{side} Geschoss {storey} als verglaste Tür ausgeführt"
        return None
    if any(float(o["width"]) > 3.0 and _overlap(_span(o), span) >= 0.9 for o in ops):
        return None  # wide glazing / glass wall: treated as the access itself
    sh = _sh(spec, v)
    h = min(h, sh - 0.35)
    wins = [o for o in ops if not _door_like(o) and _overlap(_span(o), span) >= 0.75 * float(o["width"])]
    others = [o for o in ops if o not in wins]  # windows only partly inside the span stay; a new door is placed clear of them
    if wins:
        tgt = max(wins, key=lambda o: _overlap(_span(o), span))
        c = (float(tgt["offset"]) + float(tgt["width"]) / 2)
        nw = max(float(tgt["width"]), 1.1) if french else float(tgt["width"])
        action = "Fenster zur Tür umgewandelt"
        repl = tgt
    else:
        c = (span[0] + span[1]) / 2
        nw = min(w, max(0.9, span[1] - span[0] - 0.3))
        action = "Tür ergänzt"
        repl = None
    off = c - nw / 2
    off = min(max(off, 0.2), L - nw - 0.2)
    nspan = (off, off + nw)
    # shrink to the original width if widening would hit a neighbour
    if repl is not None and any(_overlap(_span(o), nspan) > 0 for o in others):
        nw = float(repl["width"])
        off = float(repl["offset"])
        nspan = (off, off + nw)
    clash = [o for o in others if _overlap(_span(o), nspan) > 0]
    door = {"volume": vid, "side": side, "storey": storey, "offset": round(off, 3), "width": round(nw, 3), "height": round(h, 3), "sill": 0.0,
            "kind": "door", "door_type": "french" if french else "panel", "auto": True,
            "panel": (repl or {}).get("frame", "paint_white") if french else "paint_white",
            "frame": (repl or {}).get("frame", "paint_white")}
    out = [o for o in spec["openings"] if o is not repl and o not in clash]
    out.append(door)
    spec["openings"] = out
    return f"{action} für {kind_note}: {vid}-{side} Geschoss {storey} bei {off:.1f}–{off + nw:.1f} m" + (f" ({len(clash)} Fenster entfernt)" if clash else "")


STD_CAMS = ("hero_se", "hero_sw", "street_s", "street_n", "drone_se")


def frame_cameras(spec: dict) -> None:
    """Standard cameras computed from the actual building size (nothing guessed by the model): every view frames the whole house."""
    vols = spec.get("volumes", [])
    if not vols:
        return
    x0 = min(v["origin"][0] for v in vols)
    y0 = min(v["origin"][1] for v in vols)
    x1 = max(v["origin"][0] + v["size"][0] for v in vols)
    y1 = max(v["origin"][1] + v["size"][1] for v in vols)
    h = 0.0
    for v in vols:
        top = float(v.get("base_z", 0.0) or 0.0) + int(v["storeys"]) * _sh(spec, v)
        if (v.get("roof") or {}).get("type", "flat") != "flat":
            top += 0.3 * min(v["size"])
        h = max(h, top)
    cx, cy, w, d = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
    tz = max(1.5, h * 0.42)

    def cam(name, az_deg, lens, need_w, elev=0.0):
        half = math.atan(18.0 / lens)                       # half horizontal field of view (36 mm sensor)
        halfv = math.atan(10.125 / lens)                    # half vertical field of view (16:9 render)
        dist = max(need_w * 0.62 / math.tan(half), h * 0.78 / math.tan(halfv)) + 0.5 * min(w, d)
        a = math.radians(az_deg)
        pos = [cx + dist * math.sin(a), cy - dist * math.cos(a), 1.65 + elev]
        return {"name": name, "position": [round(c, 2) for c in pos], "target": [round(cx, 2), round(cy, 2), round(tz + elev * 0.3, 2)], "lens_mm": lens}

    diag = math.hypot(w, d)
    cams = [cam("hero_se", 38, 28, diag), cam("hero_sw", -38, 28, diag), cam("street_s", 0, 30, w), cam("street_n", 180, 30, w),
            cam("drone_se", 38, 32, diag, elev=max(4.0, h * 0.9))]
    keep = [c for c in (spec.get("render", {}).get("cameras") or []) if isinstance(c, dict) and c.get("name") not in STD_CAMS and c.get("name") not in {x["name"] for x in cams}]
    spec.setdefault("render", {})["cameras"] = cams + keep[:2]


def _door_lamps(spec, v, d, notes):
    """A Wandleuchte on BOTH sides of the main entrance door (symmetry; one-sided lamps look like a mistake)."""
    comps = spec.setdefault("components", [])
    side = d["side"]
    L = side_length(side, *v["size"])
    uc = float(d["offset"]) + float(d["width"]) / 2
    off = float(d["width"]) / 2 + 0.55
    z = round(max(1.6, min(float(d["sill"]) + float(d["height"]) * 0.9, 2.4)), 2)
    ref = [c for c in comps if c.get("type") == "lamp" and c.get("volume") == v["id"] and c.get("side", "S") == side
           and 0.3 < abs(float(c.get("u", L / 2)) - uc) < 2.6]
    if ref:       # one lamp already stands beside the door: mirror it exactly (same distance, same height, same model)
        r = ref[0]
        um = 2 * uc - float(r["u"])
        if 0.3 <= um <= L - 0.3 and not any(c.get("type") == "lamp" and c.get("volume") == v["id"] and c.get("side", "S") == side
                                           and abs(float(c.get("u", L / 2)) - um) < 0.6 for c in comps):
            m = dict(r)
            m["u"] = round(um, 3)
            comps.append(m)
            notes.append(f"Laterne neben Haustür {v['id']}-{side} gespiegelt ergänzt")
        return
    for sgn in (-1, 1):
        u = uc + sgn * off
        if u < 0.3 or u > L - 0.3:
            continue
        if any(c.get("type") == "lamp" and c.get("volume") == v["id"] and c.get("side", "S") == side
               and abs(float(c.get("u", L / 2)) - u) < 0.8 for c in comps):
            continue
        comps.append({"type": "lamp", "volume": v["id"], "side": side, "u": round(u, 3), "z": z})
        notes.append(f"Laterne neben Haustür {v['id']}-{side} ergänzt")


def complete(spec: dict) -> tuple[dict, list[str]]:
    spec = copy.deepcopy(spec)
    notes: list[str] = []
    structure.repair(spec, notes)          # volumes / openings / attachments must be buildable before anything else is derived from them
    V = _vol(spec)
    spec.setdefault("openings", [])
    # Entrance steps need a threshold above the ground: lift the ground-level volumes (Hochparterre) so the door is not buried by the steps.
    lift = 0.0
    for c in spec.get("components", []):
        v = V.get(c.get("volume"))
        if c.get("type") == "steps" and v and float(v.get("base_z", 0.0)) <= 0.05:
            lift = max(lift, min(0.9, int(c.get("count", 3)) * float(c.get("rise", 0.17))))
    if lift > 0.05:
        for v in spec.get("volumes", []):
            if float(v.get("base_z", 0.0)) <= 0.05:
                v["base_z"] = round(lift, 3)
        for b in spec.get("balconies", []):
            if "level" in b:
                b["level"] = round(float(b["level"]) + lift, 3)
        notes.append(f"Erdgeschoss um {lift:.2f} m angehoben (Eingangstreppe): Sockel unter dem Haus, Tür liegt über den Stufen.")
    for b in spec.get("balconies", []):
        v = V.get(b.get("volume"))
        if not v:
            continue
        st = round((float(b["level"]) - float(v.get("base_z", 0.0))) / _sh(spec, v))
        if 0 <= st < int(v["storeys"]):
            n = _make_door(spec, v, b["side"], st, (float(b["offset"]), float(b["offset"]) + float(b["width"])), "Balkon")
            if n:
                notes.append(n)
    keep = []
    for c in spec.get("components", []):
        v = V.get(c.get("volume"))
        if c.get("type") == "solar" and v and c.get("mode") == "pitched":        # pitched PV needs a gable roof; the model often asks for it on shed/hip roofs
            rt = (v.get("roof") or {}).get("type", "flat")
            if rt == "flat":
                c["mode"] = "flat"
                notes.append("Solaranlage: Flachdach, Aufständerung statt Schrägdach.")
            elif rt != "gable":
                notes.append(f"Solaranlage auf {v.get('name', v.get('id'))} entfällt: Schrägdach-PV ist nur auf Satteldächern darstellbar.")
                spec.setdefault("assumptions", []).append(notes[-1])
                continue
        keep.append(c)
    if "components" in spec:
        spec["components"] = keep
    for i, c in enumerate(spec.get("components", [])):
        v = V.get(c.get("volume"))
        t = c.get("type")
        if not v:
            continue
        side = c.get("side", "S")
        if side not in "SNEW" or t not in ("terrace", "steps", "ramp", "stair_ext", "canopy", "carport", "loggia"):
            continue
        L = side_length(side, *v["size"])
        sh = _sh(spec, v)
        u = c.get("u")
        if u is None:
            u = L / 2 if t != "stair_ext" else min(1.0, L / 4)
        if t == "terrace":
            st = round(float(c.get("z", 0.0)) / sh)
            w = float(c.get("width", 4.0))
            if 0 <= st < int(v["storeys"]):
                n = _make_door(spec, v, side, st, (u - w / 2, u + w / 2), "Terrasse", w=min(2.4, w - 0.4))
            else:   # the terrace lies above the storeys of this volume (e.g. on its roof): there is no wall here to put a door into
                n = None
                notes.append(f"Terrasse {v['id']}-{side}: liegt auf {float(c.get('z', 0.0)):.1f} m über den {int(v['storeys'])} Geschoss(en) von Volumen {v['id']}; "
                             "keine Tür ergänzt, der Zugang muss über ein angrenzendes Volumen oder eine Treppe erfolgen.")
            bz = float(v.get("base_z", 0.0) or 0.0)
            if st == 0 and bz > 0.2 and float(c.get("z", 0.0)) > -0.05:
                # Hochparterre: a deck level with the threshold would be a 0.5 m high slab. Put the deck on the ground and let a short flight
                # of steps (rise <= 0.18) lead from the door down onto it - this is how a real entrance terrace is built.
                cnt = math.ceil(bz / 0.18)
                rise = round(bz / cnt, 3)
                tread = 0.32
                c["z"] = round(0.02 - bz, 3)
                c["depth"] = max(float(c.get("depth", 3.0)), cnt * tread + 1.2)
                if not any(o.get("type") == "steps" and o.get("volume") == v["id"] and o.get("side") == side
                           and abs(float(o.get("u", L / 2)) - u) < 1.0 for o in spec.get("components", [])):
                    spec["components"].append({"type": "steps", "volume": v["id"], "side": side, "u": round(u, 3), "width": min(1.8, w - 0.6),
                                               "count": cnt, "rise": rise, "tread": tread, "material": "stone_granite_grey"})
                notes.append(f"Terrasse {v['id']}-{side}: auf Geländehöhe gelegt, {cnt} Stufen à {rise * 100:.0f} cm führen von der Tür hinunter")
        elif t == "loggia":
            st = int(c.get("storey", 1))
            w = float(c.get("width", 3.0))
            n = _make_door(spec, v, side, st, (u - w / 2, u + w / 2), "Loggia", w=min(2.4, w - 0.5)) if 0 <= st < int(v["storeys"]) else None
        elif t in ("steps", "ramp"):
            w = float(c.get("width", 1.6 if t == "steps" else 1.5))
            n = _make_door(spec, v, side, 0, (u - w / 2, u + w / 2), "Eingang " + ("Treppe" if t == "steps" else "Rampe"), w=min(1.4, w), french=False, h=2.2)
        elif t == "stair_ext":
            z1 = float(c.get("z1", 3.0))
            st = max(1, round(z1 / sh))
            if abs(z1 - st * sh) > 0.02:
                notes.append(f"Außentreppe {v['id']}-{side}: z1 {z1:.2f} auf Geschossniveau {st * sh:.2f} gesetzt")
                c["z1"] = round(st * sh, 3)
                z1 = c["z1"]
            if st >= int(v["storeys"]):
                notes.append(f"Außentreppe {v['id']}-{side}: Podest bei {z1:.1f} m liegt über dem Gebäude, keine Tür ergänzt")
                continue
            run = math.ceil(z1 / 0.18) * float(c.get("tread", 0.27))
            ld = float(c.get("landing", 1.2))
            n = _make_door(spec, v, side, st, (u + run, u + run + ld), "Außentreppe (Podest)", w=1.0, french=False, h=2.1)
        elif t == "canopy":
            w = float(c.get("width", 2.2))
            doors = [o for o in _at(spec, v["id"], side, 0) if _door_like(o) and _overlap(_span(o), (u - w / 2, u + w / 2)) > 0.2]
            if doors:
                need = max(float(o["sill"]) + float(o["height"]) for o in doors) + 0.15
                if float(c.get("z", 2.5)) < need:
                    c["z"] = round(need, 3)
                    notes.append(f"Vordach {v['id']}-{side}: Höhe auf {need:.2f} m über Tür angehoben")
            n = None
        else:
            n = None
        if n:
            notes.append(n)
    # Haustür ohne Vordach wirkt wie ein weiteres Fenster: über der Haupteingangstür (Erdgeschoss, Flügeltür) ein kleines Pultvordach ergänzen
    comps = spec.setdefault("components", [])
    for v in spec.get("volumes", []):
        if float(v.get("base_z", 0.0) or 0.0) > 1.0:
            continue
        cands = [o for o in spec.get("openings", []) if o.get("volume") == v["id"] and int(o.get("storey", 0)) == 0 and o.get("kind") == "door"
                 and o.get("door_type", "panel") == "panel" and float(o["width"]) <= 1.6]
        if cands:
            _door_lamps(spec, v, cands[0], notes)
        if not cands or any(c.get("type") == "canopy" and c.get("volume") == v["id"] for c in comps):
            continue
        d = cands[0]
        side = d["side"]
        door_span = _span(d)
        if any(b.get('volume') == v['id'] and b.get('side') == side
               and _overlap((float(b['offset']), float(b['offset']) + float(b['width'])), door_span) >= float(d['width']) - 0.05
               and float(b.get('projection', b.get('depth', 0))) >= 0.5
               and float(b['level']) >= float(v.get('base_z', 0.0) or 0.0) + float(d['sill']) + float(d['height'])
               and float(b['level']) <= float(v.get('base_z', 0.0) or 0.0) + float(d['sill']) + float(d['height']) + 1.5
               for b in spec.get('balconies', [])):
            continue
        w = float(d["width"]) + 0.9
        u = float(d["offset"]) + float(d["width"]) / 2
        L = side_length(side, *v["size"])
        w = min(w, 2 * min(u, L - u) - 0.1)
        if w < float(d["width"]) + 0.2:
            continue
        comps.append({"type": "canopy", "volume": v["id"], "side": side, "u": round(u, 3), "width": round(w, 2), "projection": 1.1,
                      "z": round(float(d["sill"]) + float(d["height"]) + 0.2, 3), "kind": "shed", "support": "brackets", "thickness": 0.08,
                      "material": "steel_black", "roof_material": None})
        notes.append(f"Vordach über Haustür {v['id']}-{side} ergänzt")
    # Oversized paving (the model copies the 17x8 m "Platz" of the example) reads as a grey slab in front of the house.
    site = spec.get("site") or {}
    if site.get("paving"):
        kept = []
        for pv in site["paving"]:
            w, d = (float(x) for x in pv.get("size", (0, 0)))
            if w * d > 36.0:
                notes.append(f"Belag „{pv.get('name', 'Platz')}“ ({w:.0f}×{d:.0f} m) entfernt: zu große Fläche, nur kleine Terrassen/Wege werden gebaut.")
                spec.setdefault("assumptions", []).append(notes[-1])
                continue
            kept.append(pv)
        site["paving"] = kept
    resolve(spec, notes)
    from collections import Counter
    cnt = Counter(notes)
    notes = [n if k == 1 else f"{n} (×{k})" for n, k in cnt.items()]
    if notes:
        spec["auto_notes"] = sorted(set(spec.get("auto_notes", [])) | set(notes))
    # Hecken niedrig halten (sonst verdecken sie das Haus) und Bäume/Sträucher nicht vor die Haustür setzen
    for c in spec.get("components", []):
        if c.get("type") == "hedge":
            if float(c.get("height", 1.0)) > 1.2:
                c["height"] = 1.2
            if float(c.get("thickness", 0.5)) > 0.6:
                c["thickness"] = 0.6
    vmap = _vol(spec)
    for c in spec.get("components", []):
        if c.get("type") not in ("tree", "shrub") or c.get("x") is None or c.get("y") is None:
            continue
        for o in spec.get("openings", []):
            v = vmap.get(o.get("volume"))
            if v is None or o.get("kind") != "door" or int(o.get("storey", 0)) != 0:
                continue
            ox, oy = v["origin"]
            W, D = v["size"]
            a, b = _span(o)
            side = o["side"]
            reach = float(c.get("radius", 1.5)) + 1.0
            if side in "SN":
                y_out = (oy - reach, oy) if side == "S" else (oy + D, oy + D + reach)
                inside = ox + a - reach < c["x"] < ox + b + reach and y_out[0] <= c["y"] <= y_out[1]
                if inside:
                    c["x"] = round(ox + (b + reach + 0.3 if c["x"] >= ox + (a + b) / 2 else a - reach - 0.3), 2)
                    notes.append("Baum/Strauch von der Haustür weggerückt")
            else:
                x_out = (ox - reach, ox) if side == "W" else (ox + W, ox + W + reach)
                inside = oy + a - reach < c["y"] < oy + b + reach and x_out[0] <= c["x"] <= x_out[1]
                if inside:
                    c["y"] = round(oy + (b + reach + 0.3 if c["y"] >= oy + (a + b) / 2 else a - reach - 0.3), 2)
                    notes.append("Baum/Strauch von der Haustür weggerückt")
    frame_cameras(spec)
    structure.clamp_params(spec, notes)
    return spec, notes


def audit(spec: dict) -> list[str]:
    w: list[str] = []
    V = _vol(spec)
    ops = spec.get("openings", [])
    # overlaps between openings
    for i, a in enumerate(ops):
        for b in ops[i + 1:]:
            if a["volume"] == b["volume"] and a["side"] == b["side"] and int(a["storey"]) == int(b["storey"]) and _overlap(_span(a), _span(b)) > 0.02:
                vz = (float(a["sill"]), float(a["sill"]) + float(a["height"]))
                bz = (float(b["sill"]), float(b["sill"]) + float(b["height"]))
                if _overlap(vz, bz) > 0:
                    w.append(f"Öffnungen überlappen: {a['volume']}-{a['side']} Geschoss {a['storey']} bei {a['offset']} und {b['offset']} m")
    if ops and not any(_door_like(o) and int(o["storey"]) == 0 for o in ops):
        w.append("Kein Eingang: keine Tür im Erdgeschoss")
    # carport hides windows
    for c in spec.get("components", []):
        v = V.get(c.get("volume"))
        if not v:
            continue
        if c.get("type") == "carport":
            side, u, ww, h = c.get("side", "S"), c.get("u"), float(c.get("width", 3.2)), float(c.get("height", 2.4))
            u = side_length(side, *v["size"]) / 2 if u is None else u
            hit = [o for o in _at(spec, v["id"], side, 0) if _overlap(_span(o), (u - ww / 2, u + ww / 2)) > 0 and float(o["sill"]) < h]
            if hit:
                w.append(f"Carport {v['id']}-{side} verdeckt {len(hit)} Öffnung(en) im Erdgeschoss")
        if c.get("type") == "downpipe":
            side, u = c.get("side", "S"), c.get("u")
            if u is not None and any(_span(o)[0] - 0.05 < u < _span(o)[1] + 0.05 for o in ops if o["volume"] == v["id"] and o["side"] == side):
                w.append(f"Fallrohr {v['id']}-{side} bei u={u} kreuzt eine Öffnung")
    # solar vs technical box on the same flat roof
    rects = {}
    for c in spec.get("components", []):
        v = V.get(c.get("volume"))
        if not v:
            continue
        if c.get("type") == "technical_box":
            x = c.get("x") if c.get("x") is not None else (v["size"][0] - float(c.get("width", 2.2))) / 2
            y = c.get("y") if c.get("y") is not None else (v["size"][1] - float(c.get("depth", 1.6))) / 2
            rects.setdefault(v["id"], []).append(("Technikaufbau", x, y, x + float(c.get("width", 2.2)), y + float(c.get("depth", 1.6))))
        if c.get("type") == "solar" and c.get("mode", "flat") == "flat":
            tilt = math.radians(float(c.get("tilt", 15)))
            run = float(c.get("panel_l", 1.75)) * math.cos(tilt)
            pitch = run + max(0.35, float(c.get("panel_l", 1.75)) * math.sin(tilt) * 1.8)
            x, y = (c.get("x") if c.get("x") is not None else 0.8), (c.get("y") if c.get("y") is not None else 0.8)
            rects.setdefault(v["id"], []).append(("Solarfeld", x, y, x + int(c.get("cols", 4)) * (float(c.get("panel_w", 1.05)) + 0.02), y + (int(c.get("rows", 2)) - 1) * pitch + run))
    for vid, rs in rects.items():
        for i, a in enumerate(rs):
            for b in rs[i + 1:]:
                if min(a[3], b[3]) - max(a[1], b[1]) > 0 and min(a[4], b[4]) - max(a[2], b[2]) > 0:
                    w.append(f"{a[0]} und {b[0]} auf Dach {vid} überlappen")
    # garden objects must stand clear of the buildings
    vr = [(v["id"], v["origin"][0], v["origin"][1], v["origin"][0] + v["size"][0], v["origin"][1] + v["size"][1]) for v in spec.get("volumes", [])]
    for c in spec.get("components", []):
        t = c.get("type")
        if t in ("tree", "shrub", "bench", "garden_set", "garden_light"):
            r = {"tree": float(c.get("crown_radius", 3.0)) * 0.6 if c.get("kind") != "conifer" else float(c.get("crown_radius", 3.0)) * 0.8,
                 "shrub": float(c.get("radius", 0.7)), "bench": 0.9, "garden_set": 1.3, "garden_light": 0.2}[t]
            box = (c.get("x", 0.0) - r, c.get("y", 0.0) - r, c.get("x", 0.0) + r, c.get("y", 0.0) + r)
        elif t in ("flowerbed", "pool", "pond", "sauna_hut", "parking") or t in G2_TYPES:
            box = (c.get("x", 0.0), c.get("y", 0.0), c.get("x", 0.0) + float(c.get("width", 3.0)), c.get("y", 0.0) + float(c.get("depth", 1.2)))
        elif t == "hedge":
            box = (min(c.get("x0", 0.0), c.get("x1", 0.0)), min(c.get("y0", 0.0), c.get("y1", 0.0)), max(c.get("x0", 0.0), c.get("x1", 0.0)), max(c.get("y0", 0.0), c.get("y1", 0.0)))
        else:
            continue
        for vid, x0, y0, x1, y1 in vr:
            if t == "garden_set" or True:
                if min(box[2], x1) - max(box[0], x0) > 0.05 and min(box[3], y1) - max(box[1], y0) > 0.05:
                    w.append(f"Gartenobjekt {t} steht im Gebäude {vid} (Position {c.get('x', c.get('x0'))}, {c.get('y', c.get('y0'))})")
    # balconies above each other must not collide
    bal = spec.get("balconies", [])
    for i, a in enumerate(bal):
        for b in bal[i + 1:]:
            if a["volume"] == b["volume"] and a["side"] == b["side"] and abs(float(a["level"]) - float(b["level"])) < 0.3 \
                    and _overlap(_span(a), _span(b)) > 0:
                w.append(f"Balkone überlappen: {a['volume']}-{a['side']} bei {a['offset']} und {b['offset']} m")
    return w


# ---------------------------------------------------------------------------------------------- clash resolution
GAP = 0.15


def _P(c, k):
    from . import catalog
    v = c.get(k)
    return v if v is not None else catalog.C.get(c.get("type"), {}).get("params", {}).get(k, (None, None))[1]


def _zr(spec, v, o):
    z0 = int(o["storey"]) * _sh(spec, v) + float(o["sill"])
    return z0, z0 + float(o["height"])


def _blocks(spec, v, side, zlo, zhi):
    out = []
    for o in spec.get("openings", []):
        if o["volume"] == v["id"] and o["side"] == side:
            a, b = _zr(spec, v, o)
            if min(b, zhi) - max(a, zlo) > 0.02:
                out.append(_span(o))
    return out


def _free(L, hw, want, blocks, margin=GAP, reach=2.5):
    """nearest centre to `want` whose [c-hw, c+hw] clears all blocks by `margin`; None if none within `reach`."""
    lo, hi = 0.15 + hw, L - 0.15 - hw
    cands = [want] + [x for b in blocks for x in (b[0] - margin - hw, b[1] + margin + hw)]
    ok = []
    for c in cands:
        if lo - 1e-9 <= c <= hi + 1e-9 and all(c + hw <= b[0] - margin + 1e-9 or c - hw >= b[1] + margin - 1e-9 for b in blocks):
            ok.append(c)
    if not ok:
        return None
    best = min(ok, key=lambda c: abs(c - want))
    return best if abs(best - want) <= reach else None


def _resolve_openings(spec, notes):
    prio = lambda o: 3 if _door_like(o) and not o.get("auto") else 2 if _door_like(o) else 1
    V = _vol(spec)
    for _ in range(6):
        changed = False
        ops = spec["openings"]
        drop = set()
        for i, a in enumerate(ops):
            for j in range(i + 1, len(ops)):
                b = ops[j]
                if i in drop or j in drop or a["volume"] != b["volume"] or a["side"] != b["side"] or a["storey"] != b["storey"]:
                    continue
                if _overlap(_span(a), _span(b)) <= 0.02:
                    continue
                v = V.get(a["volume"])
                za, zb = _zr(spec, v, a), _zr(spec, v, b)
                if _overlap(za, zb) <= 0.02:
                    continue
                weak, strong, wi = (b, a, j) if prio(b) <= prio(a) else (a, b, i)
                S0, S1 = _span(strong)
                W0, W1 = _span(weak)
                wc, sc = (W0 + W1) / 2, (S0 + S1) / 2
                if wc < sc:  # weak lies left: trim its right edge
                    nw = S0 - GAP - W0
                    if nw >= 0.6:
                        weak["width"] = round(nw, 3)
                        notes.append(f"Öffnungen {a['volume']}-{a['side']} G{a['storey']}: Fenster bei {W0:.1f} m gekürzt (Überlappung)")
                        changed = True
                        continue
                else:
                    nw = W1 - (S1 + GAP)
                    if nw >= 0.6:
                        weak["offset"], weak["width"] = round(S1 + GAP, 3), round(nw, 3)
                        notes.append(f"Öffnungen {a['volume']}-{a['side']} G{a['storey']}: Fenster bei {W0:.1f} m gekürzt (Überlappung)")
                        changed = True
                        continue
                drop.add(wi)
                notes.append(f"Öffnungen {a['volume']}-{a['side']} G{a['storey']}: Fenster bei {W0:.1f} m entfernt (Überlappung mit {'Tür' if _door_like(strong) else 'Fenster'} bei {S0:.1f} m)")
                changed = True
        if drop:
            spec["openings"] = [o for k, o in enumerate(ops) if k not in drop]
        if not changed:
            break


def _clip_openings_for_parts(spec, notes):
    V = _vol(spec)
    # cornice: top-storey openings stay below it
    for c in spec.get("components", []):
        v = V.get(c.get("volume"))
        if not v:
            continue
        t = c.get("type")
        if t == "cornice" and c.get("z") is None:
            h = float(_P(c, "height"))
            sh = _sh(spec, v)
            for o in spec["openings"]:
                if o["volume"] == v["id"] and int(o["storey"]) == int(v["storeys"]) - 1 and not _door_like(o) and (c.get("side", "all") in ("all", o["side"])):
                    lim = sh - h - 0.05
                    if float(o["sill"]) + float(o["height"]) > lim + 0.12 and lim - float(o["sill"]) >= 0.6:
                        o["height"] = round(lim - float(o["sill"]), 3)
                        notes.append(f"Fenster {v['id']}-{o['side']} G{o['storey']}: Höhe unter das Gesims begrenzt")
        if t == "quoins":
            qw = float(_P(c, "width")) + 0.08
            for o in spec["openings"]:
                if o["volume"] != v["id"]:
                    continue
                L = side_length(o["side"], *v["size"])
                a, b = _span(o)
                if a < qw:
                    if b - qw >= 0.6 and L - b >= 0:
                        o["offset"], o["width"] = round(qw, 3), round(b - qw, 3)
                        notes.append(f"Öffnung {v['id']}-{o['side']} G{o['storey']}: vom Eckstein abgerückt")
                if b > L - qw:
                    a, b = _span(o)
                    if L - qw - a >= 0.6:
                        o["width"] = round(L - qw - a, 3)
                        notes.append(f"Öffnung {v['id']}-{o['side']} G{o['storey']}: vom Eckstein abgerückt")
    # slabs below/at balconies must not cut windows of the storey beneath
    for b in spec.get("balconies", []):
        v = V.get(b.get("volume"))
        if not v:
            continue
        st = round((float(b["level"]) - float(v.get("base_z", 0.0))) / _sh(spec, v))
        sh = _sh(spec, v)
        for o in spec["openings"]:
            if o["volume"] == v["id"] and o["side"] == b["side"] and int(o["storey"]) == st - 1 and not _door_like(o) \
                    and _overlap(_span(o), (float(b["offset"]), float(b["offset"]) + float(b["width"]))) > 0 \
                    and float(o["sill"]) + float(o["height"]) > sh - float(b.get("thickness", 0.2)) - 0.05:
                lim = sh - float(b.get("thickness", 0.2)) - 0.05 - float(o["sill"])
                if lim >= 0.6:
                    o["height"] = round(lim, 3)
                    notes.append(f"Fenster {v['id']}-{o['side']} G{st - 1}: unter Balkonplatte gekürzt")


def _move_parts(spec, notes):
    """Wall-mounted small parts (downpipe, lamp, sign, bracket, pilaster, column) move to the nearest free spot beside openings."""
    V = _vol(spec)
    out, placed = [], {}
    for c in spec.get("components", []):
        t = c.get("type")
        v = V.get(c.get("volume"))
        if t not in ("downpipe", "lamp", "sign", "bracket", "pilaster", "column") or not v:
            out.append(c)
            continue
        if t == "column" and float(c.get("distance", 1.2) or 1.2) >= 0.8:
            out.append(c)          # a free-standing colonnade (portico) stands in front of the wall: doors and windows behind it do not block it
            continue
        side = c.get("side", "S")
        L = side_length(side, *v["size"])
        sh = _sh(spec, v)
        top = int(v["storeys"]) * sh
        n = int(_P(c, "count") or 1) if t in ("pilaster", "column", "bracket") else 1
        sp = float(_P(c, "spacing") or 1.0)
        u0 = c.get("u")
        u0 = L / 2 if u0 is None else float(u0)
        poss = [u0 + (k - (n - 1) / 2) * sp for k in range(n)]
        if t == "downpipe":
            hw, zr = 0.12, (float(_P(c, "z0")), float(c["z1"]) if c.get("z1") is not None else top)
        elif t == "lamp":
            hw, zr = 0.25, (float(_P(c, "z")) - 0.25, float(_P(c, "z")) + 0.25)
        elif t == "sign":
            hw, zr = 0.5, (float(_P(c, "z")) - 0.15 - float(_P(c, "height")), float(_P(c, "z")))
        elif t == "bracket":
            z = float(c["z"]) if c.get("z") is not None else top
            hw, zr = 0.18, (z - float(_P(c, "size")), z)
        elif t == "pilaster":
            hw, zr = float(_P(c, "width")) / 2 + 0.06, (float(_P(c, "z0")), float(c["z1"]) if c.get("z1") is not None else top)
        else:
            hw, zr = float(_P(c, "radius")) + 0.1, (float(_P(c, "z0")), float(_P(c, "z1")))
        key = (v["id"], side)
        res = []
        for want in poss:
            blocks = _blocks(spec, v, side, *zr)
            blocks += [(e[2], e[3]) for e in placed.get(key, []) if min(e[1], zr[1]) - max(e[0], zr[0]) > 0.02]
            got = _free(L, hw, want, blocks, reach=2.5 if t == "downpipe" else 0.9)
            if got is None:
                notes.append(f"{t} {v['id']}-{side} bei {want:.1f} m entfernt (kein freier Platz neben den Öffnungen)")
                continue
            if abs(got - want) > 0.04:
                notes.append(f"{t} {v['id']}-{side}: von {want:.2f} auf {got:.2f} m verschoben (frei von Öffnungen)")
            placed.setdefault(key, []).append((zr[0], zr[1], got - hw, got + hw))
            res.append(got)
        if len(res) == n and all(abs(r - w) < 0.04 for r, w in zip(res, poss)):
            out.append(c)
        else:
            for r in res:
                cc = dict(c)
                cc["u"] = round(r, 3)
                if "count" in cc or t in ("pilaster", "column", "bracket"):
                    cc["count"] = 1
                out.append(cc)
    spec["components"] = out


def _clip_roofing_parts(spec, notes):
    """canopy / awning must not cover windows: clip to the window-free stretch around their centre."""
    V = _vol(spec)
    for c in list(spec.get("components", [])):
        t = c.get("type")
        v = V.get(c.get("volume"))
        if t not in ("canopy", "awning") or not v:
            continue
        side = c.get("side", "S")
        L = side_length(side, *v["size"])
        u = c.get("u")
        u = L / 2 if u is None else float(u)
        w = float(_P(c, "width"))
        z = float(_P(c, "z"))
        zr = (z - (float(_P(c, "drop")) if t == "awning" else 0.0) - 0.05, z + (0.35 if t == "canopy" else 0.05))
        blocks = [bk for bk in _blocks(spec, v, side, *zr)]
        bal_blocks = []
        if t == "canopy":      # a canopy never sits under a balcony: balconies above count as blocked stretches
            for bal in spec.get("balconies", []):
                if bal.get("volume") == v["id"] and bal.get("side") == side and z < float(bal.get("level", 0.0)) <= z + 1.6:   # only a balcony directly above (first floor), not one high above the entrance
                    bal_blocks.append((float(bal["offset"]) - 0.1, float(bal["offset"]) + float(bal["width"]) + 0.1))
        a, b = u - w / 2, u + w / 2
        for lo, hi in sorted(bal_blocks):
            if hi <= a or lo >= b:
                continue
            if lo <= u <= hi:
                a, b = u, u            # centre under the balcony: nothing left
                break
            if lo > u:
                b = min(b, lo - 0.1)
            else:
                a = max(a, hi + 0.1)
        for lo, hi in sorted(blocks):
            if hi <= a or lo >= b:
                continue
            if lo <= u <= hi:
                continue  # centre sits on an opening: leave it (a later check warns)
            if lo > u:
                b = min(b, lo - 0.1)
            else:
                a = max(a, hi + 0.1)
        if (b - a) < w - 0.01:
            if b - a >= 0.8:
                c["u"], c["width"] = round((a + b) / 2, 3), round(b - a, 3)
                notes.append(f"{t} {v['id']}-{side}: auf {b - a:.1f} m gekürzt (Fenster frei)")
            else:
                spec["components"].remove(c)
                notes.append(f"{t} {v['id']}-{side} entfernt (kein freier Streifen neben Fenstern)")


def _bay_windows(spec, notes):
    V = _vol(spec)
    for c in spec.get("components", []):
        if c.get("type") != "bay" or c.get("volume") not in V:
            continue
        v = V[c["volume"]]
        side = c.get("side", "S")
        L = side_length(side, *v["size"])
        u = c.get("u")
        u = L / 2 if u is None else float(u)
        w = float(_P(c, "width"))
        a, b = u - w / 2, u + w / 2
        z0, z1 = float(_P(c, "z0")), float(_P(c, "z1"))
        kill = []
        for o in spec["openings"]:
            if o["volume"] == v["id"] and o["side"] == side and not _door_like(o):
                za, zb = _zr(spec, v, o)
                if min(zb, z1) - max(za, z0) > 0.02 and _overlap(_span(o), (a, b)) > 0:
                    kill.append(o)
        for o in kill:
            notes.append(f"Fenster {v['id']}-{side} G{o['storey']} bei {o['offset']} m entfernt (Erker davor)")
        if kill:
            spec["openings"] = [o for o in spec["openings"] if o not in kill]


def _eave_sides(v):
    r = v.get("roof") or {}
    t = r.get("type", "flat")
    if t == "gable":
        return ("S", "N") if r.get("ridge", "x") == "x" else ("W", "E")
    if t == "shed":
        return (r.get("fall_to", "S"),)
    return ("S", "E", "N", "W") if t in ("hip", "mansard", "gambrel") else ()


def _downpipes(spec, notes):
    """A gutter without a downpipe drains nowhere: every gutter side gets a downpipe at both ends (the builder joins it to the gutter outlet)."""
    comps = spec.setdefault("components", [])
    V = _vol(spec)
    done = set()
    for g in list(comps):
        if g.get("type") != "gutter" or g.get("volume") not in V:
            continue
        v = V[g["volume"]]
        sides = _eave_sides(v) if g.get("side", "all") == "all" else (g["side"],)
        for side in sides:
            if side not in _eave_sides(v) or (v["id"], side) in done:
                continue
            done.add((v["id"], side))
            L = side_length(side, *v["size"])
            have = [float(c["u"]) if c.get("u") is not None else L - 0.3 for c in comps
                    if c.get("type") == "downpipe" and c.get("volume") == v["id"] and c.get("side", "S") == side]
            for u in (0.3, L - 0.3):
                if not any(abs(h - u) < 1.5 for h in have):
                    comps.append({"type": "downpipe", "volume": v["id"], "side": side, "u": round(u, 3)})
                    have.append(u)
                    notes.append(f"Fallrohr {v['id']}-{side} bei u={u:.1f} an die Dachrinne angeschlossen ergänzt")


def _symmetrize_lamps(spec, notes):
    """The two lamps beside an entrance door hang at the same height and the same distance from the door axis (applied after all moves)."""
    V = _vol(spec)
    comps = spec.get("components", [])
    for d in spec.get("openings", []):
        v = V.get(d.get("volume"))
        if not v or d.get("kind") != "door" or int(d.get("storey", 0)) != 0:
            continue
        side = d["side"]
        uc = float(d["offset"]) + float(d["width"]) / 2
        near = [c for c in comps if c.get("type") == "lamp" and c.get("volume") == v["id"] and c.get("side", "S") == side
                and c.get("u") is not None and 0.2 < abs(float(c["u"]) - uc) < 2.8]
        left = sorted([c for c in near if float(c["u"]) < uc], key=lambda c: uc - float(c["u"]))
        right = sorted([c for c in near if float(c["u"]) > uc], key=lambda c: float(c["u"]) - uc)
        if not left or not right:
            continue
        a, b = left[0], right[0]
        dist = min(uc - float(a["u"]), float(b["u"]) - uc)
        z = round(max(1.6, min(float(d.get("sill", 0.0)) + float(d["height"]) * 0.9, 2.4)), 2)
        if (abs((uc - float(a["u"])) - (float(b["u"]) - uc)) > 0.01 or abs(float(a.get("z", z)) - float(b.get("z", z))) > 0.01
                or a.get("size") != b.get("size") or a.get("material") != b.get("material")):
            for c, sg in ((a, -1), (b, 1)):
                c["u"] = round(uc + sg * dist, 3)
                c["z"] = z
                for k in ("size", "material"):
                    if a.get(k) is not None:
                        c[k] = a[k]
                    elif k in c:
                        del c[k]
            notes.append(f"Laternen am Eingang {v['id']}-{side} symmetrisch gesetzt (gleiche Höhe {z} m, Abstand {dist:.2f} m)")


_CLEAR_R = {"tree": lambda c: float(c.get("crown_radius", 3.0)) * 0.3 + 0.3, "shrub": lambda c: float(c.get("radius", 0.7)),
            "bench": lambda c: 0.9, "garden_set": lambda c: 1.3, "garden_light": lambda c: 0.3}


def _entrance_clear(spec, notes):
    """Nothing stands in the entrance zone in front of a ground-level door (bench, garden set, shrub, tree, lamp post): move it sideways or outwards."""
    V = _vol(spec)
    out = {"S": (0.0, -1.0), "N": (0.0, 1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}
    for d in spec.get("openings", []):
        v = V.get(d.get("volume"))
        if not v or d.get("kind") != "door" or int(d.get("storey", 0)) != 0 or float(v.get("base_z", 0.0) or 0.0) > 1.5:
            continue
        side = d["side"]
        ox, oy = v["origin"]
        W, D = v["size"]
        L = side_length(side, W, D)
        u0, u1 = max(0.0, float(d["offset"]) - 0.5), min(L, float(d["offset"]) + float(d["width"]) + 0.5)
        zd = 2.4
        p = [facade_xy(side, ox, oy, W, D, u, -dd) for u in (u0, u1) for dd in (0.0, zd)]
        zx0, zx1, zy0, zy1 = min(q[0] for q in p), max(q[0] for q in p), min(q[1] for q in p), max(q[1] for q in p)
        ux, uy = out[side]
        for c in spec.get("components", []):
            t = c.get("type")
            if t not in _CLEAR_R or c.get("x") is None:
                continue
            r = _CLEAR_R[t](c)
            x, y = float(c["x"]), float(c["y"])
            if not (x + r > zx0 and x - r < zx1 and y + r > zy0 and y - r < zy1):
                continue
            # outward distance of the centre from the wall, lateral position along the wall
            dout = {"S": oy - y, "N": y - (oy + D), "E": x - (ox + W), "W": ox - x}[side]
            lat = {"S": x - ox, "N": ox + W - x, "E": y - oy, "W": oy + D - y}[side]
            uc = float(d["offset"]) + float(d["width"]) / 2
            hw = (u1 - u0) / 2 + r + 0.15
            opts = [("out", zd + r + 0.15 - dout), ("lat", hw - abs(lat - uc))]
            kind, amt = opts[1] if opts[1][1] <= opts[0][1] + 2.0 else opts[0]      # sideways first: the entrance axis stays open
            if kind == "out":
                c["x"], c["y"] = round(x + ux * amt, 2), round(y + uy * amt, 2)
            else:
                sg = 1.0 if lat >= uc else -1.0
                tx = {"S": (sg, 0.0), "N": (-sg, 0.0), "E": (0.0, sg), "W": (0.0, -sg)}[side]
                c["x"], c["y"] = round(x + tx[0] * amt, 2), round(y + tx[1] * amt, 2)
            notes.append(f"{t} bei ({x:.1f}|{y:.1f}) stand vor der Tür {v['id']}-{side}: nach ({c['x']}|{c['y']}) verschoben (Eingang bleibt frei)")


def _door_zones(spec, depth=2.4, pad=0.5):
    """Entrance zones in front of ground-level doors as (x0, y0, x1, y1) rectangles in the spec frame."""
    V = _vol(spec)
    out = []
    for d in spec.get("openings", []):
        v = V.get(d.get("volume"))
        if not v or d.get("kind") != "door" or int(d.get("storey", 0)) != 0 or float(v.get("base_z", 0.0) or 0.0) > 1.5:
            continue
        ox, oy = v["origin"]
        W, D = v["size"]
        L = side_length(d["side"], W, D)
        u0, u1 = max(0.0, float(d["offset"]) - pad), min(L, float(d["offset"]) + float(d["width"]) + pad)
        p = [facade_xy(d["side"], ox, oy, W, D, u, -dd) for u in (u0, u1) for dd in (0.0, depth)]
        out.append((min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p)))
    return out


def _carport_parking(spec, notes):
    """A carport shelters parking bays: the first bay of a parking area lies under the carport (N/S sides; the area must not hang somewhere else)."""
    V = _vol(spec)
    comps = spec.get("components", [])
    for cp in [c for c in comps if c.get("type") == "carport" and c.get("volume") in V and c.get("side") in ("N", "S")]:
        v = V[cp["volume"]]
        ox, oy = v["origin"]
        W, D = v["size"]
        side = cp["side"]
        L = side_length(side, W, D)
        u = float(cp["u"]) if cp.get("u") is not None else L / 2
        p = float(cp.get("projection", 5.5))
        cw = float(cp.get("width", 3.0))
        cx, wy = facade_xy(side, ox, oy, W, D, u, 0.0)
        y0, y1 = (wy, wy + p) if side == "N" else (wy - p, wy)
        for pk in [c for c in comps if c.get("type") == "parking" and c.get("x") is not None]:
            w, d, n = float(pk.get("width", 5.0)), float(pk.get("depth", 5.0)), max(1, int(pk.get("spaces", 2)))
            if (min(pk["x"] + w, cx + cw / 2) - max(pk["x"], cx - cw / 2) > 1.0 and min(pk["y"] + d, y1) - max(pk["y"], y0) > 1.0):
                continue
            bay = w / n
            py = y0 + (p - d) / 2
            zones = _door_zones(spec)
            cands = [cx - bay / 2, cx + bay / 2 - w]             # bays run east or west from the carport: take the side that keeps every entrance free
            ok = [px for px in cands if not any(min(px + w, z[2]) - max(px, z[0]) > 0.05 and min(py + d, z[3]) - max(py, z[1]) > 0.05 for z in zones)]
            px = cands[0]
            if cands[0] not in ok:                                   # an entrance lies east of the carport: fewer bays, they end before the entrance zone
                lim = [z[0] for z in zones if z[0] > px and min(py + d, z[3]) - max(py, z[1]) > 0.05]
                if lim and min(lim) - px >= bay:
                    k = max(1, min(n, int((min(lim) - px) // bay)))
                    pk["spaces"], pk["width"] = k, round(k * bay, 3)
                elif ok:
                    px = ok[0]
            pk["x"] = round(px, 3)
            pk["y"] = round(py, 3)
            notes.append(f"Stellplätze an das Carport {cp['volume']}-{side} gesetzt: der erste Stellplatz liegt unter dem Dach")
            break


def _bays_clear_entrance(spec, notes):
    """A bay / oriel never stands in front of an entrance door: with its lower edge at the ground it would put a glass box over the door and into the canopy.
    It is lifted above the door (and the canopy) into the upper storeys; if too little height remains it is removed."""
    V = _vol(spec)
    for c in list(spec.get("components", [])):
        if c.get("type") not in ("bay", "erker", "oriel"):
            continue
        v = V.get(c.get("volume"))
        if not v:
            continue
        side = c.get("side", "S")
        L = side_length(side, *v["size"])
        u = L / 2 if c.get("u") is None else float(c["u"])
        w = float(_P(c, "width") or 2.0)
        z0 = float(c.get("z0", 0.0) or 0.0)
        z1 = float(c.get("z1", z0 + 3.0))
        top = 0.0
        for d in _at(spec, v["id"], side, 0):
            if _door_like(d) and _overlap(_span(d), (u - w / 2 - 0.1, u + w / 2 + 0.1)) > 0.05 and float(d.get("door_type") != "french" or 1):
                top = max(top, float(d["sill"]) + float(d["height"]))
        if top <= 0 or z0 >= top + 0.3:
            continue
        for k in spec.get("components", []):       # entrance canopy and its height
            if k.get("type") == "canopy" and k.get("volume") == v["id"] and k.get("side") == side and abs(float(k.get("u", L / 2)) - u) < (w / 2 + 1.0):
                top = max(top, float(k.get("z", 2.5)) + 0.3)
        sh = _sh(spec, v)
        new0 = math.ceil(top / sh) * sh + 0.1
        if z1 - new0 < 1.3:
            spec["components"].remove(c)
            notes.append(f"Erker {v['id']}-{side} entfernt (stand vor der Haustür)")
        else:
            c["z0"] = round(new0, 2)
            notes.append(f"Erker {v['id']}-{side}: über die Haustür auf {new0:.1f} m angehoben")


def resolve(spec: dict, notes: list[str]) -> None:
    _bay_windows(spec, notes)
    _bays_clear_entrance(spec, notes)
    _downpipes(spec, notes)
    _clip_openings_for_parts(spec, notes)
    _resolve_openings(spec, notes)
    _move_parts(spec, notes)
    _symmetrize_lamps(spec, notes)
    _carport_parking(spec, notes)
    _entrance_clear(spec, notes)
    _clip_roofing_parts(spec, notes)


def normalize(spec: dict) -> dict:
    """expand compact notation, then complete logical gaps (what every consumer should read)."""
    from .expand import expand_spec
    return complete(expand_spec(spec))[0]
