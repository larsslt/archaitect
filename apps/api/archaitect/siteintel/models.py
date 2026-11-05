"""Contracts for the Hessen site screening. No value is ever presented as legally verified."""
from enum import Enum
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    NOT_BUILDABLE = 'NOT_BUILDABLE'  # indication that a residential building is excluded
    RESTRICTED = 'RESTRICTED'        # residential building only in exceptional / plan-dependent cases
    CANDIDATE = 'CANDIDATE'          # residential building conceivable, nothing verified
    UNKNOWN = 'UNKNOWN'              # not enough evidence (also: data source unavailable)


class Confidence(str, Enum):
    HIGH = 'HIGH'      # two independent official sources agree
    MEDIUM = 'MEDIUM'  # one official source
    LOW = 'LOW'        # indirect indication / heuristic only


class DesignMode(str, Enum):
    FULL = 'full'                  # nothing speaks against a residential design (still unverified, no Bebauungsplan)
    EXPLORATION = 'exploration'    # design allowed with a visible caveat: restricted, unknown or low-confidence
    BLOCKED = 'blocked'            # hard exclusion from official data, or no parcel to design on


class SourceRef(BaseModel):
    id: str
    name: str
    licence: str
    url: str | None = None
    attribution: str | None = None
    retrieved: str | None = Field(default=None, description='ISO timestamp of retrieval, or fixture marker')


class ParcelInfo(BaseModel):
    label: str = Field(description='Flurstücksnummer as printed, e.g. 73/3')
    zaehler: int | None = None
    nenner: int | None = None
    land: str = '06'
    gemarkung_nr: str | None = None
    flur: int | None = None
    national_reference: str
    area_alkis_m2: float | None = None
    valid_from: str | None = None
    geometry_type: str = 'Polygon'
    ring_lonlat: list[tuple[float, float]] = Field(description='Exterior ring, EPSG:4326 lon/lat, closed')
    n_holes_ignored: int = 0


class LandUseHit(BaseModel):
    key: str
    value: str
    name: str | None = None
    category: str
    verdict: Verdict
    reason_de: str


class Finding(BaseModel):
    rule_id: str
    verdict: Verdict
    title_de: str
    reason_de: str
    evidence: str = Field(description='What exactly was observed, with source')
    basis_status: str = Field(default='HEURISTIC_UNVERIFIED', description='HEURISTIC_UNVERIFIED | CANDIDATE_UNVERIFIED | VERIFIED')
    confidence: Confidence = Confidence.MEDIUM
    source_id: str | None = None
    affects_verdict: bool = Field(default=True, description='False = informational note that must not lower the verdict')
    share_of_parcel: float | None = Field(default=None, description='0..1 where the finding is area-based')


class RegulationItem(BaseModel):
    """One line of the "basic regulations" block. status says how much weight the line carries."""
    id: str
    label_de: str
    value_de: str
    status: str = Field(description='OFFICIAL_DATA | INDICATION | UNVERIFIED_CANDIDATE | NOT_CONNECTED')
    source_id: str | None = None
    confidence: Confidence = Confidence.MEDIUM


class LandUseShare(BaseModel):
    code: str
    name_de: str
    group_de: str
    share: float
    area_m2: float


class BuildingStats(BaseModel):
    on_parcel: int = 0
    on_parcel_footprint_m2: float = 0.0
    max_floors_on_parcel: int | None = None
    nearby_total: int = 0
    nearby_residential: int = 0
    nearby_radius_m: int = 100
    nearby_median_floors: float | None = None


class LandValue(BaseModel):
    eur_per_m2: float | None
    stichtag: str | None
    entwicklungszustand: str | None
    entwicklungszustand_de: str | None
    nutzung: str | None
    nutzung_de: str | None
    ergaenzung: str | None
    zone_nr: str | None
    gemeinde: str | None
    gemarkung: str | None
    bemerkung: str | None = None
    aussenbereich_hint: bool = False
    geschosszahl: str | None = None      # zone attributes of the Gutachterausschuss (typical for the zone, NOT a B-Plan setting)
    gfz_zone: float | None = None
    grz_zone: float | None = None
    bauweise: str | None = None
    tiefe_m: float | None = None


class PlanningHit(BaseModel):
    layer: str            # regfnp | regionalplan | lep
    code: str
    label_de: str
    nature_de: str | None = None
    share: float | None = None
    binding: str | None = None
    distance_m: float | None = None
    effect: str = 'note'  # restrict | note


class ProtectionHit(BaseModel):
    kind: str             # denkmal | archaeologie | hq100 | nsg | nationalpark | naturmonument | lsg | ffh | vsg | biosphaere | naturpark
    label_de: str
    name: str | None = None
    link: str | None = None
    on_parcel: bool = True
    distance_m: float | None = None
    share: float | None = None


class DataStatus(BaseModel):
    source_id: str
    status: str  # OK | UNAVAILABLE | NO_MATCH | PARTIAL
    detail: str | None = None
    ms: int | None = None
    cached: bool = False


class SiteAssessment(BaseModel):
    schema_version: str = 'archaitect.site-assessment/2'
    stage: str = 'full'  # core | context | full
    lat: float
    lon: float
    in_hessen: bool
    verdict: Verdict
    confidence: Confidence = Confidence.LOW
    headline_de: str
    design_mode: DesignMode = DesignMode.EXPLORATION
    design_reason_de: str = ''
    design_allowed: bool = Field(description='False only for design_mode=blocked (hard exclusion or no parcel)')
    design_override_allowed: bool = Field(default=False, description='Blocked on medium-confidence evidence only: UI may offer a conscious "open as study anyway"')
    findings: list[Finding]
    regulations: list[RegulationItem] = []
    parcel: ParcelInfo | None
    land_use: list[LandUseHit]
    land_use_shares: list[LandUseShare] = []
    buildings: BuildingStats | None = None
    land_value: LandValue | None = None
    planning: list[PlanningHit] = []
    protections: list[ProtectionHit] = []
    data_status: list[DataStatus]
    sources: list[SourceRef]
    timings_ms: dict[str, int] = {}
    disclaimer_de: str = 'Orientierende Vorprüfung auf Open-Data-Basis. Keine Baugenehmigung, keine Rechtsauskunft. Bebauungsplan, Baulasten und Grundbuch sind nicht ausgewertet.'
    mace: 'MaceOutput | None' = None


class MaceVertex(BaseModel):
    vertex_id: int
    x_coord: float
    y_coord: float
    z_coord: float | None = None


class MaceEdge(BaseModel):
    edge_id: int
    from_vertex: int
    to_vertex: int
    length_meters: float
    bearing_degrees: float


class MaceMetadata(BaseModel):
    gemarkung: str | None
    flur: int | None
    flurstueck: str
    historical_unit_detected: str = 'NONE'
    crs: str = 'EPSG:25832'


class MaceGeometry(BaseModel):
    total_area_deed_m2: float | None
    total_area_calculated_m2: float
    closure_error_meters: float | None
    vertices: list[MaceVertex]
    edges: list[MaceEdge]


class MaceConstraints(BaseModel):
    max_footprint_area_grz_m2: float | None = None
    max_total_floor_area_gfz_m2: float | None = None
    max_building_height_meters: float | None = None
    setback_lines_offset_meters: float | None = None
    buildable_envelope_vertices: list[MaceVertex] = []
    roof_types_allowed: list[str] = []
    max_stories: int | None = None
    alignment_to_street_degrees: float | None = None
    status: str = 'UNKNOWN'


class MaceTelemetry(BaseModel):
    ocr_confidence: float | None = None
    geometry_confidence: float
    manual_review_required: bool
    flags: list[str]


class MaceOutput(BaseModel):
    """Shape follows the MACE spec; null/empty = UNKNOWN, never a guessed default."""
    project_metadata: MaceMetadata
    parcel_geometry: MaceGeometry
    architectural_constraints: MaceConstraints
    pipeline_telemetry: MaceTelemetry


SiteAssessment.model_rebuild()
