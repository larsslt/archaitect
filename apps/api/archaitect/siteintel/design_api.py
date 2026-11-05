"""Studio API: the massing design of a project (revisions), its rule check, fitting into the hard limits, and several parcels per project.

Mounted into the siteintel router (prefix /siteintel). Hard rules are enforced on commit: a design that leaves the plot or breaks a verified
B-Plan value cannot be saved. HBO-derived rules only warn.
"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import transform, unary_union
from .massing import Massing, default_massing
from .dossier import PlanningLimits
from .regs import evaluate, fit, site_ctx

from .safe_route import SafeRoute

design_router = APIRouter(route_class=SafeRoute)
MAX_PARCELS = 5
_TO_LL = Transformer.from_crs('EPSG:25832', 'EPSG:4326', always_xy=True)


def _r():
    from . import router as R            # late import: router imports this module at the end
    return R


def ctx_for(pid: str):
    R = _r()
    pack = R.store().pack(pid)
    meta = R.store().meta(pid)
    ids = meta.get('parcel_ids') or pack.get('site', {}).get('parcel_ids')
    ctx = site_ctx(pack, R.store().verified(pid), R.envelope_local(R._dossier(pid), pack), ids, R.store().limits(pid))
    try:
        from . import reference
        lv = R.store().assessment(pid).land_value
        ctx.reference = reference.build(ctx, lv.model_dump() if lv is not None else None)
    except Exception:  # noqa: BLE001 - the reference frame is optional context, never a reason to fail
        ctx.reference = None
    return ctx, pack, meta


def _ensure_design(pid: str) -> Massing:
    R = _r()
    m = R.store().design(pid)
    if m is None:
        ctx, _, _ = ctx_for(pid)
        b = R.store().brief(pid).program
        reg = ctx.hard_region(Massing(volumes=[{'id': 'tmp'}], demolish=[]))
        if reg.is_empty:
            reg = ctx.site
        if reg.geom_type != 'Polygon':
            reg = max(reg.geoms, key=lambda g: g.area)
        m = default_massing(reg, b.living_area_target_m2, b.stories, (b.roof_types or [None])[0])
        m, _notes = fit(m, ctx)
        try:
            m = R.store().save_design(pid, m, None)
        except ValueError:      # two page requests created the first design at the same time; the first one wins
            m = R.store().design(pid) or m
    return m


def _site_payload(ctx, pack: dict, meta: dict) -> dict:
    return {'parcel_ids': ctx.parcel_ids, 'ring': [[round(x, 2), round(y, 2)] for x, y in ctx.site.exterior.coords], 'area_m2': round(ctx.area_m2, 1),
            'labels': [p['label'] for p in pack['parcels'] if p['id'] in ctx.parcel_ids],
            'existing': [{'id': e.id, 'ring': [[round(x, 2), round(y, 2)] for x, y in e.poly.exterior.coords], 'floors': e.floors, 'height_m': e.height_m, 'footprint_m2': round(e.poly.area, 1)} for e in ctx.existing],
            'envelope': [[round(x, 2), round(y, 2)] for x, y in ctx.envelope.exterior.coords] if ctx.envelope is not None and ctx.envelope.geom_type == 'Polygon' else None,
            'verified': vars(ctx.verified) if ctx.verified else None, 'limit_basis': ctx.src, 'limit_sources': ctx.src_text, 'frame': pack['frame'], 'name': meta['name']}


@design_router.get('/projects/{pid}/design')
def get_design(pid: str):
    R = _r()
    R._need(pid)
    m = _ensure_design(pid)
    ctx, pack, meta = ctx_for(pid)
    a = R.store().assessment(pid)
    notices = [{'kind': p.kind, 'label_de': p.label_de, 'name': p.name, 'on_parcel': p.on_parcel, 'distance_m': p.distance_m}
               for p in (getattr(a, 'protections', None) or []) if p.kind in ('denkmal', 'archaeologie', 'hq100', 'nsg', 'nationalpark', 'naturmonument', 'ffh', 'vsg')]
    return {'massing': m, 'check': evaluate(m, ctx), 'site': _site_payload(ctx, pack, meta), 'history': R.store().design_history(pid), 'notices': notices,
            'gate': {'mode': a.design_mode.value, 'reason_de': a.design_reason_de, 'override': bool(meta.get('override_blocked'))}}


class MassingBody(BaseModel):
    massing: Massing
    expected_version: int | None = Field(default=None, ge=0)


@design_router.post('/projects/{pid}/design/check')
def check_design(pid: str, body: MassingBody):
    _r()._need(pid)
    ctx, _, _ = ctx_for(pid)
    return evaluate(body.massing, ctx)


@design_router.post('/projects/{pid}/design/fit')
def fit_design(pid: str, body: MassingBody):
    _r()._need(pid)
    ctx, _, _ = ctx_for(pid)
    m, notes = fit(body.massing, ctx)
    return {'massing': m, 'notes_de': notes, 'check': evaluate(m, ctx)}


@design_router.post('/projects/{pid}/design/commit')
def commit_design(pid: str, body: MassingBody):
    R = _r()
    R._need(pid)
    ctx, _, _ = ctx_for(pid)
    chk = evaluate(body.massing, ctx)
    if not chk['hard_ok']:
        bad = '; '.join(f"{r['label_de']}: {r['message_de']}" for r in chk['results'] if r['hard'] and r['status'] == 'FAIL')
        raise HTTPException(422, f'Nicht speicherbar, harte Regel verletzt – {bad}')
    try:
        m = R.store().save_design(pid, body.massing, body.expected_version)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    return {'massing': m, 'check': chk, 'history': R.store().design_history(pid)}


class RestoreBody(BaseModel):
    version: int = Field(ge=1)
    expected_version: int = Field(ge=1)


@design_router.post('/projects/{pid}/design/restore')
def restore_design(pid: str, body: RestoreBody):
    """Non-destructive undo: an older revision is saved again as the newest one (if it still satisfies the hard rules)."""
    R = _r()
    R._need(pid)
    old = R.store().design_revision(pid, body.version)
    if old is None:
        raise HTTPException(404, 'Version nicht gefunden.')
    return commit_design(pid, MassingBody(massing=old.model_copy(update={'source': 'manual'}), expected_version=body.expected_version))


@design_router.get('/projects/{pid}/design/history')
def design_history(pid: str):
    R = _r()
    R._need(pid)
    return {'versions': R.store().design_history(pid)}


# ------------------------------------------------------------------------------------------------------------- several parcels
@design_router.get('/projects/{pid}/parcels')
def parcel_candidates(pid: str):
    """Selected parcels and the neighbours that could be added (they must share a boundary with the current plot)."""
    R = _r()
    R._need(pid)
    ctx, pack, _ = ctx_for(pid)
    sel = set(ctx.parcel_ids)
    out = []
    for p in pack['parcels']:
        poly = Polygon(p['ring']).buffer(0)
        shared = poly.buffer(0.3).intersection(ctx.site.buffer(0.3)).area / 0.6 if p['id'] not in sel else 0.0   # ≈ shared boundary length in m
        out.append({'id': p['id'], 'label': p['label'], 'area_m2': p.get('area_alkis_m2'), 'selected': p['id'] in sel, 'adjacent': shared >= 1.0, 'shared_m': round(shared, 1),
                    'ring': p['ring']})
    return {'max': MAX_PARCELS, 'selected': ctx.parcel_ids, 'primary_id': pack.get('site', {}).get('primary_id') or ctx.parcel_ids[0], 'parcels': out}


class ParcelChange(BaseModel):
    parcel_id: str = Field(min_length=3, max_length=80)
    action: str = Field(pattern='^(add|remove)$')


@design_router.post('/projects/{pid}/parcels')
def change_parcels(pid: str, body: ParcelChange):
    """Add or remove an adjacent parcel (max five). Each added parcel is screened on its own (no road/water/blocked land) and the site pack is rebuilt
    around the union with the project's original local frame, so existing designs keep their coordinates."""
    R = _r()
    R._need(pid)
    cand = parcel_candidates(pid)
    sel = list(cand['selected'])
    by_id = {p['id']: p for p in cand['parcels']}
    if body.action == 'add':
        p = by_id.get(body.parcel_id)
        if p is None:
            raise HTTPException(404, 'Flurstück liegt nicht im Umfeld dieses Projekts.')
        if p['selected']:
            return cand
        if len(sel) >= MAX_PARCELS:
            raise HTTPException(409, f'Höchstens {MAX_PARCELS} Flurstücke je Projekt.')
        if not p['adjacent']:
            raise HTTPException(409, 'Nur angrenzende Flurstücke können zusammengefasst werden.')
        pack = R.store().pack(pid)
        fr = pack['frame']
        rp = Polygon(p['ring']).buffer(0).representative_point()
        lon, lat = _TO_LL.transform(rp.x + fr['origin_e'], rp.y + fr['origin_n'])
        a2 = R.service().assess(lat, lon, stage='core')
        if a2.parcel is None or a2.parcel.national_reference != body.parcel_id:
            raise HTTPException(409, 'Flurstück konnte nicht amtlich bestätigt werden.')
        if a2.design_mode.value == 'blocked':
            raise HTTPException(409, f'Flurstück {p["label"]} ist nicht bebaubar: {a2.design_reason_de}')
        sel.append(body.parcel_id)
    else:
        if body.parcel_id == cand['primary_id']:
            raise HTTPException(409, 'Das Ausgangsflurstück kann nicht entfernt werden.')
        if body.parcel_id not in sel:
            return cand
        sel.remove(body.parcel_id)
        rest = unary_union([Polygon(by_id[i]['ring']).buffer(0.05) for i in sel])
        if rest.geom_type != 'Polygon':
            raise HTTPException(409, 'Nach dem Entfernen wäre das Grundstück nicht mehr zusammenhängend.')
    _rebuild(pid, sel)
    return parcel_candidates(pid)


def _rebuild(pid: str, sel: list[str]) -> None:
    R = _r()
    pack = R.store().pack(pid)
    fr = pack['frame']
    by_id = {p['id']: p for p in pack['parcels']}
    union = unary_union([Polygon(by_id[i]['ring']).buffer(0.05) for i in sel]).buffer(-0.05)
    if union.geom_type != 'Polygon':
        union = max(union.geoms, key=lambda g: g.area)
    union_ll = transform(lambda x, y, z=None: _TO_LL.transform(x + fr['origin_e'], y + fr['origin_n']), union)
    a = R.store().assessment(pid)
    sp = R.build_sitepack(R.service().fetcher, a, site_ll=union_ll, origin=(fr['origin_e'], fr['origin_n']), site_ids=sel)
    have = {p['id'] for p in sp.manifest['parcels']}
    for i in sel:                      # the WFS page limit can drop a selected parcel: keep its known ring (same origin, so the local ring stays valid)
        if i not in have:
            sp.manifest['parcels'].append({**by_id[i], 'is_site': True})
    R.store().replace_pack(pid, sp)
    area = sum(p.get('area_alkis_m2') or 0 for p in sp.manifest['parcels'] if p['id'] in sel)
    labels = [p['label'] for p in sp.manifest['parcels'] if p['id'] in sel]
    R.store().update_meta(pid, parcel_ids=sel, area_m2=round(area, 1), parcel_label=', '.join(labels),
                          terrain_ok=sp.manifest['terrain']['status'] == 'OK', ortho_ok=sp.manifest['ortho']['status'] == 'OK')
    R._make_thumb(pid=pid, pack=sp.manifest)


@design_router.post('/projects/{pid}/repair')
def repair_project(pid: str):
    """Fetch terrain, orthophoto and neighbourhood again for the project's current parcels (a stuck 'Daten fehlen' project, or a failed first download)."""
    R = _r()
    R._need(pid)
    meta = R.store().meta(pid)
    pack = R.store().pack(pid)
    sel = meta.get('parcel_ids') or [p['id'] for p in pack['parcels'] if p.get('is_site')]
    if not sel:
        raise HTTPException(409, 'Für dieses Projekt ist kein Flurstück gespeichert. Bitte neu anlegen.')
    _rebuild(pid, sel)
    m = R.store().meta(pid)
    return {'terrain_ok': m['terrain_ok'], 'ortho_ok': m['ortho_ok']}


# ------------------------------------------------------------------------------------------------------------- AI generation, references, rendering
import base64 as _b64  # noqa: E402
import binascii as _binascii  # noqa: E402
from fastapi import Response  # noqa: E402
from . import ai  # noqa: E402

MAX_REF_BYTES = 12_000_000
REF_TYPES = {'image/png', 'image/jpeg', 'image/webp', 'application/pdf'}


@design_router.get('/ai/status')
def ai_status():
    return ai.status()


class RefUpload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    media_type: str
    data_b64: str
    kind: str = Field(default='foto', pattern='^(foto|plan)$')


@design_router.post('/projects/{pid}/references')
def add_reference(pid: str, body: RefUpload):
    R = _r()
    R._need(pid)
    if body.media_type not in REF_TYPES:
        raise HTTPException(415, 'Erlaubt sind PNG, JPEG, WebP und PDF.')
    try:
        data = _b64.b64decode(body.data_b64.split(',', 1)[-1], validate=True)
    except (_binascii.Error, ValueError) as e:
        raise HTTPException(422, 'Datei nicht lesbar (Base64).') from e
    if len(data) > MAX_REF_BYTES:
        raise HTTPException(413, 'Höchstens 12 MB je Datei.')
    sig = {'image/png': b'\x89PNG', 'image/jpeg': b'\xff\xd8', 'application/pdf': b'%PDF', 'image/webp': b'RIFF'}[body.media_type]
    if not data.startswith(sig):
        raise HTTPException(415, 'Dateiinhalt passt nicht zum Dateityp.')
    return R.store().save_reference(pid, body.name, data, {'media_type': body.media_type, 'kind': body.kind})


@design_router.get('/projects/{pid}/references')
def list_references(pid: str):
    R = _r()
    R._need(pid)
    return {'references': R.store().references(pid)}


@design_router.get('/projects/{pid}/references/{rid}/file')
def reference_file(pid: str, rid: str):
    R = _r()
    R._need(pid)
    try:
        data, rec = R.store().reference_bytes(pid, rid)
    except KeyError as e:
        raise HTTPException(404, 'Referenz nicht gefunden.') from e
    return Response(data, media_type=rec['media_type'], headers={'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'inline'})


@design_router.delete('/projects/{pid}/references/{rid}')
def delete_reference(pid: str, rid: str):
    R = _r()
    R._need(pid)
    try:
        R.store().delete_reference(pid, rid)
    except KeyError as e:
        raise HTTPException(404, 'Referenz nicht gefunden.') from e
    return {'deleted': rid}


# ------------------------------------------------------------------------------------------------------------- own planning limits
@design_router.get('/projects/{pid}/limits')
def get_limits(pid: str):
    R = _r()
    R._need(pid)
    return {'limits': R.store().limits(pid), 'verified': R.store().verified(pid)}


@design_router.put('/projects/{pid}/limits')
def put_limits(pid: str, body: PlanningLimits):
    """Own planning limits without a verification statement. Enforced in the studio as hard limits, labelled as own limit (not B-Plan-verified).
    An all-empty body removes them."""
    R = _r()
    R._need(pid)
    empty = all(getattr(body, f) in (None, []) for f in ('grz', 'gfz', 'max_building_height_meters', 'max_stories', 'setback_lines_offset_meters', 'roof_types_allowed',
                                                          'roof_pitch_min_deg', 'roof_pitch_max_deg', 'max_eave_height_meters'))
    if body.roof_pitch_min_deg is not None and body.roof_pitch_max_deg is not None and body.roof_pitch_min_deg > body.roof_pitch_max_deg:
        raise HTTPException(422, 'Dachneigung: „von“ ist größer als „bis“.')
    R.store().save_limits(pid, None if empty else body)
    m = _ensure_design(pid)
    ctx, _, _ = ctx_for(pid)
    return {'limits': None if empty else body, 'check': evaluate(m, ctx)}
