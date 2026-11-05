"""Orchestration: point -> parcel -> (all official sources in parallel) -> evidence -> decision -> assessment.

Latency design (see docs/HESSEN_SITE_INTELLIGENCE.md): the parcel lookup is the only sequential step. Everything else is
fired at once on a shared thread pool with a hard time budget; a slow or failing source degrades to a data-status line and
never decides the verdict on its own. ``stage='core'`` (land use, buildings, land value) is what a click needs to show
something useful quickly; ``stage='full'`` adds planning, protection and the optional OSM refinement.
"""
from __future__ import annotations
import json
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from functools import lru_cache
from pathlib import Path
from shapely.geometry import Point, Polygon, shape
from . import cadastre, extract, landuse, sources
from .decision import Evidence, decide
from .fetch import Fetcher
from .mace import build_mace
from .models import DataStatus, SiteAssessment, Verdict, DesignMode
from .rules import classify_tags

OUTLINE = Path(__file__).parent / 'data' / 'hessen_outline.geojson'
_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix='siteintel')
CORE = ('elu', 'buildings', 'boris')
CONTEXT = ('regfnp', 'lep', 'denkmal', 'hq100', 'schutzgebiete')
BUDGET_S = {'core': 9.0, 'full': 14.0}
OSM_GRACE_S = 0.6


@lru_cache(maxsize=1)
def _hessen():
    return shape(json.loads(OUTLINE.read_text(encoding='utf-8'))['geometry'])


def in_hessen(lat: float, lon: float) -> bool:
    return _hessen().contains(Point(lon, lat))


class SiteService:
    def __init__(self, fetcher: Fetcher, cad: cadastre.CadastreProvider, osm: landuse.LandUseProvider | None = None):
        self.fetcher = fetcher
        self.cad = cad
        self.osm = osm

    def assess(self, lat: float, lon: float, stage: str = 'full') -> SiteAssessment:
        t_start = time.perf_counter()
        stamp = cadastre.now_iso()
        if not in_hessen(lat, lon):
            return SiteAssessment(stage=stage, lat=lat, lon=lon, in_hessen=False, verdict=Verdict.UNKNOWN, headline_de='Außerhalb von Hessen – hier nicht unterstützt.',
                                  design_mode=DesignMode.BLOCKED, design_reason_de='Nur Hessen ist angebunden.', design_allowed=False, findings=[], parcel=None, land_use=[],
                                  data_status=[DataStatus(source_id='hessen-outline', status='OUTSIDE')], sources=[])
        parcel, cs = self.cad.parcel_at(lat, lon)
        timings = {'parcel': cs.ms or 0}
        # Without a parcel (outage / no match) the land-use sources still answer for a ~2 m patch around the click.
        geom = Polygon([(x, y) for x, y in parcel.ring_lonlat]) if parcel else Point(lon, lat).buffer(0.00002)
        if not geom.is_valid:
            geom = geom.buffer(0)
        futs: dict[str, Future] = {n: _POOL.submit(sources.query, sources.SOURCES[n], self.fetcher, geom) for n in CORE}
        if stage != 'core':
            for n in CONTEXT:
                futs[n] = _POOL.submit(sources.query, sources.SOURCES[n], self.fetcher, geom)
            # Only the Regionalplan of the point's region (Regierungsbezirk from the BORIS zone; BORIS is fast and usually cached by the core call).
            wait([futs['boris']], timeout=3.0)
            boris_feats = futs['boris'].result().features if futs['boris'].done() and futs['boris'].exception() is None else []
            for n in sources.regional_plan_for(boris_feats):
                futs[n] = _POOL.submit(sources.query, sources.SOURCES[n], self.fetcher, geom)
        osm_f: Future | None = None
        if stage != 'core' and self.osm is not None:
            osm_f = _POOL.submit(self.osm.tags_at, lat, lon)
        budget = BUDGET_S['core' if stage == 'core' else 'full'] - (time.perf_counter() - t_start)
        wait(list(futs.values()), timeout=max(budget, 1.0))
        if osm_f is not None and not osm_f.done():
            # OSM is only a refinement: once every official source has answered it gets a short grace period, never the full Overpass timeout.
            wait([osm_f], timeout=OSM_GRACE_S)
        out: dict[str, sources.Outcome] = {}
        statuses: dict[str, DataStatus] = {cadastre.SOURCE.id: cs}
        for n, f in futs.items():
            if f.done() and not f.cancelled() and f.exception() is None:
                out[n] = f.result()
            else:
                reason = 'Zeitbudget überschritten' if not f.done() else f'Interner Fehler: {type(f.exception()).__name__}'
                out[n] = sources.Outcome([], DataStatus(source_id=n, status='UNAVAILABLE', detail=f'{sources.SOURCES[n].name}: {reason}'))
            statuses[n] = out[n].status
            timings[n] = out[n].status.ms or 0
        osm_hits = []
        if osm_f is not None:
            if osm_f.done() and osm_f.exception() is None:
                tags, st = osm_f.result()
                statuses['osm-overpass'] = st
                osm_hits = classify_tags(tags)
            else:
                statuses['osm-overpass'] = DataStatus(source_id='osm-overpass', status='UNAVAILABLE', detail='OSM optional: nicht rechtzeitig erreichbar (kein Einfluss auf das Ergebnis).')
        elu_ok = statuses['elu'].status in ('OK', 'NO_MATCH')
        shares = extract.land_use_shares(out['elu'].features, geom) if elu_ok else None
        bu = extract.building_stats(out['buildings'].features, geom) if statuses['buildings'].status in ('OK', 'NO_MATCH') else None
        val = extract.land_value(out['boris'].features, Point(lon, lat)) if statuses['boris'].status in ('OK', 'NO_MATCH') else None
        planning = []
        for n in ('regfnp', 'rp_sued', 'rp_mittel', 'rp_nord', 'lep'):
            if n in out and out[n].features:
                planning += extract.planning_hits({'regfnp': 'regfnp', 'lep': 'lep'}.get(n, 'regionalplan'), out[n].features, geom)
        planning = extract.dedupe_planning(planning)
        prot = extract.protection_hits(out['denkmal'].features if 'denkmal' in out else [], out['hq100'].features if 'hq100' in out else [], geom, out['schutzgebiete'].features if 'schutzgebiete' in out else [])
        ev = Evidence(parcel=parcel, shares=shares, buildings=bu, value=val, planning=planning, protections=prot, osm_hits=osm_hits, statuses=statuses, stage=stage)
        d = decide(ev)
        used = [cadastre.SOURCE.model_copy(update={'retrieved': stamp, 'attribution': '© Hessische Verwaltung für Bodenmanagement und Geoinformation'})]
        used += [sources.SOURCES[n].ref(stamp) for n in out if statuses[n].status in ('OK', 'NO_MATCH')]
        if osm_hits or (osm_f is not None and statuses.get('osm-overpass') and statuses['osm-overpass'].status == 'OK'):
            used.append(landuse.SOURCE.model_copy(update={'retrieved': stamp}))
        flags = []
        for n, o in out.items():
            if o.status.status == 'UNAVAILABLE':
                flags.append(f'SOURCE_UNAVAILABLE_{n.upper()}')
        mace = build_mace(parcel, flags) if parcel else None
        timings['total'] = int((time.perf_counter() - t_start) * 1000)
        return SiteAssessment(
            stage=stage, lat=lat, lon=lon, in_hessen=True, verdict=d.verdict, confidence=d.confidence, headline_de=d.headline_de, design_mode=d.design_mode,
            design_reason_de=d.design_reason_de, design_allowed=d.design_mode != DesignMode.BLOCKED, design_override_allowed=d.override_allowed, findings=d.findings, regulations=d.regulations, parcel=parcel,
            land_use=osm_hits, land_use_shares=shares or [], buildings=bu, land_value=val, planning=planning, protections=prot,
            data_status=list(statuses.values()), sources=used, timings_ms=timings, mace=mace)
