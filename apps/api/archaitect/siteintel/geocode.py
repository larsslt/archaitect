"""Place search restricted to Hessen via Nominatim (OSM, ODbL). Server-side so the usage policy
(identifying User-Agent, <=1 request/s, caching) is respected and no browser hits Nominatim directly."""
from __future__ import annotations
import time
import httpx

URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'ArchAItect-prototype/0.6 (research prototype; see project repository)'
VIEWBOX = '7.7725,51.6578,10.2365,49.3953'  # left,top,right,bottom of Hessen
_last = 0.0
_cache: dict[str, tuple[float, list[dict]]] = {}


def search(q: str, client: httpx.Client | None = None, limit: int = 6) -> tuple[list[dict], str | None]:
    global _last
    q = q.strip()
    if len(q) < 2:
        return [], None
    hit = _cache.get(q.lower())
    if hit and time.time() - hit[0] < 3600:
        return hit[1], None
    wait = 1.1 - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    c = client or httpx.Client(timeout=10, headers={'User-Agent': USER_AGENT})
    try:
        r = c.get(URL, params={'q': q, 'format': 'jsonv2', 'limit': limit, 'viewbox': VIEWBOX, 'bounded': 1, 'countrycodes': 'de', 'accept-language': 'de'})
        _last = time.time()
        r.raise_for_status()
        items = [{'name': i['display_name'], 'lat': float(i['lat']), 'lon': float(i['lon']), 'kind': i.get('type')} for i in r.json()]
        _cache[q.lower()] = (time.time(), items)
        return items, None
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return [], f'Ortssuche nicht erreichbar ({type(exc).__name__})'


REVERSE_URL = 'https://nominatim.openstreetmap.org/reverse'


def reverse(lat: float, lon: float, client: httpx.Client | None = None) -> dict | None:
    """Address of a point (street, number, postcode, municipality) for the project overview. Failure is harmless: returns None."""
    global _last
    key = f'rev:{lat:.5f},{lon:.5f}'
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < 86400:
        return hit[1][0] if hit[1] else None
    wait = 1.1 - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    c = client or httpx.Client(timeout=4, headers={'User-Agent': USER_AGENT})
    try:
        r = c.get(REVERSE_URL, params={'lat': f'{lat:.6f}', 'lon': f'{lon:.6f}', 'format': 'jsonv2', 'zoom': 18, 'addressdetails': 1, 'accept-language': 'de'})
        _last = time.time()
        r.raise_for_status()
        a = r.json().get('address', {})
        ort = a.get('city') or a.get('town') or a.get('village') or a.get('municipality')
        out = {'ort': ort, 'ortsteil': a.get('suburb') or a.get('city_district') or a.get('quarter'), 'strasse': a.get('road'), 'hausnummer': a.get('house_number'), 'plz': a.get('postcode')}
        _cache[key] = (time.time(), [out])
        return out
    except (httpx.HTTPError, ValueError, KeyError):
        return None
