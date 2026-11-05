"""Hessen site screening. Real recorded data wherever possible:
- tests/fixtures_siteintel/parcels.json: real ALKIS parcels (INSPIRE OGC-API), simplified rings
- tests/fixtures_siteintel/wfs/*.xml.gz: real GML responses of the official WFS services, recorded 2026-10-28 (bbox ±0.0003°, some trimmed)
- tests/fixtures_siteintel/osm_tags.json: only 'kaserne' is a real OSM observation, the rest is hand-written (see _meta there)
Where a test needs a situation that the recordings do not contain (e.g. a 3_3_1 parcel), the recorded payload is modified in the test and says so.
"""
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon
from siteintel_support import FakeCad, FakeOsm, PARCELS, TAGS, ReplayFetcher, load, run, service_for
from archaitect.siteintel import cadastre, extract, geo, landuse, sources, wfs
from archaitect.siteintel.cache import TtlCache, make_key
from archaitect.siteintel.decision import classify_code
from archaitect.siteintel.dossier import VerifiedConstraints, build_dossier, with_verified_constraints
from archaitect.siteintel.fetch import HttpFetcher
from archaitect.siteintel.models import DataStatus, DesignMode, Verdict, Confidence
from archaitect.siteintel.rules import classify_tags
from archaitect.siteintel.service import SiteService, in_hessen


# ---------------------------------------------------------------- parsing & geometry
def test_reference_parsing():
    assert cadastre.parse_reference('060474335000730003__') == {'land': '06', 'gemarkung_nr': '0474', 'flur': 335, 'zaehler': 73, 'nenner': 3}
    assert cadastre.parse_reference('06040800100397______')['nenner'] is None
    assert cadastre.parse_reference('garbage') == {}


def test_wfs_axis_order_and_hilucs_from_real_response():
    fs = wfs.parse_features(load('elu__ffm'))
    assert len(fs) == 7
    x, y = fs[0].geometry.representative_point().x, fs[0].geometry.representative_point().y
    assert 8.6 < x < 8.8 and 50.0 < y < 50.2, 'GML lat/lon must be swapped to lon/lat'
    code, eng = extract.hilucs_parts(fs[0].href('hilucsLandUse'))
    assert (code, eng) == ('5_1', 'PermanentResidentialUse')


def test_wfs_handles_multipoint_polygon_lines_and_attributes():
    d = wfs.parse_features(load('denk__fuerth'))
    assert d and d[0].get('siteName') and d[0].geometry is not None
    lep = wfs.parse_features(load('lep__ffm'))
    assert {f.geometry.geom_type for f in lep} & {'LineString', 'MultiLineString'}
    boris = wfs.parse_features(load('boris__acker'))[0]
    assert boris.get('entwicklungszustand') == 'LF' and boris.get('art') == 'A' and boris.get('bodenrichtwert') == '3.1'


def test_wfs_exception_report_and_garbage():
    with pytest.raises(ValueError, match='Dienst meldet Fehler'):
        wfs.parse_features(b'<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1"><ows:Exception><ows:ExceptionText>bad filter</ows:ExceptionText></ows:Exception></ows:ExceptionReport>')
    with pytest.raises(ValueError):
        wfs.parse_features(b'<html>502</html' )


def test_filter_body_uses_latlon_and_server_side_intersects():
    src = sources.SOURCES['elu']
    body = sources._body(src, Point(8.696, 50.129))
    assert '<fes:Intersects>' in body and '<gml:pos>50.1290000 8.6960000</gml:pos>' in body and 'xmlns:elu=' in body
    parcel = Polygon([(8.0, 50.0), (8.001, 50.0), (8.001, 50.001), (8.0, 50.001)])
    pb = sources._body(src, parcel)
    assert '<gml:posList>' in pb and pb.count('50.0000000 8.0000000') == 2  # closed ring, lat first
    assert wfs.bbox_param(50.0, 8.0, 0.001).startswith('49.999000,7.999000,50.001000,8.001000')


def test_hilucs_classification_prefix_rules():
    assert classify_code('5_1').verdict == Verdict.CANDIDATE and classify_code('5_2').category == 'residential'
    assert classify_code('1_2').verdict == Verdict.NOT_BUILDABLE
    assert classify_code('1_1_1').soft and classify_code('1_1_1').verdict == Verdict.RESTRICTED
    assert classify_code('3_3_1').category == 'military' and classify_code('3_3_2').verdict == Verdict.RESTRICTED
    assert classify_code('4_1_1').verdict == Verdict.NOT_BUILDABLE and classify_code('4_2').verdict == Verdict.RESTRICTED
    assert classify_code('6_3_2').category == 'water'
    assert classify_code('9') is None


# ---------------------------------------------------------------- end-to-end on recorded data
def test_residential_inner_city_parcel_is_a_candidate_with_basic_regulations():
    a, _ = run('darmstadt_wohn')
    assert a.verdict == Verdict.CANDIDATE and a.design_mode == DesignMode.FULL and a.design_allowed
    assert a.land_use_shares[0].code == '5_1' and a.land_use_shares[0].share > 0.95
    assert a.land_value.entwicklungszustand == 'B' and a.land_value.nutzung == 'W' and a.land_value.eur_per_m2 == 1100.0
    ids = {r.id for r in a.regulations}
    assert {'bauplanungsrecht', 'bebauungsplan', 'nutzung', 'bodenrichtwert', 'bestand', 'abstandsflaechen', 'ausnutzung'} <= ids
    assert next(r for r in a.regulations if r.id == 'bebauungsplan').status == 'NOT_CONNECTED'
    assert next(r for r in a.regulations if r.id == 'abstandsflaechen').status == 'UNVERIFIED_CANDIDATE'


def test_frankfurt_parcel_with_denkmal_and_fnp_conflict_stays_open():
    a, _ = run('frankfurt_nordend')
    assert a.buildings.on_parcel == 3 and a.buildings.max_floors_on_parcel == 4
    assert a.land_value.eur_per_m2 == 5300.0 and a.land_value.ergaenzung == 'MFH'
    assert any(p.kind == 'denkmal' and p.on_parcel for p in a.protections)
    den = next(f for f in a.findings if f.rule_id == 'DENKMAL')
    assert den.affects_verdict is False  # a note, must not lower the verdict
    assert a.verdict == Verdict.CANDIDATE and a.design_mode == DesignMode.FULL
    assert 'Widerspruch' in a.design_reason_de  # the RegFNP "Bildung" signal is shown, not hidden


def test_farmland_in_flood_zone_is_restricted_but_never_blocked():
    a, _ = run('acker_wetterau')
    assert a.verdict == Verdict.RESTRICTED and a.design_mode == DesignMode.EXPLORATION and a.design_allowed is True
    assert {f.rule_id for f in a.findings} >= {'ELU_AGRICULTURE', 'BORIS_AUSSEN_LF', 'HQ100'}
    assert a.land_value.entwicklungszustand == 'LF'


def test_forest_is_blocked_by_official_land_use_without_override():
    a, _ = run('wald_odenwald')
    assert a.verdict == Verdict.NOT_BUILDABLE and a.confidence == Confidence.HIGH
    assert a.design_mode == DesignMode.BLOCKED and a.design_allowed is False and a.design_override_allowed is False
    assert any(p.layer == 'regionalplan' and p.effect == 'restrict' for p in a.planning)
    assert next(f for f in a.findings if f.rule_id == 'BORIS_AUSSENBEREICH')  # real BORIS remark about §35 is surfaced
    assert a.land_value.aussenbereich_hint is True


def test_military_by_official_land_use_blocks_hard():
    """Recorded kaserne parcel says 5_2 in ALKIS; to test the ELU military path the HILUCS href is rewritten to 3_3_1 (modified fixture)."""
    raw = load('elu__kaserne').replace(b'5_2_ResidentialUseWithOtherCompatibleUses', b'3_3_1_PublicAdministrationDefenceAndSocialSecurityServices')
    a, _ = run('kaserne', overrides={'elu': raw})
    assert a.verdict == Verdict.NOT_BUILDABLE and a.confidence == Confidence.HIGH and a.design_mode == DesignMode.BLOCKED and not a.design_override_allowed
    assert a.findings[0].rule_id == 'ELU_MILITARY'


def test_osm_military_conflicting_with_alkis_blocks_but_allows_conscious_override():
    a, _ = run('kaserne', osm=FakeOsm(TAGS['kaserne']))
    assert a.verdict == Verdict.NOT_BUILDABLE and a.design_mode == DesignMode.BLOCKED
    assert a.confidence == Confidence.MEDIUM and a.design_override_allowed is True
    assert 'Kaserne Frankfurt-Hausen' in a.findings[0].evidence
    quiet, _ = run('kaserne')  # without OSM the official data says residential
    assert quiet.verdict == Verdict.CANDIDATE


def test_osm_outage_never_changes_the_core_result():
    ok, _ = run('darmstadt_wohn')
    down, _ = run('darmstadt_wohn', osm=FakeOsm([], 'UNAVAILABLE'))
    assert (down.verdict, down.design_mode) == (ok.verdict, ok.design_mode)
    assert any(s.source_id == 'osm-overpass' and s.status == 'UNAVAILABLE' for s in down.data_status)


def test_core_stage_skips_planning_and_protection_calls():
    a, f = run('frankfurt_nordend', stage='core')
    called = {s for s, _ in f.calls}
    assert called == {'elu', 'buildings', 'boris'} and a.stage == 'core'
    assert a.design_reason_de.endswith('(Planungs- und Schutzdaten werden noch geladen.)') or a.design_mode == DesignMode.BLOCKED
    full, f2 = run('frankfurt_nordend')
    assert {'regfnp', 'denkmal', 'hq100', 'rp_sued', 'lep'} <= {s for s, _ in f2.calls}


# ---------------------------------------------------------------- the original bug: outages must not block
def test_land_use_outage_is_exploration_not_blocked():
    a, _ = run('darmstadt_wohn', fail={'elu'})
    assert a.design_mode == DesignMode.EXPLORATION and a.design_allowed is True
    assert any(f.rule_id == 'LANDUSE_UNAVAILABLE' for f in a.findings)
    assert any(s.source_id == 'elu' and s.status == 'UNAVAILABLE' for s in a.data_status)


def test_all_sources_down_still_not_blocked_when_parcel_known():
    a, _ = run('darmstadt_wohn', fail={'elu', 'buildings', 'boris', 'regfnp', 'rp_sued', 'rp_mittel', 'rp_nord', 'lep', 'denkmal', 'hq100'})
    assert a.verdict == Verdict.UNKNOWN and a.design_mode == DesignMode.EXPLORATION and a.design_allowed is True
    assert a.mace is not None and 'SOURCE_UNAVAILABLE_ELU' in a.mace.pipeline_telemetry.flags


def test_no_parcel_blocks_with_actionable_reason():
    p = PARCELS['darmstadt_wohn']
    svc = SiteService(ReplayFetcher('darmstadt'), FakeCad('darmstadt_wohn'))
    a = svc.assess(p['lat'] + 0.01, p['lon'])
    assert a.parcel is None and a.design_mode == DesignMode.BLOCKED and 'Flurstück' in a.design_reason_de and a.design_override_allowed is False

    class DownCad:
        def parcel_at(self, lat, lon):
            return None, DataStatus(source_id='alkis-inspire-he', status='UNAVAILABLE', detail='timeout')
    a2 = SiteService(ReplayFetcher('darmstadt'), DownCad()).assess(p['lat'], p['lon'])
    assert a2.design_mode == DesignMode.BLOCKED and 'nochmal klicken' in a2.design_reason_de


def test_outside_hessen():
    assert in_hessen(50.11, 8.68) and not in_hessen(48.14, 11.58)
    a = SiteService(ReplayFetcher('ffm'), FakeCad('kaserne')).assess(48.14, 11.58)
    assert a.in_hessen is False and a.design_allowed is False


def test_slow_source_is_cut_off_by_the_time_budget(monkeypatch):
    from archaitect.siteintel import service as svc_mod
    monkeypatch.setitem(svc_mod.BUDGET_S, 'full', 1.0)

    class Slow(ReplayFetcher):
        def post_xml(self, source_id, url, body, ttl, timeout, accept=None):
            if source_id == 'rp_sued':
                time.sleep(2.2)
            return super().post_xml(source_id, url, body, ttl, timeout, accept)
    p = PARCELS['darmstadt_wohn']
    t = time.perf_counter()
    a = SiteService(Slow('darmstadt'), FakeCad('darmstadt_wohn')).assess(p['lat'], p['lon'])
    assert time.perf_counter() - t < 2.0
    st = next(s for s in a.data_status if s.source_id == 'rp_sued')
    assert st.status == 'UNAVAILABLE' and 'Zeitbudget' in st.detail
    assert a.verdict == Verdict.CANDIDATE  # the slow context layer did not flip the result


# ---------------------------------------------------------------- MACE / dossier hand-over
def test_mace_geometry_is_consistent():
    a, _ = run('darmstadt_wohn')
    g = a.mace.parcel_geometry
    assert a.mace.project_metadata.flur == 9 and a.mace.project_metadata.flurstueck == '75/5'
    assert len(g.vertices) == len(g.edges) == 13 and g.closure_error_meters < 1e-6
    assert abs(g.total_area_calculated_m2 - 3223) / 3223 < 0.02
    assert all(0 <= e.bearing_degrees < 360 and e.length_meters > 0 for e in g.edges) and g.vertices[0].x_coord > 400000
    assert a.mace.architectural_constraints.buildable_envelope_vertices == [] and a.mace.pipeline_telemetry.manual_review_required


def test_dossier_is_conservative_until_constraints_are_verified():
    d = build_dossier(run('darmstadt_wohn')[0])
    assert d.schema_version == 'archaitect.site-dossier/1' and d.design_gate.mode == DesignMode.FULL and not d.design_gate.hard_block
    hbo = next(k for k in d.known_constraints if k.id == 'hbo_abstandsflaeche')
    assert hbo.status == 'UNVERIFIED_CANDIDATE'
    assert d.mace.architectural_constraints.setback_lines_offset_meters is None
    assert any('Bebauungsplan' in q for q in d.open_questions_de)


def test_verified_constraints_derive_the_envelope():
    d = build_dossier(run('darmstadt_wohn')[0])
    v = VerifiedConstraints(verified_by='Tester (Test)', basis_de='B-Plan Test, Festsetzung 1.1', grz=0.4, gfz=0.8, max_stories=2, setback_lines_offset_meters=3.0, roof_types_allowed=['Satteldach'])
    out = with_verified_constraints(d, v)
    c = out.mace.architectural_constraints
    assert c.status == 'VERIFIED_BY_USER' and c.max_stories == 2 and c.roof_types_allowed == ['Satteldach']
    area = d.mace.parcel_geometry.total_area_calculated_m2
    assert abs(c.max_footprint_area_grz_m2 - 0.4 * area) < 0.5
    env = Polygon([(p.x_coord, p.y_coord) for p in c.buildable_envelope_vertices])
    parcel = Polygon([(p.x_coord, p.y_coord) for p in d.mace.parcel_geometry.vertices])
    assert 0 < env.area < parcel.area and parcel.buffer(1e-6).contains(env)
    assert env.distance(parcel.exterior) >= 2.99
    flags = out.mace.pipeline_telemetry.flags
    assert 'VERIFIED_BY:Tester (Test)' in flags and 'EASEMENTS_NOT_CONNECTED' not in flags and 'EASEMENTS_NOT_CONSIDERED' in flags and 'NO_VERIFIED_ZONING_RULES' not in flags
    assert not any(k.id == 'hbo_abstandsflaeche' for k in out.known_constraints)
    assert d.mace.architectural_constraints.status == 'UNKNOWN'  # original untouched


def test_verified_constraints_are_refused_on_blocked_sites():
    d = build_dossier(run('wald_odenwald')[0])
    v = VerifiedConstraints(verified_by='x y', basis_de='abc', setback_lines_offset_meters=3.0)
    assert with_verified_constraints(d, v).mace.architectural_constraints.status == 'UNKNOWN'


def test_verified_constraints_require_an_audit_trail():
    with pytest.raises(ValueError):
        VerifiedConstraints(verified_by='', basis_de='')


# ---------------------------------------------------------------- cache & HTTP behaviour
def test_cache_ttl_stale_and_persistence(tmp_path):
    db = tmp_path / 'c.sqlite'
    c = TtlCache(db)
    k = make_key('a', 'b')
    assert c.get(k, 10) is None
    c.put(k, b'xyz')
    assert c.get(k, 10) == b'xyz'
    assert c.get(k, -1) is None and c.get(k, -1, allow_stale=True) == b'xyz'
    assert TtlCache(db).get(k, 10) == b'xyz'  # survives a restart
    assert TtlCache(tmp_path / 'nope' / 'x' / 'c.sqlite').get(k, 10) is None  # unusable path degrades silently


def _fetcher(handler, cache=None):
    return HttpFetcher(cache or TtlCache(None), httpx.Client(transport=httpx.MockTransport(handler)))


def test_fetcher_caches_retries_and_serves_stale(monkeypatch):
    import archaitect.siteintel.fetch as fm
    monkeypatch.setattr(fm.time, 'sleep', lambda s: None)
    n = {'c': 0, 'mode': 'ok'}

    def h(req):
        n['c'] += 1
        if n['mode'] == 'flaky' and n['c'] == 1:
            return httpx.Response(503)
        if n['mode'] == 'down':
            return httpx.Response(502)
        if n['mode'] == '404':
            return httpx.Response(404)
        return httpx.Response(200, content=b'<ok/>')
    f = _fetcher(h)
    n['mode'] = 'flaky'
    r = f.get('s', 'https://x.test/wfs', {'a': '1'}, 100, 1)
    assert r.body == b'<ok/>' and n['c'] == 2 and not r.cached          # one retry after 503
    r = f.get('s', 'https://x.test/wfs', {'a': '1'}, 100, 1)
    assert r.cached and n['c'] == 2                                       # served from cache
    n['mode'] = 'down'
    r = f.get('s', 'https://x.test/wfs', {'a': '1'}, -1, 1)               # expired + upstream down -> stale answer
    assert r.body == b'<ok/>' and r.stale and r.error == 'HTTP 502'
    n['mode'], c0 = '404', n['c']
    r = f.get('s', 'https://x.test/wfs', {'a': '2'}, 100, 1)
    assert r.body is None and r.error == 'HTTP 404' and n['c'] == c0 + 1  # client errors are not retried


def test_query_falls_back_to_point_when_the_server_rejects_the_polygon_filter():
    bodies = []
    good = load('elu__darmstadt')

    def h(req):
        bodies.append(req.content.decode())
        if '<gml:Polygon' in bodies[-1]:
            return httpx.Response(200, content=b'<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1"><ows:Exception><ows:ExceptionText>unsupported</ows:ExceptionText></ows:Exception></ows:ExceptionReport>')
        return httpx.Response(200, content=good)
    p = PARCELS['darmstadt_wohn']
    parcel = Polygon(cadastre.parcel_from_items(p['items'], p['lat'], p['lon']).ring_lonlat)
    out = sources.query(sources.SOURCES['elu'], _fetcher(h), parcel)
    assert out.status.status == 'OK' and out.geometry_used == 'point' and len(bodies) == 2 and '<gml:Point' in bodies[1]


def test_query_reports_outage_without_raising():
    def h(req):
        raise httpx.ConnectTimeout('slow')
    out = sources.query(sources.SOURCES['boris'], _fetcher(h), Point(8.67, 49.87))
    assert out.features == [] and out.status.status == 'UNAVAILABLE' and 'ConnectTimeout' in out.status.detail


def test_inspire_parcel_provider_uses_fetcher_and_reports_outage(monkeypatch):
    p = PARCELS['darmstadt_wohn']
    seen = {}

    def ok(req: httpx.Request):
        seen['q'] = dict(req.url.params)
        return httpx.Response(200, json=p['items'])
    prov = cadastre.InspireHessenProvider(_fetcher(ok))
    parcel, st = prov.parcel_at(p['lat'], p['lon'])
    assert st.status == 'OK' and parcel.label == '75/5'
    assert seen['q']['limit'] == '5' and seen['q']['f'] == 'json' and seen['q']['bbox'].count(',') == 3
    boom = cadastre.InspireHessenProvider(_fetcher(lambda r: httpx.Response(503), TtlCache(None)))
    import archaitect.siteintel.fetch as fm
    monkeypatch.setattr(fm.time, 'sleep', lambda s: None)
    parcel, st = boom.parcel_at(p['lat'], p['lon'])
    assert parcel is None and st.status == 'UNAVAILABLE'


def test_multipolygon_parcel_is_handled():
    p = PARCELS['wald_odenwald']
    parcel = cadastre.parcel_from_items(p['items'], p['lat'], p['lon'])
    assert parcel and parcel.geometry_type == 'MultiPolygon' and parcel.label == '1'


# ---------------------------------------------------------------- OSM (optional refinement) & rules
def test_overpass_rate_limit_falls_back_to_unavailable(monkeypatch):
    monkeypatch.setattr(landuse.time, 'sleep', lambda s: None)
    calls = []

    def limited(req):
        calls.append(str(req.url))
        return httpx.Response(429, text='# 429 Too Many Requests')
    prov = landuse.OverpassProvider(client=httpx.Client(transport=httpx.MockTransport(limited)))
    tags, st = prov.tags_at(50.1, 8.6)
    assert tags == [] and st.status == 'UNAVAILABLE' and len(calls) == 4
    one = landuse.OverpassProvider(client=httpx.Client(transport=httpx.MockTransport(limited)), endpoints=landuse.ENDPOINTS[:1], attempts=1)
    calls.clear()
    one.tags_at(50.1, 8.6)
    assert len(calls) == 1


def test_overpass_success_is_cached():
    n = {'c': 0}

    def ok(req):
        n['c'] += 1
        return httpx.Response(200, json={'elements': [{'type': 'area', 'id': 1, 'tags': {'landuse': 'residential'}}]})
    prov = landuse.OverpassProvider(client=httpx.Client(transport=httpx.MockTransport(ok)))
    assert prov.tags_at(50.1, 8.6)[0] == [{'landuse': 'residential'}]
    assert prov.tags_at(50.1, 8.6)[1].detail == 'cache' and n['c'] == 1


def test_osm_rules_classify_military_and_unknown_tags():
    hits = classify_tags(TAGS['kaserne'])
    assert hits and hits[0].category == 'military' and hits[0].verdict == Verdict.NOT_BUILDABLE
    assert classify_tags([{'highway': 'residential'}, {'name': 'x'}]) == []


# ---------------------------------------------------------------- HTTP surface
def test_router_endpoints():
    from archaitect.main import app
    from archaitect.siteintel import router as r
    p = PARCELS['darmstadt_wohn']
    svc, _ = service_for('darmstadt_wohn')
    r.providers['service'] = svc
    try:
        c = TestClient(app)
        core = c.get('/siteintel/assess/core', params={'lat': p['lat'], 'lon': p['lon']}).json()
        assert core['stage'] == 'core' and core['design_mode'] in ('full', 'exploration') and core['land_use_shares']
        j = c.get('/siteintel/assess', params={'lat': p['lat'], 'lon': p['lon']}).json()
        assert j['stage'] == 'full' and j['verdict'] == 'CANDIDATE' and j['mace']['project_metadata']['flurstueck'] == '75/5' and j['timings_ms']['total'] >= 0
        d = c.get('/siteintel/dossier', params={'lat': p['lat'], 'lon': p['lon']}).json()
        assert d['schema_version'] == 'archaitect.site-dossier/1' and d['design_gate']['mode'] == 'full'
        body = {'verified_by': 'Test Reviewer', 'basis_de': 'B-Plan Test', 'setback_lines_offset_meters': 3, 'grz': 0.4}
        v = c.post('/siteintel/dossier/constraints', params={'lat': p['lat'], 'lon': p['lon']}, json=body).json()
        assert v['mace']['architectural_constraints']['status'] == 'VERIFIED_BY_USER' and v['mace']['architectural_constraints']['buildable_envelope_vertices']
        assert c.post('/siteintel/dossier/constraints', params={'lat': p['lat'], 'lon': p['lon']}, json={'verified_by': '', 'basis_de': ''}).status_code == 422
        assert c.get('/siteintel/hessen/outline').json()['geometry']['type'] == 'MultiPolygon'
        assert c.get('/siteintel/assess', params={'lat': 99, 'lon': 8}).status_code == 422
    finally:
        r.providers.clear()


# ---------------------------------------------------------------- findings from the live run (2026-10-28)
def test_truncated_landesplanung_response_is_repaired_and_not_cached(monkeypatch):
    """Live: POST answers of the PLU services sometimes end after the last </wfs:member> without closing the root."""
    full = load('lep__ffm')
    import re
    cut = re.sub(rb'</[\w.-]+:FeatureCollection>\s*$', b'', full)
    assert not cut.rstrip().endswith(b'FeatureCollection>')
    assert len(wfs.parse_features(cut)) == len(wfs.parse_features(full)) > 0
    assert wfs.usable(cut) and wfs.usable(full)
    assert not wfs.usable(b'<ows:ExceptionReport/>') and not wfs.usable(b'<html>502 Bad Gateway</html>') and not wfs.usable(b'')
    import archaitect.siteintel.fetch as fm
    monkeypatch.setattr(fm.time, 'sleep', lambda s: None)
    answers = [b'<ows:ExceptionReport xmlns:ows="x"/>']
    cache = TtlCache(None)
    f = _fetcher(lambda r: httpx.Response(200, content=answers[0]), cache)
    r = f.post_xml('lep', 'https://x.test', '<q/>', 100, 1, wfs.usable)
    assert r.body is None and r.error == 'unbrauchbare Antwort'
    assert cache.get(make_key('lep', 'https://x.test', '<q/>'), 100) is None  # garbage must never be cached
    answers[0] = cut
    assert f.post_xml('lep', 'https://x.test', '<q/>', 100, 1, wfs.usable).body == cut


def test_only_the_regional_plan_of_the_points_region_is_queried():
    boris = wfs.parse_features(load('boris__wald'))                      # Michelstadt, Regierungsbezirk 4 = Darmstadt
    assert sources.regional_plan_for(boris) == ['rp_sued']
    assert sources.regional_plan_for([]) == ['rp_sued', 'rp_mittel', 'rp_nord']
    _, f = run('wald_odenwald')
    assert {s for s, _ in f.calls} >= {'rp_sued'} and not ({s for s, _ in f.calls} & {'rp_mittel', 'rp_nord'})


def test_large_regional_plan_layers_are_asked_with_a_point_not_the_parcel_polygon():
    p = PARCELS['wald_odenwald']
    parcel = Polygon(cadastre.parcel_from_items(p['items'], p['lat'], p['lon']).ring_lonlat)
    bodies = []
    f = _fetcher(lambda r: (bodies.append(r.content.decode()), httpx.Response(200, content=load('rp_sued__wald')))[1])
    out = sources.query(sources.SOURCES['rp_sued'], f, parcel)
    assert out.status.status == 'OK' and out.geometry_used == 'point' and '<gml:Point' in bodies[0] and '<gml:Polygon' not in bodies[0]


def test_boris_military_special_zone_blocks_with_override():
    raw = load('boris__ffm').replace(b'<boris:ergaenzung>MFH</boris:ergaenzung>', b'<boris:ergaenzung>MIL</boris:ergaenzung>')
    a, _ = run('frankfurt_nordend', overrides={'boris': raw})  # modified fixture: the zone's Ergänzung is rewritten to MIL
    assert a.verdict == Verdict.NOT_BUILDABLE and a.design_mode == DesignMode.BLOCKED and a.design_override_allowed
    assert any(f.rule_id == 'BORIS_MILITAER' for f in a.findings)


def test_boris_sonstige_flaeche_is_not_called_aussenbereich():
    raw = load('boris__ffm').replace(b'<boris:entwicklungszustand>B</boris:entwicklungszustand>', b'<boris:entwicklungszustand>SF</boris:entwicklungszustand>')
    a, _ = run('frankfurt_nordend', overrides={'boris': raw})
    f = next(x for x in a.findings if x.rule_id.startswith('BORIS_'))
    assert f.rule_id == 'BORIS_SONSTIGE' and 'Außenbereich' not in f.title_de


def test_street_click_is_blocked_with_a_helpful_hint():
    raw = load('elu__darmstadt').replace(b'5_1_PermanentResidentialUse', b'4_1_1_RoadTransport')
    a, _ = run('darmstadt_wohn', overrides={'elu': raw})   # modified fixture: whole parcel classified as road
    assert a.design_mode == DesignMode.BLOCKED and 'neben der Straße' in a.design_reason_de


def test_missing_parcel_still_reports_hard_evidence_around_the_click():
    raw = load('elu__darmstadt').replace(b'5_1_PermanentResidentialUse', b'6_3_2_WaterAreasNotInOtherEconomicUse')
    p = PARCELS['darmstadt_wohn']
    a = SiteService(ReplayFetcher('darmstadt', overrides={'elu': raw}), FakeCad('darmstadt_wohn')).assess(p['lat'] + 0.01, p['lon'])  # point off the parcel
    assert a.parcel is None and a.design_mode == DesignMode.BLOCKED and a.design_allowed is False


def test_parcel_input_is_accepted_by_the_existing_geodata_pipeline():
    from archaitect.geodata import GeoJSONParcelInput, parse_parcel
    from archaitect.siteintel.dossier import to_parcel_input
    a, _ = run('darmstadt_wohn')
    payload = to_parcel_input(a)
    assert payload and payload['source_crs'] == 'EPSG:4326'
    parcel = parse_parcel(GeoJSONParcelInput(**payload))     # Muse's own validator
    assert parcel.advertised_area_m2 > 50 and parcel.coordinate_system.startswith('EPSG:326')
    blocked, _ = run('darmstadt_wohn', overrides={'elu': load('elu__darmstadt').replace(b'5_1_PermanentResidentialUse', b'4_1_1_RoadTransport')})
    assert to_parcel_input(blocked) is None


def test_slow_osm_never_delays_the_answer_beyond_the_grace_period():
    import threading
    release = threading.Event()

    class SlowOsm:
        def tags_at(self, lat, lon):
            release.wait(5)
            return {}, DataStatus(source_id='osm-overpass', status='OK')

    p = PARCELS['darmstadt_wohn']
    t0 = time.perf_counter()
    a = SiteService(ReplayFetcher('darmstadt'), FakeCad('darmstadt_wohn'), SlowOsm()).assess(p['lat'], p['lon'])
    dt = time.perf_counter() - t0
    release.set()
    assert dt < 2.0 and a.verdict == Verdict.CANDIDATE
    assert any(s.source_id == 'osm-overpass' and s.status == 'UNAVAILABLE' for s in a.data_status)


# ================================================================== terrain / imagery / protected areas / site pack / project flow
import struct
import json as _json


def _tiff(w, h, z, x0=1000.0, y0=2000.0, cell=1.0, area=True, compression=1):
    """Minimal uncompressed float32 GeoTIFF writer for synthetic terrain tests (little endian, one strip)."""
    data = struct.pack('<%df' % (w * h), *z)
    ents = []
    pre = 8
    extra = b''
    def ent(tag, typ, cnt, val):
        ents.append((tag, typ, cnt, val))
    n = 13
    ifd_size = 2 + n * 12 + 4
    base = pre + ifd_size
    scale_off = base; extra += struct.pack('<3d', cell, cell, 0.0)
    tie_off = base + len(extra); extra += struct.pack('<6d', 0, 0, 0, x0, y0, 0)
    keys = struct.pack('<8H', 1, 1, 0, 1, 1025, 0, 1, 1 if area else 2)
    key_off = base + len(extra); extra += keys
    data_off = base + len(extra)
    ent(256, 4, 1, w); ent(257, 4, 1, h); ent(258, 3, 1, 32); ent(259, 3, 1, compression); ent(262, 3, 1, 1); ent(273, 4, 1, data_off)
    ent(277, 3, 1, 1); ent(278, 4, 1, h); ent(279, 4, 1, len(data)); ent(339, 3, 1, 3); ent(33550, 12, 3, scale_off); ent(33922, 12, 6, tie_off); ent(34735, 3, 8, key_off)
    ents.sort()
    ifd = struct.pack('<H', len(ents))
    for tag, typ, cnt, val in ents:
        ifd += struct.pack('<HHI', tag, typ, cnt) + (struct.pack('<H2x', val) if typ == 3 and cnt == 1 else struct.pack('<I', val))
    ifd += struct.pack('<I', 0)
    return b'II*\x00' + struct.pack('<I', 8) + ifd + extra + data


def test_tiff_reader_georef_and_slope_on_a_synthetic_plane():
    from archaitect.siteintel import terrain
    # z rises 0.1 m per metre towards EAST -> 10 % slope, downslope bearing 270 (W)
    w = h = 20
    z = [100 + 0.1 * c for r in range(h) for c in range(w)]
    g = terrain.read_float_tiff(_tiff(w, h, z, x0=1000, y0=2000))
    assert (g.w, g.h, g.x0, g.y0) == (20, 20, 1000.0, 2000.0) and g.xy(0, 0) == (1000.5, 1999.5)
    s = terrain.summarize(g, Polygon([(1003, 1983), (1017, 1983), (1017, 1997), (1003, 1997)]))
    assert abs(s['slope_mean_pct'] - 10.0) < 0.2 and s['downslope_compass'] == 'W' and abs(s['relief_m'] - 1.3) < 0.2
    flat = terrain.summarize(terrain.read_float_tiff(_tiff(w, h, [50.0] * (w * h))), Polygon([(1003, 1985), (1015, 1985), (1015, 1997), (1003, 1997)]))
    assert flat['slope_mean_pct'] == 0.0 and flat['downslope_compass'] is None


def test_tiff_reader_pixel_is_point_shifts_half_a_cell_and_nodata_is_none():
    from archaitect.siteintel import terrain
    z = [-9999.0] + [5.0] * 15
    g = terrain.read_float_tiff(_tiff(4, 4, z, x0=100.5, y0=200.5, area=False))
    assert (g.x0, g.y0) == (100.0, 201.0) and g.at(0, 0) is None and g.at(1, 0) == 5.0


def test_tiff_reader_refuses_what_it_cannot_read():
    from archaitect.siteintel import terrain
    with pytest.raises(ValueError):
        terrain.read_float_tiff(b'not a tiff at all')
    with pytest.raises(ValueError):
        terrain.read_float_tiff(_tiff(4, 4, [1.0] * 16, compression=5))


def test_real_dgm1_fixture_is_plausible_for_darmstadt():
    from archaitect.siteintel import terrain
    g = terrain.read_float_tiff((FX_BIN / 'dgm1__darmstadt.tif').read_bytes())
    assert g.dx == 1.0 and 470000 < g.x0 < 480000 and 5520000 < g.y0 < 5530000
    vals = [v for v in g.z if v is not None]
    assert 140 < min(vals) and max(vals) < 200      # Darmstadt lies at ~150–160 m NHN


from siteintel_support import FX
FX_BIN = FX / 'bin'


def test_imagery_helpers_and_hessen_fence():
    from archaitect.siteintel import imagery
    assert imagery.looks_like_image(b'\xff\xd8\xff\xe0abc') and imagery.looks_like_image(b'\x89PNG\r\n\x1a\nxx') and not imagery.looks_like_image(b'<?xml version')
    assert imagery.bbox_in_hessen((964000, 6455000, 964600, 6455600), 'EPSG:3857')          # Frankfurt
    assert not imagery.bbox_in_hessen((1490000, 6890000, 1491000, 6891000), 'EPSG:3857')    # Berlin
    assert not imagery.bbox_in_hessen((0, 0, 1, 1), 'EPSG:4326')                            # CRS not allowed


def test_imagery_proxy_endpoint_is_not_an_open_relay():
    from archaitect.main import app
    from archaitect.siteintel import router as r
    svc, _ = service_for('darmstadt_wohn')
    r.providers['service'] = svc
    try:
        c = TestClient(app)
        ok = c.get('/siteintel/imagery/wms', params={'layers': 'luftbild', 'bbox': '964000,6455000,964600,6455600', 'width': 256, 'height': 256, 'crs': 'EPSG:3857', 'format': 'image/png'})
        assert ok.status_code == 200 and ok.headers['content-type'] == 'image/png' and 'Cache-Control' in ok.headers
        assert c.get('/siteintel/imagery/wms', params={'layers': 'google', 'bbox': '1,2,3,4'}).status_code == 400
        assert c.get('/siteintel/imagery/wms', params={'layers': 'luftbild', 'bbox': '1490000,6890000,1491000,6891000'}).status_code == 404
        assert c.get('/siteintel/imagery/wms', params={'layers': 'luftbild', 'bbox': '964000,6455000,964600,6455600', 'width': 5000}).status_code == 422
        assert c.get('/siteintel/imagery/wms', params={'layers': 'luftbild', 'bbox': 'a,b'}).status_code == 400
        assert {l['key'] for l in c.get('/siteintel/imagery/layers').json()} == {'luftbild', 'luftbild_cir', 'karte'}
    finally:
        r.providers.clear()


def test_national_park_is_a_hard_stop_with_override_hint():
    a, _ = run('darmstadt_wohn', overrides={'schutzgebiete': load('schutz__kellerwald')})   # recorded Kellerwald response replayed on a residential plot
    assert a.verdict == Verdict.NOT_BUILDABLE and a.design_mode == DesignMode.BLOCKED and a.design_override_allowed
    f = next(x for x in a.findings if x.rule_id == 'SCHUTZ_STRENG')
    assert 'Nationalpark' in f.title_de and f.source_id == 'schutzgebiete'
    assert any(p.kind == 'nationalpark' for p in a.protections) and any(r.id == 'schutzgebiete' for r in a.regulations)


def test_nature_reserve_blocks_like_a_national_park():
    raw = load('schutz__kellerwald').replace(b'Nationalpark', b'Naturschutzgebiete')   # modified fixture: same payload typed as NSG
    a, _ = run('darmstadt_wohn', overrides={'schutzgebiete': raw})
    assert any(p.kind == 'nsg' for p in a.protections) and a.verdict == Verdict.NOT_BUILDABLE


def test_landscape_and_bird_protection_are_soft_restrictions_that_bauland_can_lift():
    a, _ = run('darmstadt_wohn', overrides={'schutzgebiete': load('schutz__rhoen')})      # LSG + VSG + Biosphäre + Naturpark
    kinds = {p.kind for p in a.protections}
    assert {'lsg', 'vsg', 'biosphaere', 'naturpark'} <= kinds
    assert a.verdict == Verdict.CANDIDATE and any(f.rule_id == 'SCHUTZ_LSG' for f in a.findings) and a.design_mode != DesignMode.BLOCKED
    ack, _ = run('acker_wetterau', overrides={'schutzgebiete': load('schutz__rhoen')})
    assert ack.verdict == Verdict.RESTRICTED


def test_naturpark_and_biosphere_are_notes_only():
    a, _ = run('darmstadt_wohn')
    base = a.verdict
    raw = load('schutz__rhoen')
    only_notes = raw.replace(b'Landschaftsschutzgebiete', b'Naturparke').replace(b'Vogelschutzgebiete', b'Biosphaerenreservat')
    b, _ = run('darmstadt_wohn', overrides={'schutzgebiete': only_notes})
    assert b.verdict == base and all(not f.affects_verdict for f in b.findings if f.rule_id == 'SCHUTZ_HINWEIS')


def _pack(key='darmstadt_wohn', point_override=None, **kw):
    from archaitect.siteintel.sitepack import build_sitepack
    a, f = run(key, **kw)
    return a, build_sitepack(f, a), f


def test_site_pack_has_georeferenced_ortho_terrain_neighbours_and_honest_utilities():
    a, pack, _ = _pack()
    m = pack.manifest
    assert m['schema_version'] == 'archaitect.site-pack/1' and m['ortho']['status'] == 'OK' and pack.ortho[:8] == b'\x89PNG\r\n\x1a\n'
    o = m['ortho']
    assert o['pixel_size_m'] == pytest.approx(0.2, abs=0.01) and o['bbox_epsg25832'][2] - o['bbox_epsg25832'][0] >= 80
    ring = next(p['ring'] for p in m['parcels'] if p['is_site'])
    bx0, by0, bx1, by1 = o['bbox_local']
    assert all(bx0 < x < bx1 and by0 < y < by1 for x, y in ring), 'parcel must lie inside the orthophoto'
    assert abs(Polygon(ring).centroid.x) < 0.01 and abs(Polygon(ring).centroid.y) < 0.01, 'local frame is centred on the parcel centroid'
    assert m['terrain']['status'] == 'OK' and 140 < m['terrain']['summary']['z_mean_m'] < 200 and m['terrain']['grid']['rows'] > 10
    assert sum(1 for p in m['parcels'] if not p['is_site']) >= 5 and len(m['buildings']) >= 5
    assert all(b['height_basis'] == 'ESTIMATE_FROM_FLOORS' for b in m['buildings'] if b['height_est_m'])
    assert m['utilities']['status'] == 'NOT_OPEN_DATA' and {x['kind'] for x in m['utilities']['media']} >= {'wasser', 'gas', 'strom', 'abwasser'}
    assert 'NO_UTILITY_LINES_IN_OPEN_DATA' in m['quality_flags'] and 'verändert' in m['attribution'][0]['text']
    assert abs(m['frame']['true_north_offset_deg']) < 3
    _json.dumps(m)   # fully serialisable


def test_site_pack_degrades_per_part_not_as_a_whole():
    a, pack, _ = _pack(fail={'hessen-dgm1', 'hessen-wms-luftbild'})
    m = pack.manifest
    assert m['terrain']['status'] == 'UNAVAILABLE' and m['ortho']['status'] == 'UNAVAILABLE' and pack.ortho is None
    assert {'TERRAIN_UNAVAILABLE', 'ORTHO_UNAVAILABLE'} <= set(m['quality_flags']) and m['parcels'] and m['buildings']


def test_site_pack_needs_a_parcel():
    from archaitect.siteintel.sitepack import build_sitepack
    p = PARCELS['darmstadt_wohn']
    a = SiteService(ReplayFetcher('darmstadt'), FakeCad('darmstadt_wohn')).assess(p['lat'] + 0.01, p['lon'])
    with pytest.raises(ValueError):
        build_sitepack(ReplayFetcher('darmstadt'), a)


def test_planning_brief_validation():
    from archaitect.siteintel.brief import PlanningBrief, ConnectionPoint
    b = PlanningBrief()
    assert b.program.living_area_target_m2 is None and b.program.basement == 'unknown' and b.connections == []   # unknown stays unknown
    with pytest.raises(Exception):
        ConnectionPoint(id='x', kind='wasser', lon=13.4, lat=52.5)           # Berlin: outside Hessen
    with pytest.raises(Exception):
        ConnectionPoint(id='x', kind='atom', lon=8.6, lat=50.1)               # unknown medium
    with pytest.raises(Exception):
        PlanningBrief(program={'living_area_target_m2': 5})


def test_project_flow_end_to_end(tmp_path):
    from archaitect.main import app
    from archaitect.siteintel import router as r
    from archaitect.siteintel.projects import ProjectStore
    p = PARCELS['darmstadt_wohn']
    svc, _ = service_for('darmstadt_wohn')
    r.providers['service'] = svc
    r.providers['store'] = ProjectStore(tmp_path)
    try:
        c = TestClient(app)
        made = c.post('/siteintel/projects', json={'lat': p['lat'], 'lon': p['lon']})
        assert made.status_code == 200, made.text
        pid = made.json()['id']
        assert made.json()['ortho'] == 'OK' and made.json()['terrain'] == 'OK'
        pack = c.get(f'/siteintel/projects/{pid}/sitepack').json()
        cx = pack['frame']
        brief = {'title': 'Haus Test', 'program': {'occupants': 4, 'bedrooms': 3, 'living_area_target_m2': 140, 'stories': 2, 'roof_types': ['sattel'], 'style_keywords_de': ['modern']},
                 'wishes_de': 'Viel Licht nach Süden', 'connections': [{'id': 'w1', 'kind': 'wasser', 'lon': p['lon'], 'lat': p['lat'], 'status': 'USER_SUPPLIED', 'note_de': 'Schacht vor dem Haus'}]}
        assert c.put(f'/siteintel/projects/{pid}/brief', json=brief).status_code == 200
        assert c.put(f'/siteintel/projects/{pid}/brief', json={'connections': [{'id': 'x', 'kind': 'gas', 'lon': 2.0, 'lat': 48.0}]}).status_code == 422
        ctx = c.get(f'/siteintel/projects/{pid}/context').json()
        assert ctx['schema_version'] == 'archaitect.generation-context/1' and ctx['verified_constraints'] is None and ctx['geometry']['buildable_envelope_local'] is None
        ids = {f['id'] for f in ctx['facts']}
        assert {'gate', 'terrain', 'brief', 'conn.w1', 'utilities', 'orientation'} <= ids and ctx['retrieval_chunks'] and len(ctx['rules_for_generator']) >= 5
        assert ctx['brief']['program']['bedrooms'] == 3 and ctx['geometry']['connections_local'][0]['kind'] == 'wasser'
        # verification is the only way to a buildable envelope
        v = c.post(f'/siteintel/projects/{pid}/constraints', json={'verified_by': 'Test Reviewer', 'basis_de': 'B-Plan Test', 'setback_lines_offset_meters': 3, 'grz': 0.4})
        assert v.status_code == 200
        ctx2 = c.get(f'/siteintel/projects/{pid}/context').json()
        env = ctx2['geometry']['buildable_envelope_local']
        assert env and ctx2['verified_constraints']['status'] == 'VERIFIED_BY_USER'
        assert Polygon(ctx2['geometry']['parcel_local']).contains(Polygon(env)), 'envelope (local frame) must lie inside the parcel (local frame)'
        ov = c.get(f'/siteintel/projects/{pid}/overlay').json()
        kinds = {f['properties']['kind'] for f in ov['features']}
        assert {'parcel_site', 'parcel', 'building', 'envelope', 'connection', 'landuse'} <= kinds
        site = next(f for f in ov['features'] if f['properties']['kind'] == 'parcel_site')['geometry']['coordinates'][0]
        assert all(8.5 < lon < 8.8 and 49.8 < lat < 49.95 for lon, lat in site), 'overlay must be WGS84 lon/lat in Darmstadt'
        z = c.get(f'/siteintel/projects/{pid}/sitepack.zip')
        import zipfile, io
        names = set(zipfile.ZipFile(io.BytesIO(z.content)).namelist())
        assert z.status_code == 200 and {'manifest.json', 'context.json', 'ortho.png', 'ortho.pgw', 'README.txt'} <= names
        assert c.get(f'/siteintel/projects/{pid}/ortho.png').headers['content-type'] == 'image/png'
        assert c.get('/siteintel/projects/p_000000000000/context').status_code == 404 and c.get('/siteintel/projects/../etc/passwd').status_code in (404, 405)
        assert [m['id'] for m in c.get('/siteintel/projects').json()] == [pid]
        reloaded = c.get(f'/siteintel/projects/{pid}').json()
        assert reloaded['brief']['title'] == 'Haus Test' and reloaded['verified']['verified_by'] == 'Test Reviewer'
    finally:
        r.providers.clear()


def test_blocked_site_cannot_become_a_project_unless_override_is_allowed(tmp_path):
    from archaitect.main import app
    from archaitect.siteintel import router as r
    from archaitect.siteintel.projects import ProjectStore
    p = PARCELS['darmstadt_wohn']
    road = load('elu__darmstadt').replace(b'5_1_PermanentResidentialUse', b'4_1_1_RoadTransport')
    for overrides, expect_override in (({'elu': road}, False), ({'schutzgebiete': load('schutz__kellerwald')}, True)):
        svc, _ = service_for('darmstadt_wohn', overrides=overrides)
        r.providers['service'] = svc
        r.providers['store'] = ProjectStore(tmp_path / str(expect_override))
        try:
            c = TestClient(app)
            assert c.post('/siteintel/projects', json={'lat': p['lat'], 'lon': p['lon']}).status_code == 409
            res = c.post('/siteintel/projects', json={'lat': p['lat'], 'lon': p['lon'], 'override': True})
            assert (res.status_code == 200) is expect_override
        finally:
            r.providers.clear()
