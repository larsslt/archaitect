"""Source-gated import of externally obtained GeoJSON; no parcel boundaries inferred from imagery."""
from pydantic import BaseModel, Field
from shapely.geometry import shape, Polygon
from shapely.validation import explain_validity
from pyproj import CRS, Transformer
from shapely.ops import transform
from .models import Parcel, Point, EvidenceStatus

class GeoJSONParcelInput(BaseModel):
    name: str
    external_parcel_id: str
    source_url: str
    source_crs: str = Field(description='EPSG code of source GeoJSON coordinates')
    data: dict


def parse_parcel(payload: GeoJSONParcelInput) -> Parcel:
    if not payload.source_url.startswith(('https://','http://')):
        raise ValueError('A source URL is required')
    data = payload.data
    if data.get('type') == 'Feature':
        data = data.get('geometry') or {}
    geom = shape(data)
    if not isinstance(geom, Polygon) or geom.is_empty or not geom.is_valid or geom.area <= 0:
        raise ValueError(f'Expected valid single Polygon: {explain_validity(geom)}')
    if len(geom.interiors):
        raise ValueError('Parcel holes not yet supported by the core polygon schema')
    crs=CRS.from_user_input(payload.source_crs)
    if not crs.is_projected and not crs.is_geographic:
        raise ValueError('Unsupported CRS')
    centroid=geom.centroid
    if crs.is_geographic:
        lon,lat=centroid.x,centroid.y
    else:
        lon,lat=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform(centroid.x,centroid.y)
    if not (-180<=lon<=180 and -80<=lat<=84):
        raise ValueError('Unsupported geographic location')
    utm_zone=int((lon+180)//6)+1
    utm_epsg=32600+utm_zone if lat>=0 else 32700+utm_zone
    target=f'EPSG:{utm_epsg}'
    metric=transform(Transformer.from_crs(crs,target,always_xy=True).transform,geom)
    if not metric.is_valid or metric.area<=0:
        raise ValueError('Failed projected geometry')
    # Keep full UTM eastings/northings to preserve georeferencing. The UI must adapt its viewport.
    return Parcel(id=payload.external_parcel_id,name=payload.name,
                  points=[Point(x=float(x),y=float(y)) for x,y in list(metric.exterior.coords)[:-1]],
                  coordinate_system=target,
                  geometry_status=EvidenceStatus.EXTRACTED,
                  advertised_area_m2=round(metric.area,2), source_url=payload.source_url)
