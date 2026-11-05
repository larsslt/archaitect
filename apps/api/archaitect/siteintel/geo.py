"""Geometry helpers: metric projection (EPSG:25832) and GML snippets for server-side WFS filters."""
from __future__ import annotations
from pyproj import Transformer
from shapely.geometry import Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
import numpy as np
import shapely

URN = 'urn:ogc:def:crs:EPSG::4326'
_TO_M = Transformer.from_crs('EPSG:4326', 'EPSG:25832', always_xy=True)


def to_m(g: BaseGeometry) -> BaseGeometry:
    return shapely.transform(g, lambda c: np.column_stack(_TO_M.transform(c[:, 0], c[:, 1])))


def area_m2(g: BaseGeometry) -> float:
    return float(to_m(g).area)


def rep_point(g: BaseGeometry) -> Point:
    return g if isinstance(g, Point) else g.representative_point()


def _pos(x: float, y: float) -> str:
    return f'{y:.7f} {x:.7f}'  # lat lon: the URN CRS axis order


def gml(g: BaseGeometry, max_vertices: int = 250) -> str:
    """GML 3.2 for a Point or the exterior of a Polygon (holes dropped: a filter superset is fine, we re-test locally)."""
    if isinstance(g, Point):
        return f'<gml:Point srsName="{URN}"><gml:pos>{_pos(g.x, g.y)}</gml:pos></gml:Point>'
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda p: p.area)
    poly = Polygon(g.exterior.coords)
    if len(poly.exterior.coords) > max_vertices:
        poly = poly.simplify(2e-6, preserve_topology=True)
        if poly.geom_type != 'Polygon':
            poly = poly.convex_hull
    poly = orient(poly, 1.0)
    ring = ' '.join(_pos(x, y) for x, y in poly.exterior.coords)
    return (f'<gml:Polygon srsName="{URN}"><gml:exterior><gml:LinearRing><gml:posList>{ring}</gml:posList>'
            '</gml:LinearRing></gml:exterior></gml:Polygon>')
