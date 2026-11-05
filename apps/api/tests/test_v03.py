import pytest
from fastapi.testclient import TestClient
from archaitect.main import app
from archaitect.commands import DesignCommand, apply_command
from archaitect.fixtures import demo_project
from archaitect.geodata import GeoJSONParcelInput, parse_parcel
from archaitect.models import EvidenceStatus
from archaitect import store

client=TestClient(app)
PID='fuerth-schuetzengasse-2-10'

def test_command_rejects_unexpected_action_fields():
    with pytest.raises(ValueError):
        DesignCommand(action='rotate_building',rotation_deg=10,width_m=15)

def test_command_does_not_mutate_original():
    before=demo_project().design
    after=apply_command(before,DesignCommand(action='resize_building',width_m=13.5))
    assert after.width_m==13.5 and before.width_m==10

def test_preview_action_returns_validation_and_does_not_save():
    project=client.get(f'/projects/{PID}').json()
    result=client.post(f'/projects/{PID}/commands/preview',json={'design':project['design'],'command':{'action':'resize_building','width_m':13}})
    assert result.status_code==200, result.text
    assert result.json()['proposed_design']['width_m']==13
    assert result.json()['validation']['overall']=='UNKNOWN'
    assert client.get(f'/projects/{PID}').json()['design']==project['design']

def test_geodata_import_transforms_wgs84_but_remains_unverified():
    # Tiny polygon near Frankfurt, not a claimed legal parcel.
    item=GeoJSONParcelInput(name='synthetic-test',external_parcel_id='synthetic',source_url='https://example.org',source_crs='EPSG:4326',data={'type':'Polygon','coordinates':[[[8.67,50.1],[8.6701,50.1],[8.6701,50.1001],[8.67,50.1001],[8.67,50.1]]]})
    parcel=parse_parcel(item)
    assert parcel.coordinate_system=='EPSG:32632'
    assert parcel.geometry_status==EvidenceStatus.EXTRACTED
    assert 50<parcel.advertised_area_m2<110

def test_geodata_rejects_self_intersection():
    r=client.post('/geodata/validate',json={'name':'bad','external_parcel_id':'bad','source_url':'https://example.com','source_crs':'EPSG:4326','data':{'type':'Polygon','coordinates':[[[8,50],[9,51],[8,51],[9,50],[8,50]]]}})
    assert r.status_code==422

def test_sqlite_revision_history_persists_connection_reopening(tmp_path,monkeypatch):
    monkeypatch.setenv('ARCHAITECT_DB_PATH',str(tmp_path/'persistent.sqlite3'))
    before=store.read(PID)
    proposed=before.model_copy(update={'design':before.design.model_copy(update={'width_m':12})})
    saved=store.commit(PID,proposed,before.design.version)
    assert saved.design.version==before.design.version+1
    assert store.read(PID).design.width_m==12
    assert store.history(PID)==[1,2]
    assert store.commit(PID,proposed,1) is None
    undone=store.undo(PID,2)
    assert undone.design.version==3
    assert undone.design.width_m==10
    assert store.read(PID).design.width_m==10

def test_cannot_self_certify_cadastral_geometry():
    r=client.post('/geodata/validate',json={
      'name':'synthetic','external_parcel_id':'demo','source_url':'https://example.org',
      'source_crs':'EPSG:4326','verified_against_cadastre':True,
      'data':{'type':'Polygon','coordinates':[[[8.67,50.1],[8.6701,50.1],[8.6701,50.1001],[8.67,50.1001],[8.67,50.1]]]}
    })
    assert r.status_code==200
    assert r.json()['verified'] is False
    assert r.json()['parcel']['geometry_status']=='EXTRACTED'
