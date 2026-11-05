"""Phase-4 run API tests: binding, honesty, provenance and explicit save."""
import base64

import pytest
from fastapi.testclient import TestClient

from archaitect.main import app, registry, runs
from test_documents import SYNTHETIC_PAGES, make_pdf

PID = 'fuerth-schuetzengasse-2-10'
client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('ARCHAITECT_DB_PATH', str(tmp_path / 'runs.sqlite'))
    registry.clear()
    runs.clear()
    yield
    registry.clear()
    runs.clear()


def _upload(pages):
    data = make_pdf(pages)
    response = client.post('/documents/intake', json={
        'filename': 'synthetic.pdf',
        'content_base64': base64.b64encode(data).decode('ascii'),
    })
    assert response.status_code == 200, response.text
    return response.json()


def _adopt(doc_id, index=0, rule_id='SYN_MAX_STOREYS'):
    extracted = client.post(f'/documents/{doc_id}/extract').json()
    candidate = extracted['candidates'][index]
    response = client.post('/scenarios/conditions/adopt',
                           json={'evidence': candidate, 'rule_id': rule_id})
    assert response.status_code == 200, response.text
    return response.json()


def _current_design():
    return client.get(f'/projects/{PID}').json()['design']


def test_run_happy_path_binds_versions_and_offers_variants():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    design = _current_design()
    response = client.post(f'/projects/{PID}/runs', json={
        'design': design,
        'goal': {'objective': 'max_gross_floor_area', 'max_variants': 2},
        'rule_ids': ['SYN_MAX_STOREYS'],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['run']['state'] == 'ready'
    assert body['design_version'] == design['version']
    assert body['scenario_version'] == 1
    assert 1 <= len(body['variants']) <= 2
    assert all(v['metrics']['storeys'] <= 2 for v in body['variants'])
    fetched = client.get(f"/projects/{PID}/runs/{body['run']['run_id']}")
    assert fetched.status_code == 200


def test_run_stale_design_rejected_and_nothing_stored():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    design = _current_design()
    design['version'] += 1
    response = client.post(f'/projects/{PID}/runs', json={
        'design': design, 'rule_ids': ['SYN_MAX_STOREYS']})
    assert response.status_code == 409
    assert client.get(f'/projects/{PID}/runs').json() == []


def test_run_unknown_condition_rejected():
    design = _current_design()
    response = client.post(f'/projects/{PID}/runs', json={
        'design': design, 'rule_ids': ['SYN_NOPE']})
    assert response.status_code == 422


def test_run_scenario_drift_rejected_after_document_change():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    registry.documents[doc['document_id']].sha256 = '0' * 64
    design = _current_design()
    response = client.post(f'/projects/{PID}/runs', json={
        'design': design, 'rule_ids': ['SYN_MAX_STOREYS']})
    assert response.status_code == 409
    assert client.get(f'/projects/{PID}/runs').json() == []


def test_run_no_solution_is_honest_not_faked():
    doc = _upload(['Synthetische Seite. Maximale Grundfläche 10 m2.'])
    _adopt(doc['document_id'], rule_id='SYN_MAX_FOOTPRINT')
    design = _current_design()
    response = client.post(f'/projects/{PID}/runs', json={
        'design': design,
        'goal': {'objective': 'balanced', 'max_variants': 3},
        'space': {'widths': [5.0], 'depths': [5.0], 'storeys_options': [1]},
        'rule_ids': ['SYN_MAX_FOOTPRINT'],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['run']['state'] == 'no_solution'
    assert body['variants'] == []


def test_run_changes_neither_design_nor_history():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    before = client.get(f'/projects/{PID}').json()
    history_before = client.get(f'/projects/{PID}/revisions').json()
    client.post(f'/projects/{PID}/runs', json={
        'design': before['design'], 'rule_ids': ['SYN_MAX_STOREYS']})
    assert client.get(f'/projects/{PID}').json() == before
    assert client.get(f'/projects/{PID}/revisions').json() == history_before


def test_run_report_carries_sources_log_and_limits():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    started = client.post(f'/projects/{PID}/runs', json={
        'design': _current_design(), 'rule_ids': ['SYN_MAX_STOREYS']}).json()
    report = client.get(f"/projects/{PID}/runs/{started['run']['run_id']}/report").json()
    assert 'not planning permission' in report['disclaimer']
    assert report['model_calls'] == 0
    assert report['conditions'][0]['evidence_id'].startswith(doc['document_id'])
    assert report['outcome'] == 'ready'
    assert any('searching -> verifying' in entry for entry in report['run_log'])
    assert report['variants'][0]['metrics']['footprint_m2'] > 0


def test_variant_commit_then_stale_variant_rejected():
    doc = _upload(SYNTHETIC_PAGES)
    _adopt(doc['document_id'])
    started = client.post(f'/projects/{PID}/runs', json={
        'design': _current_design(), 'rule_ids': ['SYN_MAX_STOREYS']}).json()
    variant_design = started['variants'][0]['design']
    saved = client.post(f'/projects/{PID}/commands/commit', json={
        'design': variant_design, 'expected_version': variant_design['version']})
    assert saved.status_code == 200, saved.text
    stale = client.post(f'/projects/{PID}/commands/commit', json={
        'design': variant_design, 'expected_version': variant_design['version']})
    assert stale.status_code == 409
