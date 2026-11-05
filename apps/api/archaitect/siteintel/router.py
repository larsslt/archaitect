"""HTTP surface for the Hessen site screening. Mounted under /siteintel by main.py."""
from __future__ import annotations
import json
import os
from pathlib import Path
import io
import json as _json
import zipfile
from fastapi import APIRouter, Body, HTTPException, Query, Response
from pydantic import BaseModel
from .. import store as core_store
from . import geocode, imagery, progress
from .studio import ensure_core_project
from .brief import PlanningBrief
from .context import build_context, envelope_local, overlay_geojson
from .projects import ProjectStore
from .sitepack import build_sitepack
from .cache import TtlCache
from .cadastre import InspireHessenProvider
from .dossier import SiteDossier, VerifiedConstraints, build_dossier, to_parcel_input, with_verified_constraints
from .fetch import HttpFetcher
from .landuse import ENDPOINTS, OverpassProvider
from .models import DesignMode, SiteAssessment
from .service import OUTLINE, SiteService

from .safe_route import SafeRoute  # noqa: E402

router = APIRouter(prefix='/siteintel', tags=['siteintel'], route_class=SafeRoute)
# Overridable in tests: router.providers['service'] = SiteService(...)
providers: dict[str, object] = {}


def _default_cache_path() -> str:
    env = os.environ.get('ARCHAITECT_SITEINTEL_CACHE')
    if env:
        return env
    return str(Path(__file__).resolve().parents[4] / '.local' / 'siteintel-cache.sqlite')


def service() -> SiteService:
    svc = providers.get('service')
    if svc is None:
        fetcher = HttpFetcher(TtlCache(_default_cache_path()))
        osm = None if os.environ.get('ARCHAITECT_SITEINTEL_OSM', '1') == '0' else OverpassProvider(timeout=3.5, endpoints=ENDPOINTS[:1], attempts=1)
        svc = providers.setdefault('service', SiteService(fetcher, InspireHessenProvider(fetcher), osm))
    return svc  # type: ignore[return-value]


@router.get('/hessen/outline')
def outline():
    return json.loads(OUTLINE.read_text(encoding='utf-8'))


@router.get('/geocode')
def geocode_hessen(q: str = Query(min_length=2, max_length=120)):
    items, err = geocode.search(q)
    return {'results': items, 'error': err, 'attribution': 'Geocoding © OpenStreetMap contributors (ODbL)'}


@router.get('/assess/core', response_model=SiteAssessment)
def assess_core(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    """Fast first answer: parcel + official land use + buildings + land value (no planning/protection layers)."""
    return service().assess(lat, lon, stage='core')


@router.get('/assess', response_model=SiteAssessment)
def assess_point(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    """Complete answer incl. planning, protection and the optional OSM refinement."""
    return service().assess(lat, lon, stage='full')


@router.get('/dossier', response_model=SiteDossier)
def dossier(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    """Versioned hand-over contract for the architecture / floor-plan / house generation stage."""
    return build_dossier(service().assess(lat, lon, stage='full'))


@router.post('/dossier/constraints', response_model=SiteDossier)
def dossier_with_constraints(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), verified: VerifiedConstraints = Body(...)):
    """Merge *human- or authority-verified* values (e.g. read from a Bebauungsplan) into the dossier. Only this path can set VERIFIED."""
    return with_verified_constraints(build_dossier(service().assess(lat, lon, stage='full')), verified)


@router.get('/parcel-input')
def parcel_input(lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    """The identified parcel as a ``GeoJSONParcelInput`` for ``POST /geodata/validate`` (hand-over to the geometry/architecture pipeline)."""
    out = to_parcel_input(service().assess(lat, lon, stage='core'))
    if out is None:
        raise HTTPException(409, 'Kein übernehmbares Flurstück: Standort ist gesperrt oder es wurde kein Flurstück gefunden.')
    return out


# ------------------------------------------------------------------ imagery proxy (privacy: the user's browser never talks to the Hessen servers)
@router.get('/imagery/wms')
def imagery_wms(layers: str = Query(default='luftbild'), bbox: str = Query(), width: int = Query(default=256, ge=16, le=imagery.MAX_SIDE_PX), height: int = Query(default=256, ge=16, le=imagery.MAX_SIDE_PX),
                crs: str = Query(default='EPSG:3857'), format: str = Query(default='image/jpeg')):
    if layers not in imagery.LAYERS:
        raise HTTPException(400, f'Unbekannte Ebene. Erlaubt: {", ".join(imagery.LAYERS)}')
    if crs not in ('EPSG:3857', 'EPSG:25832') or format not in ('image/jpeg', 'image/png'):
        raise HTTPException(400, 'Nicht unterstütztes CRS oder Format.')
    try:
        box = tuple(float(v) for v in bbox.split(','))
        assert len(box) == 4 and box[0] < box[2] and box[1] < box[3]
    except (ValueError, AssertionError):
        raise HTTPException(400, 'bbox muss minx,miny,maxx,maxy sein.')
    if not imagery.bbox_in_hessen(box, crs):  # type: ignore[arg-type]
        raise HTTPException(404, 'Außerhalb Hessens.')
    res = imagery.get_map(service().fetcher, layers, box, width, height, crs, format)  # type: ignore[arg-type]
    if res.body is None:
        raise HTTPException(502, 'Bilddienst nicht erreichbar.')
    return Response(res.body, media_type='image/png' if res.body[:4] == b'\x89PNG' else 'image/jpeg',
                    headers={'Cache-Control': 'public, max-age=86400', 'X-Attribution': imagery.LAYERS[layers].attribution.encode('ascii', 'replace').decode()})


@router.get('/imagery/layers')
def imagery_layers():
    return [{'key': l.key, 'title_de': l.title_de, 'attribution': l.attribution, 'licence': imagery.LICENCE_TEXT} for l in imagery.LAYERS.values()]


# ------------------------------------------------------------------ projects: plot + site pack + planning brief + generation context
def store() -> ProjectStore:
    st = providers.get('store')
    if st is None:
        st = providers.setdefault('store', ProjectStore())
    return st  # type: ignore[return-value]


class NewProject(BaseModel):
    lat: float
    lon: float
    name: str | None = None
    override: bool = False


def _need(pid: str) -> str:
    if not store().exists(pid):
        raise HTTPException(404, 'Projekt nicht gefunden.')
    return pid


def _dossier(pid: str) -> SiteDossier:
    d = build_dossier(store().assessment(pid))
    v = store().verified(pid)
    return with_verified_constraints(d, v) if v else d


def _make_thumb(pid: str, pack: dict) -> None:
    """Small aerial thumbnail of the plot (3:2) for the overview; failure is harmless (the card falls back to an outline)."""
    try:
        site = {'ring': pack['site']['ring_local']} if pack.get('site', {}).get('ring_local') else next(p for p in pack['parcels'] if p['is_site'])
        xs = [x for x, _ in site['ring']]
        ys = [y for _, y in site['ring']]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        half_w = max((max(xs) - min(xs)), (max(ys) - min(ys)) * 1.5) / 2 * 1.35 + 10
        half_h = half_w / 1.5
        ox, oy = pack['frame']['origin_e'], pack['frame']['origin_n']
        bbox = (round(ox + cx - half_w), round(oy + cy - half_h), round(ox + cx + half_w), round(oy + cy + half_h))
        w_px = 480
        h_px = max(64, round(w_px * (bbox[3] - bbox[1]) / (bbox[2] - bbox[0])))
        res = imagery.get_map(service().fetcher, 'luftbild', tuple(float(v) for v in bbox), w_px, h_px, 'EPSG:25832', 'image/jpeg')
        if res.body:
            store().save_thumb(pid, res.body, {'bbox_local': [bbox[0] - ox, bbox[1] - oy, bbox[2] - ox, bbox[3] - oy], 'ring': site['ring'], 'w': w_px, 'h': h_px})
    except Exception:  # noqa: BLE001 - thumbnails are cosmetic
        pass


@router.post('/projects')
def create_project(body: NewProject):
    a = service().assess(body.lat, body.lon, stage='full')
    if a.parcel is None:
        raise HTTPException(409, a.design_reason_de or 'Kein Flurstück an diesem Punkt.')
    if a.design_mode == DesignMode.BLOCKED and not (body.override and a.design_override_allowed):
        raise HTTPException(409, f'Entwurf gesperrt: {a.design_reason_de}')
    pack = build_sitepack(service().fetcher, a)
    meta = store().create(a, pack, body.name, body.override)
    _make_thumb(pid=meta['id'], pack=pack.manifest)
    if os.environ.get('ARCHAITECT_SITEINTEL_OSM', '1') != '0':
        addr = geocode.reverse(a.lat, a.lon)
        if addr:
            meta = store().update_meta(meta['id'], address=addr, gemeinde=addr.get('ort') or meta.get('gemeinde'))
    return {**meta, 'sitepack_flags': pack.manifest['quality_flags'], 'ortho': pack.manifest['ortho']['status'], 'terrain': pack.manifest['terrain']['status']}


def _bim_version(pid: str) -> int | None:
    """Newest saved version of the project's BIM house, None if there is none yet."""
    try:
        hist = json.loads((store()._dir(pid) / 'bim' / 'model' / 'history.json').read_text(encoding='utf-8'))
        return hist[-1]['version'] if hist else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def _card(m: dict) -> dict:
    pid = m['id']
    try:
        brief, verified = store().brief(pid), store().verified(pid)
        des = store().design(pid)
        core = None if des else core_store.read(pid)
        dv = des.version if des else (core.design.version if core else None)
        prog = progress.compute(m, brief, verified, dv)
        bim_version = _bim_version(pid)
        a = None
        if not m.get('area_m2'):
            a = store().assessment(pid)
        return {**m, 'gemeinde': m.get('gemeinde') or (a.land_value.gemeinde if a and a.land_value else None), 'address': m.get('address'), 'area_m2': m.get('area_m2') or (a.parcel.area_alkis_m2 if a and a.parcel else None),
                'bim_version': bim_version, 'has_house': bim_version is not None,
                'has_thumb': (store()._dir(pid) / 'thumb.jpg').exists(), 'title': brief.title, 'progress': prog, 'has_studio': dv is not None, 'design_version': dv,
                'connections': len(brief.connections), 'verified': verified is not None, 'program': {'occupants': brief.program.occupants, 'living_area_target_m2': brief.program.living_area_target_m2, 'stories': brief.program.stories}}
    except Exception as exc:  # noqa: BLE001 - one damaged project must not break the overview
        return {**m, 'error': type(exc).__name__}


@router.get('/projects')
def list_projects():
    """Overview cards: meta + progress through the six preparation steps + what to do next."""
    return [_card(m) for m in store().list()]


class MetaPatch(BaseModel):
    name: str | None = None
    pinned: bool | None = None


@router.put('/projects/{pid}/meta')
def put_meta(pid: str, body: MetaPatch):
    _need(pid)
    if body.name is not None:
        name = body.name.strip()
        if not 1 <= len(name) <= 120:
            raise HTTPException(422, 'Name muss 1–120 Zeichen lang sein.')
        b = store().brief(pid)
        store().save_brief(pid, b.model_copy(update={'title': name}))
        store().update_meta(pid, name=name)
    if body.pinned is not None:
        store().update_meta(pid, pinned=body.pinned)
    return _card(store().meta(pid))


@router.delete('/projects/{pid}')
def delete_project(pid: str):
    _need(pid)
    store().delete(pid)
    core_store.delete(pid)
    return {'deleted': pid}


@router.post('/projects/{pid}/duplicate')
def duplicate_project(pid: str):
    _need(pid)
    return _card(store().duplicate(pid))


@router.get('/projects/{pid}/thumb.jpg')
def project_thumb(pid: str):
    _need(pid)
    b = store().thumb(pid)
    if b is None:
        raise HTTPException(404, 'Keine Vorschau.')
    return Response(b, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600'})


@router.post('/projects/{pid}/studio')
def open_studio(pid: str):
    """Make the plot ready for house planning: creates (once) or refreshes (rules, envelope, parcel) the design project with the same id."""
    _need(pid)
    a = store().assessment(pid)
    pack = store().pack(pid)
    meta = store().meta(pid)
    if a.parcel is None:
        raise HTTPException(409, 'Kein Flurstück.')
    proj = ensure_core_project(pid, meta, pack, a.parcel.area_alkis_m2, store().brief(pid), store().verified(pid), envelope_local(_dossier(pid), pack))
    store().touch(pid)
    return {'project': proj, 'gate': {'mode': a.design_mode.value, 'reason_de': a.design_reason_de, 'override': bool(meta.get('override_blocked'))},
            'frame': pack['frame'], 'name': meta['name'], 'parcel_label': a.parcel.label}


@router.get('/projects/{pid}')
def get_project(pid: str):
    _need(pid)
    return {'project': store().meta(pid), 'brief': store().brief(pid), 'assessment': store().assessment(pid), 'verified': store().verified(pid)}


@router.put('/projects/{pid}/brief')
def put_brief(pid: str, brief: PlanningBrief = Body(...)):
    _need(pid)
    return store().save_brief(pid, brief)


@router.post('/projects/{pid}/constraints', response_model=SiteDossier)
def put_constraints(pid: str, verified: VerifiedConstraints = Body(...)):
    _need(pid)
    store().save_verified(pid, verified)
    store().touch(pid)
    return _dossier(pid)


@router.get('/projects/{pid}/dossier', response_model=SiteDossier)
def project_dossier(pid: str):
    _need(pid)
    return _dossier(pid)


@router.get('/projects/{pid}/sitepack')
def project_sitepack(pid: str):
    _need(pid)
    return store().pack(pid)


@router.get('/projects/{pid}/overlay')
def project_overlay(pid: str):
    """Map overlay as WGS84 GeoJSON: land use, parcels, buildings, buildable envelope (only when verified), connection points."""
    _need(pid)
    return overlay_geojson(store().pack(pid), envelope_local(_dossier(pid), store().pack(pid)), store().brief(pid))


@router.get('/projects/{pid}/ortho.png')
def project_ortho(pid: str):
    _need(pid)
    b = store().ortho(pid)
    if b is None:
        raise HTTPException(404, 'Kein Luftbild gespeichert.')
    return Response(b, media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})


@router.get('/projects/{pid}/context')
def project_context(pid: str):
    """The one retrievable bundle for the generation stage: facts with provenance, geometry in the local frame, brief, rules."""
    _need(pid)
    ctx = build_context(store().meta(pid), store().assessment(pid), _dossier(pid), store().pack(pid), store().brief(pid), f'/siteintel/projects/{pid}')
    from .planning_api import context_evidence
    ctx['municipal_planning'] = context_evidence(pid)
    return ctx


def _tt(o):
    from .i18n_tree import translate_tree
    return translate_tree(o)


def _tx(s):
    from .i18n_tree import translate_text
    return translate_text(s)


@router.get('/projects/{pid}/sitepack.zip')
def project_bundle(pid: str, lang: str = 'de'):
    _need(pid)
    pack = store().pack(pid)
    ctx = build_context(store().meta(pid), store().assessment(pid), _dossier(pid), pack, store().brief(pid), '.')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', _json.dumps(pack, ensure_ascii=False, indent=1))
        z.writestr('context.json', _json.dumps(_tt(ctx) if lang == 'en' else ctx, ensure_ascii=False, indent=1))
        o = store().ortho(pid)
        if o:
            z.writestr('ortho.png', o)
            z.writestr('ortho.pgw', pack['ortho'].get('world_file', '') + '\n')
        _readme = ('ArchAItect Site-Pack\n\nmanifest.json: Geometrie im lokalen Rahmen (Meter, x=Ost, y=Nord), Gelände, Nachbarn, Landnutzung, Herkunft.\ncontext.json: Fakten mit Quelle und Status, Baufenster (falls verifiziert), Planungsbrief, Regeln für die Generierung.\n'
                                  'ortho.png + ortho.pgw: Luftbild 20 cm, EPSG:25832.\n\n' + pack['modification_notice_de'] + '\n' + '\n'.join(x['text'] for x in pack['attribution']) + '\n')
        z.writestr('README.txt', _tx(_readme) if lang == 'en' else _readme)
    return Response(buf.getvalue(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="site-pack-{pid}.zip"'})


from .design_api import design_router  # noqa: E402  (needs the helpers above)
router.include_router(design_router)

from .bim_api import bim_router  # noqa: E402
router.include_router(bim_router)

from .planning_api import planning_router
router.include_router(planning_router)

from .legal_api import legal_router
router.include_router(legal_router)
