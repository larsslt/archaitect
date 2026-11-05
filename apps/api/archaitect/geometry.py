"""Deterministic spatial logic; never derives cadastral boundaries from imagery."""
import math
from shapely.geometry import Polygon
from shapely.validation import explain_validity
from .models import BuildingDesign, Parcel

def parcel_polygon(parcel: Parcel) -> Polygon:
    polygon = Polygon([(p.x, p.y) for p in parcel.points])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f'Invalid parcel geometry: {explain_validity(polygon)}')
    return polygon

def footprint_polygon(design: BuildingDesign) -> Polygon:
    hw, hd = design.width_m/2, design.depth_m/2
    angle = math.radians(design.rotation_deg)
    co, si = math.cos(angle), math.sin(angle)
    coords = []
    for x, y in [(-hw,-hd),(hw,-hd),(hw,hd),(-hw,hd)]:
        coords.append((design.center_x+x*co-y*si, design.center_y+x*si+y*co))
    return Polygon(coords)
