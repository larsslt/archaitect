import json
from pathlib import Path
from shapely.geometry import Point
from archaitect.siteintel import planning,planning_api,wfs
from archaitect.siteintel.fetch import FetchResult
from test_bim_api import api

XML=(Path(__file__).parent/'fixtures_siteintel/planning_sample.xml').read_bytes()
# Official catalogue response retrieved 2026-11-02, GDI-Südhessen/HTK, dl-de/by-2.0.

class Fetcher:
    def get(self,sid,url,params,*args):
        if sid=='planning-catalog':
            return FetchResult(json.dumps({'service':[{'id':'755','title':'Kommunale Boden- und Raumplanung Hochtaunuskreis','accessUrl':'https://www.gdi-inspireumsetzer.de/ows/','license':'dl-de/by-2.0'}]}).encode(),1)
        return FetchResult(b'<schema targetNamespace="http://www.esdi-humboldt.eu/hale/gpkg"/>',1)
    def post_xml(self,sid,url,body,*args):return FetchResult(XML,1)


def test_discovery_retains_amendments_scope_and_original_dates():
    features=wfs.parse_features(XML)
    p=next(f.geometry for f in features if f.get('LOKAL_ID')=='WH100-030').representative_point().buffer(.00005)
    report=planning.discover(Fetcher(),p)
    plans={p['local_id']:p for p in report['plans']}
    assert len(plans)==3
    assert plans['WH100-030']['effective_date']=='2002-03-23'
    assert plans['WH100-030_1']['effective_date']=='2003-04-07'
    assert plans['WH100-030_2']['parcel_coverage']==0
    assert plans['WH100-030_2']['relation']=='related_amendment'
    assert all(p['applicability']=='SCOPE_REVIEW_REQUIRED' for p in plans.values())
    assert all(p['source'].startswith(planning.CATALOG) for p in plans.values())


def test_evidence_preserves_height_reference_and_does_not_infer_limits():
    text='GRZ: 0,35. Firsthöhe 9,50 m über Oberkante Erdgeschoss-Rohboden. GFZ = 0,60. Im Teilgebiet 1c max. 10,50 m über Straßenniveau.'
    evidence,candidates=planning.findings([{'page':3,'method':'LOCAL_OCR_UNVERIFIED','text':text}],'doc')
    assert any('Rohboden' in e['quote'] and e['page']==3 for e in evidence)
    assert {c['field'] for c in candidates}=={'grz','gfz'}
    assert all(c['status']=='REVIEW_REQUIRED' for c in candidates)
    assert not any('height' in c['field'] for c in candidates)


def test_document_download_rejects_arbitrary_hosts_and_credentials():
    assert planning.public_document_url('https://filetransfer.hochtaunuskreis.de/a.pdf')
    assert planning.public_document_url('https://gis.wetterau.de/pdf/plan.pdf')
    for u in ['http://filetransfer.hochtaunuskreis.de/a.pdf','https://127.0.0.1/a.pdf','https://evil.test/a.pdf','https://u:p@filetransfer.hochtaunuskreis.de/a.pdf','https://filetransfer.hochtaunuskreis.de/a.exe','https://filetransfer.hochtaunuskreis.de:bad/a.pdf','https://@gis.wetterau.de/pdf/plan.pdf','https://gis.wetterau.de/private/plan.pdf','https://gis.wetterau.de/pdf/%2e%2e/private/plan.pdf','https://gis.wetterau.de/pdf/x%2fplan.pdf','https://gis.wetterau.de/pdf/plan.pdf?x=1','https://gis.wetterau.de/pdf/plan.pdf#page=2']:
        assert not planning.public_document_url(u)


def test_missing_and_interrupted_jobs_do_not_change_verified_constraints(api):
    c,pid,r=api;base=f'/siteintel/projects/{pid}/planning'
    assert c.get(base).json()['state']=='missing'
    root=r.store()._dir(pid)/'planning'
    planning_api._write(root/'report.json',{'state':'documents','site_signature':planning_api.signature(r.store().pack(pid))})
    assert c.get(base).json()['state']=='interrupted'
    assert r.store().verified(pid) is None
    assert c.get(f'/siteintel/projects/{pid}/context').json()['municipal_planning']['state']=='interrupted'
    assert c.get(base+'/files/bad/abc.pdf').status_code==404


def test_geometry_change_invalidates_planning_evidence(api):
    c,pid,r=api
    planning_api._write(r.store()._dir(pid)/'planning/report.json',{'state':'done','site_signature':'old','evidence':[{'quote':'stale'}]})
    assert c.get(f'/siteintel/projects/{pid}/planning').json()['stale_geometry']
    assert planning_api.context_evidence(pid)['evidence']==[]


def test_missing_source_cannot_become_no_plan_claim():
    class Broken(Fetcher):
        def get(self,*args):return FetchResult(None,1,error='Timeout')
    import pytest
    with pytest.raises(ValueError):planning.discover(Broken(),Point(8,50).buffer(.0001))


def test_pdf_text_cache_is_content_bound_and_reasoning_is_not_a_limit(tmp_path,monkeypatch):
    monkeypatch.setattr(planning,'TEXT_CACHE',tmp_path/'cache')
    calls=[]
    def extract(data,path):
        calls.append(data)
        return [{'page':1,'method':'PDF_TEXT','text':'GRZ = 0,35. Firsthöhe über Rohboden.'}],False
    monkeypatch.setattr(planning,'pages_from_pdf',extract)
    def download(url,path):path.write_bytes(b'%PDF-test-content')
    report={'plans':[{'documents':[{'id':'a','url':'https://example.test/a','kind':'Planblatt'},
                                    {'id':'b','url':'https://example.test/b','kind':'Begründung'}]}]}
    for name in ['first','second']:
        folder=tmp_path/name;folder.mkdir()
        planning.enrich_documents(report,folder,download)
    assert len(calls)==1
    assert len(report['candidates'])==1 and report['candidates'][0]['document_id']=='a'
    assert all(d['sha256'] for d in report['documents'])


def test_generation_context_prefers_latest_intersection_and_never_confirms_height(api):
    _,pid,r=api
    report={'state':'done','site_signature':planning_api.signature(r.store().pack(pid)),
      'plans':[{'local_id':'base','effective_date':'2002-01-01','parcel_coverage':1,'documents':[{'id':'old'}]},
               {'local_id':'changed','effective_date':'2003-01-01','parcel_coverage':1,'documents':[{'id':'new'}]},
               {'local_id':'elsewhere','effective_date':'2004-01-01','parcel_coverage':0,'documents':[{'id':'other'}]}],
      'documents':[{'id':x,'url':'https://example.test/'+x} for x in ['old','new','other']],
      'evidence':[{'id':x,'document_id':x,'page':1,'topic':'hoehe','quote':x+' Firsthöhe 9,50 m über Rohboden'} for x in ['old','new','other']]}
    planning_api._write(r.store()._dir(pid)/'planning/report.json',report)
    brief=planning_api.generation_brief(pid)
    assert brief['verified_constraints'] is None
    assert [e['plan'] for e in brief['municipal_plan_evidence']]==['changed','base']
    assert all(e['status']=='UNVERIFIED_EXTRACT' for e in brief['municipal_plan_evidence'])


def test_refresh_is_idempotent_and_queue_bounded(api,monkeypatch):
    c,pid,_=api
    class Pool:
        def submit(self,*args):pass
    monkeypatch.setattr(planning_api,'_POOL',Pool())
    monkeypatch.setattr(planning_api,'_ACTIVE',{})
    base=f'/siteintel/projects/{pid}/planning/refresh'
    first=c.post(base);second=c.post(base)
    assert first.status_code==second.status_code==202
    assert first.json()['run']==second.json()['run']
    planning_api._ACTIVE.clear();planning_api._ACTIVE.update({str(i):'run' for i in range(4)})
    assert c.post(base).status_code==429


def test_extended_topics_keep_unverified_source_page_and_balance():
    pages=[{'page':n,'method':'PDF_TEXT','text':'GRZ 0,35. ' * 15 + ' Ein Kulturdenkmal und Artenschutz sind zu prüfen.'} for n in range(1,15)]
    evidence,_=planning.findings(pages,'doc')
    assert len(evidence)==100
    assert any(e['topic']=='denkmal' and e['page']>0 for e in evidence)
    assert any(e['topic']=='natur' for e in evidence)
    assert all(e['status']=='UNVERIFIED_EXTRACT' for e in evidence)


def test_document_budget_prioritises_intersecting_recent_plans_and_reports_omissions(tmp_path,monkeypatch):
    monkeypatch.setattr(planning,'TEXT_CACHE',tmp_path/'cache')
    monkeypatch.setattr(planning,'pages_from_pdf',lambda data,path:([{'page':1,'method':'PDF_TEXT','text':'Artenschutz und Kulturdenkmal.'}],False))
    fetched=[]
    def download(url,path):
        fetched.append(url)
        path.write_bytes(b'%PDF-' + url.encode())
    def doc(i):return {'id':str(i),'url':f'https://example.test/{i}.pdf','kind':'Planblatt'}
    report={'plans':[{'parcel_coverage':0,'effective_date':'2025-01-01','documents':[doc(i) for i in range(8)]},
                     {'parcel_coverage':1,'effective_date':'2023-01-01','documents':[doc(8)]}]}
    result=planning.enrich_documents(report,tmp_path,download)
    assert fetched[0].endswith('/8.pdf')
    assert len(fetched)==8
    assert any(d['status']=='LIMIT' for d in result['documents'])


def test_download_rejects_pdf_over_size_limit(tmp_path,monkeypatch):
    import httpx
    import pytest
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def raise_for_status(self):pass
        def iter_bytes(self):
            yield b'%PDF-' + b'x' * 30_000_000
    class Client:
        def __init__(self,**kwargs):assert kwargs['follow_redirects'] is False
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def stream(self,*args):return Response()
    monkeypatch.setattr(httpx,'Client',Client)
    with pytest.raises(ValueError,match='30 MB'):
        planning.download_pdf('https://gis.wetterau.de/pdf/plan.pdf',tmp_path/'plan.pdf')


def test_repeated_terms_near_page_start_have_distinct_evidence_keys():
    evidence,_=planning.findings([{'page':1,'method':'PDF_TEXT','text':'GRZ 0,3 GRZ 0,4 GRZ 0,5'}],'doc')
    hits=[e for e in evidence if e['topic']=='mass']
    assert len(hits)==3 and len({e['id'] for e in hits})==3


def test_ratio_candidates_include_gfz_above_one_without_promoting_to_verified():
    _, candidates = planning.findings([{'page': 1, 'method': 'TEXT', 'text': 'GFZ: 1,80; GRZ: 1,50; GRZ: 0,40'}], 'doc')
    assert [(c['field'], c['value']) for c in candidates] == [('gfz', 1.8), ('grz', 0.4)]
    assert all(c['status'] == 'REVIEW_REQUIRED' for c in candidates)
