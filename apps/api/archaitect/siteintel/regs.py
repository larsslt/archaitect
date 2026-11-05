"""Rule engine of the studio: checks a massing against the plot and the planning rules, with honest provenance per rule.

Four kinds of rules:
- PARCEL_GEOMETRY (hard): every volume lies inside the official plot (ALKIS, union of the selected parcels) and does not cut into
  existing buildings that are kept. Pure geometry, no legal judgement, therefore enforced.
- BPLAN_VERIFIED (hard): GRZ, GFZ, height, eave height, storeys, roof form/pitch and the building envelope, only when a person entered them
  with document and clause (``VerifiedConstraints``). Then enforced, because the user stated them as binding.
- HBO_DERIVED (warning): Abstandsflächen nach § 6 HBO computed from the statutory formula. Shown, never enforced: exceptions, Baulasten,
  B-Plan-Festsetzungen and the reading of the norm by the Bauaufsicht can differ.
- CONTEXT (info): what the surroundings look like (for § 34 BauGB "Einfügen"); a hint, not a rule.

Nothing here is a building permit or a legal determination.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from shapely.geometry import LineString, MultiPolygon, Polygon
import shapely
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from types import SimpleNamespace
from .dossier import PlanningLimits, VerifiedConstraints
from .massing import ROOF_DE, Massing, Volume, effective_storeys, support_elevations

HBO_SOURCE = ('§ 6 Abs. 4–5 HBO, amtliche Broschüre Oktober 2025/Korrektur April 2026, PDF-Seite 16; '
              'Regelfall 0,4 H, mindestens 2,50 m. '
              'Grundformel und Dachanrechnung am 02.11.2026 visuell im Primärtext geprüft. '
              'https://wirtschaft.hessen.de/sites/wirtschaft.hessen.de/files/2026-04/hbo_broschuere_stand_oktober_2025-baupaket_i.pdf#page=16 '
              'Projektanwendung bleibt Näherung: tatsächliches Gelände, Dachaufbauten, Grenzbauten und Ausnahmen gesondert prüfen.')

HBO_FACTOR = 0.4
HBO_MIN_M = 2.5
ROAD_CODES = ('4_1_1',)
EPS = 0.02


def hbo_depth(h: float, factor: float = HBO_FACTOR) -> float:
    return max(HBO_MIN_M, math.floor(factor * h * 10 + 1e-9) / 10)


def roof_credit(pitch_deg: float) -> float:
    """Share of the roof height added to the wall height H (secondary source; flagged in HBO_SOURCE)."""
    return 1.0 if pitch_deg > 70 else (1 / 3 if pitch_deg > 45 else 0.0)


GRID = 0.001     # 1 mm precision grid: keeps GEOS overlay operations robust on nearly collinear ALKIS edges


def clean(g):
    """Valid geometry snapped to the 1 mm grid (avoids GEOS TopologyException 'side location conflict' on near-degenerate overlays)."""
    if g is None or g.is_empty:
        return g
    if not g.is_valid:
        g = shapely.make_valid(g)
    g = shapely.set_precision(g, GRID)
    if g.geom_type == 'GeometryCollection':
        polys = [x for x in g.geoms if x.geom_type in ('Polygon', 'MultiPolygon')]
        g = unary_union(polys) if polys else Polygon()
    if g.geom_type == 'Polygon':
        g = orient(g, 1.0)
    return g


def _poly(ring: list[list[float]]) -> Polygon:
    return clean(Polygon(ring))


def _rings(g) -> list[list[list[float]]]:
    if g is None or g.is_empty:
        return []
    geoms = g.geoms if hasattr(g, 'geoms') else [g]
    out = []
    for x in geoms:
        if x.geom_type == 'Polygon' and x.area > 0.01:
            out.append([[round(a, 2), round(b, 2)] for a, b in x.exterior.coords])
    return out


@dataclass
class Existing:
    id: str
    poly: Polygon
    floors: int | None
    height_m: float | None
    height_basis: str | None = None


@dataclass
class SiteCtx:
    site: Polygon                         # union of the selected parcels (local frame)
    area_m2: float                        # ALKIS area (sum) — the legal reference for GRZ/GFZ
    existing: list[Existing]              # buildings on the plot
    neighbours: list[Existing]            # buildings around (for context only)
    roads: list[Polygon]                  # ALKIS land use "Straßenverkehr"
    verified: SimpleNamespace | None      # effective limits: verified B-Plan values, gaps filled with the user's own limits
    envelope: Polygon | None              # building envelope (local)
    terrain: dict | None = None
    parcel_ids: list[str] = field(default_factory=list)
    src: dict = field(default_factory=dict)        # field -> 'BPLAN_VERIFIED' | 'USER_LIMIT'
    src_text: dict = field(default_factory=dict)   # basis -> source sentence
    reference: dict | None = None                  # Richtwert-Rahmen aus der Umgebung (reference.build), never binding

    def basis(self, fld: str) -> str:
        return self.src.get(fld, 'BPLAN_VERIFIED')

    def source(self, fld: str) -> str | None:
        return self.src_text.get(self.src.get(fld, ''), None)

    def z(self, x: float, y: float) -> float | None:
        t = self.terrain
        if not t:
            return None
        fx = (x - t['x_west_local']) / t['cell_m']
        fy = (t['y_north_local'] - y) / t['cell_m']
        c = max(0.0, min(t['cols'] - 1.001, fx))
        r = max(0.0, min(t['rows'] - 1.001, fy))
        c0, r0 = int(c), int(r)
        tx, ty = c - c0, r - r0
        H = t['heights_m']
        vals = [H[r0][c0], H[r0][c0 + 1], H[r0 + 1][c0], H[r0 + 1][c0 + 1]]
        if any(v is None for v in vals):
            ok = [v for v in vals if v is not None]
            return sum(ok) / len(ok) if ok else None
        return (vals[0] * (1 - tx) + vals[1] * tx) * (1 - ty) + (vals[2] * (1 - tx) + vals[3] * tx) * ty

    def kept(self, m: Massing) -> list[Existing]:
        return [e for e in self.existing if e.id not in set(m.demolish)]

    def hard_region(self, m: Massing):
        region = self.site
        if self.envelope is not None:
            region = clean(region.intersection(self.envelope))
        kept = [e.poly for e in self.kept(m)]
        if kept:
            region = clean(region.difference(clean(unary_union(kept))))
        return region

    def road_allowance(self) -> Polygon | MultiPolygon | None:
        """Abstandsflächen may extend onto public roads up to their middle (§ 6 Abs. 2 HBO, nach Sekundärquelle). The middle is estimated from the
        ALKIS road polygon (half width ≈ area / perimeter of the adjacent piece) — an estimate, flagged in the message."""
        parts = []
        near = self.site.buffer(1.0)
        for r in self.roads:
            if not r.intersects(near):
                continue
            piece = r.intersection(self.site.buffer(40))
            if piece.is_empty or piece.length == 0:
                continue
            half = max(1.0, min(15.0, piece.area / piece.length))
            parts.append(clean(r.intersection(self.site.buffer(half))))
        return clean(unary_union(parts)) if parts else None


LIMIT_FIELDS = ('grz', 'gfz', 'max_building_height_meters', 'max_stories', 'setback_lines_offset_meters', 'roof_types_allowed', 'roof_pitch_min_deg', 'roof_pitch_max_deg', 'max_eave_height_meters')
USER_SOURCE = 'Eigene Planungsvorgabe (nicht als Bebauungsplan geprüft)'


def merge_limits(verified: VerifiedConstraints | None, user: PlanningLimits | None) -> tuple[SimpleNamespace | None, dict, dict]:
    """Per field: a verified B-Plan value wins; otherwise the user's own limit applies. Both are hard in the studio; the basis is reported per rule."""
    if verified is None and user is None:
        return None, {}, {}
    vals, src = {}, {}
    for f in LIMIT_FIELDS:
        vv = getattr(verified, f, None) if verified else None
        uv = getattr(user, f, None) if user else None
        if vv not in (None, []):
            vals[f], src[f] = vv, 'BPLAN_VERIFIED'
        elif uv not in (None, []):
            vals[f], src[f] = uv, 'USER_LIMIT'
        else:
            vals[f] = [] if f == 'roof_types_allowed' else None
    texts = {}
    if verified:
        texts['BPLAN_VERIFIED'] = f'{verified.basis_de} · geprüft von {verified.verified_by}'
    if user:
        texts['USER_LIMIT'] = USER_SOURCE + (f': {user.note_de}' if user.note_de else '')
    ns = SimpleNamespace(**vals, basis_de=texts.get('BPLAN_VERIFIED') or texts.get('USER_LIMIT'))
    return ns, src, texts


def site_ctx(pack: dict, verified: VerifiedConstraints | None, envelope_local: list[list[float]] | None, parcel_ids: list[str] | None = None,
             user_limits: PlanningLimits | None = None) -> SiteCtx:
    site_parcels = [p for p in pack['parcels'] if (p['id'] in parcel_ids if parcel_ids else p['is_site'])]
    site = clean(unary_union([_poly(p['ring']) for p in site_parcels]))
    if site.geom_type != 'Polygon':
        site = max(site.geoms, key=lambda g: g.area) if hasattr(site, 'geoms') else site
    area = sum(p.get('area_alkis_m2') or _poly(p['ring']).area for p in site_parcels)
    ex, nb = [], []
    for b in pack.get('buildings', []):
        poly = _poly(b['ring'])
        on = poly.intersection(site).area / max(poly.area, 0.1) >= 0.5
        (ex if on else nb).append(Existing(b['id'], poly, b.get('floors'), b.get('height_est_m'), b.get('height_basis')))
    roads = [_poly(lu['ring']) for lu in pack.get('landuse', []) if (lu.get('code') or '').startswith(ROAD_CODES)]
    terr = pack['terrain']['grid'] if pack.get('terrain', {}).get('status') == 'OK' else None
    eff, src, texts = merge_limits(verified, user_limits)
    env = _poly(envelope_local) if envelope_local and len(envelope_local) >= 3 else None
    if env is not None:
        src['envelope'] = 'BPLAN_VERIFIED'
    if eff is not None and eff.setback_lines_offset_meters and (env is None or src.get('setback_lines_offset_meters') == 'USER_LIMIT'):
        e = site.buffer(-eff.setback_lines_offset_meters, join_style=2)
        if not e.is_empty:
            env = e if env is None else env.intersection(e)
            src['envelope'] = src.get('envelope') if src.get('envelope') == 'BPLAN_VERIFIED' and src.get('setback_lines_offset_meters') != 'USER_LIMIT' else src['setback_lines_offset_meters']
    return SiteCtx(site=site, area_m2=area, existing=ex, neighbours=nb, roads=roads, verified=eff, envelope=env, terrain=terr, parcel_ids=[p['id'] for p in site_parcels], src=src, src_text=texts)


# ------------------------------------------------------------------------------------------------------------------- evaluation
def _res(rid: str, label: str, status: str, basis: str, hard: bool, msg: str, observed=None, limit=None, source: str | None = None) -> dict:
    return {'id': rid, 'label_de': label, 'status': status, 'basis': basis, 'hard': hard, 'message_de': msg, 'observed': observed, 'limit': limit, 'source_de': source}


def base_level(m: Massing, ctx: SiteCtx) -> float:
    zs = []
    for v in m.volumes:
        for x, y in list(v.footprint().exterior.coords)[::2]:
            z = ctx.z(x, y)
            if z is not None:
                zs.append(z)
    return min(zs) if zs else 0.0


def abstandsflaechen(m: Massing, ctx: SiteCtx) -> list[dict]:
    """One rectangle per exterior wall segment, depth from its own height H (terrain at the wall middle, roof credit by pitch)."""
    z0 = base_level(m, ctx)
    fps = {v.id: orient(clean(v.footprint()), 1.0) for v in m.volumes}       # CCW after snapping: outward normals below rely on it
    out = []
    for v in m.volumes:
        if v.role == 'garage' and v.elevation_m == 0 and v.eave_m <= 3.0:
            continue                              # Grenzgarage: separate info rule
        others = clean(unary_union([f for k, f in fps.items() if k != v.id])) if len(fps) > 1 else None
        if v.shape == 'round':
            # one annulus instead of 64 wall facets; H at the lowest ground around the cylinder
            ring_pts = list(fps[v.id].exterior.coords)[::8]
            zs = [ctx.z(x, y) for x, y in ring_pts]
            drop = min((z - z0) for z in zs if z is not None) if any(z is not None for z in zs) else 0.0
            h = max(0.0, v.elevation_m + v.eave_m - drop + roof_credit(v.roof_pitch_deg) * v.roof_rise_m)
            t = hbo_depth(h)
            ann = clean(clean(fps[v.id].buffer(t, 16)).difference(fps[v.id]))
            if others is not None:
                ann = clean(ann.difference(others))
            out.append({'volume_id': v.id, 'wall': 0, 'H_m': round(h, 2), 'depth_m': t, 'poly': ann})
            continue
        ring = list(fps[v.id].exterior.coords)
        for i in range(len(ring) - 1):
            (x1, y1), (x2, y2) = ring[i], ring[i + 1]
            seg = LineString([(x1, y1), (x2, y2)])
            if seg.length < 0.2:
                continue
            if others is not None:
                rest = seg.difference(others.buffer(-0.01)) if not others.buffer(-0.01).is_empty else seg
                if rest.is_empty or rest.length < 0.2:
                    continue
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            zt = ctx.z(mx, my)
            drop = (zt - z0) if zt is not None else 0.0
            wall = v.elevation_m + v.eave_m - drop
            if v.roof == 'pult':
                # the high side of a mono-pitch roof is a real wall: find whether this edge is on the high side
                hi = _pult_high_edge(v)
                if hi is not None and abs((mx - hi[0]) * hi[2] + (my - hi[1]) * hi[3]) < 0.05 * max(v.width_m, v.depth_m) + 0.05:
                    wall += v.roof_rise_m
                else:
                    wall += roof_credit(v.roof_pitch_deg) * v.roof_rise_m
            else:
                wall += roof_credit(v.roof_pitch_deg) * v.roof_rise_m
            h = max(0.0, wall)
            t = hbo_depth(h)
            dx, dy = x2 - x1, y2 - y1
            ln = math.hypot(dx, dy)
            nx, ny = dy / ln, -dx / ln            # outward for a CCW ring
            rect = clean(Polygon([(x1, y1), (x2, y2), (x2 + nx * t, y2 + ny * t), (x1 + nx * t, y1 + ny * t)]))
            if others is not None:
                rect = clean(rect.difference(others))
            out.append({'volume_id': v.id, 'wall': i, 'H_m': round(h, 2), 'depth_m': t, 'poly': rect})
    return out


def _pult_high_edge(v: Volume):
    """Point on the high edge + its normal (direction of rise) for a rectangular mono-pitch roof."""
    if v.shape != 'rect':
        return None
    a = math.radians(v.rotation_deg)
    ux, uy = math.cos(a), math.sin(a)
    vx, vy = -math.sin(a), math.cos(a)
    if v.ridge_along == 'width':          # rises towards +depth
        return (v.cx + vx * v.depth_m / 2, v.cy + vy * v.depth_m / 2, vx, vy)
    return (v.cx + ux * v.width_m / 2, v.cy + uy * v.width_m / 2, ux, uy)


def evaluate(m: Massing, ctx: SiteCtx) -> dict:
    res: list[dict] = []
    v = ctx.verified
    fps = {x.id: clean(x.footprint()) for x in m.volumes}
    union = clean(unary_union(list(fps.values())))
    kept = ctx.kept(m)

    # --- hard: plot geometry
    outside = union.difference(ctx.site.buffer(EPS))
    res.append(_res('PARCEL', 'Lage im Grundstück', 'FAIL' if outside.area > 0.05 else 'PASS', 'PARCEL_GEOMETRY', True,
                    f'{outside.area:.1f} m² ragen über die Flurstücksgrenze.' if outside.area > 0.05 else 'Alle Baukörper liegen innerhalb der amtlichen Flurstücksgrenze.',
                    round(outside.area, 2), 0, 'ALKIS-Flurstück(e), Liegenschaftskataster Hessen'))
    clash = [e.id for e in kept if e.poly.buffer(-EPS).intersects(union)]
    if ctx.existing:
        res.append(_res('EXISTING', 'Bestand auf dem Grundstück', 'FAIL' if clash else 'PASS', 'PARCEL_GEOMETRY', True,
                        f'Entwurf schneidet {len(clash)} Bestandsgebäude. Bestand entfernen oder Baukörper verschieben.' if clash else
                        f'{len(kept)} Bestandsgebäude bleiben, {len(m.demolish)} als Abriss angenommen (Abriss ist genehmigungs- bzw. anzeigepflichtig zu prüfen).',
                        len(clash), 0, 'ALKIS-Gebäude'))

    # --- B-Plan values (hard only when verified)
    area = ctx.area_m2
    met = m.metrics()
    fp_kept = sum(e.poly.intersection(ctx.site).area for e in kept)
    fp_main = met['footprint_main_m2'] + fp_kept
    fp_all = met['footprint_m2'] + fp_kept
    gfa = met['gross_floor_area_m2'] + sum((e.floors or 0) * e.poly.area for e in kept)
    z0 = base_level(m, ctx)
    top = max(x.top_m for x in m.volumes)
    eave = max(x.elevation_m + x.eave_m for x in m.volumes)

    def limit(rid, label, val, lim, fmt, unit, extra='', fld=''):
        ref = (getattr(ctx, 'reference', None) or {}).get({'GRZ': 'grz', 'GFZ': 'gfz', 'STOREYS': 'max_storeys', 'HEIGHT': 'max_height_m'}.get(rid, ''))
        if lim is None and ref is not None:      # no binding value: the surroundings give a frame to design in (not law)
            ok = val <= float(ref) + 1e-6
            res.append(_res(rid, label, 'PASS' if ok else 'WARN', 'CONTEXT_REFERENCE', False,
                            f'{fmt(val)}{unit} bei einem Richtwert der Umgebung von {fmt(float(ref))}{unit}{extra}. Keine Festsetzung. ' + ('Innerhalb des Rahmens.' if ok else 'Über dem Richtwert: vermutlich Genehmigung bzw. Befreiung nötig.'),
                            round(val, 3), float(ref), '; '.join((ctx.reference or {}).get('sources', [])) or None))
        elif lim is None:
            res.append(_res(rid, label, 'UNKNOWN', 'BPLAN_VERIFIED', False, f'Keine Grenze festgelegt (Ist-Wert {fmt(val)}{unit}{extra}). Wert unter „Vorschriften“ eintragen.', round(val, 3), None))
        else:
            ok = val <= lim + 1e-6
            res.append(_res(rid, label, 'PASS' if ok else 'FAIL', ctx.basis(fld), True, f'{fmt(val)}{unit} von höchstens {fmt(lim)}{unit}{extra}.', round(val, 3), lim, ctx.source(fld)))

    f2 = lambda x: f'{x:.2f}'.replace('.', ',')
    f1 = lambda x: f'{x:.1f}'.replace('.', ',')
    limit('GRZ', 'Grundflächenzahl (GRZ)', fp_main / area, v.grz if v else None, f2, '', f' · {fp_main:.0f} m² von {area:.0f} m², inkl. Bestand', 'grz')
    if v and v.grz:
        cap = min(v.grz * 1.5, 0.8)
        res.append(_res('GRZ2', 'GRZ inkl. Garagen/Nebenanlagen', 'UNKNOWN', ctx.basis('grz'), False,
                        f'Ermittelter Näherungswert {f2(fp_all / area)}; Orientierungswert {f2(cap)}. Maßgebliche BauNVO-Fassung, Nebenanlagen und örtliche Ausnahmen gesondert prüfen.', round(fp_all / area, 3), None, ctx.source('grz')))
    limit('GFZ', 'Geschossflächenzahl (GFZ)', gfa / area, v.gfz if v else None, f2, '', f' · {gfa:.0f} m² Geschossfläche der Vollgeschosse', 'gfz')
    eff_st = effective_storeys(m.volumes)
    limit('STOREYS', 'Vollgeschosse', float(max(eff_st.values())), float(v.max_stories) if v and v.max_stories else None, lambda x: f'{x:.0f}', '',
          ' · gestapelte Baukörper zählen zusammen, Dachgeschoss als Nicht-Vollgeschoss angenommen', 'max_stories')
    limit('HEIGHT', 'Gebäudehöhe', top, v.max_building_height_meters if v else None, f1, ' m', ' · über tiefstem Geländepunkt am Gebäude', 'max_building_height_meters')
    sb = (getattr(ctx, 'reference', None) or {}).get('setback_m')
    if sb and not (v and getattr(v, 'setback_lines_offset_meters', None)):
        dmin = min((x.footprint().exterior.distance(ctx.site.exterior) if ctx.site.contains(x.footprint()) else 0.0) for x in m.volumes)
        ok = dmin + 0.05 >= sb
        res.append(_res('SETBACK_REF', 'Grenzabstand (Richtwert Umgebung)', 'PASS' if ok else 'WARN', 'CONTEXT_REFERENCE', False,
                        f'Geringster Abstand zur Grundstücksgrenze {f1(dmin)} m, typisch in der Umgebung {f1(sb)} m. Keine Festsetzung; die Abstandsflächen nach HBO werden gesondert geprüft.'
                        + ('' if ok else ' Unter dem üblichen Abstand: vermutlich Abstimmung mit der Bauaufsicht nötig.'), round(dmin, 2), float(sb),
                        '; '.join((ctx.reference or {}).get('sources', [])) or None))
    if v and v.max_eave_height_meters:
        limit('EAVE', 'Traufhöhe', eave, v.max_eave_height_meters, f1, ' m', '', 'max_eave_height_meters')
    # roof form / pitch
    roofs = {x.roof for x in m.volumes if x.role != 'garage'}
    allowed = {r for r in (v.roof_types_allowed if v else []) if r != 'egal'}
    if allowed:
        bad = sorted(r for r in roofs if r not in allowed and not (r == 'walm' and 'kruppelwalm' in allowed))
        res.append(_res('ROOF', 'Dachform', 'FAIL' if bad else 'PASS', ctx.basis('roof_types_allowed'), True,
                        f'Nicht zulässig: {", ".join(ROOF_DE[r] for r in bad)}. Zulässig: {", ".join(ROOF_DE.get(r, r) for r in sorted(allowed))}.' if bad else f'Zulässig: {", ".join(ROOF_DE.get(r, r) for r in sorted(allowed))}.', None, None, ctx.source('roof_types_allowed')))
    else:
        res.append(_res('ROOF', 'Dachform', 'UNKNOWN', 'BPLAN_VERIFIED', False, 'Keine Grenze festgelegt. Zulässige Dachformen unter „Vorschriften“ eintragen.'))
    pitches = [x.roof_pitch_deg for x in m.volumes if x.roof != 'flach' and x.role != 'garage']
    if v and (v.roof_pitch_min_deg is not None or v.roof_pitch_max_deg is not None) and pitches:
        lo, hi = v.roof_pitch_min_deg or 0, v.roof_pitch_max_deg or 90
        bad = [p for p in pitches if p < lo - 1e-6 or p > hi + 1e-6]
        fld = 'roof_pitch_min_deg' if v.roof_pitch_min_deg is not None else 'roof_pitch_max_deg'
        res.append(_res('PITCH', 'Dachneigung', 'FAIL' if bad else 'PASS', ctx.basis(fld), True, f'Neigung {", ".join(f"{p:.0f}°" for p in pitches)}, zulässig {lo:.0f}–{hi:.0f}°.', None, None, ctx.source(fld)))
    if ctx.envelope is not None:
        out_env = union.difference(ctx.envelope.buffer(EPS))
        res.append(_res('ENVELOPE', 'Baufenster', 'FAIL' if out_env.area > 0.05 else 'PASS', ctx.basis('envelope'), True,
                        f'{out_env.area:.1f} m² außerhalb des Baufensters.' if out_env.area > 0.05 else 'Innerhalb des Baufensters.', round(out_env.area, 2), 0, ctx.source('envelope')))

    # --- HBO Abstandsflächen (warning)
    afs = abstandsflaechen(m, ctx)
    road = ctx.road_allowance()
    allowed_area = clean(ctx.site.union(road)) if road is not None else ctx.site
    allowed_buf = clean(allowed_area.buffer(EPS))
    viol = []
    for a in afs:
        ex = clean(a['poly'].difference(allowed_buf))
        a['excess_m2'] = round(ex.area, 2)
        a['ok'] = ex.area <= 0.05
        if not a['ok']:
            viol.append(ex)
    overlap = []
    for e in kept:
        for a in afs:
            if a['poly'].buffer(-EPS).intersects(e.poly):
                overlap.append(e.id)
                break
    nbad = sum(1 for a in afs if not a['ok'])
    dmin = min((a['depth_m'] for a in afs), default=None)
    dmax = max((a['depth_m'] for a in afs), default=None)
    bad_vols = sorted({a['volume_id'] for a in afs if not a['ok']})
    names = {x.id: x.name for x in m.volumes}
    msg = (f'Abstandsflächen von {", ".join(names[i] for i in bad_vols)} reichen über das Grundstück ({f1(sum(x.area for x in viol))} m², {nbad} Wandabschnitte).' if nbad else
           f'Alle {len(afs)} Abstandsflächen liegen auf dem Grundstück' + (' bzw. bis zur geschätzten Straßenmitte' if road is not None else '') + '.')
    if afs:
        msg += f' Tiefen {f1(dmin)}–{f1(dmax)} m.' if dmin != dmax else f' Tiefe {f1(dmin)} m.'
    res.append(_res('HBO_ABSTAND', 'Abstandsflächen (§ 6 HBO)', 'WARN' if nbad else 'PASS', 'HBO_DERIVED', False, msg, round(sum(x.area for x in viol), 2), 0, HBO_SOURCE))
    if overlap:
        res.append(_res('HBO_OVERLAP', 'Abstandsflächen und Bestand', 'WARN', 'HBO_DERIVED', False,
                        f'Abstandsflächen überdecken {len(overlap)} verbleibende Bestandsgebäude (Überdeckungsverbot § 6 Abs. 3 HBO, Ausnahmen möglich).', len(overlap), 0, HBO_SOURCE))
    garages = [x for x in m.volumes if x.role == 'garage' and x.eave_m <= 3.0 and x.elevation_m == 0]
    if garages:
        res.append(_res('HBO_GARAGE', 'Grenzgarage', 'INFO', 'HBO_DERIVED', False,
                        'Garagen bis 3 m Wandhöhe ohne eigene Abstandsfläche angenommen (§ 6 HBO, Grenzbebauung). Längen- und Wandflächengrenzen je Nachbargrenze gegen den Primärtext prüfen.', None, None, HBO_SOURCE))
    if road is not None:
        res.append(_res('HBO_ROAD', 'Straßenseite', 'INFO', 'HBO_DERIVED', False,
                        'Abstandsflächen dürfen bis zur Mitte öffentlicher Verkehrsflächen reichen; die Straßenmitte ist aus der ALKIS-Bodennutzung geschätzt.', None, None, HBO_SOURCE))

    # --- context (§ 34 BauGB hint)
    near = [e for e in ctx.neighbours if e.poly.distance(ctx.site) < 60]
    fl = sorted(e.floors for e in near if e.floors)
    if fl:
        med = fl[len(fl) // 2]
        res.append(_res('CONTEXT', 'Umgebung (§ 34 BauGB)', 'INFO', 'CONTEXT', False,
                        f'{len(near)} Gebäude im Umkreis von 60 m, Geschosse {fl[0]}–{fl[-1]} (Median {med}). Ohne Bebauungsplan muss sich das Vorhaben einfügen; das entscheidet die Bauaufsicht.',
                        float(met['max_storeys']), float(fl[-1])))

    hard_fail = [r for r in res if r['hard'] and r['status'] == 'FAIL']
    warn = [r for r in res if r['status'] == 'WARN']
    unknown = [r for r in res if r['status'] == 'UNKNOWN']
    overall = 'FAIL' if hard_fail else ('WARN' if warn else ('UNKNOWN' if unknown else 'PASS'))
    return {
        'overall': overall, 'hard_ok': not hard_fail, 'results': res,
        'metrics': {**met, 'site_area_m2': round(area, 1), 'grz': round(fp_main / area, 3), 'gfz': round(gfa / area, 3), 'base_level_m': round(z0, 2),
                    'kept_existing_footprint_m2': round(fp_kept, 1), 'top_m': round(top, 2)},
        'overlays': {'abstandsflaechen': [{'volume_id': a['volume_id'], 'ring': (_rings(a['poly']) or [None])[0], 'H_m': a['H_m'], 'depth_m': a['depth_m'], 'ok': a['ok']} for a in afs if _rings(a['poly'])],
                     'violations': [r for g in viol for r in _rings(g)], 'road_allowance': _rings(road)},
        'limits': limits(m, ctx),
        'disclaimer_de': 'Vorprüfung auf Basis amtlicher Geometrie und eingetragener Werte. Keine Baugenehmigung, keine Rechtsberatung.',
    }


def limits(m: Massing, ctx: SiteCtx) -> dict:
    """What the editor must enforce on its own (hard rules), so dragging and sliders stop at the limit instead of producing invalid states."""
    v = ctx.verified
    region = ctx.hard_region(m)
    kept_fp = sum(e.poly.intersection(ctx.site).area for e in ctx.kept(m))
    out = {'region': _rings(region), 'holes': [[[round(a, 2), round(b, 2)] for a, b in i.coords] for g in (region.geoms if hasattr(region, 'geoms') else [region]) if g.geom_type == 'Polygon' for i in g.interiors],
           'site_area_m2': round(ctx.area_m2, 1), 'max_footprint_main_m2': None, 'max_footprint_all_m2': None, 'max_gfa_m2': None,
           'max_storeys': None, 'max_height_m': None, 'max_eave_m': None, 'roofs_allowed': None, 'pitch_min_deg': None, 'pitch_max_deg': None,
           'basis': {k: ctx.src.get(f) for k, f in (('grz', 'grz'), ('gfz', 'gfz'), ('max_storeys', 'max_stories'), ('max_height_m', 'max_building_height_meters'), ('max_eave_m', 'max_eave_height_meters'),
                                                    ('roofs_allowed', 'roof_types_allowed'), ('pitch', 'roof_pitch_min_deg'), ('envelope', 'envelope'))}}
    if v:
        if v.grz:
            out['max_footprint_main_m2'] = round(v.grz * ctx.area_m2 - kept_fp, 1)
        if v.gfz:
            out['max_gfa_m2'] = round(v.gfz * ctx.area_m2 - sum((e.floors or 0) * e.poly.area for e in ctx.kept(m)), 1)
        out['max_storeys'] = v.max_stories
        out['max_height_m'] = v.max_building_height_meters
        out['max_eave_m'] = v.max_eave_height_meters
        allowed = [r for r in v.roof_types_allowed if r != 'egal']
        if allowed:
            out['roofs_allowed'] = sorted(set(allowed) | ({'walm'} if 'kruppelwalm' in allowed else set()))
        out['pitch_min_deg'] = v.roof_pitch_min_deg
        out['pitch_max_deg'] = v.roof_pitch_max_deg
    return out


# ------------------------------------------------------------------------------------------------------------------- fitting
def fit(m: Massing, ctx: SiteCtx) -> tuple[Massing, list[str]]:
    """Bring a proposed massing (e.g. from the AI) inside all hard rules: roof/pitch/storeys/height caps, then position and size inside the region,
    then GRZ/GFZ by uniform scaling. Returns the fitted massing and what was changed (German, for the user)."""
    from shapely.ops import polylabel
    notes: list[str] = []
    lim = limits(m, ctx)
    region = ctx.hard_region(m)
    if region.is_empty:
        return m, ['Kein bebaubarer Bereich: Grundstück vollständig durch Bestand oder Baufenster belegt.']
    big = max(region.geoms, key=lambda g: g.area) if hasattr(region, 'geoms') else region
    target = polylabel(big, 0.1)
    vols = []
    for v in m.volumes:
        upd = {}
        if lim['roofs_allowed'] and v.role != 'garage' and v.roof not in lim['roofs_allowed']:
            from .massing import ROOFS_BY_SHAPE
            alt = next((r for r in lim['roofs_allowed'] if r in ROOFS_BY_SHAPE[v.shape]), None)
            if alt:
                upd['roof'] = alt
                notes.append(f'{v.name}: Dach auf {ROOF_DE[alt]} geändert (Festsetzung).')
        if v.roof != 'flach' or upd.get('roof') not in (None, 'flach'):
            p = v.roof_pitch_deg
            if lim['pitch_min_deg'] is not None and p < lim['pitch_min_deg']:
                upd['roof_pitch_deg'] = lim['pitch_min_deg']
            if lim['pitch_max_deg'] is not None and p > lim['pitch_max_deg']:
                upd['roof_pitch_deg'] = lim['pitch_max_deg']
        below = _storeys_below(v, m.volumes)
        if lim['max_storeys'] and v.storeys + below > lim['max_storeys']:
            if below >= lim['max_storeys']:
                upd['elevation_m'] = 0.0
                below = 0
            upd['storeys'] = max(1, lim['max_storeys'] - below)
            notes.append(f'{v.name}: auf {lim["max_storeys"]} Vollgeschosse begrenzt' + (' (inkl. Baukörper darunter).' if below else '.'))
        nv = Volume.model_validate({**v.model_dump(), **upd})
        for _ in range(40):
            over_h = lim['max_height_m'] is not None and nv.top_m > lim['max_height_m'] + 1e-6
            over_e = lim['max_eave_m'] is not None and nv.elevation_m + nv.eave_m > lim['max_eave_m'] + 1e-6
            if not (over_h or over_e):
                break
            if nv.roof != 'flach' and nv.roof_pitch_deg > max(lim['pitch_min_deg'] or 0, 10) and not over_e:
                nv = Volume.model_validate({**nv.model_dump(), 'roof_pitch_deg': max(nv.roof_pitch_deg - 2.5, lim['pitch_min_deg'] or 0)})
            elif nv.storeys > 1:
                nv = Volume.model_validate({**nv.model_dump(), 'storeys': nv.storeys - 1})
            elif nv.storey_height_m > 2.5:
                nv = Volume.model_validate({**nv.model_dump(), 'storey_height_m': round(nv.storey_height_m - 0.1, 2)})
            else:
                break
        if nv.top_m != v.top_m and (lim['max_height_m'] or lim['max_eave_m']):
            notes.append(f'{v.name}: Höhe auf {nv.top_m:.1f} m angepasst.')
        vols.append(nv)

    def inside(vol: Volume) -> bool:
        return region.buffer(EPS).covers(vol.footprint())

    def moved(vol: Volume, dx: float, dy: float) -> Volume:
        d = vol.model_dump()
        d['cx'] += dx
        d['cy'] += dy
        if d.get('points'):
            d['points'] = [[x + dx, y + dy] for x, y in d['points']]
        return Volume.model_validate(d)

    def scaled(vol: Volume, k: float) -> Volume:
        d = vol.model_dump()
        d['width_m'] = max(0.6, d['width_m'] * k)
        d['depth_m'] = max(0.6, d['depth_m'] * k)
        if d.get('points'):
            c = Polygon(d['points']).centroid
            d['points'] = [[c.x + (x - c.x) * k, c.y + (y - c.y) * k] for x, y in d['points']]
        return Volume.model_validate(d)

    fitted = []
    # the group moves together: shift the whole composition so its centroid sits on the region's pole first, if it is outside
    comp = unary_union([x.footprint() for x in vols])
    if not region.buffer(EPS).covers(comp):
        c = comp.centroid
        dx, dy = target.x - c.x, target.y - c.y
        vols = [moved(x, dx, dy) for x in vols]
        notes.append('Entwurf in den bebaubaren Bereich verschoben.')
    for vol in vols:
        if inside(vol):
            fitted.append(vol)
            continue
        # try moving towards the pole, then shrink
        c = vol.footprint().centroid
        best = None
        for t in (0.25, 0.5, 0.75, 1.0):
            cand = moved(vol, (target.x - c.x) * t, (target.y - c.y) * t)
            if inside(cand):
                best = cand
                break
        k = 1.0
        cur = best or moved(vol, target.x - c.x, target.y - c.y)
        while best is None and k > 0.25:
            k *= 0.93
            cand = scaled(cur, k)
            if inside(cand):
                best = cand
        if best is None:
            notes.append(f'{vol.name}: passt nicht auf das Grundstück und wurde entfernt.')
            continue
        if k < 1.0:
            notes.append(f'{vol.name}: auf {k * 100:.0f} % verkleinert, damit er im Grundstück liegt.')
        fitted.append(best)
    if not fitted:
        return m, notes + ['Kein Baukörper passt in den bebaubaren Bereich.']
    out = m.model_copy(update={'volumes': support_elevations(fitted, notes)})
    # GRZ / GFZ by uniform scaling of the footprints (about each centre)
    for _ in range(30):
        met = out.metrics()
        k = 1.0
        if lim['max_footprint_main_m2'] is not None and met['footprint_main_m2'] > lim['max_footprint_main_m2'] + 0.1:
            k = min(k, math.sqrt(max(lim['max_footprint_main_m2'], 1) / met['footprint_main_m2']))
        if lim['max_gfa_m2'] is not None and met['gross_floor_area_m2'] > lim['max_gfa_m2'] + 0.1:
            k = min(k, math.sqrt(max(lim['max_gfa_m2'], 1) / met['gross_floor_area_m2']))
        if k >= 0.999:
            break
        out = out.model_copy(update={'volumes': [scaled(x, k * 0.995) for x in out.volumes]})
        if _ == 0:
            kept_fp = sum(e.poly.intersection(ctx.site).area for e in ctx.kept(m))
            notes.append('Grundfläche verkleinert, um GRZ/GFZ einzuhalten.' + (f' Erhaltener Bestand belegt bereits {kept_fp:.0f} m² des GRZ-Budgets – unter „Bestand“ abreißen, um mehr Fläche zu bekommen.' if kept_fp > 1 else ''))
    return out, notes


def _storeys_below(v: Volume, vols: list[Volume]) -> int:
    eff = effective_storeys(vols)
    return eff.get(v.id, v.storeys) - v.storeys
