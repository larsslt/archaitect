from fastapi.testclient import TestClient
from archaitect.main import app

client = TestClient(app)
PID='fuerth-schuetzengasse-2-10'

def test_revision_save_conflict_undo_and_report():
    before = client.get(f'/projects/{PID}').json()
    revision = before['design']['version']
    proposed = {**before['design'], 'width_m': 11}
    saved = client.post(f'/projects/{PID}/commands/commit', json={'design':proposed,'expected_version':revision})
    assert saved.status_code == 200
    assert saved.json()['design']['version'] == revision+1
    assert saved.json()['design']['width_m'] == 11
    stale=client.post(f'/projects/{PID}/commands/commit', json={'design':proposed,'expected_version':revision})
    assert stale.status_code == 409
    undo=client.post(f'/projects/{PID}/commands/undo', json={'design':saved.json()['design'],'expected_version':revision+1})
    assert undo.status_code == 200
    assert undo.json()['design']['width_m'] == before['design']['width_m']
    assert undo.json()['design']['version'] == revision+2
    report=client.get(f'/projects/{PID}/report')
    assert report.status_code == 200
    assert report.json()['geometry_status']=='DEMO_ASSUMPTION'
    assert report.json()['results']['overall']=='UNKNOWN'

def test_rejects_wrong_design_identity():
    before=client.get(f'/projects/{PID}').json()
    wrong={**before['design'],'id':'other'}
    r=client.post(f'/projects/{PID}/commands/commit',json={'design':wrong,'expected_version':before['design']['version']})
    assert r.status_code==422
