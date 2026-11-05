"""Official Hessen aerial imagery (DOP20) and map WMS, delivered through our own proxy.

Why a proxy (privacy + licence, see docs/HESSEN_SITE_INTELLIGENCE.md):
- The browser talks only to our API; the Hessen service never sees the user's IP address, and we never log or forward user coordinates
  beyond the cache key of a tile.
- Licence: HVGG §18 / §24, stated verbatim in the service's AccessConstraints: any use incl. commercial, modification, passing on to third
  parties and integration into products is allowed without condition; a source note, if given, must say that data were modified.
- Only these official layers are reachable and only inside Hessen: the proxy is not an open relay.
"""
from __future__ import annotations
from dataclasses import dataclass
from pyproj import Transformer
from .fetch import FetchResult, Fetcher

BASE = 'https://www.gds-srv.hessen.de/cgi-bin/lika-services/'
SERVICE_INFO = 'https://www.geoportal.hessen.de/'
LICENCE_TEXT = 'Datenlizenz Deutschland – Zero – Version 2.0; Nutzung nach § 18 HVGG ohne Einschränkung oder Bedingung (auch kommerziell, Veränderung und Weitergabe erlaubt)'
MAX_SIDE_PX = 1024
HESSEN_BBOX = (7.6, 49.3, 10.35, 51.75)   # lon/lat, generous margin around the state; the proxy refuses anything outside

_TO_4326 = {'EPSG:3857': Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True), 'EPSG:25832': Transformer.from_crs('EPSG:25832', 'EPSG:4326', always_xy=True)}


@dataclass(frozen=True)
class Layer:
    key: str
    service: str
    layers: str
    title_de: str
    attribution: str
    changed_attribution: str


_AERIAL = 'Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation: Digitale Orthophotos'
_MAP = 'Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation: Amtliche Karten'
LAYERS: dict[str, Layer] = {l.key: l for l in [
    Layer('luftbild', 'ogc-free-images.ows', 'he_dop_rgb', 'Luftbild (DOP, 20 cm)', _AERIAL, _AERIAL + ' (verändert: gerendert/bearbeitet)'),
    Layer('luftbild_cir', 'ogc-free-images.ows', 'he_dop_cir', 'Luftbild Color-Infrarot', _AERIAL, _AERIAL + ' (verändert: gerendert/bearbeitet)'),
    Layer('karte', 'ogc-free-maps.ows', 'he_uek1000,he_uek200,he_uek,he_dtk50,he_dtk25,he_alk', 'Amtliche Karte (ÜK/DTK/ALK)', _MAP, _MAP + ' (verändert)'),
]}


def looks_like_image(b: bytes) -> bool:
    return b[:3] == b'\xff\xd8\xff' or b[:8] == b'\x89PNG\r\n\x1a\n'


def bbox_in_hessen(bbox: tuple[float, float, float, float], crs: str) -> bool:
    tr = _TO_4326.get(crs)
    if tr is None:
        return False
    x0, y0, x1, y1 = bbox
    lon0, lat0 = tr.transform(x0, y0)
    lon1, lat1 = tr.transform(x1, y1)
    w, s, e, n = HESSEN_BBOX
    return not (max(lon0, lon1) < w or min(lon0, lon1) > e or max(lat0, lat1) < s or min(lat0, lat1) > n)


def get_map(fetcher: Fetcher, layer: str, bbox: tuple[float, float, float, float], width: int, height: int, crs: str = 'EPSG:3857', fmt: str = 'image/jpeg',
            ttl: float = 30 * 86400, timeout: float = 12.0) -> FetchResult:
    """WMS 1.3.0 GetMap. ``bbox`` is x/y order for the projected CRS we allow (EPSG:3857 / EPSG:25832)."""
    L = LAYERS[layer]
    params = {'SERVICE': 'WMS', 'VERSION': '1.3.0', 'REQUEST': 'GetMap', 'LAYERS': L.layers, 'STYLES': '', 'FORMAT': fmt, 'CRS': crs,
              'BBOX': ','.join(f'{v:.3f}' for v in bbox), 'WIDTH': str(width), 'HEIGHT': str(height)}
    return fetcher.get('hessen-wms-' + layer, BASE + L.service, params, ttl, timeout, looks_like_image)
