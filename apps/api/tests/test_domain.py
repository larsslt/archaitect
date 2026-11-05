import pytest
from fastapi.testclient import TestClient
from archaitect.fixtures import demo_project
from archaitect.geometry import footprint_polygon, parcel_polygon
from archaitect.constraints import validate
from archaitect.models import EvidenceStatus, Status
from archaitect.main import app

def test_area_matches_advertised_only_as_synthetic_fixture():
    project=demo_project()
    assert parcel_polygon(project.parcel).area == pytest.approx(422)
    assert project.parcel.geometry_status == EvidenceStatus.DEMO_ASSUMPTION

def test_rotation_preserves_footprint_area():
    p=demo_project()
    for angle in (0,15,45,90,180):
        assert footprint_polygon(p.design.model_copy(update={'rotation_deg':angle})).area == pytest.approx(90)

def test_not_certified_from_demo_rules():
    result=validate(demo_project())
    assert result.overall == Status.UNKNOWN
    assert all(r.status == Status.UNKNOWN for r in result.results)

def test_verified_oversize_constraint_fails():
    p=demo_project()
    rule=p.rules[1].model_copy(update={'value':50,'review_status':EvidenceStatus.VERIFIED})
    p.rules[1]=rule
    result=validate(p)
    assert any(r.rule_id == 'DEMO_MAX_FOOTPRINT' and r.status == Status.FAIL for r in result.results)

def test_fixture_boundary_violation_is_unknown_not_legal_failure():
    p=demo_project()
    p.design.center_x=30
    results=validate(p).results
    assert next(r for r in results if r.rule_id == 'PARCEL_CONTAINMENT').status==Status.UNKNOWN

def test_health():
    client=TestClient(app)
    assert client.get('/health').json()['status']=='ok'

def test_preview_does_not_mutate_project():
    client=TestClient(app)
    project=client.get('/projects/fuerth-schuetzengasse-2-10').json()
    modified={**project['design'],'width_m':12}
    response=client.post('/projects/fuerth-schuetzengasse-2-10/validate',json={'design':modified})
    assert response.status_code==200
    assert response.json()['footprint_m2']==108
    assert client.get('/projects/fuerth-schuetzengasse-2-10').json()['design']['width_m']==10

def test_commit_rejects_stale_revision():
    client=TestClient(app)
    project=client.get('/projects/fuerth-schuetzengasse-2-10').json()
    r=client.post('/projects/fuerth-schuetzengasse-2-10/commands/commit',json={'design':project['design'],'expected_version':0})
    assert r.status_code == 422
