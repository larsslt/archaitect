"""Gemessene Gebäudehöhen aus dem amtlichen LoD2-Modell Hessen (INSPIRE bu-core3d, HVBG, DL-DE Zero 2.0).

ALKIS nennt Geschosszahlen oft nicht. Das LoD2-Modell kennt dagegen für fast jedes Gebäude die gemessene Höhe über Grund
(heightAboveGround, Status "measured"). Dieses Modul holt die Gebäude um das Grundstück, liest Höhe und Grundriss
(terrainIntersection) und ordnet sie den ALKIS-Gebäuden zu. Nichts hier ist Baurecht: die Höhe beschreibt den Bestand
(Basis LOD2_MEASURED) und geht nur in den Richtwert-Rahmen der Umgebung ein.
Ausfall des Dienstes -> leere Liste, nie eine Exception."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from shapely.geometry import MultiPoint, Polygon

SOURCE_ID = "lod2"
HEIGHT_BASIS = "LOD2_MEASURED"
STOREY_HEIGHT_M = 2.9
ROOF_ALLOWANCE_M = 1.5
MAX_PLAUSIBLE_M = 120.0
MIN_PLAUSIBLE_M = 1.0


def _name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _pairs(text: str) -> list[tuple[float, float]]:
    nums = [float(t) for t in (text or "").split()]
    # EPSG:4326 (urn axis order): lat lon -> return (lon, lat)
    return [(nums[i + 1], nums[i]) for i in range(0, len(nums) - 1, 2)]


def _heights(el: ET.Element) -> list[float]:
    out = []
    for h in el.iter():
        if _name(h.tag) == "HeightAboveGround":
            for v in h:
                if _name(v.tag) == "value":
                    try:
                        out.append(float((v.text or "").strip()))
                    except ValueError:
                        pass
    return out


def parse(xml: bytes | str) -> list[dict[str, Any]]:
    """[{id, height_m, hull}] per Building; height = highest part, hull = convex hull of the terrain intersection (lon/lat)."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for b in root.iter():
        if _name(b.tag) != "Building":
            continue
        hs = [h for h in _heights(b) if MIN_PLAUSIBLE_M <= h <= MAX_PLAUSIBLE_M]
        pts: list[tuple[float, float]] = []
        for el in b.iter():
            if _name(el.tag) == "posList":
                pts.extend(_pairs(el.text or ""))
        if not hs or len(pts) < 3:
            continue
        hull = MultiPoint(pts).convex_hull
        if not isinstance(hull, Polygon) or hull.area <= 0:
            continue
        gid = next((v for k, v in b.attrib.items() if k.endswith("}id") or k == "id"), None)
        out.append({"id": gid, "height_m": round(max(hs), 1), "hull": hull})
    return out


def fetch(fetcher, src, lat: float, lon: float, half_deg: float) -> list[dict[str, Any]]:
    """Best effort: any failure yields []."""
    from . import wfs
    try:
        res = fetcher.get(src.id, src.url, wfs.request_params(src.types[0], lat, lon, half_deg, src.count), src.ttl_s, src.timeout_s, wfs.usable)
        return parse(res.body) if res.body else []
    except Exception:  # noqa: BLE001 - enrichment must never break the site pack
        return []


def match(buildings: list[dict[str, Any]], lod: list[dict[str, Any]], to_local) -> dict[str, float]:
    """ALKIS building id -> measured height. A LoD2 building belongs to the ALKIS footprint it overlaps most (>= 50 % of the smaller area).
    to_local maps a lon/lat shapely geometry into the local metres of the building rings."""
    polys = {b["id"]: Polygon(b["ring"]) for b in buildings if b.get("ring") and len(b["ring"]) >= 3}
    result: dict[str, list[float]] = {}
    for l in lod:
        g = to_local(l["hull"])
        best, best_ov = None, 0.0
        for bid, p in polys.items():
            if not p.is_valid or not g.intersects(p):
                continue
            ov = g.intersection(p).area / max(min(g.area, p.area), 0.1)
            if ov > best_ov:
                best, best_ov = bid, ov
        if best is not None and best_ov >= 0.5:
            result.setdefault(best, []).append(l["height_m"])
    return {k: max(v) for k, v in result.items()}


def storeys_from_height(h: float) -> int:
    return max(1, round((h - ROOF_ALLOWANCE_M) / STOREY_HEIGHT_M))
