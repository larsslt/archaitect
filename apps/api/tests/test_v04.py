import json
import pytest
from fastapi.testclient import TestClient
from archaitect.main import app
from archaitect.agent import AgentRequest, AgentUnavailable, AgentInvalidOutput, propose_meta, _parse_message
from archaitect.fixtures import demo_project
from archaitect import store

PID='fuerth-schuetzengasse-2-10'
client=TestClient(app)

def test_model_command_parsing_is_allowlisted():
    assert _parse_message('{"command":{"action":"rotate_building","rotation_deg":45}}').rotation_deg == 45
    for output in ('{"command":null}', '{"command":{"action":"delete_project"}}',
                   '{"command":{"action":"set_storeys","storeys":2,"width_m":10}}',
                   'Sure! Here is your house.'):
        with pytest.raises(AgentInvalidOutput):
            _parse_message(output)

def test_no_api_key_is_explicit_and_free(monkeypatch):
    monkeypatch.delenv('MODEL_API_KEY', raising=False)
    with pytest.raises(AgentUnavailable, match='missing'):
        propose_meta(AgentRequest(instruction='Rotate to 20 degrees', design=demo_project().design))

def test_agent_preview_does_not_commit(monkeypatch, tmp_path):
    monkeypatch.setenv('ARCHAITECT_DB_PATH', str(tmp_path/'agent.sqlite'))
    class Proposal:
        provider='meta'
        model='muse-spark-1.3'
        input_tokens=123
        output_tokens=23
        from archaitect.commands import DesignCommand
        command=DesignCommand(action='resize_building', width_m=12)
    monkeypatch.setattr('archaitect.main.propose_meta', lambda _:Proposal())
    current=client.get(f'/projects/{PID}').json()
    r=client.post(f'/projects/{PID}/agent/preview',json={'instruction':'Please widen the house','design':current['design']})
    assert r.status_code==200, r.text
    assert r.json()['proposed_design']['width_m']==12
    assert r.json()['validation']['overall']=='UNKNOWN'
    assert r.json()['usage']=={'input_tokens':123,'output_tokens':23}
    assert client.get(f'/projects/{PID}').json()==current

def test_agent_rejects_stale_design_without_calling_model(monkeypatch,tmp_path):
    monkeypatch.setenv('ARCHAITECT_DB_PATH',str(tmp_path/'stale.sqlite'))
    current=client.get(f'/projects/{PID}').json()
    current['design']['version']=5
    monkeypatch.setattr('archaitect.main.propose_meta',lambda _:pytest.fail('should not call Meta'))
    r=client.post(f'/projects/{PID}/agent/preview',json={'instruction':'Make wider','design':current['design']})
    assert r.status_code==409

def test_agent_unavailable_returns_503_without_saving(monkeypatch,tmp_path):
    monkeypatch.setenv('ARCHAITECT_DB_PATH',str(tmp_path/'unavailable.sqlite'))
    monkeypatch.setattr('archaitect.main.propose_meta',lambda _: (_ for _ in ()).throw(AgentUnavailable('Meta down')))
    original=client.get(f'/projects/{PID}').json()
    r=client.post(f'/projects/{PID}/agent/preview',json={'instruction':'Make wider','design':original['design']})
    assert r.status_code==503
    assert client.get(f'/projects/{PID}').json()==original

def test_instruction_length_bounded():
    with pytest.raises(ValueError):
        AgentRequest(instruction='a'*481,design=demo_project().design)
