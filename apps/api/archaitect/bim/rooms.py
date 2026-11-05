"""Rooms: data model helpers, automatic detection of windows/doors/stairs, plausibility hints, partitions.

A room is an axis-aligned rectangle on one level: {"id","name","function","level","rect":[x0,y0,x1,y1]}.
Windows, doors and the stair are NOT entered by hand: they are found from the spec geometry
(openings on the facade, glass faces of curtain walls) by looking at which room edge touches them.
All hints are heuristics for the sketch phase, not a building-code check.
"""
from __future__ import annotations

from shapely.geometry import LineString, box
from shapely.ops import unary_union

from .geom import facade_xy, side_length

# function -> (label, plan colour, counts as Aufenthaltsraum)
FUNCTIONS: dict[str, tuple[str, str, bool]] = {
    "wohnen": ("Wohnen", "#f6e7c1", True),
    "essen": ("Essen", "#f9d9a8", True),
    "kueche": ("Küche", "#f7c9a0", True),
    "schlafen": ("Schlafen", "#cfdcf5", True),
    "kind": ("Kind", "#d3e8c0", True),
    "arbeiten": ("Arbeiten", "#e1d2f0", True),
    "atelier": ("Atelier", "#ead3f0", True),
    "bad": ("Bad", "#b9e2ea", False),
    "wc": ("WC", "#c9e8ee", False),
    "ankleide": ("Ankleide", "#e9e1d3", False),
    "hwr": ("Hauswirtschaft", "#dcdcdc", False),
    "technik": ("Technik", "#cfcfcf", False),
    "abstell": ("Abstellraum", "#d9d9d9", False),
    "sauna": ("Sauna", "#ecc9a6", False),
    "flur": ("Flur / Diele", "#efefef", False),
    "treppe": ("Treppenhaus", "#e2e2e2", False),
    "sonstiges": ("Sonstiges", "#f2f2f2", False),
}
LIGHT_RATIO = 1 / 8     # HBO § 50 Abs. 2: Rohbaumaß der Fensteröffnungen >= 1/8 der Netto-Raumfläche
TOL_EDGE = 0.2          # room edge may be this far from the inner wall face
SNAP = 0.01


def function_names() -> list[str]:
    return list(FUNCTIONS)


def is_living(function: str) -> bool:
    return FUNCTIONS.get(function, ("", "", False))[2]


def levels(spec: dict) -> list[dict]:
    return sorted(spec.get("levels", []), key=lambda l: l["elevation"])


def level_elev(spec: dict, name: str) -> float:
    for l in spec.get("levels", []):
        if l["name"] == name:
            return float(l["elevation"])
    raise KeyError(name)


def level_height(spec: dict, name: str) -> float:
    ls = levels(spec)
    for i, l in enumerate(ls):
        if l["name"] == name:
            return float(ls[i + 1]["elevation"] - l["elevation"]) if i + 1 < len(ls) else float(spec.get("storey_height", 3.0))
    return float(spec.get("storey_height", 3.0))


def footprints(spec: dict, level: str) -> list[dict]:
    """Inner floor rectangles available for rooms at this level (volumes shrunk by wall thickness; stair tower)."""
    elev = level_elev(spec, level)
    sh = float(spec.get("storey_height", 3.0))
    wt = float(spec.get("defaults", {}).get("wall_thickness", 0.36))
    out = []
    for v in spec.get("volumes", []):
        vh = float(v.get("storey_height", sh))
        t = float(v.get("wall_thickness", wt))
        for k in range(int(v.get("storeys", 1))):
            if abs(float(v.get("base_z", 0.0)) + k * vh - elev) < 0.2:
                (ox, oy), (W, D) = v["origin"], v["size"]
                out.append({"id": v["id"], "name": v.get("name", v["id"]), "kind": "volume",
                            "rect": [round(ox + t, 3), round(oy + t, 3), round(ox + W - t, 3), round(oy + D - t, 3)]})
    for cw in spec.get("curtain_walls", []):
        (ox, oy), (W, D) = cw["origin"], cw["size"]
        if float(cw["top_z"]) > elev + 1.0:
            out.append({"id": cw.get("id", "T"), "name": cw.get("name", "Glasturm"), "kind": "tower",
                        "rect": [round(ox + 0.12, 3), round(oy + 0.12, 3), round(ox + W - 0.12, 3), round(oy + D - 0.12, 3)]})
    return out


def _segments(spec: dict, level: str, internal: bool = False) -> list[dict]:
    """Facade openings (windows/doors) and curtain-wall glass at this level as world-space segments."""
    elev, lh = level_elev(spec, level), level_height(spec, level)
    sh = float(spec.get("storey_height", 3.0))
    vols = {v["id"]: v for v in spec.get("volumes", [])}
    segs = []
    for o in spec.get("openings", []):
        v = vols.get(o["volume"])
        if not v or (o.get("internal") and not internal):
            continue
        vh = float(v.get("storey_height", sh))
        if abs(float(v.get("base_z", 0.0)) + int(o["storey"]) * vh - elev) > 0.2:
            continue
        (ox, oy), (W, D) = v["origin"], v["size"]
        u0, u1 = float(o["offset"]), float(o["offset"]) + float(o["width"])
        p0, p1 = facade_xy(o["side"], ox, oy, W, D, u0, 0.0), facade_xy(o["side"], ox, oy, W, D, u1, 0.0)
        segs.append({"kind": o["kind"], "side": o["side"], "p": (p0, p1), "width": float(o["width"]),
                     "height": float(o["height"]), "src": "Öffnung"})
    for cw in spec.get("curtain_walls", []):
        (ox, oy), (W, D) = cw["origin"], cw["size"]
        for f in cw.get("faces", []):
            L = side_length(f["side"], W, D)
            a, b = f.get("span", (0.0, L))
            z0, z1 = max(float(f["z0"]), elev), min(float(f["z1"]), elev + lh)
            if z1 - z0 < 0.3:
                continue
            p0, p1 = facade_xy(f["side"], ox, oy, W, D, a, 0.0), facade_xy(f["side"], ox, oy, W, D, b, 0.0)
            segs.append({"kind": "window", "side": f["side"], "p": (p0, p1), "width": float(b - a),
                         "height": z1 - z0, "src": "Glaswand"})
    return segs


def _inward_edge(side: str, r: list[float]) -> float:
    return {"S": r[1], "N": r[3], "E": r[2], "W": r[0]}[side]


def _seg_on_room(s: dict, r: list[float]) -> float:
    """Length of the segment lying on the room's exterior-facing edge (0 if it does not touch)."""
    (x0, y0), (x1, y1) = s["p"]
    if abs(y0 - y1) < 1e-6:                      # S/N facade (horizontal line)
        if s["side"] not in ("S", "N") or abs(_inward_edge(s["side"], r) - y0) > 0.6:
            return 0.0
        return max(0.0, min(max(x0, x1), r[2]) - max(min(x0, x1), r[0]))
    if s["side"] not in ("E", "W") or abs(_inward_edge(s["side"], r) - x0) > 0.6:
        return 0.0
    return max(0.0, min(max(y0, y1), r[3]) - max(min(y0, y1), r[1]))


def analyze(spec: dict) -> list[dict]:
    """Per room: area, detected windows/doors/stair, hints."""
    rooms = spec.get("rooms", [])
    out = []
    by_level: dict[str, list[dict]] = {}
    for r in rooms:
        by_level.setdefault(r["level"], []).append(r)
    for lvl, rs in by_level.items():
        try:
            fps, segs = footprints(spec, lvl), _segments(spec, lvl)
        except KeyError:
            fps, segs = [], []
        free = unary_union([box(*f["rect"]).buffer(0.06) for f in fps]) if fps else None
        towers = [box(*f["rect"]) for f in fps if f["kind"] == "tower"]
        for r in rs:
            x0, y0, x1, y1 = r["rect"]
            rb = box(x0, y0, x1, y1)
            area = rb.area
            wins, doors = [], []
            for s in segs:
                share = _seg_on_room(s, r["rect"])
                if share <= 0.05:
                    continue
                item = {"kind": s["kind"], "side": s["side"], "width": round(min(share, s["width"]), 2),
                        "height": round(s["height"], 2), "area": round(min(share, s["width"]) * s["height"], 2),
                        "src": s["src"]}
                (doors if s["kind"] == "door" else wins).append(item)
            glass = round(sum(w["area"] for w in wins) + sum(d["area"] for d in doors if d["height"] > 1.8 and False), 2)
            hints = []
            if free is not None and not rb.within(free):
                hints.append("ragt über die nutzbare Gebäudefläche hinaus")
            for o in rs:
                if o["id"] < r["id"] and rb.intersection(box(*o["rect"])).area > 0.05:
                    hints.append(f"überlappt mit „{o['name']}“")
            if is_living(r["function"]):
                if not wins:
                    hints.append("Aufenthaltsraum ohne Fenster (HBO § 50: Belichtung nötig)")
                elif glass < LIGHT_RATIO * area:
                    hints.append(f"Fensterfläche {glass:.1f} m² unter 1/8 der Raumfläche ({area / 8:.1f} m²), vgl. HBO § 50")
            out.append({"id": r["id"], "name": r["name"], "function": r["function"], "level": lvl,
                        "rect": r["rect"], "area": round(area, 2), "windows": wins, "doors": doors,
                        "glass_area": glass, "stair": any(rb.intersection(t).area > 1.0 for t in towers),
                        "hints": hints})
    return out


def free_area_report(spec: dict, level: str) -> dict:
    """How much of the usable floor area at this level is covered by rooms."""
    fps = footprints(spec, level)
    if not fps:
        return {"total": 0.0, "covered": 0.0}
    total = unary_union([box(*f["rect"]) for f in fps])
    rs = [box(*r["rect"]) for r in spec.get("rooms", []) if r["level"] == level]
    cov = unary_union(rs).intersection(total).area if rs else 0.0
    return {"total": round(total.area, 2), "covered": round(cov, 2)}


def next_id(spec: dict) -> str:
    used = {r["id"] for r in spec.get("rooms", [])}
    n = 1
    while f"r{n:03d}" in used:
        n += 1
    return f"r{n:03d}"


def snap_rect(rect, ndigits=2) -> list[float]:
    x0, y0, x1, y1 = [round(round(float(c) / SNAP) * SNAP, ndigits) for c in rect]
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


# --- limits used by the layout checks and the prompt (metres / square metres)
MIN_CORRIDOR = 1.4     # clear width so that a 0.9 m door can swing open and two people pass
MIN_BATH = 1.6
MIN_ROOM = 2.0
MAX_AREA = {"wohnen": 70, "essen": 32, "kueche": 24, "schlafen": 30, "kind": 20, "arbeiten": 24, "atelier": 40,
            "bad": 16, "wc": 5, "ankleide": 14, "hwr": 16, "technik": 14, "abstell": 8, "sauna": 12, "flur": 25}
MIN_AREA = {"bad": 4.0, "wc": 1.8, "schlafen": 9.0, "kind": 8.0}
CIRC = ("flur", "treppe")
OPEN_PLAN = ("wohnen", "essen", "kueche")
DOOR_W = 0.9
NARROW_DOOR = {"bad": 0.8, "wc": 0.8, "abstell": 0.8, "technik": 0.8, "hwr": 0.8, "ankleide": 0.8, "sauna": 0.8}


def shared_edge(a: list, b: list, tol: float = 0.03):
    """Common edge of two rectangles: ('h'|'v', fixed coordinate, lo, hi) or None. 'h' runs along x."""
    if abs(a[3] - b[1]) < tol or abs(b[3] - a[1]) < tol:
        lo, hi = max(a[0], b[0]), min(a[2], b[2])
        if hi - lo > 0.05:
            return ("h", a[3] if abs(a[3] - b[1]) < tol else a[1], lo, hi)
    if abs(a[2] - b[0]) < tol or abs(b[2] - a[0]) < tol:
        lo, hi = max(a[1], b[1]), min(a[3], b[3])
        if hi - lo > 0.05:
            return ("v", a[2] if abs(a[2] - b[0]) < tol else a[0], lo, hi)
    return None


def door_plan(spec: dict, level: str) -> list[dict]:
    """Which room boundaries get a door (or an open passage): every room reaches a corridor/stair/neighbour,
    open living areas are joined by wide openings, and the whole level is connected where the geometry allows."""
    rs = [r for r in spec.get("rooms", []) if r["level"] == level]
    edges = []
    for i, a in enumerate(rs):
        for b in rs[i + 1:]:
            e = shared_edge(a["rect"], b["rect"])
            if e:
                edges.append({"a": a, "b": b, "axis": e[0], "fixed": e[1], "lo": e[2], "hi": e[3], "len": e[3] - e[2]})
    chosen: dict[int, dict] = {}

    def add(i, width, leaf=True):
        e = edges[i]
        if i not in chosen and e["len"] >= width + 0.3:
            chosen[i] = {"width": width, "leaf": leaf}

    for i, e in enumerate(edges):
        fa, fb = e["a"]["function"], e["b"]["function"]
        if fa in OPEN_PLAN and fb in OPEN_PLAN and e["len"] >= 1.6:
            add(i, round(min(2.0, e["len"] - 0.4), 2), leaf=False)
        elif fa == "flur" and fb == "flur":
            add(i, round(min(1.4, e["len"] - 0.3), 2), leaf=False)
        elif {fa, fb} == {"flur", "treppe"}:
            add(i, 1.0)
    prio = lambda e, r: (0 if e["b" if e["a"] is r else "a"]["function"] == "flur" else
                         1 if e["b" if e["a"] is r else "a"]["function"] == "treppe" else 2, -e["len"])
    for r in rs:
        if r["function"] in CIRC:
            continue
        mine = [i for i, e in enumerate(edges) if r in (e["a"], e["b"])]
        if any(i in chosen for i in mine):
            continue
        for i in sorted(mine, key=lambda i: prio(edges[i], r)):
            w = NARROW_DOOR.get(r["function"], DOOR_W)
            if edges[i]["len"] >= w + 0.3:
                add(i, w)
                break
    # connect the remaining components, circulation first
    parent = {r["id"]: r["id"] for r in rs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in chosen:
        parent[find(edges[i]["a"]["id"])] = find(edges[i]["b"]["id"])
    for i in sorted(range(len(edges)), key=lambda i: (edges[i]["a"]["function"] not in CIRC and edges[i]["b"]["function"] not in CIRC,
                                                      -edges[i]["len"])):
        e = edges[i]
        if find(e["a"]["id"]) != find(e["b"]["id"]) and i not in chosen and e["len"] >= DOOR_W + 0.3:
            add(i, DOOR_W)
            parent[find(e["a"]["id"])] = find(e["b"]["id"])
    out = []
    for i, c in chosen.items():
        e = edges[i]
        w = c["width"]
        center = (e["lo"] + e["hi"]) / 2
        out.append({"axis": e["axis"], "fixed": round(e["fixed"], 3), "center": round(center, 3), "width": w,
                    "leaf": c["leaf"], "between": [e["a"]["name"], e["b"]["name"]]})
    return out


def _storey_of(spec: dict, v: dict, level: str) -> int:
    vh = float(v.get("storey_height", spec.get("storey_height", 3.0)))
    return int(round((level_elev(spec, level) - float(v.get("base_z", 0.0))) / vh))


def passage_openings(spec: dict, level: str, width: float = 1.0) -> list[dict]:
    """Doors through volume walls to a stair room (separate floor rectangle), e.g. from a corridor into the glass tower.
    Skipped where a glass face of the tower blocks the wall. One door per volume and stair room."""
    rs = [r for r in spec.get("rooms", []) if r["level"] == level]
    vols = spec.get("volumes", [])
    elev, lh = level_elev(spec, level), level_height(spec, level)
    rank = {"flur": 0, "wohnen": 1, "essen": 1, "kueche": 1, "arbeiten": 2, "atelier": 2}
    out = []
    for t in [r for r in rs if r["function"] == "treppe"]:
        tr = t["rect"]
        best = {}
        for a in rs:
            if a is t or a["function"] not in rank:
                continue
            ar = a["rect"]
            for side, gap, lo, hi, axis in (
                    ("W", ar[0] - tr[2], max(ar[1], tr[1]), min(ar[3], tr[3]), "y"),
                    ("E", tr[0] - ar[2], max(ar[1], tr[1]), min(ar[3], tr[3]), "y"),
                    ("S", ar[1] - tr[3], max(ar[0], tr[0]), min(ar[2], tr[2]), "x"),
                    ("N", tr[1] - ar[3], max(ar[0], tr[0]), min(ar[2], tr[2]), "x")):
                if not (0.05 < gap < 0.8) or hi - lo < width + 0.3:
                    continue
                cx, cy = (ar[0] + ar[2]) / 2, (ar[1] + ar[3]) / 2
                v = next((v for v in vols if v["origin"][0] <= cx <= v["origin"][0] + v["size"][0]
                          and v["origin"][1] <= cy <= v["origin"][1] + v["size"][1]), None)
                if not v:
                    continue
                opp = {"W": "E", "E": "W", "S": "N", "N": "S"}[side]
                blocked = []
                for cw in spec.get("curtain_walls", []):
                    (cx0, cy0), (cW, cD) = cw["origin"], cw["size"]
                    if not (cx0 - 0.1 <= (tr[0] + tr[2]) / 2 <= cx0 + cW + 0.1 and cy0 - 0.1 <= (tr[1] + tr[3]) / 2 <= cy0 + cD + 0.1):
                        continue
                    for f in cw.get("faces", []):
                        if f["side"] != opp:
                            continue
                        z0, z1 = max(float(f["z0"]), elev), min(float(f["z1"]), elev + lh)
                        if z1 - z0 < 0.3:
                            continue
                        a_, b_ = f.get("span", (0.0, side_length(opp, cW, cD)))
                        p0, p1 = facade_xy(opp, cx0, cy0, cW, cD, a_, 0.0), facade_xy(opp, cx0, cy0, cW, cD, b_, 0.0)
                        k = 1 if axis == "y" else 0
                        blocked.append((min(p0[k], p1[k]), max(p0[k], p1[k])))
                free, cur = [], lo
                for b0, b1 in sorted(blocked):
                    if b1 <= cur:
                        continue
                    if b0 > cur:
                        free.append((cur, min(b0, hi)))
                    cur = max(cur, b1)
                if cur < hi:
                    free.append((cur, hi))
                free = [f for f in free if f[1] - f[0] >= width + 0.3]
                if not free:
                    continue
                f0, f1 = max(free, key=lambda f: f[1] - f[0])
                c = (f0 + f1) / 2
                ox, oy = v["origin"]
                W, D = v["size"]
                u0 = {"S": c - width / 2 - ox, "N": ox + W - c - width / 2, "E": c - width / 2 - oy, "W": oy + D - c - width / 2}[side]
                cand = (rank[a["function"]], -(f1 - f0), {
                    "volume": v["id"], "side": side, "storey": _storey_of(spec, v, level), "offset": round(u0, 3),
                    "width": width, "height": 2.1, "sill": 0.0, "kind": "door", "internal": True, "panel": "walnut",
                    "note": f"Tür {a['name']} / {t['name']}"})
                if v["id"] not in best or cand[:2] < best[v["id"]][:2]:
                    best[v["id"]] = cand
        out.extend(c[2] for c in best.values())
    return out


# --- furniture suited to the room function: (name, length along the wall, depth, height, material)
FURN = {
    "schlafen": [("Bett", 1.8, 2.0, 0.5, "fabric_sand"), ("Kleiderschrank", 2.0, 0.6, 2.2, "walnut")],
    "kind": [("Bett", 0.9, 2.0, 0.45, "fabric_sand"), ("Schreibtisch", 1.4, 0.7, 0.75, "walnut")],
    "wohnen": [("Sofa", 2.4, 0.95, 0.42, "fabric_grey"), ("Sideboard", 1.8, 0.4, 0.8, "walnut")],
    "essen": [("Esstisch", 1.8, 0.9, 0.75, "walnut")],
    "kueche": [("Küchenzeile", 3.0, 0.6, 0.92, "interior_white")],
    "arbeiten": [("Schreibtisch", 1.6, 0.8, 0.75, "walnut"), ("Regal", 1.5, 0.35, 2.0, "walnut")],
    "atelier": [("Arbeitstisch", 2.4, 1.0, 0.8, "walnut"), ("Regal", 2.4, 0.4, 2.2, "walnut")],
    "bad": [("Waschtisch", 1.0, 0.5, 0.85, "interior_white"), ("Dusche", 0.9, 0.9, 0.06, "interior_white")],
    "ankleide": [("Kleiderregal", 1.8, 0.5, 2.2, "walnut")],
}
CENTER_ITEMS = {"Esstisch", "Arbeitstisch"}


def furnish(spec: dict, level: str) -> dict:
    """Place furniture that fits each room's function against walls, clear of doors, walls and other furniture.
    Replaces earlier automatically placed furniture of this level; hand-placed furniture stays and is respected."""
    elev = level_elev(spec, level)
    spec["furniture"] = [f for f in spec.get("furniture", []) if not (f.get("auto") == level)]
    rs = [r for r in spec.get("rooms", []) if r["level"] == level]
    blocked = []
    for d in door_plan(spec, level):
        c, w, f = d["center"], d["width"], d["fixed"]
        blocked.append(box(c - w / 2, f - w, c + w / 2, f + w) if d["axis"] == "h" else box(f - w, c - w / 2, f + w, c + w / 2))
    for s in _segments(spec, level, internal=True):
        if s["kind"] == "door":
            (xa, ya), (xb, yb) = s["p"]
            blocked.append(box(min(xa, xb), min(ya, yb), max(xa, xb), max(ya, yb)).buffer(1.0))
    for fu in spec.get("furniture", []):
        x, y, z = fu["origin"]
        if elev - 0.4 <= z < elev + level_height(spec, level) - 0.2:
            blocked.append(box(x, y, x + fu["size"][0], y + fu["size"][1]).buffer(0.1))
    placed, skipped = [], []
    for r in rs:
        x0, y0, x1, y1 = r["rect"]
        ix0, iy0, ix1, iy1 = x0 + 0.1, y0 + 0.1, x1 - 0.1, y1 - 0.1
        for name, L, Dp, H, mat in FURN.get(r["function"], []):
            cands = []
            if name in CENTER_ITEMS:
                for dx in (0, -0.4, 0.4):
                    for dy in (0, -0.4, 0.4):
                        cx, cy = (ix0 + ix1) / 2 + dx, (iy0 + iy1) / 2 + dy
                        for ww, dd in ((L, Dp), (Dp, L)):
                            cands.append((cx - ww / 2, cy - dd / 2, ww, dd))
            else:
                sides = sorted(("S", "N", "W", "E"), key=lambda s: -((ix1 - ix0) if s in "SN" else (iy1 - iy0)))
                for s in sides:
                    span0, span1 = (ix0, ix1) if s in "SN" else (iy0, iy1)
                    Le = min(L, span1 - span0 - 0.2)
                    if Le < 0.6 or Dp > min(ix1 - ix0, iy1 - iy0) - 0.9:
                        continue
                    mid = (span0 + span1) / 2
                    pos = sorted([span0 + Le / 2 + k * 0.1 for k in range(int((span1 - span0 - Le) / 0.1) + 1)],
                                 key=lambda c: abs(c - mid))
                    for c in pos:
                        if s == "S":
                            cands.append((c - Le / 2, iy0, Le, Dp))
                        elif s == "N":
                            cands.append((c - Le / 2, iy1 - Dp, Le, Dp))
                        elif s == "W":
                            cands.append((ix0, c - Le / 2, Dp, Le))
                        else:
                            cands.append((ix1 - Dp, c - Le / 2, Dp, Le))
            for (x, y, w, d) in cands:
                b = box(x, y, x + w, y + d)
                if x < ix0 - 1e-6 or y < iy0 - 1e-6 or x + w > ix1 + 1e-6 or y + d > iy1 + 1e-6:
                    continue
                if any(b.intersects(o) and b.intersection(o).area > 0.001 for o in blocked):
                    continue
                spec["furniture"].append({"name": f"{name} {r['name']}", "origin": [round(x, 3), round(y, 3), elev],
                                          "size": [round(w, 3), round(d, 3), H], "material": mat, "auto": level})
                blocked.append(b.buffer(0.25))
                placed.append(f"{name} {r['name']}")
                break
            else:
                skipped.append(f"{name} {r['name']}")
    return {"moebel_gesetzt": len(placed), "moebel_ohne_platz": skipped}


def clean_furniture(spec: dict, level: str, parts: list[dict], doors: list[dict]) -> list[str]:
    """Remove furniture on this level that stands in a wall, blocks a door, or sits in a room it does not belong in.
    Returns the removed names."""
    elev, top = level_elev(spec, level), level_elev(spec, level) + level_height(spec, level)
    rs = [r for r in spec.get("rooms", []) if r["level"] == level]
    bad_fn = {"flur", "treppe", "technik", "hwr", "abstell", "wc", "bad", "sauna"}
    walls = []
    for p in parts:
        (xa, ya), (xb, yb) = p["start"], p["end"]
        t = float(p.get("thickness", 0.12))
        walls.append(box(min(xa, xb) - t / 2 - 0.02, min(ya, yb) - t / 2 - 0.02, max(xa, xb) + t / 2 + 0.02, max(ya, yb) + t / 2 + 0.02))
    swing = []
    for d in doors:
        c, w, f = d["center"], d["width"], d["fixed"]
        swing.append(box(c - w / 2, f - w, c + w / 2, f + w) if d["axis"] == "h" else box(f - w, c - w / 2, f + w, c + w / 2))
    keep, removed = [], []
    for fu in spec.get("furniture", []):
        x, y, z = fu["origin"]
        w, d, h = fu["size"]
        if not (elev - 0.4 <= z < top - 0.2):
            keep.append(fu)
            continue
        fb = box(x, y, x + w, y + d)
        cx, cy = x + w / 2, y + d / 2
        room = next((r for r in rs if r["rect"][0] <= cx <= r["rect"][2] and r["rect"][1] <= cy <= r["rect"][3]), None)
        bad = (any(fb.intersects(wb) and fb.intersection(wb).area > 0.002 for wb in walls) or
               any(fb.intersects(sb) and fb.intersection(sb).area > 0.02 for sb in swing) or
               (room is not None and room["function"] in bad_fn and not fu.get("auto")))
        (removed if bad else keep).append(fu["name"] if bad else fu)
    spec["furniture"] = [f for f in keep if isinstance(f, dict)]
    return removed


def partitions_from_rooms(spec: dict, level: str, thickness: float = 0.12) -> list[dict]:
    """Interior walls along room boundaries (not along the outer wall), with door openings from door_plan()."""
    fps = footprints(spec, level)
    rs = [r for r in spec.get("rooms", []) if r["level"] == level]
    if not fps or not rs:
        return []
    outer = unary_union([box(*f["rect"]) for f in fps]).boundary.buffer(0.1)
    lines = []
    for r in rs:
        x0, y0, x1, y1 = r["rect"]
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            lines.append(LineString([a, b]))
    merged = unary_union(lines).difference(outer)
    parts = []
    for g in getattr(merged, "geoms", [merged]):
        if g.is_empty or g.length < 0.3:
            continue
        for seg in ([g] if g.geom_type == "LineString" else list(g.geoms)):
            (xa, ya), (xb, yb) = seg.coords[0], seg.coords[-1]
            if abs(xa - xb) > 1e-6 and abs(ya - yb) > 1e-6:
                continue
            parts.append({"name": f"Raumwand {level}", "start": [round(xa, 3), round(ya, 3)],
                          "end": [round(xb, 3), round(yb, 3)], "z": level_elev(spec, level), "thickness": thickness,
                          "height": level_height(spec, level) - float(spec.get("slab_thickness", 0.3))})
    for d in door_plan(spec, level):
        for p in parts:
            (xa, ya), (xb, yb) = p["start"], p["end"]
            horiz = abs(ya - yb) < 1e-6
            if horiz != (d["axis"] == "h") or abs((ya if horiz else xa) - d["fixed"]) > 0.03:
                continue
            lo, hi = (min(xa, xb), max(xa, xb)) if horiz else (min(ya, yb), max(ya, yb))
            a, b = d["center"] - d["width"] / 2, d["center"] + d["width"] / 2
            if a >= lo - 1e-3 and b <= hi + 1e-3:
                p.setdefault("doors", []).append({"offset": round(a - lo, 3), "width": d["width"], "height": 2.1,
                                                  "leaf": d["leaf"], "name": "Tür " + " / ".join(d["between"])})
                break
    return parts
