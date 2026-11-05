"""Land-use context from OpenStreetMap via Overpass (ODbL). Heuristic input only — not an official zoning source.

The public Overpass instances rate-limit (observed HTTP 429 on 2026-10-28), so: short timeout, one retry per
endpoint, in-memory cache, and a clean UNAVAILABLE status that makes the verdict UNKNOWN instead of guessing.
"""
from __future__ import annotations
import time
from typing import Protocol
import httpx
from .models import DataStatus, SourceRef

ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
SOURCE = SourceRef(id='osm-overpass', name='OpenStreetMap-Flächennutzung (Overpass)', licence='ODbL 1.0 © OpenStreetMap contributors', url='https://www.openstreetmap.org/copyright')
USER_AGENT = 'ArchAItect-prototype/0.6 (research prototype; see project repository)'

KEYS = ['landuse', 'natural', 'leisure', 'military', 'aeroway', 'building', 'amenity', 'water', 'waterway', 'power', 'man_made', 'railway']


def query_for(lat: float, lon: float) -> str:
    parts = ''.join(f'area.a["{k}"];' for k in KEYS) + 'area.a["boundary"~"protected_area|national_park"];'
    return f'[out:json][timeout:20];is_in({lat:.6f},{lon:.6f})->.a;({parts});out tags;'


class LandUseProvider(Protocol):
    def tags_at(self, lat: float, lon: float) -> tuple[list[dict[str, str]], DataStatus]: ...


class OverpassProvider:
    def __init__(self, client: httpx.Client | None = None, ttl_s: int = 3600, timeout: float = 14.0, endpoints: list[str] | None = None, attempts: int = 2):
        self.client = client or httpx.Client(timeout=timeout, headers={'User-Agent': USER_AGENT})
        self.endpoints = endpoints or ENDPOINTS
        self.attempts = attempts
        self.ttl = ttl_s
        self._cache: dict[tuple[float, float], tuple[float, list[dict[str, str]]]] = {}

    def tags_at(self, lat: float, lon: float) -> tuple[list[dict[str, str]], DataStatus]:
        key = (round(lat, 4), round(lon, 4))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.ttl:
            return hit[1], DataStatus(source_id=SOURCE.id, status='OK', detail='cache')
        last = 'no attempt'
        for url in self.endpoints:
            for attempt in range(self.attempts):
                try:
                    r = self.client.post(url, data={'data': query_for(lat, lon)})
                    if r.status_code in (429, 502, 503, 504):
                        last = f'{url} HTTP {r.status_code}'
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    r.raise_for_status()
                    tags = [e['tags'] for e in r.json().get('elements', []) if e.get('tags')]
                    self._cache[key] = (time.time(), tags)
                    return tags, DataStatus(source_id=SOURCE.id, status='OK')
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    last = f'{url} {type(exc).__name__}'
                    break
        return [], DataStatus(source_id=SOURCE.id, status='UNAVAILABLE', detail=f'Overpass nicht erreichbar ({last}); Flächennutzung unbekannt.')
