"""Generic WFS 2.0 / GML 3.2 reader for the Hessen open-data services.

Why: the OGC-API GeoJSON facades drop nested INSPIRE attributes (HILUCS land use, PLU regulation codes), so we read the
GML directly. Every service we use returns EPSG:4326 *in lat/lon order* when asked for srsName=urn:ogc:def:crs:EPSG::4326.
The parser is deliberately schema-agnostic: it flattens leaf properties to ``a>b>c`` paths, keeps xlink:href tails and
builds Shapely geometries (lon/lat) from gml:posList / gml:pos.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
from shapely.geometry import LineString, MultiLineString, MultiPoint, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

GML = '{http://www.opengis.net/gml/3.2}'
GML_V3 = '{http://www.opengis.net/gml}'
XLINK_HREF = '{http://www.w3.org/1999/xlink}href'
_GEOM_WRAPPERS = {'geometry', 'boundedBy', 'the_geom', 'msGeometry', 'Shape', 'position', 'pl', 'geom'}
_GEOM_TAGS = {'Polygon', 'MultiSurface', 'Surface', 'MultiPolygon', 'Point', 'MultiPoint', 'LineString', 'MultiCurve',
              'Curve', 'Envelope', 'LinearRing', 'CompositeSurface'}
_SKIP_PROPS = {'inspireId', 'identifier', 'name', 'metaDataProperty', 'description', 'boundedBy'}


def local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _floats(text: str | None) -> list[float]:
    return [float(x) for x in (text or '').split()]


def _ring(el: ET.Element) -> list[tuple[float, float]]:
    """gml:LinearRing -> [(lon, lat)] (input is lat lon, optional 3rd value = z when srsDimension==3)."""
    pl = next((e for e in el.iter() if local(e.tag) in ('posList', 'coordinates')), None)
    if pl is None:
        pts = [e for e in el.iter() if local(e.tag) == 'pos']
        return [(_floats(p.text)[1], _floats(p.text)[0]) for p in pts if len(_floats(p.text)) >= 2]
    dim = int(pl.attrib.get('srsDimension') or el.attrib.get('srsDimension') or 2)
    v = _floats(pl.text)
    return [(v[i + 1], v[i]) for i in range(0, len(v) - dim + 1, dim)]


def _polygon(el: ET.Element) -> Polygon | None:
    ext = next((c for c in el.iter() if local(c.tag) == 'exterior'), None)
    if ext is None:
        return None
    shell = _ring(ext)
    holes = [_ring(i) for i in el.iter() if local(i.tag) == 'interior']
    if len(shell) < 4:
        return None
    try:
        p = Polygon(shell, [h for h in holes if len(h) >= 4])
        return p if p.is_valid else p.buffer(0)
    except Exception:  # noqa: BLE001
        return None


def geometry_from(el: ET.Element) -> BaseGeometry | None:
    name = local(el.tag)
    if name == 'Polygon':
        return _polygon(el)
    if name in ('MultiSurface', 'MultiPolygon', 'Surface', 'CompositeSurface'):
        polys = [g for g in (_polygon(p) for p in el.iter() if local(p.tag) == 'Polygon') if g is not None and not g.is_empty]
        if not polys:
            return None
        return polys[0] if len(polys) == 1 else unary_union(polys)
    if name == 'Point':
        pos = next((e for e in el.iter() if local(e.tag) == 'pos'), None)
        v = _floats(pos.text) if pos is not None else []
        return Point(v[1], v[0]) if len(v) >= 2 else None
    if name in ('LineString', 'Curve'):
        pl = next((e for e in el.iter() if local(e.tag) == 'posList'), None)
        if pl is None:
            return None
        dim = int(pl.attrib.get('srsDimension') or 2)
        v = _floats(pl.text)
        pts = [(v[i + 1], v[i]) for i in range(0, len(v) - dim + 1, dim)]
        return LineString(pts) if len(pts) >= 2 else None
    if name == 'MultiPoint':
        pts = [g for g in (geometry_from(c) for c in el.iter() if local(c.tag) == 'Point') if g is not None]
        return None if not pts else (pts[0] if len(pts) == 1 else MultiPoint(pts))
    if name == 'MultiCurve':
        lines = [g for g in (geometry_from(c) for c in el.iter() if local(c.tag) == 'LineString') if g is not None]
        return None if not lines else (lines[0] if len(lines) == 1 else MultiLineString(lines))
    return None


@dataclass
class Feature:
    type: str
    gml_id: str
    props: dict[str, str] = field(default_factory=dict)
    hrefs: dict[str, str] = field(default_factory=dict)
    geometry: BaseGeometry | None = None

    def get(self, *paths: str, default: str | None = None) -> str | None:
        """First property whose path ends with one of ``paths`` (``a>b`` or just ``b``)."""
        for p in paths:
            for k, v in self.props.items():
                if k == p or k.endswith('>' + p):
                    return v
        return default

    def href(self, *names: str) -> str | None:
        for n in names:
            for k, v in self.hrefs.items():
                if k == n or k.endswith('>' + n):
                    return v
        return None


def _walk(el: ET.Element, prefix: str, feat: Feature, depth: int = 0) -> None:
    for c in el:
        nm = local(c.tag)
        if nm in _GEOM_TAGS or nm in _GEOM_WRAPPERS and any(local(g.tag) in _GEOM_TAGS for g in c):
            if feat.geometry is None:
                g = geometry_from(c) if nm in _GEOM_TAGS else next((geometry_from(x) for x in c if local(x.tag) in _GEOM_TAGS and local(x.tag) != 'Envelope'), None)
                if g is not None:
                    feat.geometry = g
            continue
        if nm in _SKIP_PROPS and depth == 0 and len(c) == 0 and not (c.text or '').strip():
            continue
        path = prefix + nm
        href = c.attrib.get(XLINK_HREF)
        if href:
            feat.hrefs[path] = href
        text = (c.text or '').strip()
        if len(c) == 0:
            if text and nm not in _SKIP_PROPS:
                feat.props[path] = text
        elif depth < 6 and nm not in ('inspireId', 'lebenszeitintervall', 'modellart', 'basiskarte'):
            _walk(c, path + '>', feat, depth + 1)


_ROOT_OPEN = re.compile(rb'<((?:[\w.-]+:)?FeatureCollection)\b')
_LAST_MEMBER = re.compile(rb'</(?:[\w.-]+:)?(?:member|featureMember)>')


def repair_truncated(xml: bytes) -> bytes | None:
    """Observed 2026-10-28: the Landesplanung PLU services (POST + filter) sometimes end the document right after the last
    ``</wfs:member>`` and omit ``</wfs:FeatureCollection>``. Cut after the last complete member and close the root."""
    root = _ROOT_OPEN.search(xml[:4000])
    ends = [m.end() for m in _LAST_MEMBER.finditer(xml)]
    if not root or not ends:
        return None
    return xml[: ends[-1]] + b'\n</' + root.group(1) + b'>'


def usable(xml: bytes) -> bool:
    """Cheap pre-cache check: a feature collection that is complete or repairable. Exception reports/HTML/empty are not cached."""
    t = xml.rstrip()
    if b'FeatureCollection' not in xml[:4000]:
        return False
    return t.endswith(b'FeatureCollection>') or bool(_LAST_MEMBER.search(t[-40:]))


def parse_features(xml: bytes | str) -> list[Feature]:
    """Parse a wfs:FeatureCollection. Raises ValueError for ExceptionReports / non-XML. Repairs the truncation described above."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        fixed = repair_truncated(xml if isinstance(xml, bytes) else xml.encode('utf-8'))
        if fixed is None:
            raise ValueError(f'kein gültiges XML: {exc}') from exc
        try:
            root = ET.fromstring(fixed)
        except ET.ParseError as exc2:
            raise ValueError(f'kein gültiges XML: {exc2}') from exc2
    if local(root.tag) in ('ExceptionReport', 'ServiceExceptionReport'):
        text = ' '.join((e.text or '').strip() for e in root.iter() if local(e.tag) in ('ExceptionText', 'ServiceException'))
        raise ValueError(f'Dienst meldet Fehler: {text[:200]}')
    out: list[Feature] = []
    for m in root:
        if local(m.tag) not in ('member', 'featureMember'):
            continue
        for fe in m:
            f = Feature(type=local(fe.tag), gml_id=fe.attrib.get(GML + 'id') or fe.attrib.get(GML_V3 + 'id') or '')
            _walk(fe, '', f)
            out.append(f)
    return out


def bbox_param(lat: float, lon: float, d: float) -> str:
    """WFS 2.0 bbox for urn:ogc:def:crs:EPSG::4326 = lat1,lon1,lat2,lon2 (axis order!)."""
    return f'{lat - d:.6f},{lon - d:.6f},{lat + d:.6f},{lon + d:.6f},urn:ogc:def:crs:EPSG::4326'


def request_params(type_name: str, lat: float, lon: float, d: float, count: int, extra: dict[str, str] | None = None) -> dict[str, str]:
    p = {'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature', 'typeNames': type_name, 'count': str(count),
         'srsName': 'urn:ogc:def:crs:EPSG::4326', 'bbox': bbox_param(lat, lon, d)}
    if extra:
        p.update(extra)
    return p
