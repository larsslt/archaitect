"""Local project-level review/evidence endpoints. Source refresh never submits an application."""
from __future__ import annotations
import json
import hashlib
import re
import threading
import uuid
from pathlib import Path
from datetime import date,datetime,timezone
from typing import Literal
from urllib.parse import urlparse
from fastapi import APIRouter,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field,field_validator
from . import hessen_sources,legal_review,planning_api

legal_router=APIRouter()
_LOCK=threading.Lock()
ENGINE_FILES=[*(Path(__file__).parent.parent/'bim').glob('*.py'),Path(__file__).parent.parent/'bim/schema.json',
  *Path(__file__).parent.glob('*.py')]


def engine_signature():
    h=hashlib.sha256()
    for path in sorted(ENGINE_FILES):h.update(path.name.encode());h.update(path.read_bytes())
    return h.hexdigest()



def _R():return planning_api._R()


def inputs(pid):
    R=_R();R._need(pid)
    pack=R.store().pack(pid);meta=R.store().meta(pid);a=R.store().assessment(pid)
    from ..bim.projects import Project
    project=Project('model',root=R.store()._dir(pid)/'bim')
    spec=project.spec() if project.exists() else None
    model_sig=legal_review.digest(spec) if spec else None
    site_sig=planning_api.signature(pack)
    planning=planning_api.read_report(pid)
    source_data=hessen_sources.read_sources()
    basis=legal_review.digest({'pack':pack,'assessment':a.model_dump(mode='json'),'parcel_ids':meta.get('parcel_ids'),
      'planning':{k:planning.get(k) for k in ('run','state','stale_geometry','plans','documents','evidence')},
      'laws':[{k:s.get(k) for k in ('id','sha256','status')} for s in source_data.get('sources',[])],
      'engine':engine_signature(),
      'verified':R.store().verified(pid),'limits':R.store().limits(pid)})
    return meta,a,pack,planning,spec,site_sig,model_sig,basis


def _records(pid):
    path=_R().store()._dir(pid)/'legal-review/evidence.json'
    if not path.exists():return []
    return json.loads(path.read_text())


def report(pid):
    meta,a,pack,planning,spec,site_sig,model_sig,basis=inputs(pid)
    checks=[]
    if spec:
        from .design_api import ctx_for
        from .bim_bridge import spec_to_massing
        from .regs import evaluate
        ctx,_,_=ctx_for(pid);m,notes=spec_to_massing(spec)
        if m:
            result=evaluate(m,ctx);checks=result['results']
    r=legal_review.assess(meta=meta,assessment=a,pack=pack,planning=planning,sources=hessen_sources.read_sources(),spec=spec,checks=checks,
      records=_records(pid),site_signature=site_sig,model_signature=model_sig,inputs_signature=basis)
    r['report_signature']=legal_review.digest({k:v for k,v in r.items() if k!='generated_at'})
    return r


@legal_router.get('/legal/sources')
def sources():
    r=hessen_sources.read_sources()
    return {k:v for k,v in r.items() if k!='municipalities'}|{'municipality_count':len(r.get('municipalities',[]))}


@legal_router.post('/legal/sources/refresh')
def refresh_sources():return {k:v for k,v in hessen_sources.refresh(_R().service().fetcher).items() if k!='municipalities'}


@legal_router.get('/projects/{pid}/legal-review')
def get_review(pid:str):return report(pid)


@legal_router.post('/projects/{pid}/legal-review/run')
def run_review(pid:str):
    r=report(pid);run=uuid.uuid4().hex
    r['run']=run
    planning_api._write(_R().store()._dir(pid)/'legal-review/runs'/f'{run}.json',r)
    return r


@legal_router.get('/projects/{pid}/legal-review/export')
def export_review(pid:str,lang:str='de'):
    rep=report(pid)
    if lang=='en':
        from .i18n_tree import translate_tree
        rep=translate_tree(rep)
    return JSONResponse(rep,headers={'Content-Disposition':f'attachment; filename="archaitect-hessen-pruefbericht-{pid}.json"','Cache-Control':'no-store'})


class Evidence(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True,extra='forbid')
    supersedes:str|None=Field(default=None,pattern='^[a-f0-9]{32}$')
    topic:str
    outcome:Literal['reviewed','conflict','not_applicable']
    checked_by:str=Field(min_length=3,max_length=120)
    document_ref:str=Field(min_length=8,max_length=500)
    source_url:str|None=Field(default=None,max_length=2000)
    locator:str=Field(min_length=3,max_length=300)
    reason:str=Field(min_length=20,max_length=4000)
    valid_until:date
    scope:Literal['parcel','model']='model'
    @field_validator('topic')
    @classmethod
    def topic_known(cls,v):
        if v not in legal_review.TOPIC_IDS:raise ValueError('Unbekannter Prüfbereich.')
        return v
    @field_validator('source_url')
    @classmethod
    def url_safe(cls,v):
        if v:
            u=urlparse(v)
            if u.scheme!='https' or not u.hostname or u.username:raise ValueError('Nur HTTPS-Quellenlinks ohne Zugangsdaten.')
        return v
    @field_validator('valid_until')
    @classmethod
    def date_current(cls,v):
        if v<date.today():raise ValueError('Gültigkeit darf nicht bereits abgelaufen sein.')
        return v


@legal_router.post('/projects/{pid}/legal-review/evidence',status_code=201)
def add_evidence(pid:str,body:Evidence):
    meta,a,pack,planning,spec,site_sig,model_sig,basis=inputs(pid)
    if body.scope=='parcel' and body.topic not in legal_review.PARCEL_TOPICS:raise HTTPException(422,'Dieser Prüfbereich benötigt einen konkreten Gebäudestand.')
    if body.topic in {'plan_scope','grz','gfz','heights','roof','envelope','local_statutes'} and planning.get('state') in ('queued','discovering','documents'):raise HTTPException(409,'Planrecherche läuft noch; Ergebnis vor Dokumentation abwarten.')
    if body.scope=='model' and not model_sig:raise HTTPException(409,'Kein Gebäudestand vorhanden; zuerst Entwurf speichern oder Grundstücksbezug wählen.')
    rec={**body.model_dump(mode='json'),'id':uuid.uuid4().hex,'recorded_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
         'site_signature':site_sig,'model_signature':model_sig if body.scope=='model' else None,'inputs_signature':basis,
         'verification':'ATTRIBUTED_HUMAN_STATEMENT_NOT_AUTOMATICALLY_VERIFIED'}
    with _LOCK:
        records=_records(pid)
        if body.supersedes and not any(r['id']==body.supersedes and r['topic']==body.topic for r in records):raise HTTPException(422,'Ersetzter Nachweis muss zum selben Prüfbereich dieses Projekts gehören.')
        if len(records)>=1000:raise HTTPException(409,'Nachweisarchiv voll; Projektarchiv prüfen.')
        planning_api._write(_R().store()._dir(pid)/'legal-review/evidence.json',[*records,rec])
    return {'record':rec,'review':report(pid)}
