"""Turn raw WFS features into small, typed facts. No judgement here (that is decision.py)."""
from __future__ import annotations
import re
from statistics import median
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from . import geo
from .models import BuildingStats, LandUseShare, LandValue, PlanningHit, ProtectionHit
from .wfs import Feature

# ---- HILUCS (INSPIRE Hierarchical INSPIRE Land Use Classification System) -------------------------------------------
GROUP_DE = {'1': 'Primärproduktion', '2': 'Produktion/Industrie', '3': 'Dienstleistung', '4': 'Verkehr/Versorgung', '5': 'Wohnen', '6': 'Sonstiges'}
# Only labels that were observed in the live data or are top-level categories; anything else falls back to the code's English name.
HILUCS_DE = {
    '1': 'Primärproduktion', '1_1': 'Landwirtschaft', '1_1_1': 'Landwirtschaftliche Produktion', '1_2': 'Forstwirtschaft (Wald)', '1_3': 'Bergbau/Gewinnung',
    '2': 'Produktion/Industrie', '3': 'Dienstleistung', '3_1_1': 'Handel/Kfz-Gewerbe', '3_3_1': 'Öffentliche Verwaltung/Verteidigung', '3_3_2': 'Bildung',
    '3_3_3': 'Gesundheit/Soziales', '3_3_4': 'Religion', '3_4_3': 'Sport', '3_4_4': 'Parks/Erholung im Freien',
    '4_1_1': 'Straßenverkehr', '4_1_2': 'Schienenverkehr', '4_1_3': 'Luftverkehr', '4_1_4': 'Wasserverkehr', '4_2': 'Logistik/Lagerung', '4_3_2': 'Wasser-/Abwasseranlagen',
    '5': 'Wohnen', '5_1': 'Dauerwohnnutzung', '5_2': 'Wohnen mit verträglicher Mischnutzung', '6_3_2': 'Gewässer',
}
_HIL = re.compile(r'^(?P<code>\d(?:_\d+)*)_?(?P<name>[A-Za-z].*)?$')


def hilucs_parts(href: str | None) -> tuple[str, str]:
    """'.../5_1_PermanentResidentialUse' -> ('5_1', 'PermanentResidentialUse')."""
    tail = (href or '').rsplit('/', 1)[-1]
    m = _HIL.match(tail)
    return (m['code'], m['name'] or '') if m else ('', tail)


def hilucs_label(code: str, english: str) -> str:
    if code in HILUCS_DE:
        return HILUCS_DE[code]
    parent = code
    while '_' in parent:
        parent = parent.rsplit('_', 1)[0]
        if parent in HILUCS_DE:
            return f'{HILUCS_DE[parent]} – {_camel(english)}' if english else HILUCS_DE[parent]
    return _camel(english) or code


def land_use_shares(features: list[Feature], parcel: BaseGeometry) -> list[LandUseShare]:
    pm = geo.to_m(parcel)
    total = max(pm.area, 1.0)
    acc: dict[str, list] = {}
    for f in features:
        if f.geometry is None:
            continue
        code, eng = hilucs_parts(f.href('hilucsLandUse'))
        if not code:
            continue
        inter = geo.to_m(f.geometry).intersection(pm).area
        if inter <= 0.05:
            continue
        slot = acc.setdefault(code, [0.0, eng])
        slot[0] += inter
    out = [LandUseShare(code=c, name_de=hilucs_label(c, e), group_de=GROUP_DE.get(c[0], ''), share=round(min(a / total, 1.0), 4), area_m2=round(a, 1)) for c, (a, e) in acc.items()]
    return sorted(out, key=lambda x: -x.share)


# ---- Gebäude ----------------------------------------------------------------------------------------------------------
def building_stats(features: list[Feature], parcel: BaseGeometry, radius_m: int = 100) -> BuildingStats:
    pm = geo.to_m(parcel)
    centre = pm.centroid
    on_n = 0
    on_fp = 0.0
    floors_on: list[int] = []
    near_n = near_res = 0
    near_floors: list[int] = []
    for f in features:
        if f.geometry is None:
            continue
        bm = geo.to_m(f.geometry)
        use = (f.href('currentUse', 'currentUse>CurrentUse>currentUse') or '').rsplit('/', 1)[-1]
        fl = f.get('numberOfFloorsAboveGround')
        floors = int(float(fl)) if fl and fl.replace('.', '', 1).isdigit() else None
        inter = bm.intersection(pm).area
        if bm.area > 0 and inter / bm.area >= 0.5:
            on_n += 1
            on_fp += inter
            if floors:
                floors_on.append(floors)
        if bm.centroid.distance(centre) <= radius_m + pm.length / 8:
            near_n += 1
            near_res += 1 if use.startswith('residential') else 0
            if floors:
                near_floors.append(floors)
    return BuildingStats(on_parcel=on_n, on_parcel_footprint_m2=round(on_fp, 1), max_floors_on_parcel=max(floors_on) if floors_on else None,
                         nearby_total=near_n, nearby_residential=near_res, nearby_radius_m=radius_m,
                         nearby_median_floors=float(median(near_floors)) if near_floors else None)


# ---- BORIS Bodenrichtwerte -----------------------------------------------------------------------------------------
ENTW_DE = {'B': 'baureifes Land', 'R': 'Rohbauland', 'E': 'Bauerwartungsland', 'LF': 'land-/forstwirtschaftliche Fläche', 'SF': 'sonstige Fläche'}
ART_DE = {'W': 'Wohnbaufläche', 'WR': 'reines Wohngebiet', 'WS': 'Kleinsiedlungsgebiet', 'WA': 'allgemeines Wohngebiet', 'WB': 'besonderes Wohngebiet',
          'M': 'gemischte Baufläche', 'MD': 'Dorfgebiet', 'MI': 'Mischgebiet', 'MK': 'Kerngebiet', 'G': 'gewerbliche Baufläche', 'GE': 'Gewerbegebiet', 'GI': 'Industriegebiet',
          'S': 'Sonderbaufläche', 'SO': 'Sondergebiet', 'A': 'Acker', 'GR': 'Grünland', 'F': 'Forst', 'LW': 'Landwirtschaft', 'EF': 'Erholungsfläche', 'WF': 'Wasserfläche', 'FH': 'Friedhof'}
BUILDABLE_ART = {'W', 'WR', 'WS', 'WA', 'WB', 'M', 'MD', 'MI', 'MK'}
_NUM = re.compile(r'^-?\d+(\.\d+)?$')


def land_value(features: list[Feature], point: Point) -> LandValue | None:
    """Prefer the zone with baureifes Land and a residential/mixed use; otherwise the first one."""
    best: Feature | None = None
    for f in features:
        if f.geometry is not None and not f.geometry.buffer(1e-9).contains(point) and len(features) > 1:
            continue
        if best is None:
            best = f
        if f.get('entwicklungszustand') == 'B' and f.get('art') in BUILDABLE_ART and not (best.get('entwicklungszustand') == 'B' and best.get('art') in BUILDABLE_ART):
            best = f
    if best is None and features:
        best = features[0]
    if best is None:
        return None
    v = best.get('bodenrichtwert')
    art = best.get('art')
    ent = best.get('entwicklungszustand')
    rem = best.get('bemerkungen')
    def zone(name: str) -> str | None:
        vals = [x for k, x in best.props.items() if k == name or k.startswith(name + '>')]
        vals = [x.strip() for x in vals if x and x.strip()]
        return '-'.join(dict.fromkeys(vals)) if vals else None

    def num(text: str | None) -> float | None:
        m = re.search(r'\d+(?:[.,]\d+)?', text or '')
        return float(m.group(0).replace(',', '.')) if m else None
    return LandValue(
        geschosszahl=zone('geschosszahl'), gfz_zone=num(zone('geschossflaechenzahl')), grz_zone=num(zone('grundflaechenzahl')), bauweise=zone('bauweise'), tiefe_m=num(zone('tiefe')),
        eur_per_m2=float(v) if v and _NUM.match(v) else None, stichtag=best.get('stichtag'), entwicklungszustand=ent, entwicklungszustand_de=ENTW_DE.get(ent or ''),
        nutzung=art, nutzung_de=ART_DE.get(art or ''), ergaenzung=best.get('ergaenzung'), zone_nr=best.get('bodenrichtwertNummer'),
        gemeinde=best.get('BR_Gemeinde>name', 'gemeinde>BR_Gemeinde>name'), gemarkung=best.get('BR_Gemarkung>name', 'gemarkung>BR_Gemarkung>name'),
        bemerkung=rem, aussenbereich_hint=bool(rem and re.search(r'au(ß|ss)enbereich|§\s*35', rem, re.I)))


# ---- Planung (RegFNP, Regionalplan, LEP) ---------------------------------------------------------------------------
REG_DE = {
    'Hochwasserschutz': 'Hochwasserschutz', 'Grundwasserschutz': 'Grundwasserschutz', 'BesondereKlimaschutzfunktion': 'Besondere Klimafunktion',
    'Gruenzug': 'Regionaler Grünzug', 'NaturLandschaft': 'Natur und Landschaft', 'Biotopverbund': 'Biotopverbund', 'Forstwirtschaft': 'Forstwirtschaft (Wald)',
    'Fernstrasse': 'Fernstraße', 'Bundesstrasse': 'Bundesstraße', 'Zweistreifig': 'Straße (zweistreifig)', 'Dreistreifig': 'Straße (dreistreifig)', 'Vierstreifig': 'Straße (vierstreifig)',
    'AllgemeinerSchienenverkehr': 'Schienenverkehr', 'SBahn': 'S-Bahn', 'Fernverkehr': 'Fernverkehr (Schiene)', 'Nahverkehr': 'Nahverkehr (Schiene)',
    'Haupteisenbahnstrecke': 'Haupteisenbahnstrecke', 'Wasserstrasse': 'Wasserstraße', 'Gas': 'Gasleitung', 'Pipeline': 'Rohrleitung', 'Hochspannungsleitung': 'Hochspannungsleitung',
    'KV110': '110-kV-Leitung', 'Verbindungsachse': 'Verbindungsachse', 'Verdichtungsraum': 'Verdichtungsraum', 'Ordnungsraum': 'Ordnungsraum', 'LaendlicherRaum': 'Ländlicher Raum',
}
# Freiraum designations that make a *new residential building* doubtful when they are a binding Ziel and overlap the parcel.
RESTRICTING = {'Gruenzug', 'NaturLandschaft', 'Forstwirtschaft'}


def _camel(s: str) -> str:
    return re.sub(r'(?<=[a-zäöü])(?=[A-Z])', ' ', s)


def reg_name(href: str | None) -> tuple[str, str]:
    tail = (href or '').rsplit('/', 1)[-1]
    name = re.sub(r'^(?:\d+_)+', '', tail)
    code = tail[: len(tail) - len(name)].rstrip('_')
    return code, name


def planning_hits(layer: str, features: list[Feature], parcel: BaseGeometry) -> list[PlanningHit]:
    pm = geo.to_m(parcel)
    total = max(pm.area, 1.0)
    out: list[PlanningHit] = []
    seen: set[tuple[str, str]] = set()
    for f in features:
        if f.geometry is None:
            continue
        gm = geo.to_m(f.geometry)
        binding = (f.href('regulationNature') or '').rsplit('/', 1)[-1] or None
        if layer == 'regfnp':
            code, eng = hilucs_parts(f.href('hilucsLandUse'))
            if not code:
                continue
            share = gm.intersection(pm).area / total
            if share < 0.02:
                continue
            key = (layer, code)
            if key in seen:
                continue
            seen.add(key)
            out.append(PlanningHit(layer=layer, code=code, label_de=hilucs_label(code, eng), share=round(min(share, 1.0), 3), binding=binding, effect='note'))
            continue
        code, name = reg_name(f.href('specificSupplementaryRegulation'))
        nature = f.get('specificRegulationNature')
        dist = gm.distance(pm)
        is_area = gm.geom_type in ('Polygon', 'MultiPolygon')
        share = gm.intersection(pm).area / total if is_area else None
        if is_area and (share or 0) < 0.02:
            continue
        if not is_area and dist > 30:
            continue
        key = (layer, name + (nature or ''))
        if key in seen:
            continue
        seen.add(key)
        is_ziel = bool(nature and re.search(r'\bZiel\b', nature)) and 'Nachricht' not in (nature or '')
        effect = 'restrict' if (is_area and name in RESTRICTING and is_ziel and (share or 0) >= 0.25) else 'note'
        out.append(PlanningHit(layer=layer, code=code, label_de=REG_DE.get(name, _camel(name)), nature_de=nature, share=round(min(share, 1.0), 3) if share is not None else None,
                               binding=binding, distance_m=None if is_area else round(dist, 1), effect=effect))
    return out


# ---- Schutzgebiete / Hinweise -----------------------------------------------------------------------------------------
SCHUTZ_KIND = {'Naturschutzgebiete': ('nsg', 'Naturschutzgebiet'), 'Nationalpark': ('nationalpark', 'Nationalpark'), 'Nationales_Naturmonument': ('naturmonument', 'Nationales Naturmonument'),
               'Landschaftsschutzgebiete': ('lsg', 'Landschaftsschutzgebiet'), 'Fauna-Flora-Habitate': ('ffh', 'FFH-Gebiet (Natura 2000)'), 'Vogelschutzgebiete': ('vsg', 'Vogelschutzgebiet (Natura 2000)'),
               'Biosphaerenreservat': ('biosphaere', 'Biosphärenreservat'), 'Naturparke': ('naturpark', 'Naturpark')}


def protection_hits(denkmal: list[Feature], hq: list[Feature], parcel: BaseGeometry, schutz: list[Feature] | None = None) -> list[ProtectionHit]:
    pm = geo.to_m(parcel)
    total = max(pm.area, 1.0)
    out: list[ProtectionHit] = []
    for f in denkmal:
        if f.geometry is None:
            continue
        gm = geo.to_m(f.geometry)
        d = gm.distance(pm)
        if d > 30:
            continue
        kind = {'baudenkmal': 'denkmal', 'flaechendenkmal': 'denkmal', 'archaeologischesDenkmal': 'archaeologie'}.get(f.type, 'denkmal')
        label = {'baudenkmal': 'Baudenkmal (Kulturdenkmal)', 'flaechendenkmal': 'Denkmalfläche (Gesamtanlage)', 'archaeologischesDenkmal': 'Archäologisches Denkmal'}.get(f.type, 'Denkmal')
        out.append(ProtectionHit(kind=kind, label_de=label, name=f.get('siteName'), link=f.get('publicationSource'), on_parcel=d < 0.5, distance_m=round(d, 1)))
    for f in hq:
        if f.geometry is None:
            continue
        share = geo.to_m(f.geometry).intersection(pm).area / total
        if share <= 0.0:
            continue
        status = f.get('STATUS')
        out.append(ProtectionHit(kind='hq100', label_de=f'Überschwemmungsgebiet HQ100' + (f' ({status})' if status else ''), name=f.get('NAME'), on_parcel=True, share=round(min(share, 1.0), 3)))
    for f in schutz or []:
        kind, label = SCHUTZ_KIND.get(f.type, ('schutzgebiet', f.type))
        name = f.get('NAME', 'GEBIET_NAME', 'Name')
        out.append(ProtectionHit(kind=kind, label_de=label, name=name, on_parcel=True, share=None))  # point test only: the polygons can be huge (Nationalpark)
    out.sort(key=lambda h: (h.kind not in ('nsg', 'nationalpark', 'naturmonument', 'hq100'), h.kind != 'hq100', h.distance_m or 0))
    return out


def dedupe_planning(hits: list[PlanningHit]) -> list[PlanningHit]:
    """Regionalplan and LEP repeat the same designation; keep one per (label, nature), preferring the larger share."""
    best: dict[tuple[str, str | None], PlanningHit] = {}
    for h in hits:
        key = (h.label_de, h.nature_de) if h.layer != 'regfnp' else ('regfnp', h.code)
        cur = best.get(key)
        if cur is None or (h.share or 0) > (cur.share or 0):
            best[key] = h
    return list(best.values())
