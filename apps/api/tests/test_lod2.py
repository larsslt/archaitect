from shapely.geometry import Polygon

from archaitect.siteintel import lod2

XML = """<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2"
 xmlns:bu-base="b" xmlns:bu-core3d="c">
 <wfs:member><bu-core3d:Building gml:id="B1">
  <bu-base:heightAboveGround><bu-base:HeightAboveGround><bu-base:value uom="m">9.5</bu-base:value></bu-base:HeightAboveGround></bu-base:heightAboveGround>
  <bu-core3d:terrainIntersection><gml:MultiCurve><gml:curveMember><gml:LineString>
   <gml:posList>50.0000 8.0000 50.0000 8.0002 50.0002 8.0002 50.0002 8.0000</gml:posList></gml:LineString></gml:curveMember></gml:MultiCurve></bu-core3d:terrainIntersection>
 </bu-core3d:Building></wfs:member>
 <wfs:member><bu-core3d:Building gml:id="B2">
  <bu-base:heightAboveGround><bu-base:HeightAboveGround><bu-base:value uom="m">500</bu-base:value></bu-base:HeightAboveGround></bu-base:heightAboveGround>
  <gml:posList>50.1 8.1 50.1 8.2 50.2 8.2</gml:posList>
 </bu-core3d:Building></wfs:member>
</wfs:FeatureCollection>"""


def test_parse_reads_height_and_footprint_and_drops_implausible():
    out = lod2.parse(XML)
    assert [o["id"] for o in out] == ["B1"] and out[0]["height_m"] == 9.5
    x0, y0, x1, y1 = out[0]["hull"].bounds
    assert (round(x0, 4), round(y0, 4)) == (8.0, 50.0)       # lat/lon swapped to lon/lat


def test_parse_garbage_is_empty():
    assert lod2.parse(b"<html>") == [] and lod2.parse("") == []


def test_match_assigns_by_overlap():
    lod = [{"id": "x", "height_m": 9.5, "hull": Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])},
           {"id": "y", "height_m": 3.0, "hull": Polygon([(100, 100), (104, 100), (104, 104), (100, 104)])}]
    blds = [{"id": "a", "ring": [(1, 1), (9, 1), (9, 9), (1, 9)]}, {"id": "b", "ring": [(50, 50), (55, 50), (55, 55), (50, 55)]}]
    assert lod2.match(blds, lod, lambda g: g) == {"a": 9.5}


def test_storeys_from_height():
    assert lod2.storeys_from_height(10.0) == 3 and lod2.storeys_from_height(2.5) == 1
