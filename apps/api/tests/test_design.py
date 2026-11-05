"""Studio design engine: hard plot limits, verified B-Plan values, HBO Abstandsflächen as warnings, fitting, revisions, several parcels."""
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon
from siteintel_support import PARCELS, service_for
from archaitect.siteintel.regs import hbo_depth, roof_credit


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHAITECT_DB_PATH', str(tmp_path / 'core.sqlite'))
    monkeypatch.setenv('ARCHAITECT_SITEINTEL_OSM', '0')
    from archaitect.main import app
    from archaitect.siteintel import router as r
    from archaitect.siteintel.projects import ProjectStore
    p = PARCELS['darmstadt_wohn']
    svc, _ = service_for('darmstadt_wohn')
    r.providers['service'] = svc
    r.providers['store'] = ProjectStore(tmp_path / 'projects')
    c = TestClient(app)
    made = c.post('/siteintel/projects', json={'lat': p['lat'], 'lon': p['lon']})
    assert made.status_code == 200, made.text
    yield c, made.json()['id'], r
    r.providers.pop('service', None)
    r.providers.pop('store', None)


def _status(chk, rid):
    return next(x for x in chk['results'] if x['id'] == rid)['status']


def test_hbo_formula():
    assert hbo_depth(6.5) == 2.6 and hbo_depth(3.0) == 2.5 and hbo_depth(10.0) == 4.0 and hbo_depth(6.49) == 2.5
    assert roof_credit(30) == 0 and abs(roof_credit(50) - 1 / 3) < 1e-9 and roof_credit(75) == 1


def test_initial_design_is_inside_and_rules_are_honest(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m, chk, site = d['massing'], d['check'], d['site']
    assert m['version'] == 1 and len(m['volumes']) == 1 and d['history'][0]['version'] == 1
    assert chk['hard_ok'] and _status(chk, 'PARCEL') == 'PASS'
    assert _status(chk, 'GRZ') == 'UNKNOWN' and _status(chk, 'HEIGHT') == 'UNKNOWN', 'without verified B-Plan values nothing is claimed'
    assert _status(chk, 'HBO_ABSTAND') in ('PASS', 'WARN') and chk['overlays']['abstandsflaechen']
    af = chk['overlays']['abstandsflaechen'][0]
    assert af['depth_m'] >= 2.5 and af['H_m'] > 5
    assert Polygon(site['ring']).area > 1000 and chk['limits']['region']


def test_outside_the_plot_is_hard_and_cannot_be_saved(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m = d['massing']
    cx0 = m['volumes'][0]['cx']
    bx = Polygon(d['site']['ring']).bounds
    m['volumes'][0]['cx'] = bx[2] + 3
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    assert _status(chk, 'PARCEL') == 'FAIL' and not chk['hard_ok'] and chk['overall'] == 'FAIL'
    r = c.post(f'/siteintel/projects/{pid}/design/commit', json={'massing': m, 'expected_version': 1})
    assert r.status_code == 422 and 'Flurstücksgrenze' in r.text
    fitted = c.post(f'/siteintel/projects/{pid}/design/fit', json={'massing': m}).json()
    assert fitted['check']['hard_ok'] and fitted['notes_de']
    saved = c.post(f'/siteintel/projects/{pid}/design/commit', json={'massing': fitted['massing'], 'expected_version': 1})
    assert saved.status_code == 200 and saved.json()['massing']['version'] == 2
    assert c.post(f'/siteintel/projects/{pid}/design/commit', json={'massing': fitted['massing'], 'expected_version': 1}).status_code == 409, 'stale version'
    back = c.post(f'/siteintel/projects/{pid}/design/restore', json={'version': 1, 'expected_version': 2}).json()
    assert back['massing']['version'] == 3 and back['massing']['volumes'][0]['cx'] == cx0


def test_verified_values_are_enforced_and_fit_repairs(api):
    c, pid, _ = api
    assert c.post(f'/siteintel/projects/{pid}/constraints', json={'verified_by': 'Test', 'basis_de': 'B-Plan Nr. 1, Festsetzung 2', 'grz': 0.3, 'gfz': 0.6, 'max_stories': 2,
                                                                   'max_building_height_meters': 9.5, 'roof_types_allowed': ['sattel'], 'roof_pitch_min_deg': 25, 'roof_pitch_max_deg': 40}).status_code == 200
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m = d['massing']
    v = m['volumes'][0]
    v.update({'storeys': 4, 'roof': 'flach', 'width_m': v['width_m'] * 1.6, 'depth_m': v['depth_m'] * 1.6})
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    for rid in ('STOREYS', 'HEIGHT', 'ROOF'):
        assert _status(chk, rid) == 'FAIL', rid
    assert all(x['hard'] for x in chk['results'] if x['basis'] == 'BPLAN_VERIFIED' and x['status'] == 'FAIL')
    assert chk['limits']['max_storeys'] == 2 and chk['limits']['roofs_allowed'] == ['sattel'] and chk['limits']['max_footprint_main_m2'] > 0
    f = c.post(f'/siteintel/projects/{pid}/design/fit', json={'massing': m}).json()
    fv = f['massing']['volumes'][0]
    assert f['check']['hard_ok'], [x for x in f['check']['results'] if x['status'] == 'FAIL']
    assert fv['storeys'] <= 2 and fv['roof'] == 'sattel' and 25 <= fv['roof_pitch_deg'] <= 40
    met = f['check']['metrics']
    assert met['grz'] <= 0.3 + 1e-3 and met['gfz'] <= 0.6 + 1e-3 and met['top_m'] <= 9.5 + 1e-6


def test_abstandsflaeche_near_the_boundary_warns_but_does_not_block(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m0 = d['massing']
    seen = []
    for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
        m = {**m0, 'volumes': [dict(m0['volumes'][0])]}
        v = m['volumes'][0]
        last_ok = None
        for _ in range(160):
            v['cx'] += dx * 0.25
            v['cy'] += dy * 0.25
            chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
            if _status(chk, 'PARCEL') == 'FAIL':
                break
            last_ok = chk
        seen.append(_status(last_ok, 'HBO_ABSTAND'))
        if seen[-1] == 'WARN':
            assert last_ok['hard_ok'] and last_ok['overlays']['violations']
            hbo = next(x for x in last_ok['results'] if x['id'] == 'HBO_ABSTAND')
            assert not hbo['hard'] and '2,50' in hbo['source_de']
    assert 'WARN' in seen, seen


def test_existing_buildings_block_until_demolished(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    ex = d['site']['existing']
    if not ex:
        pytest.skip('fixture plot has no building')
    b = Polygon(ex[0]['ring'])
    m = d['massing']
    m['volumes'] = [{'id': 'v1', 'shape': 'poly', 'points': [list(p) for p in list(b.buffer(-0.5).exterior.coords)[:-1]], 'roof': 'flach', 'storeys': 2}]
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    assert _status(chk, 'EXISTING') == 'FAIL'
    m['demolish'] = [ex[0]['id']]
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    assert _status(chk, 'EXISTING') == 'PASS' and 'Abriss' in next(x for x in chk['results'] if x['id'] == 'EXISTING')['message_de']


def test_special_shapes_and_validation(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m = d['massing']
    v = m['volumes'][0]
    m['volumes'].append({'id': 'tower', 'name': 'Turm', 'shape': 'round', 'cx': v['cx'], 'cy': v['cy'], 'width_m': 5, 'storeys': 3, 'roof': 'kegel', 'roof_pitch_deg': 50})
    m['volumes'].append({'id': 'g', 'name': 'Garage', 'role': 'garage', 'cx': v['cx'] + 2, 'cy': v['cy'], 'width_m': 6, 'depth_m': 3, 'storeys': 1, 'storey_height_m': 2.5, 'roof': 'flach'})
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    assert chk['metrics']['volumes'] == 3 and any(x['id'] == 'HBO_GARAGE' for x in chk['results'])
    m['volumes'][1]['roof'] = 'sattel'
    assert c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).status_code == 422, 'a round body cannot carry a gable roof'


def test_adjacent_parcels_can_be_combined(api, monkeypatch):
    c, pid, r = api
    cand = c.get(f'/siteintel/projects/{pid}/parcels').json()
    assert cand['max'] == 5 and cand['selected'] == [cand['primary_id']]
    adj = [p for p in cand['parcels'] if p['adjacent'] and not p['selected']]
    far = [p for p in cand['parcels'] if not p['adjacent'] and not p['selected']]
    assert adj, 'fixture has neighbours'
    if far:
        assert c.post(f'/siteintel/projects/{pid}/parcels', json={'parcel_id': far[0]['id'], 'action': 'add'}).status_code == 409
    real = r.service().assess

    home = PARCELS['darmstadt_wohn']

    def fake(lat, lon, stage='full'):
        a = real(home['lat'], home['lon'], stage)
        return a.model_copy(update={'parcel': a.parcel.model_copy(update={'national_reference': adj[0]['id']})})
    monkeypatch.setattr(r.service(), 'assess', fake)
    before = c.get(f'/siteintel/projects/{pid}/design').json()['site']
    res = c.post(f'/siteintel/projects/{pid}/parcels', json={'parcel_id': adj[0]['id'], 'action': 'add'})
    assert res.status_code == 200, res.text
    assert set(res.json()['selected']) == {cand['primary_id'], adj[0]['id']}
    after = c.get(f'/siteintel/projects/{pid}/design').json()['site']
    assert Polygon(after['ring']).area > Polygon(before['ring']).area + 50
    assert after['frame']['origin_e'] == before['frame']['origin_e'], 'local frame stays, so designs keep their coordinates'
    meta = c.get(f'/siteintel/projects/{pid}').json()['project']
    assert len(meta['parcel_ids']) == 2
    assert c.post(f'/siteintel/projects/{pid}/parcels', json={'parcel_id': cand['primary_id'], 'action': 'remove'}).status_code == 409
    rem = c.post(f'/siteintel/projects/{pid}/parcels', json={'parcel_id': adj[0]['id'], 'action': 'remove'})
    assert rem.status_code == 200 and rem.json()['selected'] == [cand['primary_id']]


PNG_1PX = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='


def test_reference_upload_is_validated(api):
    c, pid, _ = api
    assert c.post(f'/siteintel/projects/{pid}/references', json={'name': 'x.exe', 'media_type': 'application/x-msdownload', 'data_b64': PNG_1PX}).status_code == 415
    assert c.post(f'/siteintel/projects/{pid}/references', json={'name': 'fake.pdf', 'media_type': 'application/pdf', 'data_b64': PNG_1PX}).status_code == 415
    ok = c.post(f'/siteintel/projects/{pid}/references', json={'name': 'plan.png', 'media_type': 'image/png', 'data_b64': PNG_1PX, 'kind': 'plan'}).json()
    assert c.get(f'/siteintel/projects/{pid}/references').json()['references'][0]['kind'] == 'plan'
    f = c.get(f'/siteintel/projects/{pid}/references/{ok["id"]}/file')
    assert f.headers['content-type'] == 'image/png' and f.headers['x-content-type-options'] == 'nosniff'
    assert c.delete(f'/siteintel/projects/{pid}/references/{ok["id"]}').status_code == 200


def test_own_limits_are_enforced_without_verification(api):
    c, pid, _ = api
    r = c.put(f'/siteintel/projects/{pid}/limits', json={'max_stories': 2, 'roof_types_allowed': ['sattel'], 'note_de': 'Wunsch Bauherr'})
    assert r.status_code == 200, r.text
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    assert d['site']['limit_basis']['max_stories'] == 'USER_LIMIT' and d['check']['limits']['max_storeys'] == 2
    m = d['massing']
    m['volumes'][0].update({'storeys': 3, 'roof': 'sattel'})
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    st = next(x for x in chk['results'] if x['id'] == 'STOREYS')
    assert st['status'] == 'FAIL' and st['hard'] and st['basis'] == 'USER_LIMIT' and 'nicht als Bebauungsplan geprüft' in st['source_de']
    assert c.post(f'/siteintel/projects/{pid}/design/commit', json={'massing': m, 'expected_version': 1}).status_code == 422
    # verified value wins over the own limit
    c.post(f'/siteintel/projects/{pid}/constraints', json={'verified_by': 'Test', 'basis_de': 'B-Plan 3', 'max_stories': 3})
    d2 = c.get(f'/siteintel/projects/{pid}/design').json()
    assert d2['check']['limits']['max_storeys'] == 3 and d2['site']['limit_basis']['max_stories'] == 'BPLAN_VERIFIED'
    assert d2['site']['limit_basis']['roof_types_allowed'] == 'USER_LIMIT'
    assert c.put(f'/siteintel/projects/{pid}/limits', json={}).json()['limits'] is None


def test_stacked_volumes_count_as_storeys(api):
    c, pid, _ = api
    c.put(f'/siteintel/projects/{pid}/limits', json={'max_stories': 2})
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    m = d['massing']
    v = dict(m['volumes'][0])
    v.update({'storeys': 2, 'roof': 'flach'})
    top = {**v, 'id': 'top', 'name': 'Aufstockung', 'storeys': 1, 'elevation_m': round(0.3 + 2 * v['storey_height_m'], 2), 'width_m': v['width_m'] * 0.6, 'depth_m': v['depth_m'] * 0.6}
    m['volumes'] = [v, top]
    chk = c.post(f'/siteintel/projects/{pid}/design/check', json={'massing': m}).json()
    st = next(x for x in chk['results'] if x['id'] == 'STOREYS')
    assert st['status'] == 'FAIL' and st['observed'] == 3
    f = c.post(f'/siteintel/projects/{pid}/design/fit', json={'massing': m}).json()
    assert f['check']['hard_ok'] and next(x for x in f['check']['results'] if x['id'] == 'STOREYS')['observed'] <= 2


def test_sitepack_site_keeps_location_and_selection(api):
    c, pid, _ = api
    site = c.get(f'/siteintel/projects/{pid}/sitepack').json()['site']
    assert {'lat', 'lon', 'parcel_id', 'area_alkis_m2', 'parcel_ids', 'primary_id', 'ring_local'} <= set(site)


def test_legacy_project_without_data_flags_is_not_reported_as_missing_data(api):
    """Projects created before terrain_ok/ortho_ok existed stored their data but showed 'Daten fehlen'."""
    import json
    c, pid, r = api
    f = r.store()._dir(pid) / 'project.json'
    meta = json.loads(f.read_text(encoding='utf-8'))
    meta.pop('terrain_ok', None)
    meta.pop('ortho_ok', None)
    f.write_text(json.dumps(meta), encoding='utf-8')
    card = next(x for x in c.get('/siteintel/projects').json() if x['id'] == pid)
    data_step = next(s for s in card['progress']['steps'] if s['key'] == 'data')
    assert data_step['done'] is True
    assert not card['progress']['next'] or card['progress']['next']['key'] != 'data'


def test_repair_refetches_data_and_reports_state(api):
    c, pid, _ = api
    res = c.post(f'/siteintel/projects/{pid}/repair')
    assert res.status_code == 200, res.text
    assert set(res.json()) == {'terrain_ok', 'ortho_ok'}
    assert c.post('/siteintel/projects/p_000000000000/repair').status_code == 404


def test_design_response_lists_protection_notices(api):
    c, pid, _ = api
    d = c.get(f'/siteintel/projects/{pid}/design').json()
    assert isinstance(d['notices'], list)
    for n in d['notices']:
        assert {'kind', 'label_de', 'on_parcel'} <= set(n)


def test_unexpected_errors_keep_cors_headers(api, monkeypatch):
    c, pid, _ = api
    from archaitect.siteintel import design_api as D

    def boom(*a, **k):
        raise ValueError('kaputt')
    monkeypatch.setattr(D, 'evaluate', boom)
    from fastapi.testclient import TestClient
    from archaitect.main import app
    c2 = TestClient(app, raise_server_exceptions=False)
    r = c2.get(f'/siteintel/projects/{pid}/design', headers={'Origin': 'http://localhost:3000'})
    assert r.status_code == 500 and 'ValueError' in r.json()['detail']
    assert r.headers.get('access-control-allow-origin'), 'error must carry CORS headers, otherwise the browser only says "Load failed"'


def test_random_designs_never_crash_the_rule_engine(api):
    """Regression: overlays on near-degenerate edges raised GEOS TopologyException (HTTP 500 -> 'Load failed' in Safari)."""
    import copy
    import random
    from archaitect.siteintel import design_api as D
    from archaitect.siteintel.massing import Massing
    from archaitect.siteintel.regs import evaluate, fit
    c, pid, _ = api
    base = c.get(f'/siteintel/projects/{pid}/design').json()['massing']
    ctx, _, _ = D.ctx_for(pid)
    rnd = random.Random(3)
    for _ in range(120):
        m = copy.deepcopy(base)
        v = m['volumes'][0]
        v.update(cx=v['cx'] + rnd.uniform(-30, 30), cy=v['cy'] + rnd.uniform(-30, 30), width_m=rnd.uniform(2, 40), depth_m=rnd.uniform(2, 30), rotation_deg=rnd.uniform(-90, 90),
                 storeys=rnd.randint(1, 6), elevation_m=rnd.choice([0, 0, 3.2]), roof=rnd.choice(['flach', 'sattel', 'walm', 'pult', 'zelt']), roof_pitch_deg=rnd.uniform(5, 60))
        for k in range(rnd.choice([0, 1, 2])):
            w = copy.deepcopy(v)
            w.update(id=f'w{k}', cx=v['cx'] + rnd.uniform(-6, 6), cy=v['cy'] + rnd.uniform(-6, 6), rotation_deg=rnd.uniform(-90, 90))
            m['volumes'].append(w)
        mm = Massing.model_validate(m)
        evaluate(mm, ctx)
        f, _n = fit(mm, ctx)
        assert evaluate(f, ctx)['hard_ok'] or not f.volumes


def test_secondary_grz_is_unknown_without_specific_rule_basis(api):
    c,pid,_=api
    assert c.post(f'/siteintel/projects/{pid}/constraints',json={'verified_by':'Test','basis_de':'Plan Festsetzung 1','grz':0.3}).status_code==200
    d=c.get(f'/siteintel/projects/{pid}/design').json()
    check=c.post(f'/siteintel/projects/{pid}/design/check',json={'massing':d['massing']}).json()
    row=next(x for x in check['results'] if x['id']=='GRZ2')
    assert row['status']=='UNKNOWN' and row['hard'] is False
    assert check['limits']['max_footprint_all_m2'] is None
