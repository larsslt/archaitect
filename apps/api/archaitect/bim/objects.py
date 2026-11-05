"""Individually selectable, movable and deletable objects of a design: buildings (connected volumes), pool/paving/path/hedge/tree entries of
``site`` and garden components with a fixed position. Ids are stable within one version: ``bld:<first volume>``, ``site.<key>.<i>``, ``comp.<i>``.

Pure functions on the spec dict (no IFC, no I/O); the spec frame is the house frame, ``dx``/``dy`` are spec-frame metres.
"""
from __future__ import annotations

import copy
import re

from shapely.geometry import Point, box
from shapely.ops import unary_union

from .terrain import _rect

SITE_KEYS = ("pools", "paving", "paths", "hedges", "trees")
SITE_LABEL = {"pools": "Pool", "paving": "Belag", "paths": "Weg", "hedges": "Hecke", "trees": "Baum"}
from .ifc_garden2 import TYPES as G2_TYPES, LABEL as G2_LABEL, OBJECTS as G2_OBJECTS

COMP_BOX = ("pool", "pond", "sauna_hut", "flowerbed", "parking", "terrace", "carport", "ramp", "garden_set", "bench") + tuple(G2_TYPES)
COMP_POINT = ("tree", "shrub", "garden_light")
COMP_LABEL = {"pool": "Pool", "pond": "Teich", "sauna_hut": "Saunahütte", "flowerbed": "Beet", "parking": "Stellplatz", "terrace": "Terrasse", "carport": "Carport", "ramp": "Rampe",
              "garden_set": "Sitzgruppe", "bench": "Bank", "tree": "Baum", "shrub": "Strauch", "garden_light": "Gartenleuchte", **G2_LABEL}
MIN_OVERLAP_M2 = 0.05


# Platzierbare Bibliotheksobjekte: id -> (Kategorie, Bauteiltyp, Parameter-Abweichungen, Anzeigename). Der Typ steht im Katalog (bim/catalog.py).
LIBRARY_OBJECTS: dict[str, tuple[str, str, dict, str]] = {
    "sauna_hut": ("Nebengebäude", "sauna_hut", {}, "Saunahaus"),
    "parking_2": ("Nebengebäude", "parking", {"width": 5.0, "depth": 5.0, "spaces": 2}, "Stellplatz (2)"),
    "parking_4": ("Nebengebäude", "parking", {"width": 10.0, "depth": 5.0, "spaces": 4}, "Stellplätze (4)"),
    "pool": ("Wasser & Pool", "pool", {}, "Pool"),
    "pool_small": ("Wasser & Pool", "pool", {"width": 6.0, "depth": 3.0, "deep": 1.2}, "Kleiner Pool"),
    "pond": ("Wasser & Pool", "pond", {}, "Teich"),
    "pond_small": ("Wasser & Pool", "pond", {"width": 5.0, "depth": 3.5, "deep": 0.6}, "Kleiner Teich"),
    "tree": ("Pflanzen", "tree", {}, "Laubbaum"),
    "tree_small": ("Pflanzen", "tree", {"height": 5.0, "crown_radius": 1.9}, "Obstbaum"),
    "conifer": ("Pflanzen", "tree", {"kind": "conifer", "height": 12.0, "crown_radius": 2.4}, "Nadelbaum"),
    "shrub": ("Pflanzen", "shrub", {}, "Strauch"),
    "shrub_pot": ("Pflanzen", "shrub", {"pot": True, "radius": 0.55}, "Kübelpflanze"),
    "flowerbed": ("Pflanzen", "flowerbed", {}, "Blumenbeet"),
    "flowerbed_long": ("Pflanzen", "flowerbed", {"width": 5.0, "depth": 1.2}, "Langes Beet"),
    "bench": ("Möbel & Licht", "bench", {}, "Gartenbank"),
    "bench_long": ("Möbel & Licht", "bench", {"length": 2.4}, "Lange Bank"),
    "garden_set": ("Möbel & Licht", "garden_set", {}, "Sitzgruppe"),
    "garden_light": ("Möbel & Licht", "garden_light", {"height": 3.0}, "Gartenleuchte"),
    "garden_light_low": ("Möbel & Licht", "garden_light", {"height": 0.9}, "Pollerleuchte"),
    "tree_large": ("Pflanzen", "tree", {"height": 16.0, "crown_radius": 5.0}, "Großbaum"),
    "tree_slim": ("Pflanzen", "tree", {"height": 8.0, "crown_radius": 1.4}, "Säulenbaum"),
    "tree_young": ("Pflanzen", "tree", {"height": 4.0, "crown_radius": 1.3}, "Jungbaum"),
    "conifer_small": ("Pflanzen", "tree", {"kind": "conifer", "height": 5.0, "crown_radius": 1.3}, "Zierkonifere"),
    "conifer_tall": ("Pflanzen", "tree", {"kind": "conifer", "height": 18.0, "crown_radius": 3.2}, "Hohe Fichte"),
    "shrub_large": ("Pflanzen", "shrub", {"radius": 1.2, "height": 1.6}, "Großstrauch"),
    "shrub_pot_large": ("Pflanzen", "shrub", {"pot": True, "radius": 0.8}, "Großer Kübel"),
    "flowerbed_square": ("Pflanzen", "flowerbed", {"width": 2.2, "depth": 2.2}, "Quadratisches Beet"),
    "bench_short": ("Möbel & Licht", "bench", {"length": 1.2}, "Kleine Bank"),
    "bench_light": ("Möbel & Licht", "bench", {"length": 2.0, "material": "wood_thermo", "frame_material": "alu_white"}, "Bank hell"),
    "garden_set_white": ("Möbel & Licht", "garden_set", {"material": "paint_white", "frame_material": "alu_white", "parasol_material": "fabric_grey"}, "Sitzgruppe weiß"),
    "garden_set_open": ("Möbel & Licht", "garden_set", {"parasol": False, "material": "wood_thermo"}, "Sitzgruppe ohne Schirm"),
    "garden_light_post": ("Möbel & Licht", "garden_light", {"kind": "post", "height": 4.0}, "Lichtmast"),
    "garden_light_row": ("Möbel & Licht", "garden_light", {"count": 4, "pitch": 2.5}, "Pollerreihe (4)"),
    "parking_1": ("Nebengebäude", "parking", {"width": 2.6, "depth": 5.0, "spaces": 1}, "Stellplatz (1)"),
    **G2_OBJECTS,
}


SAUNA_PORCH = 1.5
TURN = ("S", "E", "N", "W")          # counter-clockwise seen from above


def box_dims(c: dict) -> tuple[float, float]:
    """Footprint (dx, dy) of a box-like component; the sauna hut includes its porch and swaps with its facing."""
    if c.get("type") == "sauna_hut":
        w, d = float(c.get("width", 3.8)), float(c.get("depth", 3.0)) + SAUNA_PORCH
        return (d, w) if c.get("facing", "S") in ("E", "W") else (w, d)
    return float(c.get("width", 3.0)), float(c.get("depth", 3.0))


def rotate(spec: dict, oid: str, quarters: int) -> dict:
    """Turn a sauna hut by 90 degree steps around its footprint centre (changes `facing`); refuses overlaps."""
    s = copy.deepcopy(spec)
    if not oid.startswith("comp."):
        raise ValueError("Dieses Objekt lässt sich nicht einzeln drehen.")
    c = s["components"][int(oid.split(".")[1])]
    if c.get("type") != "sauna_hut":
        raise ValueError(f"„{COMP_LABEL.get(c.get('type'), c.get('type'))}“ lässt sich nicht einzeln drehen.")
    w0, d0 = box_dims(c)
    cx, cy = c["x"] + w0 / 2, c["y"] + d0 / 2
    c["facing"] = TURN[(TURN.index(c.get("facing", "S")) + int(quarters)) % 4]
    w1, d1 = box_dims(c)
    c["x"], c["y"] = round(cx - w1 / 2, 3), round(cy - d1 / 2, 3)
    me = next((o for o in objects(s) if o["id"] == oid), None)
    for o in objects(s):
        if o["id"] != oid and me and me["poly"].intersection(o["poly"]).area > MIN_OVERLAP_M2 and not _benign(me, o):
            raise ValueError(f"Gedreht würde „{me['label']}“ in „{o['label']}“ stehen. Bitte erst „{o['label']}“ verschieben.")
    return s


def _vpoly(v):
    return _rect(v["origin"], v["size"], float(v.get("rotation_deg", 0.0)))


def building_clusters(spec: dict) -> list[list[dict]]:
    """Volumes whose footprints touch or overlap form one building (stacked or attached volumes move together), unless one was set apart ('building' key)."""
    vols = list(spec.get("volumes", []))
    polys = [_vpoly(v).buffer(0.06) for v in vols]
    parent = list(range(len(vols)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(vols)):
        for j in range(i + 1, len(vols)):
            if polys[i].intersects(polys[j]) and vols[i].get("building") == vols[j].get("building"):
                parent[find(i)] = find(j)
    groups: dict[int, list[dict]] = {}
    for i, v in enumerate(vols):
        groups.setdefault(find(i), []).append(v)
    return sorted(groups.values(), key=lambda g: min(str(v["id"]) for v in g))


def _site_poly(key, it):
    if key == "trees":
        x, y = it.get("position") or it.get("origin") or (it.get("x", 0), it.get("y", 0))
        return Point(x, y).buffer(max(0.4, float(it.get("crown_radius", 1.5)) * 0.5))
    return _rect(it["origin"], it["size"])


def objects(spec: dict) -> list[dict]:
    out = []
    for g in building_clusters(spec):
        poly = unary_union([_vpoly(v) for v in g])
        n = len(out)
        out.append({"id": f"bld:{min(str(v['id']) for v in g)}", "kind": "house", "label": "Haus" if n == 0 else f"Gebäude {n + 1}",
                    "poly": poly, "volumes": [v["id"] for v in g]})
    site = spec.get("site") or {}
    for key in SITE_KEYS:
        for i, it in enumerate(site.get(key, [])):
            try:
                out.append({"id": f"site.{key}.{i}", "kind": key, "label": it.get("name") or SITE_LABEL[key], "poly": _site_poly(key, it)})
            except (KeyError, TypeError, ValueError):
                continue
    for i, c in enumerate(spec.get("components", [])):
        t, x, y = c.get("type"), c.get("x"), c.get("y")
        if x is None or y is None:
            continue
        if t in COMP_BOX:
            w, d = box_dims(c)
            poly = box(x, y, x + w, y + d)
        elif t in COMP_POINT:
            poly = Point(x, y).buffer(0.5)
        else:
            continue
        out.append({"id": f"comp.{i}", "kind": t, "label": COMP_LABEL.get(t, t), "poly": poly})
    return out


def public(spec: dict) -> list[dict]:
    return [{"id": o["id"], "kind": o["kind"], "label": o["label"], "bounds": [round(b, 2) for b in o["poly"].bounds]} for o in objects(spec)]


def object_of_element(name: str, spec: dict, default: str | None = None) -> str | None:
    """Fallback for IFC elements without an explicit tag: match volume ids in the element name, else the first building."""
    objs = objects(spec)
    houses = [o for o in objs if o["kind"] == "house"]
    for o in houses:
        for vid in o["volumes"]:
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(str(vid))}(?![A-Za-z0-9])", name or ""):
                return o["id"]
    return default or (houses[0]["id"] if houses else None)


def move(spec: dict, oid: str, dx: float, dy: float) -> dict:
    """Return a moved copy; ValueError (German message) if the object does not exist or would overlap another object."""
    s = copy.deepcopy(spec)
    objs = {o["id"]: o for o in objects(s)}
    if oid not in objs:
        raise ValueError("Objekt nicht gefunden.")
    if oid.startswith("bld:"):
        ids = set(objs[oid]["volumes"])
        for v in s["volumes"]:
            if v["id"] in ids:
                v["origin"] = [round(v["origin"][0] + dx, 3), round(v["origin"][1] + dy, 3)]
        for c in s.get("components", []):       # building-bound components with absolute coordinates
            if c.get("volume") in ids:
                for kx, ky in (("x0", "y0"), ("x1", "y1")):
                    if c.get(kx) is not None and c.get(ky) is not None:
                        c[kx], c[ky] = round(c[kx] + dx, 3), round(c[ky] + dy, 3)
    elif oid.startswith("site."):
        _, key, i = oid.split(".")
        it = s["site"][key][int(i)]
        for k in ("origin", "position"):
            if k in it:
                it[k] = [round(it[k][0] + dx, 3), round(it[k][1] + dy, 3)]
                break
        else:
            it["x"], it["y"] = round(it.get("x", 0) + dx, 3), round(it.get("y", 0) + dy, 3)
    else:
        c = s["components"][int(oid.split(".")[1])]
        c["x"], c["y"] = round(c["x"] + dx, 3), round(c["y"] + dy, 3)
    new = {o["id"]: o for o in objects(s)}
    if oid.startswith("bld:"):          # the cluster id may change when the building touches another one: compare volumes, not ids
        mine = set(objs[oid]["volumes"])
        me = {"kind": "house", "label": objs[oid]["label"], "poly": unary_union([_vpoly(v) for v in s["volumes"] if v["id"] in mine])}
        others = [{"kind": "house", "label": f"Gebäude {v['id']}", "poly": _vpoly(v)} for v in s["volumes"] if v["id"] not in mine]
        others += [o for o in new.values() if o["kind"] != "house"]
    else:
        me = new.get(oid)
        if me is None:
            raise ValueError("Objekt nicht gefunden.")
        others = [o for k, o in new.items() if k != oid]
    for o in others:
        if me["poly"].intersection(o["poly"]).area > MIN_OVERLAP_M2 and not _benign(me, o):
            raise ValueError(f"„{me['label']}“ würde in „{o['label']}“ stehen. Bitte erst „{o['label']}“ verschieben oder löschen.")
    return s


def _benign(a: dict, b: dict) -> bool:
    """Paving/paths may lie next to or under other things (terraces, entrances); everything else must not overlap."""
    return a["kind"] in ("paving", "paths") or b["kind"] in ("paving", "paths")


def delete(spec: dict, oid: str) -> dict:
    s = copy.deepcopy(spec)
    objs = {o["id"]: o for o in objects(s)}
    if oid not in objs:
        raise ValueError("Objekt nicht gefunden.")
    if oid.startswith("bld:"):
        ids = set(objs[oid]["volumes"])
        s["volumes"] = [v for v in s["volumes"] if v["id"] not in ids]
        s["openings"] = [o for o in s.get("openings", []) if o.get("volume") not in ids]
        s["balconies"] = [b for b in s.get("balconies", []) if b.get("volume") not in ids]
        s["components"] = [c for c in s.get("components", []) if c.get("volume") not in ids]
    elif oid.startswith("site."):
        _, key, i = oid.split(".")
        del s["site"][key][int(i)]
    else:
        del s["components"][int(oid.split(".")[1])]
    return s


def delete_volume(spec: dict, vid: str) -> dict:
    """Remove ONE volume (e.g. a roof block or an annex) with its openings, balconies and components. The last volume stays: delete the building instead."""
    s = copy.deepcopy(spec)
    if vid not in {str(v["id"]) for v in s.get("volumes", [])}:
        raise ValueError("Bauteil nicht gefunden.")
    if len(s["volumes"]) <= 1:
        raise ValueError("Das ist das einzige Bauteil des Gebäudes. Lösche stattdessen das ganze Gebäude.")
    s["volumes"] = [v for v in s["volumes"] if str(v["id"]) != vid]
    s["openings"] = [o for o in s.get("openings", []) if str(o.get("volume")) != vid]
    s["balconies"] = [b for b in s.get("balconies", []) if str(b.get("volume")) != vid]
    s["components"] = [c for c in s.get("components", []) if str(c.get("volume")) != vid]
    return s


def detach_volume(spec: dict, vid: str) -> dict:
    """Make a volume its own movable building (e.g. a garage standing against the house)."""
    s = copy.deepcopy(spec)
    for v in s.get("volumes", []):
        if str(v["id"]) == vid:
            if not any(c is not v and c.get("building") == v.get("building") for c in s["volumes"]):
                raise ValueError("Das Bauteil ist bereits ein eigenes Gebäude.")
            v["building"] = f"sep_{vid}"
            return s
    raise ValueError("Bauteil nicht gefunden.")
