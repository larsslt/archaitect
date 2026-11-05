"""Evidence -> findings -> verdict -> design mode. Pure functions, no I/O, fully unit-testable.

Principles
- Only *hard evidence* blocks a design (official land use clearly non-residential, or no parcel). Everything uncertain
  becomes ``exploration``: the pipeline keeps going, the UI shows a caveat. An outage never blocks by itself.
- Nothing here is ever VERIFIED. A residential permit depends on a Bebauungsplan or §34/§35 BauGB assessment by the authority.
- Positive evidence can lift a *soft* restriction (agricultural/other land use that BORIS or the FNP shows as building land),
  never a hard one (flood zone, regional green belt, Außenbereich note, not-yet-buildable land, non-buildable land use).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .extract import BUILDABLE_ART
from .models import (BuildingStats, Confidence, DataStatus, DesignMode, Finding, LandUseHit, LandUseShare, LandValue, ParcelInfo, PlanningHit,
                     ProtectionHit, RegulationItem, Verdict)

ORDER = {Verdict.NOT_BUILDABLE: 3, Verdict.RESTRICTED: 2, Verdict.CANDIDATE: 1, Verdict.UNKNOWN: 0}
CONF_ORDER = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


@dataclass(frozen=True)
class UseClass:
    verdict: Verdict
    category: str
    title_de: str
    reason_de: str
    soft: bool = False  # a restriction that positive evidence for building land may lift


_AUSSEN = 'Voraussichtlich Außenbereich (Konzept §35 BauGB, ungeprüft): ein Wohnhaus ist dort in der Regel nicht zulässig, außer es besteht ein Bebauungsplan oder eine Privilegierung.'
# Longest matching prefix wins. HILUCS = INSPIRE land-use classification used by the ALKIS ELU service.
CLASSES: list[tuple[str, UseClass]] = [
    ('1_1', UseClass(Verdict.RESTRICTED, 'agriculture', 'Landwirtschaftliche Nutzung', _AUSSEN, soft=True)),
    ('1_2', UseClass(Verdict.NOT_BUILDABLE, 'forest', 'Wald', 'Waldfläche. Eine Wohnbebauung ist dort nicht zulässig.')),
    ('1_3', UseClass(Verdict.NOT_BUILDABLE, 'mining', 'Bergbau / Gewinnung', 'Abbau- oder Gewinnungsfläche. Wohnbebauung ist dort nicht vorgesehen.')),
    ('1', UseClass(Verdict.RESTRICTED, 'agriculture', 'Primärproduktion', _AUSSEN, soft=True)),
    ('2', UseClass(Verdict.RESTRICTED, 'industry', 'Industrie / Produktion', 'Industrielle Nutzung. Wohnen ist dort je nach Baugebiet nur ausnahmsweise (z. B. Betriebsleiter) oder gar nicht zulässig.')),
    ('3_1', UseClass(Verdict.RESTRICTED, 'commercial', 'Handel / Gewerbe', 'Gewerblich geprägte Fläche. Wohnen ist je nach Baugebiet nur ausnahmsweise oder gar nicht zulässig (Gebietsart ungeprüft).', soft=True)),
    ('3_3_1', UseClass(Verdict.NOT_BUILDABLE, 'military', 'Öffentliche Verwaltung / Verteidigung', 'Fläche für Verwaltung, Verteidigung oder Sozialversicherung (u. a. Militär, Kasernen). Zivile Wohnbebauung ist dort nicht vorgesehen.')),
    ('3_3', UseClass(Verdict.RESTRICTED, 'institutional', 'Öffentliche Einrichtung', 'Fläche für Bildung, Gesundheit, Soziales oder Religion. Ein privates Wohnhaus ist dort in der Regel nicht vorgesehen.')),
    ('3_4', UseClass(Verdict.RESTRICTED, 'recreation', 'Sport / Erholung / Park', 'Sport-, Park- oder Erholungsfläche. Ein Wohnhaus ist dort in der Regel nicht vorgesehen.')),
    ('3', UseClass(Verdict.RESTRICTED, 'services', 'Dienstleistung', 'Dienstleistungsnutzung. Wohnen ist je nach Baugebiet nur eingeschränkt zulässig.', soft=True)),
    ('4_1', UseClass(Verdict.NOT_BUILDABLE, 'transport', 'Verkehrsfläche', 'Straße, Schiene, Luft- oder Wasserverkehr. Wohnbebauung ist dort nicht vorgesehen.')),
    ('4_2', UseClass(Verdict.RESTRICTED, 'logistics', 'Logistik / Lagerung', 'Logistik- oder Lagerfläche. Wohnen ist dort in der Regel nicht vorgesehen.')),
    ('4_3', UseClass(Verdict.NOT_BUILDABLE, 'utilities', 'Ver- und Entsorgung', 'Anlage für Energie, Wasser, Abwasser oder Abfall. Wohnbebauung ist dort nicht vorgesehen.')),
    ('4', UseClass(Verdict.RESTRICTED, 'utilities', 'Verkehr / Versorgung', 'Verkehrs- oder Versorgungsnutzung. Wohnen ist dort in der Regel nicht vorgesehen.')),
    ('5', UseClass(Verdict.CANDIDATE, 'residential', 'Wohnnutzung', 'Amtliche Bodennutzung ist Wohnen. Eine Wohnbebauung ist denkbar; Zulässigkeit nach Bebauungsplan oder §34 BauGB ist nicht geprüft.')),
    ('6_3_2', UseClass(Verdict.NOT_BUILDABLE, 'water', 'Gewässer', 'Wasserfläche. Eine Bebauung mit einem Wohnhaus ist ausgeschlossen.')),
    ('6', UseClass(Verdict.RESTRICTED, 'other', 'Sonstige Fläche (Brache/Natur)', 'Brach-, Übergangs- oder Naturfläche. Ob dort gebaut werden darf, hängt von Innen-/Außenbereich und Plan ab.', soft=True)),
]


def classify_code(code: str) -> UseClass | None:
    best: tuple[int, UseClass] | None = None
    for prefix, cls in CLASSES:
        if code == prefix or code.startswith(prefix + '_'):
            if best is None or len(prefix) > best[0]:
                best = (len(prefix), cls)
    return best[1] if best else None


@dataclass
class Evidence:
    parcel: ParcelInfo | None
    shares: list[LandUseShare] | None            # None = source unavailable
    buildings: BuildingStats | None
    value: LandValue | None
    planning: list[PlanningHit] = field(default_factory=list)
    protections: list[ProtectionHit] = field(default_factory=list)
    osm_hits: list[LandUseHit] = field(default_factory=list)
    statuses: dict[str, DataStatus] = field(default_factory=dict)
    stage: str = 'full'


@dataclass
class Decision:
    verdict: Verdict
    confidence: Confidence
    headline_de: str
    design_mode: DesignMode
    design_reason_de: str
    findings: list[Finding]
    regulations: list[RegulationItem]
    override_allowed: bool = False


def pct(x: float) -> str:
    return f'{round(x * 100):d} %'


def euro(v: float) -> str:
    s = f'{v:,.2f}' if v != int(v) else f'{int(v):,}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def _ok(ev: Evidence, sid: str) -> bool:
    st = ev.statuses.get(sid)
    return st is not None and st.status in ('OK', 'NO_MATCH')


def build_findings(ev: Evidence) -> list[Finding]:
    out: list[Finding] = []
    # --- amtliche Bodennutzung (ALKIS ELU) ------------------------------------------------------------------------
    if ev.shares is None:
        out.append(Finding(rule_id='LANDUSE_UNAVAILABLE', verdict=Verdict.UNKNOWN, title_de='Amtliche Bodennutzung nicht abrufbar',
                           reason_de=(ev.statuses.get('elu').detail if ev.statuses.get('elu') else None) or 'Dienst nicht erreichbar. Das blockiert den Entwurf nicht, senkt aber die Aussagekraft.',
                           evidence='ALKIS ELU: Dienst nicht erreichbar', confidence=Confidence.LOW, source_id='elu', affects_verdict=False))
    elif not ev.shares:
        out.append(Finding(rule_id='LANDUSE_NONE', verdict=Verdict.UNKNOWN, title_de='Keine amtliche Bodennutzung erfasst',
                           reason_de='Für dieses Flurstück liefert ALKIS keine Nutzungsfläche.', evidence='ALKIS ELU: keine Fläche', confidence=Confidence.LOW, source_id='elu', affects_verdict=False))
    else:
        blockers = sum(s.share for s in ev.shares if (c := classify_code(s.code)) and c.verdict == Verdict.NOT_BUILDABLE)
        for s in ev.shares:
            cls = classify_code(s.code)
            if cls is None or s.share < 0.05:
                continue
            v = cls.verdict
            title = cls.title_de
            if v == Verdict.NOT_BUILDABLE and blockers < 0.5:
                v = Verdict.RESTRICTED if s.share >= 0.15 or blockers >= 0.15 else Verdict.UNKNOWN
                title = f'{cls.title_de} (Teilfläche)'
            if v == Verdict.UNKNOWN:
                continue
            conf = Confidence.HIGH if s.share >= 0.8 else Confidence.MEDIUM
            out.append(Finding(rule_id=f'ELU_{cls.category.upper()}', verdict=v, title_de=title, reason_de=cls.reason_de,
                               evidence=f'ALKIS Bodennutzung {s.code.replace("_", ".")} „{s.name_de}“: {pct(s.share)} des Flurstücks', confidence=conf,
                               source_id='elu', share_of_parcel=s.share, basis_status='OFFICIAL_DATA_UNVERIFIED'))
    # --- Bodenrichtwert --------------------------------------------------------------------------------------------
    v = ev.value
    if v:
        ev_txt = f'Bodenrichtwert {v.zone_nr or ""}: {v.entwicklungszustand_de or v.entwicklungszustand}, {v.nutzung_de or v.nutzung}' + (f' ({v.ergaenzung})' if v.ergaenzung else '')
        if (v.ergaenzung or '').upper() == 'MIL':
            out.append(Finding(rule_id='BORIS_MILITAER', verdict=Verdict.NOT_BUILDABLE, title_de='Militärische Sonderbaufläche (Richtwertzone)',
                               reason_de='Die Bodenrichtwertzone ist als Sonderbaufläche mit der Ergänzung „MIL“ geführt (Militär). Zivile Wohnbebauung ist dort nicht vorgesehen. Die Zone ist nicht parzellenscharf.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand == 'B' and v.aussenbereich_hint:
            out.append(Finding(rule_id='BORIS_AUSSENBEREICH', verdict=Verdict.RESTRICTED, title_de='Bauen im Außenbereich (§35 BauGB)',
                               reason_de=f'Der Bodenrichtwert gilt laut Gutachterausschuss für Wohnen im Außenbereich: „{(v.bemerkung or "")[:160]}“. Das ist keine reguläre Baulandlage.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand == 'B' and (v.nutzung or '') in BUILDABLE_ART:
            out.append(Finding(rule_id='BORIS_BAULAND', verdict=Verdict.CANDIDATE, title_de='Baureifes Land für Wohnen/Mischnutzung',
                               reason_de='Der Gutachterausschuss führt dieses Gebiet als baureifes Land mit Wohn- oder Mischnutzung. Das spricht für eine bebaubare Lage; die konkrete Zulässigkeit ist damit nicht belegt.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand in ('R', 'E'):
            out.append(Finding(rule_id='BORIS_NICHT_BAUREIF', verdict=Verdict.RESTRICTED, title_de=f'Noch nicht baureif ({v.entwicklungszustand_de})',
                               reason_de='Rohbauland/Bauerwartungsland ist noch nicht erschlossen oder noch nicht verbindlich beplant. Eine sofortige Bebauung ist unsicher.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand == 'SF':
            out.append(Finding(rule_id='BORIS_SONSTIGE', verdict=Verdict.RESTRICTED, title_de='Sonstige Fläche (Richtwertzone)',
                               reason_de='Die Bodenrichtwertzone ist keine Bau-, sondern eine „sonstige Fläche“ (z. B. Gemeinbedarf, Verkehr, Wasser, Friedhof). Wohnbebauung ist dort in der Regel nicht vorgesehen.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand == 'LF' or (v.nutzung or '') in ('A', 'GR', 'F', 'LW'):
            out.append(Finding(rule_id='BORIS_AUSSEN_LF', verdict=Verdict.RESTRICTED, title_de='Land-/forstwirtschaftliche Fläche (Richtwertzone)',
                               reason_de='Die Bodenrichtwertzone ist land- oder forstwirtschaftlich eingestuft: üblicherweise Außenbereich, Wohnbebauung dort in der Regel nicht zulässig.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
        elif v.entwicklungszustand == 'B' and (v.nutzung or '') in ('G', 'GE', 'GI', 'S', 'SO'):
            out.append(Finding(rule_id='BORIS_GEWERBE', verdict=Verdict.RESTRICTED, title_de='Gewerbe-/Sonderbaufläche (Richtwertzone)',
                               reason_de='Die Richtwertzone ist gewerblich oder als Sondergebiet eingestuft. Wohnen ist dort nur eingeschränkt zulässig.',
                               evidence=ev_txt, confidence=Confidence.MEDIUM, source_id='boris'))
    # --- Flächennutzungsplan / Regionalplan -------------------------------------------------------------------------
    for h in ev.planning:
        if h.layer == 'regfnp':
            cls = classify_code(h.code)
            if cls is None or (h.share or 0) < 0.4:
                continue
            if cls.verdict == Verdict.CANDIDATE:
                out.append(Finding(rule_id='FNP_WOHNEN', verdict=Verdict.CANDIDATE, title_de='Flächennutzungsplan: Wohn-/gemischte Baufläche',
                                   reason_de='Der Regionale Flächennutzungsplan stellt hier Bauland mit Wohnnutzung dar. Der FNP ist vorbereitend und nicht parzellenscharf; das Baurecht regelt der Bebauungsplan.',
                                   evidence=f'RegFNP: {h.label_de} ({pct(h.share or 0)} des Flurstücks)', confidence=Confidence.MEDIUM, source_id='regfnp'))
            else:
                out.append(Finding(rule_id='FNP_NICHT_WOHNEN', verdict=Verdict.RESTRICTED, title_de=f'Flächennutzungsplan: {cls.title_de}',
                                   reason_de='Der Flächennutzungsplan stellt hier keine Wohnbaufläche dar (vorbereitender Plan, nicht parzellenscharf).',
                                   evidence=f'RegFNP: {h.label_de} ({pct(h.share or 0)} des Flurstücks)', confidence=Confidence.LOW, source_id='regfnp'))
        elif h.effect == 'restrict':
            out.append(Finding(rule_id='REGIONALPLAN_FREIRAUM', verdict=Verdict.RESTRICTED, title_de=f'Regionalplan: {h.label_de}',
                               reason_de='Das Flurstück liegt (zu einem relevanten Teil) in einem Freiraum-Ziel der Regionalplanung. Neue Wohnbebauung ist dort grundsätzlich nicht vorgesehen.',
                               evidence=f'{h.nature_de or "Regionalplan"}: {h.label_de} ({pct(h.share or 0)})', confidence=Confidence.MEDIUM, source_id=h.layer, share_of_parcel=h.share))
        else:
            note_names = ('Hochwasserschutz', 'Grundwasserschutz', 'Besondere Klimafunktion', 'Regionaler Grünzug', 'Natur und Landschaft', 'Biotopverbund',
                          'Bahn', 'Gasleitung', 'Rohrleitung', 'Hochspannungsleitung', '110-kV-Leitung', 'Schienenverkehr', 'Haupteisenbahnstrecke', 'S-Bahn')
            if any(n in h.label_de for n in note_names):
                where = f'{pct(h.share)} des Flurstücks' if h.share is not None else f'{h.distance_m:.0f} m entfernt'
                out.append(Finding(rule_id='PLANUNG_HINWEIS', verdict=Verdict.UNKNOWN, title_de=f'Planungshinweis: {h.label_de}',
                                   reason_de='Raumordnerische Festlegung bzw. Infrastruktur in unmittelbarer Nähe. Kann Abstände, Immissionen oder Auflagen auslösen; nicht parzellenscharf.',
                                   evidence=f'{h.nature_de or h.layer}: {h.label_de} ({where})', confidence=Confidence.MEDIUM, source_id=h.layer, affects_verdict=False))
    # --- Schutz / Gefahren --------------------------------------------------------------------------------------------
    for p in ev.protections:
        if p.kind == 'hq100' and (p.share or 0) >= 0.02:
            out.append(Finding(rule_id='HQ100', verdict=Verdict.RESTRICTED, title_de='Überschwemmungsgebiet (HQ100)',
                               reason_de='Das Flurstück liegt zu einem Teil in einem festgesetzten Überschwemmungsgebiet. Neue Wohnbebauung ist dort rechtlich stark eingeschränkt (Wasserrecht); der Kartendienst ist selbst nicht rechtsverbindlich.',
                               evidence=f'HQ100 {p.name or ""}: {pct(p.share or 0)} des Flurstücks'.replace('  ', ' '), confidence=Confidence.MEDIUM, source_id='hq100', share_of_parcel=p.share))
        elif p.kind in ('nsg', 'nationalpark', 'naturmonument'):
            out.append(Finding(rule_id='SCHUTZ_STRENG', verdict=Verdict.NOT_BUILDABLE, title_de=f'{p.label_de}' + (f' „{p.name}“' if p.name else ''),
                               reason_de='Das Flurstück liegt in einem streng geschützten Gebiet. Neue Wohnbebauung ist dort nach den Schutzgebietsverordnungen in der Regel verboten. Der Dienst ist nicht rechtsverbindlich.',
                               evidence=f'Schutzgebiete Hessen: {p.label_de}' + (f' {p.name}' if p.name else '') + ' (Punkttest)', confidence=Confidence.MEDIUM, source_id='schutzgebiete'))
        elif p.kind in ('lsg', 'ffh', 'vsg'):
            out.append(Finding(rule_id='SCHUTZ_' + p.kind.upper(), verdict=Verdict.RESTRICTED, title_de=f'{p.label_de}' + (f' „{p.name}“' if p.name else ''),
                               reason_de='Der Punkt liegt in einem Schutzgebiet mit Bauverboten oder Genehmigungsvorbehalten (häufig im Außenbereich). Innerhalb von Bebauungsplan-Gebieten ist die Wirkung oft ausgenommen; das ist hier nicht geprüft.',
                               evidence=f'Schutzgebiete Hessen: {p.label_de}' + (f' {p.name}' if p.name else '') + ' (Punkttest)', confidence=Confidence.MEDIUM, source_id='schutzgebiete'))
        elif p.kind in ('biosphaere', 'naturpark'):
            out.append(Finding(rule_id='SCHUTZ_HINWEIS', verdict=Verdict.UNKNOWN, title_de=f'{p.label_de}' + (f' „{p.name}“' if p.name else ''),
                               reason_de='Großräumiges Gebiet, das Bebauung nicht pauschal ausschließt (Zonierung bzw. Landschaftsrahmen).', evidence=f'Schutzgebiete Hessen: {p.label_de}', confidence=Confidence.MEDIUM, source_id='schutzgebiete', affects_verdict=False))
        elif p.kind in ('denkmal', 'archaeologie'):
            near = 'auf dem Flurstück' if p.on_parcel else f'{p.distance_m:.0f} m entfernt'
            out.append(Finding(rule_id='DENKMAL', verdict=Verdict.UNKNOWN, title_de=f'{p.label_de} {near}',
                               reason_de='Maßnahmen an oder in der Umgebung von Kulturdenkmälern brauchen die Zustimmung der Denkmalbehörde. Das schließt Neubau nicht aus, kann ihn aber prägen.',
                               evidence=f'DenkXweb: {p.name or p.label_de}', confidence=Confidence.HIGH, source_id='denkmal', affects_verdict=False))
    # --- OSM (optional Verfeinerung) --------------------------------------------------------------------------------
    elu_missing = ev.shares is None or not ev.shares
    elu_top = classify_code(ev.shares[0].code) if ev.shares else None
    elu_says_blocked = bool(elu_top and elu_top.verdict == Verdict.NOT_BUILDABLE)
    for h in ev.osm_hits:
        if h.category in ('military', 'protected') or (elu_missing and h.verdict in (Verdict.NOT_BUILDABLE, Verdict.RESTRICTED)):
            if h.verdict == Verdict.CANDIDATE:
                continue
            verdict, title, conf = h.verdict, f'OSM: {h.category}', Confidence.HIGH if h.category == 'military' else Confidence.MEDIUM
            if h.category == 'military' and not elu_missing and not elu_says_blocked:
                # Official land use does not say "military": OSM may be outdated (converted barracks). Still stop (the user's rule: military is
                # never a house site), but at MEDIUM confidence, which leaves a conscious "open as study anyway" override in the UI.
                verdict, title, conf = Verdict.NOT_BUILDABLE, 'OSM markiert militärisches Gelände – widerspricht der amtlichen Wohnnutzung', Confidence.MEDIUM
            out.append(Finding(rule_id=f'OSM_{h.category.upper()}', verdict=verdict, title_de=title, reason_de=h.reason_de,
                               evidence=f'OSM {h.key}={h.value}' + (f' („{h.name}“)' if h.name else ''), confidence=conf, source_id='osm-overpass'))
    # --- Innenbereich-Indiz (Baulücke) --------------------------------------------------------------------------------
    b = ev.buildings
    if b and b.nearby_residential >= 8 and ev.shares:
        top = classify_code(ev.shares[0].code)
        if top and top.verdict == Verdict.RESTRICTED and top.soft:
            out.append(Finding(rule_id='INNENBEREICH_INDIZ', verdict=Verdict.CANDIDATE, title_de='Dicht bebaute Umgebung (Baulücke denkbar)',
                               reason_de=f'{b.nearby_residential} Wohngebäude im Umkreis von {b.nearby_radius_m} m. Liegt das Flurstück im Zusammenhang bebauten Ortsteil, wäre §34 BauGB (Einfügen in die Umgebung) maßgeblich. Das ist nur ein Indiz.',
                               evidence=f'ALKIS Gebäude: {b.nearby_residential} von {b.nearby_total} Gebäuden im Umkreis sind Wohngebäude', confidence=Confidence.LOW, source_id='buildings'))
    return sorted(out, key=lambda f: (-ORDER[f.verdict], -CONF_ORDER[f.confidence]))


def _aggregate(findings: list[Finding]) -> tuple[Verdict, Confidence]:
    live = [f for f in findings if f.affects_verdict]
    nb = [f for f in live if f.verdict == Verdict.NOT_BUILDABLE]
    rs = [f for f in live if f.verdict == Verdict.RESTRICTED]
    pos = [f for f in live if f.verdict == Verdict.CANDIDATE]
    if nb:
        srcs = {f.source_id for f in nb}
        top = max(CONF_ORDER[f.confidence] for f in nb)
        return Verdict.NOT_BUILDABLE, Confidence.HIGH if (len(srcs) >= 2 or top == 2) else Confidence.MEDIUM
    if rs:
        soft_ids = {f'ELU_{c.category.upper()}' for _, c in CLASSES if c.soft} | {'FNP_NICHT_WOHNEN', 'SCHUTZ_LSG', 'SCHUTZ_FFH', 'SCHUTZ_VSG'}
        hard = [f for f in rs if f.rule_id not in soft_ids]
        lifters = [f for f in pos if f.rule_id in ('BORIS_BAULAND', 'FNP_WOHNEN', 'INNENBEREICH_INDIZ')
                   or (f.rule_id == 'ELU_RESIDENTIAL' and (f.share_of_parcel or 0) >= 0.4)]
        if not hard and lifters:
            strong = [f for f in lifters if f.rule_id != 'INNENBEREICH_INDIZ']
            return Verdict.CANDIDATE, Confidence.MEDIUM if strong else Confidence.LOW
        srcs = {f.source_id for f in rs}
        return Verdict.RESTRICTED, Confidence.HIGH if len(srcs) >= 2 else Confidence.MEDIUM
    if pos:
        srcs = {f.source_id for f in pos}
        return Verdict.CANDIDATE, Confidence.HIGH if len(srcs) >= 2 else (Confidence.MEDIUM if pos[0].confidence != Confidence.LOW else Confidence.LOW)
    return Verdict.UNKNOWN, Confidence.LOW


HEADLINES = {
    Verdict.NOT_BUILDABLE: 'Hier ist ein Wohnhaus voraussichtlich nicht zulässig.',
    Verdict.RESTRICTED: 'Wohnbebauung nur eingeschränkt oder ausnahmsweise denkbar.',
    Verdict.CANDIDATE: 'Wohnbebauung voraussichtlich denkbar – nichts davon ist amtlich bestätigt.',
    Verdict.UNKNOWN: 'Eignung nicht sicher bestimmbar – Entwurf nur mit Vorbehalt.',
}


def decide(ev: Evidence) -> Decision:
    findings = build_findings(ev)
    verdict, conf = _aggregate(findings)
    pending_core = ev.stage == 'core'
    if ev.parcel is None:
        st = ev.statuses.get('alkis-inspire-he')
        outage = bool(st and st.status == 'UNAVAILABLE')
        reason = ('Das Liegenschaftskataster ist gerade nicht erreichbar. Bitte gleich nochmal klicken.' if outage else
                  'An diesem Punkt gibt es kein Flurstück (z. B. außerhalb Hessens, Gewässer oder Datenlücke). Bitte einen anderen Punkt wählen.')
        top = next((f for f in findings if f.verdict == Verdict.NOT_BUILDABLE and f.affects_verdict), None)
        if top:
            reason += f' Die Umgebungsdaten sagen außerdem: {top.title_de}.'
        headline = HEADLINES[Verdict.NOT_BUILDABLE] if top and not outage else ('Kataster nicht erreichbar.' if outage else 'Kein Flurstück gefunden – ohne Grundstück kein Entwurf.')
        return Decision(verdict, conf, headline, DesignMode.BLOCKED, reason, findings, regulations(ev, verdict))
    if verdict == Verdict.NOT_BUILDABLE:
        top = next(f for f in findings if f.verdict == Verdict.NOT_BUILDABLE and f.affects_verdict)
        mode, reason = DesignMode.BLOCKED, f'Gesperrt wegen: {top.title_de}. {top.evidence}.'
        if top.rule_id == 'ELU_TRANSPORT':
            reason += ' Tipp: ein Flurstück neben der Straße bzw. Verkehrsfläche anklicken.'
        override = conf != Confidence.HIGH
    elif verdict == Verdict.CANDIDATE and conf != Confidence.LOW:
        conflict = next((f for f in findings if f.affects_verdict and f.verdict == Verdict.RESTRICTED), None)
        mode = DesignMode.FULL
        reason = ('Nach den angebundenen Quellen spricht nichts Hartes gegen einen Wohnhaus-Entwurf. Bebauungsplan und Abstandsrecht sind trotzdem noch zu prüfen.'
                  + (f' Widerspruch beachten: {conflict.title_de}.' if conflict else ''))
    elif verdict == Verdict.CANDIDATE:
        mode, reason = DesignMode.EXPLORATION, 'Entwurf möglich, aber nur als Studie: die Hinweise auf Bauland sind schwach (Umgebung statt amtlicher Plan).'
    elif verdict == Verdict.RESTRICTED:
        top = next((f for f in findings if f.verdict == Verdict.RESTRICTED and f.affects_verdict), None)
        mode, reason = DesignMode.EXPLORATION, f'Entwurf als Studie möglich, eine Genehmigung ist unsicher: {top.title_de if top else "Einschränkung"}.'
    else:
        mode, reason = DesignMode.EXPLORATION, 'Die Datenlage reicht nicht für ein Urteil. Der Entwurf läuft als Studie weiter; die offenen Punkte stehen unten.'
    down = [n for n in ('elu', 'boris', 'buildings') if ev.statuses.get(n) and ev.statuses[n].status == 'UNAVAILABLE']
    if down and mode == DesignMode.FULL:
        mode, reason = DesignMode.EXPLORATION, f'Entwurf als Studie: {len(down)} Kernquelle(n) nicht erreichbar ({", ".join(down)}); bitte später erneut abfragen.'
    if pending_core and verdict != Verdict.NOT_BUILDABLE:
        reason += ' (Planungs- und Schutzdaten werden noch geladen.)'
    return Decision(verdict, conf, HEADLINES[verdict], mode, reason, findings, regulations(ev, verdict), override_allowed=(verdict == Verdict.NOT_BUILDABLE and conf != Confidence.HIGH))


def regulations(ev: Evidence, verdict: Verdict) -> list[RegulationItem]:
    R = RegulationItem
    items: list[RegulationItem] = []
    b, v = ev.buildings, ev.value
    # Einordnung
    residential_top = bool(ev.shares) and (classify_code(ev.shares[0].code) or None) is not None and classify_code(ev.shares[0].code).verdict == Verdict.CANDIDATE
    dense = bool(b and b.nearby_residential >= 8)
    out_hint = bool(v and (v.aussenbereich_hint or v.entwicklungszustand in ('LF', 'SF'))) or (bool(ev.shares) and classify_code(ev.shares[0].code) is not None and classify_code(ev.shares[0].code).category in ('agriculture', 'forest') and not dense)
    if verdict == Verdict.NOT_BUILDABLE:
        einordnung, st = 'Keine Wohnbaufläche – Bebauung nicht vorgesehen.', 'INDICATION'
    elif out_hint:
        einordnung, st = 'Voraussichtlich Außenbereich (§ 35 BauGB): Wohnhaus nur ausnahmsweise.', 'INDICATION'
    elif residential_top or (v and v.entwicklungszustand == 'B') or dense:
        einordnung, st = 'Voraussichtlich Innenbereich (§ 34 BauGB) bzw. Baugebiet: Zulässigkeit nach Bebauungsplan oder Einfügen in die Umgebung.', 'INDICATION'
    else:
        einordnung, st = 'Planungsrechtliche Einordnung nicht bestimmbar.', 'NOT_CONNECTED'
    items.append(R(id='bauplanungsrecht', label_de='Planungsrechtliche Einordnung', value_de=einordnung, status=st, confidence=Confidence.LOW))
    items.append(R(id='bebauungsplan', label_de='Bebauungsplan', status='NOT_CONNECTED', confidence=Confidence.LOW,
                   value_de='Nicht angebunden: Hessen hat kein landesweites B-Plan-Open-Data-Register; Gemeinden stellen XPlanGML einzeln bereit. GRZ/GFZ, Geschosse, Baugrenzen und Dachform stehen dort. Auskunft bei der Gemeinde oder über bauleitplanung.hessen.de.'))
    fnp = [h for h in ev.planning if h.layer == 'regfnp']
    if fnp:
        items.append(R(id='fnp', label_de='Flächennutzungsplan (RegFNP)', status='OFFICIAL_DATA', source_id='regfnp', confidence=Confidence.MEDIUM,
                       value_de='; '.join(f'{h.label_de} ({pct(h.share or 0)})' for h in fnp)))
    elif 'regfnp' in ev.statuses and ev.statuses['regfnp'].status in ('OK', 'NO_MATCH'):
        items.append(R(id='fnp', label_de='Flächennutzungsplan (RegFNP)', status='NOT_CONNECTED', source_id='regfnp', confidence=Confidence.LOW,
                       value_de='Kein Treffer: der Regionale FNP deckt nur die Region FrankfurtRheinMain ab. Kommunale Flächennutzungspläne sind nicht angebunden.'))
    if ev.shares:
        items.append(R(id='nutzung', label_de='Amtliche Bodennutzung (ALKIS)', status='OFFICIAL_DATA', source_id='elu', confidence=Confidence.HIGH,
                       value_de='; '.join(f'{s.name_de} {pct(s.share)}' for s in ev.shares[:4])))
    if v and v.eur_per_m2 is not None:
        bits = [f'{euro(v.eur_per_m2)} €/m²', v.entwicklungszustand_de or v.entwicklungszustand or '', v.nutzung_de or v.nutzung or '']
        extra = f', {v.ergaenzung}' if v.ergaenzung else ''
        items.append(R(id='bodenrichtwert', label_de='Bodenrichtwert', status='OFFICIAL_DATA', source_id='boris', confidence=Confidence.MEDIUM,
                       value_de=', '.join(x for x in bits if x) + extra + (f' · Stichtag {v.stichtag}' if v.stichtag else '') + (f' · {v.gemeinde}' if v.gemeinde else '')))
    if b:
        on = (f'{b.on_parcel} Gebäude auf dem Flurstück ({b.on_parcel_footprint_m2:.0f} m² Grundfläche' + (f', bis {b.max_floors_on_parcel} Geschosse' if b.max_floors_on_parcel else '') + ')') if b.on_parcel else 'Flurstück unbebaut'
        near = f'Umkreis {b.nearby_radius_m} m: {b.nearby_total} Gebäude, davon {b.nearby_residential} Wohngebäude' + (f', typisch {b.nearby_median_floors:g} Geschosse' if b.nearby_median_floors else '')
        items.append(R(id='bestand', label_de='Bebauung (ALKIS)', status='OFFICIAL_DATA', source_id='buildings', confidence=Confidence.HIGH, value_de=f'{on}. {near}.'))
    den = [p for p in ev.protections if p.kind in ('denkmal', 'archaeologie')]
    if den:
        items.append(R(id='denkmal', label_de='Denkmalschutz', status='OFFICIAL_DATA', source_id='denkmal', confidence=Confidence.HIGH,
                       value_de='; '.join(f'{p.label_de}' + (f' „{p.name}“' if p.name else '') + ('' if p.on_parcel else f' ({p.distance_m:.0f} m)') for p in den[:3])))
    elif 'denkmal' in ev.statuses and ev.statuses['denkmal'].status == 'NO_MATCH':
        items.append(R(id='denkmal', label_de='Denkmalschutz', status='OFFICIAL_DATA', source_id='denkmal', confidence=Confidence.MEDIUM, value_de='Kein Kulturdenkmal auf oder bis 30 m neben dem Flurstück erfasst.'))
    hq = [p for p in ev.protections if p.kind == 'hq100']
    if hq:
        items.append(R(id='hochwasser', label_de='Hochwasser (HQ100)', status='OFFICIAL_DATA', source_id='hq100', confidence=Confidence.MEDIUM, value_de=f'Flurstück zu {pct(hq[0].share or 0)} im festgesetzten Überschwemmungsgebiet' + (f' „{hq[0].name}“' if hq[0].name else '') + '.'))
    elif 'hq100' in ev.statuses and ev.statuses['hq100'].status == 'NO_MATCH':
        items.append(R(id='hochwasser', label_de='Hochwasser (HQ100)', status='OFFICIAL_DATA', source_id='hq100', confidence=Confidence.MEDIUM, value_de='Kein festgesetztes Überschwemmungsgebiet (HQ100) auf dem Flurstück erfasst.'))
    sg = [p for p in ev.protections if p.kind in ('nsg', 'nationalpark', 'naturmonument', 'lsg', 'ffh', 'vsg', 'biosphaere', 'naturpark')]
    if sg:
        items.append(R(id='schutzgebiete', label_de='Naturschutz (Schutzgebiete)', status='OFFICIAL_DATA', source_id='schutzgebiete', confidence=Confidence.MEDIUM,
                       value_de='; '.join(f'{p.label_de}' + (f' „{p.name}“' if p.name else '') for p in sg[:4]) + ' (Punkttest am Flurstück).'))
    elif 'schutzgebiete' in ev.statuses and ev.statuses['schutzgebiete'].status == 'NO_MATCH':
        items.append(R(id='schutzgebiete', label_de='Naturschutz (Schutzgebiete)', status='OFFICIAL_DATA', source_id='schutzgebiete', confidence=Confidence.MEDIUM, value_de='Kein Schutzgebiet (NSG, LSG, Natura 2000, Nationalpark) am Flurstück erfasst (Punkttest).'))
    rp = [h for h in ev.planning if h.layer in ('regionalplan', 'lep') and h.share is not None]
    if rp:
        items.append(R(id='regionalplan', label_de='Regionalplan / LEP', status='OFFICIAL_DATA', source_id=rp[0].layer, confidence=Confidence.MEDIUM,
                       value_de='; '.join(f'{h.label_de} ({h.nature_de or h.layer}, {pct(h.share or 0)})' for h in rp[:4])))
    items.append(R(id='abstandsflaechen', label_de='Abstandsflächen (HBO)', status='UNVERIFIED_CANDIDATE', confidence=Confidence.LOW,
                   value_de='Grundformel § 6 Abs. 4–5 HBO im amtlichen Primärtext geprüft (02.11.2026). Projektbezogene Höhen, Dachanteile und Ausnahmen bleiben zu prüfen; daraus wird keine Baugrenze abgeleitet.'))
    items.append(R(id='ausnutzung', label_de='GRZ / GFZ / Höhe / Dachform', status='NOT_CONNECTED', confidence=Confidence.LOW,
                   value_de=('Stehen im Bebauungsplan bzw. folgen aus § 34 BauGB. Aus den abgefragten offenen Daten nicht verfügbar. '
                          + 'Festsetzungen unter „Vorschriften“ eintragen, sobald sie vorliegen; eingetragene Werte gelten hart. '
                          + 'Bis dahin dient die Umgebung als Richtwert-Rahmen (nicht verbindlich): Geschosse, Höhe und Grenzabstand der Nachbargebäude'
                          + (f', Geschosszahl der Bodenrichtwertzone: {v.geschosszahl}' if v and getattr(v, 'geschosszahl', None) else '')
                          + (f', typisch {b.nearby_median_floors:g} Geschosse im Umkreis von {b.nearby_radius_m} m' if b and b.nearby_median_floors else '')
                          + '. Der Entwurf wird automatisch in diesen Rahmen gebaut; Überschreitungen werden als „vermutlich Genehmigung nötig“ gemeldet.')))
    return items
