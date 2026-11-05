"""Generation context: ONE retrievable bundle per project for the (separately built) architecture / floor-plan / house / render stage.

Design for retrieval: every statement is a ``fact`` with id, topic, source, status and confidence, plus ``retrieval_chunks`` (short German
passages with stable ids) so an LLM can cite exactly what it used. Binding numbers exist only under ``verified_constraints``.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pyproj import Transformer
from .brief import PlanningBrief
from .dossier import SiteDossier
from .models import SiteAssessment

SCHEMA = 'archaitect.generation-context/1'
_TO_UTM = Transformer.from_crs('EPSG:4326', 'EPSG:25832', always_xy=True)
_TO_LL = Transformer.from_crs('EPSG:25832', 'EPSG:4326', always_xy=True)

RULES_FOR_GENERATOR = [
    'Verbindliche Zahlen (GRZ, GFZ, Höhe, Geschosse, Abstände, Dachformen) stehen NUR unter verified_constraints. Fehlt ein Wert, ist er unbekannt: nicht schätzen, sondern als Annahme kennzeichnen.',
    'Das Haus liegt innerhalb des Baufensters (geometry.buildable_envelope_local), sofern vorhanden. Ohne Baufenster ist jede Platzierung ein Vorschlag und trägt den Hinweis „Abstandsflächen/Baugrenzen ungeprüft“.',
    'design_gate.mode == blocked: keinen Entwurf erzeugen. exploration: Entwurf nur mit sichtbarem Vorbehalt (design_gate.reason_de).',
    'Leitungs- und Anschlusspunkte stammen ausschließlich aus brief.connections (Status USER_SUPPLIED/AUTHORITY_PLAN). Keine Leitungsverläufe erfinden.',
    'Umgebungsgebäude: Höhen sind Schätzungen (height_basis ESTIMATE_FROM_FLOORS). Gelände: DGM1 ohne Bebauung und Bewuchs.',
    'Quellenangaben aus attribution übernehmen; bearbeitete oder gerenderte Darstellungen der Geobasisdaten mit dem Zusatz „verändert“.',
]


def _pt(lon: float, lat: float, ox: float, oy: float) -> list[float]:
    x, y = _TO_UTM.transform(lon, lat)
    return [round(x - ox, 2), round(y - oy, 2)]


def envelope_local(d: SiteDossier, pack: dict) -> list[list[float]] | None:
    m = d.mace
    if not (m and m.architectural_constraints.status == 'VERIFIED_BY_USER' and m.architectural_constraints.buildable_envelope_vertices):
        return None
    ox, oy = pack['frame']['origin_e'], pack['frame']['origin_n']
    return [[round(v.x_coord - ox, 2), round(v.y_coord - oy, 2)] for v in m.architectural_constraints.buildable_envelope_vertices]


def overlay_geojson(pack: dict, env: list[list[float]] | None, brief: PlanningBrief) -> dict:
    """Everything the map draws, as one WGS84 GeoJSON FeatureCollection (local metric frame -> lon/lat)."""
    ox, oy = pack['frame']['origin_e'], pack['frame']['origin_n']

    def ring(r: list[list[float]]) -> list[list[float]]:
        xs, ys = _TO_LL.transform([x + ox for x, _ in r], [y + oy for _, y in r])
        return [[round(a, 7), round(b, 7)] for a, b in zip(xs, ys)]

    feats: list[dict] = []

    def add(kind: str, r: list[list[float]] | None, **props) -> None:
        if r:
            feats.append({'type': 'Feature', 'properties': {'kind': kind, **props}, 'geometry': {'type': 'Polygon', 'coordinates': [ring(r)]}})

    for lu in pack.get('landuse', []):
        add('landuse', lu['ring'], code=lu['code'], label=lu['label_de'])
    for p in pack.get('parcels', []):
        add('parcel_site' if p['is_site'] else 'parcel', p['ring'], id=p['id'], label=p['label'], area=p.get('area_alkis_m2'))
    for b in pack.get('buildings', []):
        add('building', b['ring'], floors=b['floors'], height_est_m=b['height_est_m'], use=b['use'], on_site=b['on_site'])
    add('envelope', env)
    for c in brief.connections:
        feats.append({'type': 'Feature', 'properties': {'kind': 'connection', 'medium': c.kind, 'id': c.id, 'status': c.status}, 'geometry': {'type': 'Point', 'coordinates': [c.lon, c.lat]}})
    return {'type': 'FeatureCollection', 'features': feats}


def build_context(meta: dict, a: SiteAssessment, d: SiteDossier, pack: dict, brief: PlanningBrief, base: str) -> dict:
    fr = pack['frame']
    ox, oy = fr['origin_e'], fr['origin_n']
    facts: list[dict] = []

    def fact(fid: str, topic: str, text: str, source: str, status: str, conf: str = 'MEDIUM', data: dict | None = None) -> None:
        facts.append({'id': fid, 'topic': topic, 'text_de': text, 'source': source, 'status': status, 'confidence': conf, **({'data': data} if data else {})})

    fact('gate', 'eignung', f'{a.headline_de} {a.design_reason_de}', 'siteintel', 'INDICATION', a.confidence.value, {'verdict': a.verdict.value, 'design_mode': a.design_mode.value})
    for r in a.regulations:
        fact(f'reg.{r.id}', 'vorschrift', f'{r.label_de}: {r.value_de}', r.source_id or 'siteintel', r.status, r.confidence.value)
    for f in a.findings:
        fact(f'finding.{f.rule_id}.{len([x for x in facts if x["id"].startswith("finding."+f.rule_id)])}', 'befund', f'{f.title_de}. {f.reason_de}', f.source_id or 'siteintel',
             'INDICATION' if f.affects_verdict else 'NOTE', f.confidence.value, {'evidence': f.evidence})
    t = pack.get('terrain', {})
    if t.get('status') == 'OK':
        s = t['summary']
        slope = f'Neigung im Mittel {s.get("slope_mean_pct")} %, maximal {s.get("slope_max_pct")} %' if s.get('slope_mean_pct') is not None else ''
        down = f', Gefälle nach {s["downslope_compass"]}' if s.get('downslope_compass') else ''
        fact('terrain', 'gelaende', f'Gelände {s.get("z_min_m")}–{s.get("z_max_m")} m ü. NHN (Höhenunterschied {s.get("relief_m")} m). {slope}{down}.', 'dgm1', 'OFFICIAL_DATA', 'HIGH', s)
    if pack.get('street_frontage'):
        sf = pack['street_frontage']
        d_rd = sf['distance_to_road_m']
        fact('frontage', 'erschliessung', (f'Straße grenzt im {sf["compass"]} an' if d_rd < 1 else f'Straße {d_rd:.0f} m entfernt, Richtung {sf["compass"]}') + ' (Hinweis aus der amtlichen Bodennutzung; Zufahrt und Hausnummer nicht geprüft).', 'elu', 'INDICATION', 'MEDIUM', sf)
    bl = [b for b in pack.get('buildings', []) if not b['on_site']]
    if bl:
        hs = [b['height_est_m'] for b in bl if b.get('height_est_m')]
        fact('neighbours', 'umgebung', f'{len(bl)} Gebäude im Paketbereich' + (f', geschätzte Höhen {min(hs):.1f}–{max(hs):.1f} m' if hs else '') + '.', 'alkis-buildings', 'INDICATION', 'MEDIUM')
    fact('orientation', 'ausrichtung', f'Gitter-Nord weicht {fr["true_north_offset_deg"]}° von geografisch Nord ab; Standort {fr["latitude"]:.5f} N, {fr["longitude"]:.5f} O.', 'projection', 'OFFICIAL_DATA', 'HIGH')
    p = brief.program
    bits = [x for x in (f'{p.occupants} Personen' if p.occupants else '', f'{p.bedrooms} Schlafzimmer' if p.bedrooms is not None else '', f'ca. {p.living_area_target_m2:.0f} m² Wohnfläche' if p.living_area_target_m2 else '',
                        f'{p.stories} Geschosse' if p.stories else '', f'Dach: {", ".join(p.roof_types)}' if p.roof_types else '', f'Stil: {", ".join(p.style_keywords_de)}' if p.style_keywords_de else '',
                        f'Energie: {p.energy_standard}' if p.energy_standard != 'unknown' else '') if x]
    if bits or brief.wishes_de:
        fact('brief', 'wunsch', 'Bauherrenwunsch: ' + '; '.join(bits) + ('. ' + brief.wishes_de if brief.wishes_de else ''), 'nutzer', 'USER_SUPPLIED', 'HIGH')
    for c in brief.connections:
        fact(f'conn.{c.id}', 'anschluss', f'Anschluss {c.kind} bei lokal {_pt(c.lon, c.lat, ox, oy)} ({c.status}){": " + c.note_de if c.note_de else ""}', 'nutzer', c.status, 'MEDIUM' if c.status == 'ESTIMATE' else 'HIGH')
    fact('utilities', 'anschluss', 'Leitungsverläufe sind kein Open Data; Auskunft bei Netzbetreibern/BIL nötig. Stand: ' + brief.utilities_enquiry.status + '.', 'siteintel', 'NOT_OPEN_DATA', 'HIGH')

    site_ring = pack.get('site', {}).get('ring_local') or next((x['ring'] for x in pack['parcels'] if x['is_site']), None)
    mace = d.mace
    env = envelope_local(d, pack)
    verified = None
    if mace and mace.architectural_constraints.status == 'VERIFIED_BY_USER':
        verified = mace.architectural_constraints.model_dump(exclude={'buildable_envelope_vertices'})
        if env:
            fact('envelope', 'baufenster', 'Baufenster aus Flurstück abzüglich gleichmäßigem Abstand (ohne Baulasten und Leitungsrechte).', 'verified', 'VERIFIED_BY_USER', 'MEDIUM')
    chunks = [{'id': f'chunk.{i}', 'title': f'{x["topic"]} · {x["id"]}', 'text': x['text_de'], 'fact': x['id']} for i, x in enumerate(facts)]
    return {
        'schema_version': SCHEMA, 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'project': {k: meta[k] for k in ('id', 'name', 'created_at', 'updated_at', 'lat', 'lon', 'parcel_label')},
        'design_gate': d.design_gate.model_dump(), 'rules_for_generator': RULES_FOR_GENERATOR,
        'verified_constraints': verified,
        'geometry': {'frame': fr, 'parcel_local': site_ring, 'buildable_envelope_local': env, 'connections_local': [{'id': c.id, 'kind': c.kind, 'xy': _pt(c.lon, c.lat, ox, oy), 'status': c.status} for c in brief.connections],
                     'street_frontage': pack.get('street_frontage')},
        'facts': facts, 'retrieval_chunks': chunks, 'open_questions_de': d.open_questions_de, 'brief': brief.model_dump(),
        'assets': {'site_pack_manifest': f'{base}/sitepack', 'orthophoto': f'{base}/ortho.png', 'bundle_zip': f'{base}/sitepack.zip', 'dossier': f'{base}/dossier'},
        'attribution': pack['attribution'], 'modification_notice_de': pack['modification_notice_de'], 'disclaimer_de': d.disclaimer_de,
    }
