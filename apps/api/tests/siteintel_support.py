"""Shared test doubles for the site screening: replay recorded WFS responses (gzip) and recorded ALKIS parcels."""
from __future__ import annotations
import gzip
import json
from pathlib import Path
from archaitect.siteintel import cadastre
from archaitect.siteintel.fetch import FetchResult
from archaitect.siteintel.models import DataStatus
from archaitect.siteintel.service import SiteService

FX = Path(__file__).parent / 'fixtures_siteintel'
PARCELS = json.loads((FX / 'parcels.json').read_text())
TAGS = json.loads((FX / 'osm_tags.json').read_text())
EMPTY = (b'<?xml version="1.0"?><wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" '
         b'numberMatched="0" numberReturned="0"/>')
# scenario (parcel fixture key) -> recorded point suffix
POINT = {'frankfurt_nordend': 'ffm', 'darmstadt_wohn': 'darmstadt', 'acker_wetterau': 'acker', 'wald_odenwald': 'wald', 'kaserne': 'kaserne'}
SRC_FILE = {'elu': 'elu', 'buildings': 'bu', 'boris': 'boris', 'regfnp': 'regfnp', 'rp_sued': 'rp_sued', 'rp_mittel': 'rp_mittel', 'rp_nord': 'rp_nord', 'lep': 'lep', 'hq100': 'hq100', 'denkmal': 'denk'}


BIN = {'hessen-dgm1': 'bin/dgm1__{p}.tif', 'hessen-wms-luftbild': 'bin/ortho__{p}.png', 'alkis-inspire-he': 'bin/parcels_around__{p}.json.gz'}


def load(name: str) -> bytes | None:
    f = FX / 'wfs' / f'{name}.xml.gz'
    return gzip.decompress(f.read_bytes()) if f.exists() else None


class ReplayFetcher:
    """Answers every request of a source with the recorded response of the scenario; no recording -> empty collection.
    ``fail`` makes the given sources behave like an outage (body None)."""

    def __init__(self, point: str, fail: set[str] | tuple[str, ...] = (), overrides: dict[str, bytes] | None = None):
        self.point, self.fail, self.overrides = point, set(fail), overrides or {}
        self.calls: list[tuple[str, str]] = []

    def _answer(self, sid: str, kind: str) -> FetchResult:
        self.calls.append((sid, kind))
        if sid in self.fail:
            return FetchResult(None, 1, error='ConnectTimeout')
        if sid in BIN:
            f = FX / BIN[sid].format(p=self.point)
            if not f.exists():
                return FetchResult(None, 1, error='kein Fixture')
            data = f.read_bytes()
            return FetchResult(gzip.decompress(data) if f.suffix == '.gz' else data, 1)
        if sid in self.overrides:
            return FetchResult(self.overrides[sid], 1)
        body = load(f'{SRC_FILE.get(sid, sid)}__{self.point}')
        return FetchResult(body if body is not None else EMPTY, 1)

    def post_xml(self, source_id, url, body, ttl, timeout, accept=None):
        return self._answer(source_id, 'post')

    def get(self, source_id, url, params, ttl, timeout, accept=None):
        return self._answer(source_id, 'get')


class FakeCad:
    def __init__(self, key):
        self.key = key

    def parcel_at(self, lat, lon):
        p = cadastre.parcel_from_items(PARCELS[self.key]['items'], lat, lon)
        return p, DataStatus(source_id='alkis-inspire-he', status='OK' if p else 'NO_MATCH', ms=1)


class FakeOsm:
    def __init__(self, tags, status='OK'):
        self.tags, self.status = tags, status

    def tags_at(self, lat, lon):
        return (self.tags if self.status == 'OK' else []), DataStatus(source_id='osm-overpass', status=self.status, detail=None if self.status == 'OK' else 'down')


def service_for(key: str, fail=(), osm=None, overrides=None) -> tuple[SiteService, ReplayFetcher]:
    f = ReplayFetcher(POINT[key], fail, overrides)
    return SiteService(f, FakeCad(key), osm), f


def run(key: str, stage='full', fail=(), osm=None, overrides=None):
    svc, f = service_for(key, fail, osm, overrides)
    p = PARCELS[key]
    return svc.assess(p['lat'], p['lon'], stage=stage), f
