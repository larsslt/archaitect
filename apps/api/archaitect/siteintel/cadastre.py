"""ALKIS cadastral parcels for Hessen via the INSPIRE OGC-API (Geoportal Hessen), licence DL-DE Zero 2.0.

Source: INSPIRE-WFS HE Flurstücke/Grundstücke ALKIS, collection cp:CadastralParcel.
Observed behaviour (checked 2026-10-28 from a browser, not from this repo's CI):
- bbox is lon/lat; `limit` must be one of 1,5,10,20,50,100,200,500; coordinates are EPSG:4326.
- a tiny bbox can return several parcels (bbox *intersects*), so the point-in-polygon test is done here.
- geometries can be Polygon or MultiPolygon; `label` may be a number.
"""
from __future__ import annotations
import json
import re
import time
from datetime import datetime, timezone
from typing import Protocol
from shapely.geometry import Point, Polygon
from .fetch import Fetcher, HttpFetcher
from .models import DataStatus, ParcelInfo, SourceRef

ITEMS_URL = 'https://www.geoportal.hessen.de/spatial-objects/710/collections/cp:CadastralParcel/items'
SOURCE = SourceRef(id='alkis-inspire-he', name='ALKIS Flurstücke Hessen (INSPIRE, HLBG/HVBG)', licence='DL-DE Zero 2.0', url='https://www.geoportal.hessen.de/spatial-objects/710')

_REF = re.compile(r'^(?P<land>\d{2})(?P<gem>\d{4})(?P<flur>\d{3})(?P<z>\d{5})(?P<n>\d{4}|_{4})(?P<f>\d{2}|_{2})$')


def parse_reference(ref: str) -> dict:
    """Split the 20-char ALKIS Flurstückskennzeichen: Land(2) Gemarkung(4) Flur(3) Zähler(5) Nenner(4) Folge(2)."""
    m = _REF.match(ref or '')
    if not m:
        return {}
    n = m['n']
    return {'land': m['land'], 'gemarkung_nr': m['gem'], 'flur': int(m['flur']), 'zaehler': int(m['z']), 'nenner': None if n.startswith('_') else int(n)}


def _dedupe(ring: list[list[float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for x, y in ring:
        p = (float(x), float(y))
        if not out or p != out[-1]:
            out.append(p)
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out


def _polygons(geom: dict) -> list[list[list[list[float]]]]:
    t = geom.get('type')
    if t == 'Polygon':
        return [geom['coordinates']]
    if t == 'MultiPolygon':
        return list(geom['coordinates'])
    return []


def _info(feat: dict, poly: list, ring: list[tuple[float, float]]) -> ParcelInfo:
    p = feat.get('properties') or {}
    ref = str(p.get('nationalCadastralReference') or '')
    return ParcelInfo(
        label=str(p.get('label')), national_reference=ref, area_alkis_m2=(float(p['areaValue']) if p.get('areaValue') is not None else None),
        valid_from=p.get('validFrom') or p.get('beginLifespanVersion'),
        geometry_type=feat['geometry']['type'], ring_lonlat=ring, n_holes_ignored=len(poly) - 1, **parse_reference(ref))


def parcels_from_items(payload: dict) -> list[ParcelInfo]:
    """All valid parcels of a response (neighbours for the site pack)."""
    out: list[ParcelInfo] = []
    for feat in payload.get('features') or []:
        for poly in _polygons(feat.get('geometry') or {}):
            ring = _dedupe(poly[0])
            if len(ring) >= 4 and Polygon(ring).is_valid:
                out.append(_info(feat, poly, ring))
    return out


def parcel_from_items(payload: dict, lat: float, lon: float) -> ParcelInfo | None:
    """Pick the parcel whose polygon contains the point. Invalid/degenerate geometry is skipped, not repaired."""
    pt = Point(lon, lat)
    for feat in payload.get('features') or []:
        for poly in _polygons(feat.get('geometry') or {}):
            ring = _dedupe(poly[0])
            if len(ring) < 4:
                continue
            shp = Polygon(ring)
            if not shp.is_valid or not shp.contains(pt):
                continue
            return _info(feat, poly, ring)
    return None


class CadastreProvider(Protocol):
    def parcel_at(self, lat: float, lon: float) -> tuple[ParcelInfo | None, DataStatus]: ...


class InspireHessenProvider:
    """ALKIS parcel at a point. Goes through the shared Fetcher (pooled client, retry, persistent cache)."""

    def __init__(self, fetcher: Fetcher | None = None, half_size_deg: float = 0.00005, timeout: float = 6.0):
        self.fetcher = fetcher or HttpFetcher()
        self.d = half_size_deg
        self.timeout = timeout

    def parcel_at(self, lat: float, lon: float) -> tuple[ParcelInfo | None, DataStatus]:
        t0 = time.perf_counter()
        lat, lon = round(lat, 5), round(lon, 5)  # ~1 m: repeated clicks on one spot share a cache entry

        def st(state: str, detail: str | None = None, cached: bool = False) -> DataStatus:
            return DataStatus(source_id=SOURCE.id, status=state, detail=detail, ms=int((time.perf_counter() - t0) * 1000), cached=cached)

        params = {'f': 'json', 'limit': '5', 'bbox': f'{lon-self.d:.6f},{lat-self.d:.6f},{lon+self.d:.6f},{lat+self.d:.6f}'}
        res = self.fetcher.get(SOURCE.id, ITEMS_URL, params, 7 * 86400, self.timeout)
        if res.body is None:
            return None, st('UNAVAILABLE', f'Liegenschaftskataster nicht erreichbar ({res.error})')
        try:
            payload = json.loads(res.body)
        except ValueError as exc:
            return None, st('UNAVAILABLE', f'Ungültige Antwort: {exc}')
        found = parcel_from_items(payload, lat, lon)
        if found:
            return found, st('OK', 'veralteter Cache' if res.stale else None, res.cached)
        return None, st('NO_MATCH', 'Kein Flurstück an diesem Punkt (außerhalb Hessens, Straße/Gewässer ohne Flurstück oder Datenlücke).', res.cached)


def parcels_around(fetcher: Fetcher, lat: float, lon: float, half_deg: float = 0.0009, timeout: float = 8.0) -> list[ParcelInfo]:
    """Parcels within ~±100 m (neighbour boundaries for rendering). Best effort: an outage yields an empty list."""
    lat, lon = round(lat, 4), round(lon, 4)
    params = {'f': 'json', 'limit': str(min(500, int(100 * max(1.0, (half_deg / 0.0009) ** 2)))), 'bbox': f'{lon-half_deg:.6f},{lat-half_deg:.6f},{lon+half_deg:.6f},{lat+half_deg:.6f}'}
    res = fetcher.get(SOURCE.id, ITEMS_URL, params, 7 * 86400, timeout)
    if res.body is None:
        return []
    try:
        return parcels_from_items(json.loads(res.body))
    except ValueError:
        return []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
