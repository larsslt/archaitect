"""Overview, studio bridge and project operations on top of the site-intel project store (fixtures replay the real Darmstadt answers)."""
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon
from siteintel_support import PARCELS, service_for


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
    yield TestClient(app), p
    r.providers.pop('service', None)
    r.providers.pop('store', None)


def _new(c, p):
    made = c.post('/siteintel/projects', json={'lat': p['lat'], 'lon': p['lon']})
    assert made.status_code == 200, made.text
    return made.json()['id']


def test_overview_cards_show_progress_and_next_step(api):
    c, p = api
    pid = _new(c, p)
    card = c.get('/siteintel/projects').json()[0]
    assert card['id'] == pid and card['area_m2'] > 1000 and card['has_thumb']
    steps = {s['key']: s['done'] for s in card['progress']['steps']}
    assert steps == {'site': True, 'data': True, 'brief': False, 'utilities': False, 'rules': False, 'design': False}
    assert card['progress']['next']['key'] == 'brief' and card['progress']['next']['tab'] == 'program'
    assert card['thumb']['ring'] and len(card['thumb']['bbox_local']) == 4
    assert c.get(f'/siteintel/projects/{pid}/thumb.jpg').headers['content-type'] == 'image/jpeg'
    c.put(f'/siteintel/projects/{pid}/brief', json={'program': {'occupants': 4, 'living_area_target_m2': 150, 'stories': 2}, 'connections': [{'id': 'w', 'kind': 'wasser', 'lon': p['lon'], 'lat': p['lat']}]})
    card = c.get('/siteintel/projects').json()[0]
    assert card['progress']['next']['key'] == 'rules' and card['progress']['done'] == 4


def test_studio_starts_inside_the_parcel_and_rules_only_verified_by_people(api):
    c, p = api
    pid = _new(c, p)
    c.put(f'/siteintel/projects/{pid}/brief', json={'program': {'occupants': 4, 'living_area_target_m2': 150, 'stories': 2, 'roof_types': ['sattel']}})
    s = c.post(f'/siteintel/projects/{pid}/studio').json()
    proj = s['project']
    parcel = Polygon([(q['x'], q['y']) for q in proj['parcel']['points']])
    assert proj['rules'] == [] and proj['envelope'] is None and proj['design']['version'] == 1
    assert abs(parcel.centroid.x) < 15 and abs(parcel.centroid.y) < 15, 'studio works in the local frame around the parcel centroid'
    v0 = c.post(f'/projects/{pid}/validate', json={'design': proj['design']}).json()
    assert v0['overall'] == 'UNKNOWN', 'unverified parcel + no rules must never pass'
    # verification by a person -> verified rules + envelope, design untouched
    assert c.post(f'/siteintel/projects/{pid}/constraints', json={'verified_by': 'Test', 'basis_de': 'B-Plan §1', 'setback_lines_offset_meters': 3, 'grz': 0.4, 'max_stories': 2, 'max_building_height_meters': 11}).status_code == 200
    s2 = c.post(f'/siteintel/projects/{pid}/studio').json()['project']
    assert {r['kind'] for r in s2['rules']} == {'MAX_STOREYS', 'MAX_HEIGHT', 'MAX_FOOTPRINT', 'BUILDING_ENVELOPE'} and s2['envelope'] and s2['design'] == proj['design']
    env = Polygon([(q['x'], q['y']) for q in s2['envelope']])
    assert parcel.contains(env)
    ok = c.post(f'/projects/{pid}/validate', json={'design': s2['design']}).json()
    by = {r['rule_id']: r['status'] for r in ok['results']}
    assert by['VERIFIED_BUILDING_ENVELOPE'] == 'PASS' and by['VERIFIED_MAX_STOREYS'] == 'PASS', ok
    d = dict(s2['design'])
    d['storeys'] = 3
    d['center_x'] = parcel.bounds[2] + 5          # outside the plot
    bad = c.post(f'/projects/{pid}/validate', json={'design': d}).json()
    by = {r['rule_id']: r['status'] for r in bad['results']}
    assert by['VERIFIED_BUILDING_ENVELOPE'] == 'FAIL' and by['VERIFIED_MAX_STOREYS'] == 'FAIL' and bad['overall'] == 'FAIL'
    # saving a revision works with the generic core endpoints
    saved = c.post(f'/projects/{pid}/commands/commit', json={'design': s2['design'], 'expected_version': 1})
    assert saved.status_code == 200 and saved.json()['design']['version'] == 2
    # re-opening the studio after a design commit keeps the revision
    again = c.post(f'/siteintel/projects/{pid}/studio').json()['project']
    assert again['design']['version'] == 2
    card = c.get('/siteintel/projects').json()[0]
    assert card['has_studio'] and card['design_version'] == 2 and card['progress']['steps'][-1]['done']


def test_rename_pin_duplicate_delete(api):
    c, p = api
    pid = _new(c, p)
    c.post(f'/siteintel/projects/{pid}/studio')
    r = c.put(f'/siteintel/projects/{pid}/meta', json={'name': 'Haus am Park', 'pinned': True}).json()
    assert r['name'] == 'Haus am Park' and r['pinned'] is True and r['title'] == 'Haus am Park'
    assert c.put(f'/siteintel/projects/{pid}/meta', json={'name': ' '}).status_code == 422
    dup = c.post(f'/siteintel/projects/{pid}/duplicate').json()
    assert dup['id'] != pid and dup['name'].endswith('(Kopie)')
    assert len(c.get('/siteintel/projects').json()) == 2
    assert c.delete(f'/siteintel/projects/{pid}').status_code == 200
    assert c.get(f'/siteintel/projects/{pid}').status_code == 404 and c.get(f'/projects/{pid}').status_code == 404
    assert [m['id'] for m in c.get('/siteintel/projects').json()] == [dup['id']]


def test_height_rule_is_respected_by_the_first_design(api):
    c, p = api
    pid = _new(c, p)
    c.put(f'/siteintel/projects/{pid}/brief', json={'program': {'stories': 3, 'living_area_target_m2': 300}})
    c.post(f'/siteintel/projects/{pid}/constraints', json={'verified_by': 'Test', 'basis_de': 'B-Plan', 'max_stories': 2, 'max_building_height_meters': 8, 'grz': 0.3, 'setback_lines_offset_meters': 4})
    d = c.post(f'/siteintel/projects/{pid}/studio').json()['project']['design']
    assert d['storeys'] == 2 and d['ridge_height_m'] <= 8.0 + 1e-6 and d['ridge_height_m'] >= d['eave_height_m']
    res = c.post(f'/projects/{pid}/validate', json={'design': d}).json()
    assert all(r['status'] == 'PASS' for r in res['results'] if r['rule_id'].startswith('VERIFIED')), res


def test_address_is_stored_when_reverse_geocoding_works(api, monkeypatch):
    c, p = api
    monkeypatch.setenv('ARCHAITECT_SITEINTEL_OSM', '1')
    from archaitect.siteintel import geocode
    monkeypatch.setattr(geocode, 'reverse', lambda lat, lon, client=None: {'ort': 'Darmstadt', 'ortsteil': 'Mitte', 'strasse': 'Teststraße', 'hausnummer': '7', 'plz': '64283'})
    pid = _new(c, p)
    card = c.get('/siteintel/projects').json()[0]
    assert card['id'] == pid and card['gemeinde'] == 'Darmstadt' and card['address']['strasse'] == 'Teststraße'


