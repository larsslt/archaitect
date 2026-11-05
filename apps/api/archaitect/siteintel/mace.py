"""MACE-shaped output for the parcel part that can be computed honestly from cadastral vector data.

Not computable here (-> null/UNKNOWN + flag): GRZ/GFZ/height/roof/setback rules, the buildable envelope.
Rule 3 of the spec says the envelope is the *intersection* of boundary, setbacks and easements; with no verified
setback/easement data the intersection is undefined, so no envelope is emitted rather than a guessed one.
"""
from __future__ import annotations
import math
from pyproj import Transformer
from shapely.geometry import Polygon
from .models import MaceConstraints, MaceEdge, MaceGeometry, MaceMetadata, MaceOutput, MaceTelemetry, MaceVertex, ParcelInfo

CRS = 'EPSG:25832'  # ETRS89 / UTM 32N — the official CRS in Hessen
_T = Transformer.from_crs('EPSG:4326', CRS, always_xy=True)
AREA_TOLERANCE = 0.015  # relative deviation between ALKIS area and recomputed area that triggers review


def bearing(dx: float, dy: float) -> float:
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0  # azimuth, clockwise from grid north


def build_mace(parcel: ParcelInfo, extra_flags: list[str] | None = None) -> MaceOutput:
    pts = [_T.transform(lon, lat) for lon, lat in parcel.ring_lonlat]
    ring = pts[:-1]
    poly = Polygon(ring)
    vertices = [MaceVertex(vertex_id=i + 1, x_coord=round(x, 3), y_coord=round(y, 3), z_coord=None) for i, (x, y) in enumerate(ring)]
    edges: list[MaceEdge] = []
    sx = sy = 0.0
    for i, (x, y) in enumerate(ring):
        nx, ny = ring[(i + 1) % len(ring)]
        dx, dy = nx - x, ny - y
        sx += dx
        sy += dy
        edges.append(MaceEdge(edge_id=i + 1, from_vertex=i + 1, to_vertex=(i + 1) % len(ring) + 1, length_meters=round(math.hypot(dx, dy), 3), bearing_degrees=round(bearing(dx, dy), 3)))
    area = poly.area
    flags = list(extra_flags or [])
    # Vector data from ALKIS is closed by construction: the misclosure is arithmetic noise, not a field measurement.
    flags.append('CLOSURE_TRIVIAL_VECTOR_DATA')
    flags.append('NO_VERIFIED_ZONING_RULES')
    flags.append('BUILDABLE_ENVELOPE_NOT_DERIVABLE')
    confidence = 1.0
    if parcel.area_alkis_m2:
        dev = abs(area - parcel.area_alkis_m2) / parcel.area_alkis_m2
        if dev > AREA_TOLERANCE:
            flags.append(f'AREA_DEVIATION_{dev*100:.1f}PCT')
            confidence -= 0.3
    else:
        flags.append('ALKIS_AREA_MISSING')
        confidence -= 0.2
    if parcel.n_holes_ignored:
        flags.append('PARCEL_HOLES_IGNORED')
        confidence -= 0.2
    if not poly.is_valid:
        flags.append('INVALID_POLYGON')
        confidence -= 0.5
    return MaceOutput(
        project_metadata=MaceMetadata(gemarkung=(f'Gemarkung {parcel.gemarkung_nr}' if parcel.gemarkung_nr else None), flur=parcel.flur, flurstueck=parcel.label),
        parcel_geometry=MaceGeometry(total_area_deed_m2=parcel.area_alkis_m2, total_area_calculated_m2=round(area, 2), closure_error_meters=round(math.hypot(sx, sy), 6), vertices=vertices, edges=edges),
        architectural_constraints=MaceConstraints(),
        pipeline_telemetry=MaceTelemetry(ocr_confidence=None, geometry_confidence=round(max(confidence, 0.0), 2), manual_review_required=True, flags=flags))
