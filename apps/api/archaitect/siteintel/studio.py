"""Bridge from a siteintel project (official plot data + brief + verified constraints) to the design core (``archaitect.models.Project``).

The studio works in the project's local metric frame (origin = parcel centroid, x East, y North). Rules only carry the status VERIFIED when a
person has verified them (``VerifiedConstraints``); everything else stays an unverified exploration, exactly as the core evaluator demands.
"""
from __future__ import annotations
import math
from shapely.geometry import Polygon
from shapely.ops import polylabel
from .. import store as core_store
from ..geometry import footprint_polygon
from ..models import BuildingDesign, EvidenceStatus, Parcel, PlanningRule, Point, Project
from .brief import PlanningBrief
from .dossier import VerifiedConstraints

SOURCE_URL = 'https://www.geoportal.hessen.de/'


def _open_ring(ring: list[list[float]]) -> list[list[float]]:
    return ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring


def core_parcel(meta: dict, pack: dict, area_m2: float | None) -> tuple[Parcel, Polygon]:
    site = next(p for p in pack['parcels'] if p['is_site'])
    ring = _open_ring(site['ring'])
    poly = Polygon(ring)
    fr = pack['frame']
    parcel = Parcel(id=f'alkis-{site["id"]}', name=f'Flurstück {site["label"]}', points=[Point(x=x, y=y) for x, y in ring],
                    coordinate_system=f'LOCAL_METRIC_ORIGIN_{fr["crs"].replace(":", "")}_{fr["origin_e"]}_{fr["origin_n"]}', geometry_status=EvidenceStatus.EXTRACTED,
                    advertised_area_m2=round(area_m2 or poly.area, 1), source_url=SOURCE_URL)
    return parcel, poly


def core_rules(v: VerifiedConstraints | None, area_m2: float, has_envelope: bool) -> list[PlanningRule]:
    if v is None:
        return []
    ok = EvidenceStatus.VERIFIED
    q = v.basis_de
    rules: list[PlanningRule] = []
    if v.max_stories is not None:
        rules.append(PlanningRule(id='VERIFIED_MAX_STOREYS', kind='MAX_STOREYS', value=v.max_stories, review_status=ok, source_quote=q))
    if v.max_building_height_meters is not None:
        rules.append(PlanningRule(id='VERIFIED_MAX_HEIGHT', kind='MAX_HEIGHT', value=v.max_building_height_meters, review_status=ok, source_quote=q))
    if v.grz is not None:
        rules.append(PlanningRule(id='VERIFIED_MAX_FOOTPRINT_GRZ', kind='MAX_FOOTPRINT', value=round(v.grz * area_m2, 2), review_status=ok, source_quote=f'GRZ {v.grz} × {area_m2:.0f} m² · {q}'))
    if has_envelope:
        rules.append(PlanningRule(id='VERIFIED_BUILDING_ENVELOPE', kind='BUILDING_ENVELOPE', value=0.0, review_status=ok, source_quote=q))
    return rules


def initial_design(poly: Polygon, envelope: Polygon | None, brief: PlanningBrief, v: VerifiedConstraints | None, design_id: str = 'design-001') -> BuildingDesign:
    """A first massing that fits the buildable region: placed at its pole of inaccessibility, aligned to its main axis, sized from the brief."""
    region = envelope if envelope is not None and not envelope.is_empty else poly.buffer(-3)
    if region.is_empty:
        region = poly.buffer(-1) if not poly.buffer(-1).is_empty else poly
    if region.geom_type != 'Polygon':
        region = max(region.geoms, key=lambda g: g.area)
    c = polylabel(region, 0.05)
    mrr = region.minimum_rotated_rectangle
    xs, ys = mrr.exterior.coords.xy
    edges = [(math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]), math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i])) for i in range(4)]
    ang = math.degrees(max(edges)[1])
    ang = (ang + 90) % 180 - 90                     # into [-90, 90): the sliders and the core model both stay in range
    p = brief.program
    storeys = p.stories or 2
    if v and v.max_stories:
        storeys = min(storeys, v.max_stories)
    storeys = max(1, min(storeys, 4))
    living = p.living_area_target_m2 or 140.0
    footprint = max(40.0, min(living / storeys * 1.15, region.area * 0.6))
    if v and v.grz:
        footprint = min(footprint, v.grz * poly.area)
    ratio = 1.25
    w = math.sqrt(footprint * ratio)
    d = footprint / w
    flat = bool(p.roof_types) and p.roof_types[0] == 'flach'
    rotation = round(ang, 1)
    for _ in range(60):
        design = BuildingDesign(id=design_id, center_x=round(c.x, 2), center_y=round(c.y, 2), width_m=round(w, 1), depth_m=round(d, 1), rotation_deg=rotation, storeys=storeys,
                                eave_height_m=2.8 * storeys + 0.4, ridge_height_m=2.8 * storeys + 0.4 + (0 if flat else math.tan(math.radians(30)) * d / 2), roof_type='flat' if flat else 'gable')
        if region.buffer(1e-6).covers(footprint_polygon(design)) or min(w, d) <= 4.0:
            break
        w *= 0.94
        d *= 0.94
    eave = 2.8 * storeys + 0.4
    ridge = design.ridge_height_m
    if v and v.max_building_height_meters and ridge > v.max_building_height_meters:
        ridge = max(v.max_building_height_meters, eave)
        eave = min(eave, ridge)
    pitch = 0.0 if flat else round(math.degrees(math.atan2(max(ridge - eave, 0.0), design.depth_m / 2)), 1)
    return design.model_copy(update={'eave_height_m': round(eave, 2), 'ridge_height_m': round(ridge, 2), 'roof_pitch_deg': pitch})


def ensure_core_project(pid: str, meta: dict, pack: dict, area_m2: float | None, brief: PlanningBrief, v: VerifiedConstraints | None, envelope_local: list[list[float]] | None) -> Project:
    """Create the design project once; on later calls only refresh parcel, rules and envelope (the user's design and its revisions stay untouched)."""
    parcel, poly = core_parcel(meta, pack, area_m2)
    env_poly = Polygon(envelope_local) if envelope_local and len(envelope_local) >= 3 else None
    rules = core_rules(v, area_m2 or poly.area, env_poly is not None)
    env_pts = [Point(x=x, y=y) for x, y in envelope_local] if env_poly is not None and envelope_local else None
    existing = core_store.read(pid)
    if existing is None:
        design = initial_design(poly, env_poly, brief, v)
        return core_store.create(Project(id=pid, parcel=parcel, design=design, rules=rules, envelope=env_pts))
    return core_store.sync_context(pid, parcel, rules, env_pts) or existing


# ---------------------------------------------------------------------------------------------------------- variants


