"""Versioned hand-over contract between site screening and the (separately built) architecture/house generation.

The dossier says what is known, how sure we are, and what is still open. It is deliberately conservative:
- ``architectural_constraints`` stay empty until a human or authority *verifies* values (``VerifiedConstraints``). Only then a
  buildable envelope is derived (parcel minus uniform setback — the intersection rule of the MACE spec; easements are an
  open point and flagged).
- Candidate values (e.g. HBO setback) travel as ``known_constraints`` with status UNVERIFIED_CANDIDATE and are never fed into geometry.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from .models import (BuildingStats, Confidence, DesignMode, LandUseShare, LandValue, MaceConstraints, MaceOutput, MaceVertex, PlanningHit, ProtectionHit,
                     RegulationItem, SiteAssessment, SourceRef, Verdict)

SCHEMA = 'archaitect.site-dossier/1'
_TO_UTM = Transformer.from_crs('EPSG:4326', 'EPSG:25832', always_xy=True)


class DesignGate(BaseModel):
    mode: DesignMode
    verdict: Verdict
    confidence: Confidence
    reason_de: str
    hard_block: bool
    override_allowed: bool = False


class SiteRef(BaseModel):
    lat: float
    lon: float
    municipality: str | None
    gemarkung_nr: str | None
    flur: int | None
    flurstueck: str | None
    national_reference: str | None
    area_alkis_m2: float | None


class KnownConstraint(BaseModel):
    id: str
    kind: str                     # setback | zoning | protection | hazard | density | height
    value: dict
    status: str                   # OFFICIAL_DATA | INDICATION | UNVERIFIED_CANDIDATE | VERIFIED_BY_USER
    source: str
    note_de: str = ''


class SiteContext(BaseModel):
    land_use_shares: list[LandUseShare]
    buildings: BuildingStats | None
    land_value: LandValue | None
    planning: list[PlanningHit]
    protections: list[ProtectionHit]


class SiteDossier(BaseModel):
    schema_version: str = SCHEMA
    generated_at: str
    design_gate: DesignGate
    site: SiteRef
    mace: MaceOutput | None
    regulations: list[RegulationItem]
    context: SiteContext
    known_constraints: list[KnownConstraint]
    open_questions_de: list[str]
    sources: list[SourceRef]
    next_stages: list[str] = ['bebauungsplan_intake', 'verified_constraints', 'buildable_envelope', 'massing_and_plan', 'render_and_video']
    disclaimer_de: str


class VerifiedConstraints(BaseModel):
    """Values someone checked against the Bebauungsplan / authority statement. Everything is optional; null stays UNKNOWN."""
    verified_by: str = Field(min_length=2, description='Who verified (name/role) — mandatory, this is the audit trail')
    basis_de: str = Field(min_length=3, description='Document and clause, e.g. "B-Plan Nr. 12, textliche Festsetzung 2.1"')
    grz: float | None = Field(default=None, gt=0, le=1)
    gfz: float | None = Field(default=None, gt=0, le=4)
    max_building_height_meters: float | None = Field(default=None, gt=0, le=200)
    max_stories: int | None = Field(default=None, ge=1, le=60)
    setback_lines_offset_meters: float | None = Field(default=None, ge=0, le=50, description='Uniform distance to the parcel boundary')
    roof_types_allowed: list[str] = []
    roof_pitch_min_deg: float | None = Field(default=None, ge=0, le=75)
    roof_pitch_max_deg: float | None = Field(default=None, ge=0, le=75)
    max_eave_height_meters: float | None = Field(default=None, gt=0, le=100, description='Traufhöhe, falls festgesetzt')
    bauweise: str | None = Field(default=None, max_length=20, description='offen / geschlossen / abweichend')


class PlanningLimits(BaseModel):
    """The user's own planning limits (e.g. read from a B-Plan but not formally verified, or a self-imposed brief). Enforced in the studio like
    verified values, but always labelled 'eigene Vorgabe, nicht als Bebauungsplan geprüft' and never exported as VERIFIED."""
    grz: float | None = Field(default=None, gt=0, le=1)
    gfz: float | None = Field(default=None, gt=0, le=4)
    max_building_height_meters: float | None = Field(default=None, gt=0, le=200)
    max_stories: int | None = Field(default=None, ge=1, le=60)
    setback_lines_offset_meters: float | None = Field(default=None, ge=0, le=50)
    roof_types_allowed: list[str] = []
    roof_pitch_min_deg: float | None = Field(default=None, ge=0, le=75)
    roof_pitch_max_deg: float | None = Field(default=None, ge=0, le=75)
    max_eave_height_meters: float | None = Field(default=None, gt=0, le=100)
    note_de: str = Field(default='', max_length=300)


def _open_questions(a: SiteAssessment) -> list[str]:
    q = ['Bebauungsplan der Gemeinde einholen (Festsetzungen zu GRZ/GFZ, Geschossen, Baugrenzen, Dachform).',
         'Abstandsflächen projektbezogen prüfen: Gelände, Dachaufbauten, Grenzbauten und Ausnahmen; Grundformel ist gegen HBO-Primärtext geprüft.',
         'Baulasten, Grunddienstbarkeiten und Leitungsrechte beim Bauaufsichtsamt/Grundbuch erfragen (nicht in Open Data).']
    if a.design_mode != DesignMode.FULL:
        q.append('Planungsrechtliche Zulässigkeit (§ 34/§ 35 BauGB) mit der Bauaufsicht klären – Vorprüfung ist nicht belastbar genug.')
    if any(s.status == 'UNAVAILABLE' for s in a.data_status):
        q.append('Mindestens eine Datenquelle war nicht erreichbar: Abfrage später wiederholen.')
    if a.protections and any(p.kind == 'hq100' for p in a.protections):
        q.append('Überschwemmungsgebiet: wasserrechtliche Anforderungen bei der Wasserbehörde erfragen.')
    if a.protections and any(p.kind in ('denkmal', 'archaeologie') for p in a.protections):
        q.append('Denkmalschutz: Abstimmung mit der Denkmalbehörde vor Entwurfsfreigabe.')
    return q


def build_dossier(a: SiteAssessment) -> SiteDossier:
    p = a.parcel
    muni = a.land_value.gemeinde if a.land_value else None
    kc: list[KnownConstraint] = [
        KnownConstraint(id='hbo_abstandsflaeche', kind='setback', value={'factor_h': 0.4, 'min_m': 2.5, 'gewerbe_factor_h': 0.2}, status='UNVERIFIED_CANDIDATE',
                        source='Amtliche HBO-Broschüre Oktober 2025/Korrektur April 2026, PDF-Seite 16, § 6 Abs. 4–5; Grundformel visuell geprüft 02.11.2026',
                        note_de='Grundformel belegt; konkrete Grundstücks-/Gebäudeanwendung und Ausnahmen bleiben zu prüfen.'),
    ]
    for h in a.planning:
        if h.share is not None and h.layer in ('regionalplan', 'lep', 'regfnp'):
            kc.append(KnownConstraint(id=f'{h.layer}:{h.code}', kind='zoning', value={'label': h.label_de, 'share': h.share, 'nature': h.nature_de}, status='OFFICIAL_DATA', source=h.layer))
    for pr in a.protections:
        kc.append(KnownConstraint(id=f'{pr.kind}', kind='hazard' if pr.kind == 'hq100' else 'protection', value={'label': pr.label_de, 'name': pr.name, 'on_parcel': pr.on_parcel, 'share': pr.share}, status='OFFICIAL_DATA', source=pr.kind))
    if a.land_value and a.land_value.eur_per_m2:
        kc.append(KnownConstraint(id='bodenrichtwert', kind='density', value={'eur_per_m2': a.land_value.eur_per_m2, 'nutzung': a.land_value.nutzung, 'ergaenzung': a.land_value.ergaenzung}, status='OFFICIAL_DATA', source='boris',
                                  note_de='Hinweis auf übliche Nutzung (z. B. MFH), keine Festsetzung.'))
    return SiteDossier(
        generated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        design_gate=DesignGate(mode=a.design_mode, verdict=a.verdict, confidence=a.confidence, reason_de=a.design_reason_de, hard_block=a.design_mode == DesignMode.BLOCKED, override_allowed=a.design_override_allowed),
        site=SiteRef(lat=a.lat, lon=a.lon, municipality=muni, gemarkung_nr=p.gemarkung_nr if p else None, flur=p.flur if p else None, flurstueck=p.label if p else None,
                     national_reference=p.national_reference if p else None, area_alkis_m2=p.area_alkis_m2 if p else None),
        mace=a.mace, regulations=a.regulations,
        context=SiteContext(land_use_shares=a.land_use_shares, buildings=a.buildings, land_value=a.land_value, planning=a.planning, protections=a.protections),
        known_constraints=kc, open_questions_de=_open_questions(a), sources=a.sources, disclaimer_de=a.disclaimer_de)


def with_verified_constraints(d: SiteDossier, v: VerifiedConstraints) -> SiteDossier:
    """Return a copy whose MACE constraints carry the verified values; derive the envelope when a setback is given."""
    if d.mace is None or d.design_gate.hard_block:
        return d
    out = d.model_copy(deep=True)
    m = out.mace
    assert m is not None
    c = m.architectural_constraints
    area = m.parcel_geometry.total_area_calculated_m2
    new = MaceConstraints(
        max_footprint_area_grz_m2=round(v.grz * area, 2) if v.grz else None,
        max_total_floor_area_gfz_m2=round(v.gfz * area, 2) if v.gfz else None,
        max_building_height_meters=v.max_building_height_meters, setback_lines_offset_meters=v.setback_lines_offset_meters,
        roof_types_allowed=v.roof_types_allowed, max_stories=v.max_stories, status='VERIFIED_BY_USER')
    flags = [f for f in m.pipeline_telemetry.flags if f not in ('NO_VERIFIED_ZONING_RULES', 'BUILDABLE_ENVELOPE_NOT_DERIVABLE')]
    if v.setback_lines_offset_meters is not None:
        ring = [(vx.x_coord, vx.y_coord) for vx in m.parcel_geometry.vertices]
        env = Polygon(ring).buffer(-v.setback_lines_offset_meters, join_style=2)
        if env.is_empty:
            flags.append('ENVELOPE_EMPTY_AFTER_SETBACK')
        else:
            if env.geom_type == 'MultiPolygon':
                env = max(env.geoms, key=lambda g: g.area)
                flags.append('ENVELOPE_LARGEST_PART_ONLY')
            pts = list(orient(env, 1.0).exterior.coords)[:-1]
            new.buildable_envelope_vertices = [MaceVertex(vertex_id=i + 1, x_coord=round(x, 3), y_coord=round(y, 3)) for i, (x, y) in enumerate(pts)]
        flags.append('ENVELOPE_UNIFORM_SETBACK_ONLY')
        flags.append('EASEMENTS_NOT_CONSIDERED')
    else:
        flags.append('BUILDABLE_ENVELOPE_NOT_DERIVABLE')
    flags.append(f'VERIFIED_BY:{v.verified_by}')
    m.architectural_constraints = new
    m.pipeline_telemetry.flags = flags
    out.known_constraints = [k for k in out.known_constraints if k.id != 'hbo_abstandsflaeche'] + [
        KnownConstraint(id='verified_by_user', kind='zoning', status='VERIFIED_BY_USER', source=v.verified_by, value=v.model_dump(exclude={'verified_by', 'basis_de'}), note_de=v.basis_de)]
    out.open_questions_de = [q for q in out.open_questions_de if 'Bebauungsplan der Gemeinde' not in q and 'Abstandsflächen' not in q]
    return out


def to_parcel_input(a: SiteAssessment) -> dict | None:
    """Exactly the payload of ``POST /geodata/validate`` (``GeoJSONParcelInput``): the identified parcel as a WGS84 polygon with its source.

    Feeds the existing parcel/geometry pipeline without any copy-paste. ``None`` when no parcel was identified or the site is hard-blocked.
    """
    p = a.parcel
    if p is None or a.design_mode == DesignMode.BLOCKED:
        return None
    muni = a.land_value.gemeinde if a.land_value else None
    ring = [[lon, lat] for lon, lat in p.ring_lonlat]
    return {
        'name': f'Flurstück {p.label}' + (f', {muni}' if muni else ''),
        'external_parcel_id': p.national_reference,
        'source_url': 'https://www.geoportal.hessen.de/spatial-objects/710',
        'source_crs': 'EPSG:4326',
        'data': {'type': 'Feature', 'properties': {'verdict': a.verdict.value, 'design_mode': a.design_mode.value, 'area_alkis_m2': p.area_alkis_m2},
                 'geometry': {'type': 'Polygon', 'coordinates': [ring]}},
    }
