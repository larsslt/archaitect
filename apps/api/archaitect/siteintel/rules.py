"""Screening rule register: OSM land-use tags -> buildability indication for a *residential* building.

Every rule is a HEURISTIC on a non-authoritative source. Statute references are the general concepts only
(BauGB §34 Innenbereich / §35 Außenbereich) and are marked unverified; no paragraph is claimed to be applied.
A VERIFIED status is impossible here by design — that needs a Bebauungsplan / Behördenauskunft.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from .models import Finding, LandUseHit, Verdict

Tags = dict[str, str]
ORDER = {Verdict.NOT_BUILDABLE: 3, Verdict.RESTRICTED: 2, Verdict.CANDIDATE: 1, Verdict.UNKNOWN: 0}


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    title_de: str
    verdict: Verdict
    reason_de: str
    match: Callable[[Tags], bool]
    key: Callable[[Tags], tuple[str, str]]


def _in(tag: str, *values: str) -> Callable[[Tags], bool]:
    return lambda t: t.get(tag) in values


def _any(*fs: Callable[[Tags], bool]) -> Callable[[Tags], bool]:
    return lambda t: any(f(t) for f in fs)


def _k(tag: str) -> Callable[[Tags], tuple[str, str]]:
    return lambda t: (tag, t.get(tag, ''))


AUSSENBEREICH = 'Voraussichtlich Außenbereich (Konzept §35 BauGB, ungeprüft): ein Wohnhaus ist dort in der Regel nicht zulässig, außer es existiert ein Bebauungsplan oder eine Privilegierung.'

RULES: list[Rule] = [
    Rule('MILITARY', 'military', 'Militärisches Gelände', Verdict.NOT_BUILDABLE,
         'Fläche ist als militärisch genutzt erfasst. Zivile Wohnbebauung ist dort nicht vorgesehen.',
         _any(_in('landuse', 'military'), lambda t: 'military' in t), lambda t: ('military', t.get('military') or t.get('landuse', ''))),
    Rule('WATER', 'water', 'Gewässer / Feuchtfläche', Verdict.NOT_BUILDABLE,
         'Wasser- oder Feuchtfläche. Eine Bebauung mit einem Wohnhaus ist ausgeschlossen.',
         _any(_in('natural', 'water', 'wetland', 'bay'), lambda t: 'water' in t, _in('landuse', 'reservoir', 'basin'), _in('waterway', 'riverbank', 'dock')), _k('natural')),
    Rule('NATURE_RESERVE', 'protected', 'Naturschutzgebiet / Nationalpark', Verdict.NOT_BUILDABLE,
         'Als Naturschutzgebiet oder Nationalpark erfasst. Wohnbebauung ist dort nicht vorgesehen.',
         _any(_in('leisure', 'nature_reserve'), _in('boundary', 'national_park')), _k('leisure')),
    Rule('PROTECTED_AREA', 'protected', 'Schutzgebiet', Verdict.RESTRICTED,
         'Die Fläche liegt in einem erfassten Schutzgebiet (Art/Schutzklasse hier nicht bestimmt). Bauen höchstens nach Einzelfallprüfung.',
         _in('boundary', 'protected_area'), _k('boundary')),
    Rule('FOREST', 'forest', 'Wald', Verdict.NOT_BUILDABLE,
         'Waldfläche. Eine Wohnbebauung ist dort nicht zulässig.',
         _any(_in('landuse', 'forest'), _in('natural', 'wood')), _k('landuse')),
    Rule('INFRASTRUCTURE', 'infrastructure', 'Verkehrs-/Energie-/Sonderfläche', Verdict.NOT_BUILDABLE,
         'Fläche für Bahn, Flugbetrieb, Energieanlage, Deponie, Abbau oder Friedhof. Wohnbebauung ist dort nicht vorgesehen.',
         _any(_in('landuse', 'railway', 'landfill', 'quarry', 'cemetery'), lambda t: 'aeroway' in t, lambda t: 'railway' in t,
              lambda t: t.get('power') in ('plant', 'substation', 'generator'), _in('amenity', 'grave_yard')), _k('landuse')),
    Rule('AGRICULTURE', 'agriculture', 'Landwirtschaft / Freifläche', Verdict.RESTRICTED, AUSSENBEREICH,
         _any(_in('landuse', 'farmland', 'meadow', 'orchard', 'vineyard', 'grass', 'greenhouse_horticulture', 'plant_nursery', 'allotments', 'brownfield'),
              _in('natural', 'grassland', 'scrub', 'heath', 'fell')), _k('landuse')),
    Rule('COMMERCIAL', 'commercial', 'Gewerbe / Industrie / Handel', Verdict.RESTRICTED,
         'Gewerblich geprägte Fläche. Wohnen ist dort je nach Baugebiet nur ausnahmsweise oder gar nicht zulässig (BauNVO-Gebietsart ungeprüft).',
         _in('landuse', 'industrial', 'commercial', 'retail'), _k('landuse')),
    Rule('INSTITUTIONAL', 'institutional', 'Öffentliche Einrichtung', Verdict.RESTRICTED,
         'Fläche für Bildung, Gesundheit oder öffentliche Einrichtung. Ein privates Wohnhaus ist dort in der Regel nicht vorgesehen.',
         _any(_in('landuse', 'education', 'institutional', 'religious'), _in('amenity', 'school', 'university', 'hospital', 'college', 'kindergarten')), _k('amenity')),
    Rule('RECREATION', 'recreation', 'Park / Sport / Erholung', Verdict.RESTRICTED,
         'Park-, Sport- oder Erholungsfläche. Ein Wohnhaus ist dort in der Regel nicht vorgesehen.',
         _any(_in('leisure', 'park', 'pitch', 'sports_centre', 'golf_course', 'playground', 'stadium', 'garden', 'recreation_ground'), _in('landuse', 'recreation_ground', 'village_green')), _k('leisure')),
    Rule('RESIDENTIAL', 'residential', 'Wohngebiet (Flächennutzung)', Verdict.CANDIDATE,
         'Die Umgebung ist als Wohngebiet erfasst. Eine Wohnbebauung ist denkbar; Zulässigkeit nach Bebauungsplan oder §34 BauGB ist nicht geprüft.',
         _in('landuse', 'residential'), _k('landuse')),
]


def classify_tags(tag_sets: list[Tags]) -> list[LandUseHit]:
    hits: list[LandUseHit] = []
    seen: set[tuple[str, str]] = set()
    for tags in tag_sets:
        for rule in RULES:
            if rule.match(tags):
                k, v = rule.key(tags)
                sig = (rule.id, tags.get('name', '') + v)
                if sig in seen:
                    continue
                seen.add(sig)
                hits.append(LandUseHit(key=k or rule.id, value=v, name=tags.get('name'), category=rule.category, verdict=rule.verdict, reason_de=rule.reason_de))
    return hits


def findings_from_hits(hits: list[LandUseHit]) -> list[Finding]:
    by_cat = {r.category: r for r in RULES}
    out: list[Finding] = []
    for h in hits:
        rule = next(r for r in RULES if r.category == h.category and r.verdict == h.verdict)
        label = f'{h.key}={h.value}' + (f' („{h.name}“)' if h.name else '')
        out.append(Finding(rule_id=rule.id, verdict=h.verdict, title_de=rule.title_de, reason_de=rule.reason_de,
                           evidence=f'OSM {label}'))
    return sorted(out, key=lambda f: -ORDER[f.verdict])


def strongest(hits: list[LandUseHit]) -> Verdict:
    if not hits:
        return Verdict.UNKNOWN
    return max((h.verdict for h in hits), key=lambda v: ORDER[v])
