"""Registry of the official Hessen WFS sources and the generic "ask the server with a spatial filter" query.

Every source below was probed live on 2026-10-28 (see docs/HESSEN_SITE_INTELLIGENCE.md): HTTP 200, WFS 2.0.0, GML 3.2,
EPSG:4326. Querying with ``fes:Intersects`` (POST) lets the *server* do the point/parcel test, which returned exactly the
covering features in 0.15–0.5 s, where a bbox GET returned up to 2.8 MB / ~1 s and could silently hit the ``count`` cap.
Licences: automated retrieval of the Hessen geobasis data is free (§24 HVGG); each source carries its own licence/attribution.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from shapely.geometry.base import BaseGeometry
from . import geo, wfs
from .fetch import Fetcher
from .models import DataStatus, SourceRef

NS_PLU = {'plu': 'http://inspire.ec.europa.eu/schemas/plu/4.0'}
HE_GOV = 'Hessisches Ministerium für Landesentwicklung, Wohnen, ländlichen Raum und Verbraucherschutz'
_RP = 'https://geodatendienste-landesplanung-hessen.de/ows/services/'
_UMWELT_NS = 'https://geodienste-umwelt.hessen.de/arcgis/services/inspire/gebiete_naturbedingter_risiken/MapServer/WFSServer'


@dataclass(frozen=True)
class WfsSource:
    id: str
    name: str
    url: str
    types: tuple[str, ...]
    ns: dict[str, str]
    geom_prop: str | None            # None -> bbox GET (geometry path too complex for a filter)
    licence: str
    info_url: str
    attribution: str
    ttl_s: float = 7 * 86400
    timeout_s: float = 8.0
    count: int = 50
    buffer_deg: float = 0.0          # widen the query geometry (≈ 0.0003° ≈ 25–33 m) to see neighbours
    point_only: bool = False         # ask with the parcel's representative point: huge parcels (forest) otherwise return multi-MB polygons
    heavy: bool = False
    extra: dict[str, str] = field(default_factory=dict)

    def ref(self, stamp: str | None = None) -> SourceRef:
        return SourceRef(id=self.id, name=self.name, licence=self.licence, url=self.info_url, attribution=self.attribution, retrieved=stamp)


SOURCES: dict[str, WfsSource] = {s.id: s for s in [
    WfsSource('elu', 'ALKIS Existierende Bodennutzung (INSPIRE ELU)', 'https://inspire-hessen.de/ows/services/org.2.5112b27b-55b7-47df-89f0-b169add4a471_wfs',
              ('elu:ExistingLandUseObject',), {'elu': 'http://inspire.ec.europa.eu/schemas/elu/4.0'}, 'elu:geometry',
              'DL-DE Zero 2.0', 'https://www.geoportal.hessen.de/spatial-objects/709', '© Hessische Verwaltung für Bodenmanagement und Geoinformation', timeout_s=7),
    WfsSource('buildings', 'ALKIS Gebäude 2D (INSPIRE BU)', 'https://inspire-hessen.de/ows/services/org.2.1f07430b-f7b0-4c4e-a698-fb6c60384f59_wfs',
              ('bu-core2d:Building',), {'bu-core2d': 'http://inspire.ec.europa.eu/schemas/bu-core2d/4.0'}, None,
              'DL-DE Zero 2.0', 'https://www.geoportal.hessen.de/spatial-objects/711', '© Hessische Verwaltung für Bodenmanagement und Geoinformation', timeout_s=7, count=90),
    WfsSource('lod2', 'Gebäude 3D LoD2 Hessen (INSPIRE bu-core3d, gemessene Höhen)', 'https://inspire-hessen.de/ows/services/org.2.ef07833e-78a6-4c2c-a895-e31de788aac3_wfs',
              ('bu-core3d:Building',), {'bu-core3d': 'http://inspire.ec.europa.eu/schemas/bu-core3d/4.0'}, None,
              'DL-DE Zero 2.0', 'https://www.geoportal.hessen.de/spatial-objects/831', '© Hessische Verwaltung für Bodenmanagement und Geoinformation', timeout_s=12, count=120, ttl_s=30 * 86400),
    WfsSource('boris', 'Bodenrichtwerte Hessen 2024 (BORIS)', 'https://www.gds.hessen.de/wfs2/boris/cgi-bin/brw/2024/wfs',
              ('boris:BR_BodenrichtwertZonal',), {'boris': 'http://www.adv-online.de/namespaces/adv/brm/2.1', 'adv': 'http://www.adv-online.de/namespaces/adv/gid/7.1'}, 'adv:position',
              'DL-DE Zero 2.0', 'https://www.geoportal.hessen.de/spatial-objects/864', '© Gutachterausschüsse für Immobilienwerte in Hessen / HVBG', timeout_s=8, count=20, ttl_s=30 * 86400),
    WfsSource('regfnp', 'Regionaler Flächennutzungsplan FrankfurtRheinMain (INSPIRE PLU)', 'https://www.gdi-inspireumsetzer.de/ows/services/org.15.0c0e71f6-43c6-495f-9683-38444bc2ef30_wfs',
              ('plu:ZoningElement',), NS_PLU, 'plu:geometry', 'siehe Dienstmetadaten (Regionalverband FrankfurtRheinMain)', 'https://www.geoportal.hessen.de/spatial-objects/843',
              '© Regionalverband FrankfurtRheinMain', timeout_s=8, count=20),
    WfsSource('rp_sued', 'Regionalplan Südhessen (INSPIRE PLU)', _RP + 'org.3.e6a0ab53-0f15-42b7-ab4f-ec66febe249f_wfs', ('plu:SupplementaryRegulation',), NS_PLU, 'plu:geometry',
              'dl-by-de/2.0 (Namensnennung)', 'https://landesplanung.hessen.de', f'Datenquelle: {HE_GOV}', timeout_s=10, count=30, point_only=True, heavy=True),
    WfsSource('rp_mittel', 'Regionalplan Mittelhessen (INSPIRE PLU)', _RP + 'org.3.590d38d2-c837-4824-a74d-d35089dd45c5_wfs', ('plu:SupplementaryRegulation',), NS_PLU, 'plu:geometry',
              'dl-by-de/2.0 (Namensnennung)', 'https://landesplanung.hessen.de', f'Datenquelle: {HE_GOV}', timeout_s=10, count=30, point_only=True, heavy=True),
    WfsSource('rp_nord', 'Regionalplan Nordhessen (INSPIRE PLU)', _RP + 'org.3.d391703f-373c-4bb9-ace7-45e9f159fb23_wfs', ('plu:SupplementaryRegulation',), NS_PLU, 'plu:geometry',
              'dl-by-de/2.0 (Namensnennung)', 'https://landesplanung.hessen.de', f'Datenquelle: {HE_GOV}', timeout_s=10, count=30, point_only=True, heavy=True),
    WfsSource('lep', 'Landesentwicklungsplan Hessen (INSPIRE PLU)', _RP + 'org.3.f15cc73c-df6a-40ba-a05a-f4d8e221e75c_wfs', ('plu:SupplementaryRegulation',), NS_PLU, 'plu:geometry',
              'dl-by-de/2.0 (Namensnennung)', 'https://landesplanung.hessen.de', f'Datenquelle: {HE_GOV}', timeout_s=8, count=30, buffer_deg=0.0003),
    WfsSource('hq100', 'Überschwemmungsgebiete HQ100 nach HWG', 'https://geodienste-umwelt.hessen.de/arcgis/services/inspire/gebiete_naturbedingter_risiken/MapServer/WFSServer',
              ('inspire_gebiete_naturbedingter_risiken:Ueberschwemmungsgebiete_HQ100_nach_HWG',), {'inspire_gebiete_naturbedingter_risiken': _UMWELT_NS},
              'inspire_gebiete_naturbedingter_risiken:SHAPE', 'DL-DE Zero 2.0 (laut Dienst: keine rechtsverbindliche Darstellung)', 'https://www.geoportal.hessen.de/spatial-objects/264',
              '© Hessisches Landesamt für Naturschutz, Umwelt und Geologie (HLNUG)', timeout_s=8, count=10, ttl_s=14 * 86400, heavy=True),
    WfsSource('schutzgebiete', 'Schutzgebiete Hessen (INSPIRE, HMLU/HLNUG)', 'https://geodienste-umwelt.hessen.de/arcgis/services/inspire/schutzgebiete/MapServer/WFSServer',
              tuple(f'inspire_schutzgebiete:{t}' for t in ('Naturschutzgebiete', 'Nationalpark', 'Nationales_Naturmonument', 'Landschaftsschutzgebiete', 'Fauna-Flora-Habitate', 'Vogelschutzgebiete', 'Biosphaerenreservat', 'Naturparke')),
              {'inspire_schutzgebiete': 'https://10.23.18.33:6443/arcgis/services/services/schutzgebiete/MapServer/WFSServer'}, 'inspire_schutzgebiete:Shape',
              'Kostenfreie Nutzung inkl. gewerblich; Weiterverkauf der Daten unzulässig; keine rechtsverbindliche Auskunft', 'https://geodienste-umwelt.hessen.de/arcgis/rest/services/inspire/schutzgebiete/MapServer',
              'Darstellung auf der Grundlage von Daten des Hessischen Ministeriums für Landwirtschaft und Umwelt, Weinbau, Forsten, Jagd und Heimat (HMLU); Naturparke: Landesbetrieb HessenForst',
              timeout_s=8, count=20, ttl_s=14 * 86400, point_only=True, heavy=True),
    WfsSource('denkmal', 'Denkmalschutz Hessen (DenkXweb)', 'https://geodienste.denkx.de/geoserver/denkx/wfs',
              ('denkx:baudenkmal', 'denkx:flaechendenkmal', 'denkx:archaeologischesDenkmal'), {'denkx': 'denkx'}, 'denkx:geometry',
              'siehe Dienstmetadaten (Landesamt für Denkmalpflege Hessen)', 'https://denkxweb.denkmalpflege-hessen.de', '© Landesamt für Denkmalpflege Hessen',
              timeout_s=8, count=30, buffer_deg=0.0003),
]}


# Hessen: Regierungsbezirk digit of the Gemeindekennzeichen (06 4 xx = Darmstadt, 5 = Gießen, 6 = Kassel) == the three Planungsregionen.
REGION_SOURCE = {'4': 'rp_sued', '5': 'rp_mittel', '6': 'rp_nord'}


def regional_plan_for(boris_features: list[wfs.Feature]) -> list[str]:
    """Only the Regionalplan of the region the point lies in (BORIS carries the Gemeindekennzeichen); unknown -> ask all three."""
    for f in boris_features:
        rb = f.get('gemeinde>BR_Gemeinde>kennzeichen>BR_Gemeindekennzeichen>regierungsbezirk', 'regierungsbezirk')
        if rb in REGION_SOURCE:
            return [REGION_SOURCE[rb]]
    return list(REGION_SOURCE.values())


@dataclass
class Outcome:
    features: list[wfs.Feature]
    status: DataStatus
    geometry_used: str = 'parcel'


def _body(src: WfsSource, g: BaseGeometry) -> str:
    nsd = ' '.join(f'xmlns:{k}="{v}"' for k, v in src.ns.items())
    gm = geo.gml(g)
    qs = ''.join(
        f'<wfs:Query typeNames="{t}" srsName="{geo.URN}"><fes:Filter><fes:Intersects><fes:ValueReference>{src.geom_prop}</fes:ValueReference>{gm}</fes:Intersects></fes:Filter></wfs:Query>'
        for t in src.types)
    return (f'<?xml version="1.0" encoding="UTF-8"?><wfs:GetFeature service="WFS" version="2.0.0" count="{src.count}" '
            f'xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:fes="http://www.opengis.net/fes/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" {nsd}>{qs}</wfs:GetFeature>')


def query(src: WfsSource, fetcher: Fetcher, g: BaseGeometry, bbox_half_deg: float = 0.0006) -> Outcome:
    """Features of ``src`` that intersect ``g`` (parcel polygon or point). Never raises: failures become a status."""
    t0 = time.perf_counter()

    def status(state: str, detail: str | None = None, cached: bool = False) -> DataStatus:
        return DataStatus(source_id=src.id, status=state, detail=detail, ms=int((time.perf_counter() - t0) * 1000), cached=cached)

    centre = geo.rep_point(g)
    attempts: list[tuple[str, BaseGeometry]] = []
    if src.point_only:
        attempts.append(('point', centre))
    else:
        q = g.buffer(src.buffer_deg) if src.buffer_deg else g
        attempts.append(('parcel' if g.geom_type != 'Point' else 'point', q))
        if g.geom_type != 'Point':
            attempts.append(('point', centre))
    last_err = 'keine Antwort'
    for label, qg in attempts:
        if src.geom_prop is None:  # bbox GET (buildings)
            params = wfs.request_params(src.types[0], centre.y, centre.x, bbox_half_deg, src.count)
            res = fetcher.get(src.id, src.url, params, src.ttl_s, src.timeout_s, wfs.usable)
        else:
            res = fetcher.post_xml(src.id, src.url, _body(src, qg), src.ttl_s, src.timeout_s, wfs.usable)
        if res.body is None:
            last_err = res.error or last_err
            if label == 'point' or (res.error or '').startswith('Timeout') or 'Connect' in (res.error or ''):
                break
            continue
        try:
            feats = wfs.parse_features(res.body)
        except ValueError as exc:
            last_err = str(exc)
            continue  # e.g. polygon filter rejected -> retry with a point
        note = 'veralteter Cache (Dienst nicht erreichbar)' if res.stale else ('Cache' if res.cached else None)
        return Outcome(feats, status('OK' if feats else 'NO_MATCH', note, res.cached), geometry_used=label)
    return Outcome([], status('UNAVAILABLE', f'{src.name}: {last_err}'))
