import json
from datetime import date,timedelta,datetime,timezone
from pathlib import Path
import pytest
from archaitect.siteintel import legal_api,legal_review,hessen_sources,planning_api
from archaitect.siteintel.fetch import FetchResult
from test_bim_api import api,put,house


@pytest.fixture(autouse=True)
def isolated_sources(tmp_path,monkeypatch):monkeypatch.setattr(hessen_sources,'SNAPSHOT',tmp_path/'sources.json')


def payload(**kw):
    return {'topic':'easements','outcome':'reviewed','checked_by':'Test Fachplaner','document_ref':'Testauskunft Aktenzeichen 123',
      'locator':'Seite 1','reason':'Reproduzierbare Testaussage, keine reale Rechtsauskunft.',
      'valid_until':(date.today()+timedelta(days=10)).isoformat(),'scope':'parcel',**kw}


def test_no_model_produces_full_gap_report_not_approval(api):
    c,pid,_=api;r=c.get(f'/siteintel/projects/{pid}/legal-review')
    assert r.status_code==200
    d=r.json();assert d['overall']=='REVIEW_INCOMPLETE'
    assert d['summary']['topics']==27 and d['summary']['missing']==27
    assert not d['legally_complete'] and not d['permit_issued']
    assert d['jurisdiction']=='Hessen' and d['calculated_checks']==[]


def test_record_is_attributed_and_invalidated_on_plan_content_change(api):
    c,pid,r=api;path=r.store()._dir(pid)/'planning/report.json'
    base={'state':'done','run':'a'*32,'site_signature':planning_api.signature(r.store().pack(pid)),'documents':[{'id':'doc','sha256':'one'}]}
    planning_api._write(path,base)
    added=c.post(f'/siteintel/projects/{pid}/legal-review/evidence',json=payload())
    assert added.status_code==201,added.text
    assert added.json()['review']['summary']['documented']==1
    assert 'NOT_AUTOMATICALLY_VERIFIED' in added.json()['record']['verification']
    planning_api._write(path,{**base,'documents':[{'id':'doc','sha256':'two'}]})
    d=c.get(f'/siteintel/projects/{pid}/legal-review').json()
    assert d['summary']['documented']==0 and d['invalidated_evidence']
    assert not d['legally_complete']


def test_model_dependent_topic_requires_model_and_model_scope(api):
    c,pid,_=api;base=f'/siteintel/projects/{pid}/legal-review/evidence'
    assert c.post(base,json=payload(topic='fire')).status_code==422
    assert c.post(base,json=payload(topic='fire',scope='model')).status_code==409
    put(c,pid)
    assert c.post(base,json=payload(topic='fire',scope='model')).status_code==201
    d=c.get(f'/siteintel/projects/{pid}/legal-review').json()
    assert any(x['id']=='fire' and x['status']=='DOCUMENTED' for x in d['review_topics'])
    spec=house();spec['name']='Anderer Gebäudestand';put(c,pid,spec)
    d=c.get(f'/siteintel/projects/{pid}/legal-review').json()
    assert any(x['id']=='fire' and x['status']=='MISSING' for x in d['review_topics'])


def test_pending_plan_does_not_accept_applicability_attestation(api):
    c,pid,r=api
    planning_api._write(r.store()._dir(pid)/'planning/report.json',{'state':'documents','site_signature':planning_api.signature(r.store().pack(pid))})
    # Real active ingest; read_report legitimately treats abandoned runs as interrupted.
    planning_api._ACTIVE[pid]='run'
    try:assert c.post(f'/siteintel/projects/{pid}/legal-review/evidence',json=payload(topic='plan_scope')).status_code==409
    finally:planning_api._ACTIVE.pop(pid,None)


def test_conflict_can_be_superseded_without_erasing_history(api):
    c,pid,_=api;base=f'/siteintel/projects/{pid}/legal-review/evidence'
    first=c.post(base,json=payload(outcome='conflict')).json()
    assert first['review']['overall']=='CONFLICTS_FOUND'
    second=c.post(base,json=payload(supersedes=first['record']['id']))
    assert second.status_code==201,second.text
    d=second.json()['review'];assert d['summary']['evidence_conflicts']==0
    assert d['summary']['documented']==1 and len(d['invalidated_evidence'])==1
    assert c.post(base,json=payload(topic='contamination',supersedes=first['record']['id'])).status_code==422


def test_evidence_input_bounds_and_export(api):
    c,pid,_=api;base=f'/siteintel/projects/{pid}/legal-review'
    for p in [payload(source_url='javascript:alert(1)'),payload(checked_by='   '),payload(topic='fake'),payload(valid_until='2000-01-01')]:
        assert c.post(base+'/evidence',json=p).status_code==422
    r=c.get(base+'/export');assert r.status_code==200 and 'attachment' in r.headers['content-disposition']
    assert c.post(base+'/run').json()['run']


def test_old_sources_expire_and_law_revision_invalidates_evidence(api):
    c,pid,_=api
    stamp=datetime.now(timezone.utc).isoformat()
    hessen_sources.SNAPSHOT.write_text(json.dumps({'state':'parsed_directory','retrieved_at':stamp,'sources':[{'id':'hbo','sha256':'v1','status':'RETRIEVED'}]}))
    c.post(f'/siteintel/projects/{pid}/legal-review/evidence',json=payload())
    hessen_sources.SNAPSHOT.write_text(json.dumps({'state':'parsed_directory','retrieved_at':'2020-01-01T00:00:00+00:00','sources':[{'id':'hbo','sha256':'v1','status':'RETRIEVED'}]}))
    assert hessen_sources.read_sources()['sources'][0]['status']=='STALE'
    d=c.get(f'/siteintel/projects/{pid}/legal-review').json()
    assert d['summary']['documented']==0 and d['directory_state']=='stale'


def test_engine_signature_tracks_rule_file_changes(tmp_path,monkeypatch):
    p=tmp_path/'regs.py';p.write_text('one')
    monkeypatch.setattr(legal_api,'ENGINE_FILES',[p]);a=legal_api.engine_signature();p.write_text('two')
    assert a!=legal_api.engine_signature()


def test_directory_parser_separates_valid_plans_and_procedure():
    p=hessen_sources.Municipalities();p.feed('<h3><button>Teststadt</button></h3><a href="https://test.example/plans" title="Zum rechtskräftigen Bebauungsplan">Pläne</a><a href="https://test.example/procedure" title="Zum Bebauungsplan im Verfahren">Verfahren</a>')
    assert [x['kind'] for x in p.entries['Teststadt']['links']]==['binding_plans','procedure']
    snapshot={'municipalities':[p.entries['Teststadt']]}
    assert hessen_sources.municipality_entry('Teststadt',snapshot)
    assert hessen_sources.municipality_entry('Testst',snapshot) is None
    assert hessen_sources.html_text(b'Geb\xe4udeenergiegesetz')=='Gebäudeenergiegesetz'


def test_empty_changed_directory_layout_is_not_success():
    class Fetcher:
        def get(self,sid,url,*args):
            if url==hessen_sources.INDEX:
                links=''.join(f'<a href="/bebauungsplaene-in-hessen-a-z/{x}">page</a>' for x in ['a-c','d-f','g-i','j-l','m-o','p-r','s-u','v-z'])
                return FetchResult(('<html>'+links+'</html>').encode(),1)
            return FetchResult(b'<html><h1>Unexpected layout</h1>'+b'x'*150+b'</html>',1)
    r=hessen_sources.refresh(Fetcher())
    assert r['state']=='partial' and not r['municipalities']
    assert all(s['status']=='INVALID_CONTENT' for s in r['sources'])


def test_even_all_human_statements_are_not_an_automatic_legal_approval(api):
    c,pid,r=api
    put(c,pid)
    meta,a,pack,planning,spec,site,model,basis=legal_api.inputs(pid)
    records=[{**payload(topic=t[0]),'id':str(i),'site_signature':site,'model_signature':model,'inputs_signature':basis,'scope':'model'} for i,t in enumerate(legal_review.TOPICS)]
    review=legal_review.assess(meta=meta,assessment=a,pack=pack,planning=planning,sources={},spec=spec,checks=[],records=records,site_signature=site,model_signature=model,inputs_signature=basis)
    assert review['summary']['documented']==27 and review['overall']=='EXPERT_REVIEW_DOCUMENTED'
    assert not review['legally_complete'] and not review['automatic_legal_approval'] and not review['permit_issued']


def test_geo_details_include_missing_categories_and_failed_service(api):
    from archaitect.siteintel.models import ProtectionHit, DataStatus
    _,pid,_=api
    meta,a,pack,planning,spec,site,model,basis=legal_api.inputs(pid)
    a.protections=[ProtectionHit(kind='biosphaere',label_de='Biosphärenreservat',name='Testgebiet'),
                   ProtectionHit(kind='naturmonument',label_de='Naturmonument')]
    a.data_status=[DataStatus(source_id='schutzgebiete',status='PARTIAL',detail='Ein Teil der Ebenen nicht verfügbar')]
    report=legal_review.assess(meta=meta,assessment=a,pack=pack,planning=planning,sources={},spec=spec,checks=[],records=[],site_signature=site,model_signature=model,inputs_signature=basis)
    nature=next(t for t in report['review_topics'] if t['id']=='nature')
    assert {h['kind'] for h in nature['geodata']['hits']}=={'biosphaere','naturmonument'}
    assert nature['geodata']['sources'][0]['status']=='PARTIAL'
    assert nature['status']=='MISSING'
    flood=next(t for t in report['review_topics'] if t['id']=='flood')
    assert flood['geodata']['sources'][0]['status']=='NOT_CONNECTED'
    assert flood['status']=='MISSING'
