"""Official Hessen-wide municipality directory and versioned legal source receipts.

A directory entry is a route to documents, never proof of applicability or machine-readable coverage.
"""
from __future__ import annotations
import hashlib
import json
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from urllib.parse import urljoin,urlparse

ROOT=Path(__file__).resolve().parents[4]
SNAPSHOT=ROOT/'.local/hessen-legal-sources.json'
INDEX='https://bauleitplanung.hessen.de/bebauungsplaene-in-hessen-a-z'
SOURCE_DEFS={
 'hbo_primary':{'title':'HBO-Primärtext, Broschüre Oktober 2025/Korrektur April 2026','url':'https://wirtschaft.hessen.de/sites/wirtschaft.hessen.de/files/2026-04/hbo_broschuere_stand_oktober_2025-baupaket_i.pdf'},
 'hbo':{'title':'Hessische Bauordnung – amtlicher Stand und Änderungen','url':'https://wirtschaft.hessen.de/wohnen-bauen/baurecht-und-bautechnik/hessische-bauordnung-hbo'},
 'bauvorlagen':{'title':'Bauvorlagenerlass und Nachweise','url':'https://wirtschaft.hessen.de/wohnen-bauen/bauvorschriften/dokumente-und-vordrucke'},
 'bautechnik':{'title':'Technische Baubestimmungen','url':'https://wirtschaft.hessen.de/Technische-Baubestimmungen-Planung-Bemessung-und-Ausfuehrungsregeln-baulicher-Anlagen'},
 'baubehoerden':{'title':'Baurecht, Baunebenrecht und Bauaufsichtsbehörden','url':'https://wirtschaft.hessen.de/wohnen-bauen/baurecht-und-bautechnik'},
 'baugb':{'title':'Baugesetzbuch','url':'https://www.gesetze-im-internet.de/bbaug/'},
 'baunvo':{'title':'Baunutzungsverordnung','url':'https://www.gesetze-im-internet.de/baunvo/'},
 'geg':{'title':'Energierecht für Gebäude (GModG; früher GEG)','url':'https://www.gesetze-im-internet.de/geg/'},
 'bnatschg':{'title':'Bundesnaturschutzgesetz','url':'https://www.gesetze-im-internet.de/bnatschg_2009/'},
 'whg':{'title':'Wasserhaushaltsgesetz','url':'https://www.gesetze-im-internet.de/whg_2009/'},
}
_LOCK=threading.Lock()


def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')


def html_text(body):
    try:return body.decode('utf-8')
    except UnicodeDecodeError:return body.decode('iso-8859-1')



def normalise(value):
    value=unicodedata.normalize('NFKD',value.casefold().replace('ß','ss'))
    value=''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]','',value)


def safe_link(url):
    try:
        u=urlparse(url)
        return u.scheme in ('https','http') and bool(u.hostname) and not u.username and u.port in (None,80,443)
    except ValueError:return False


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.anchor=None;self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.anchor=dict(attrs);self.text=[]
    def handle_data(self,data):
        if self.anchor is not None:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor is not None:
            self.links.append({**self.anchor,'text':' '.join(' '.join(self.text).split())});self.anchor=None


class Municipalities(Links):
    def __init__(self):super().__init__();self.in_heading=False;self.heading=[];self.current=None;self.entries={}
    def handle_starttag(self,tag,attrs):
        if tag=='h3':self.in_heading=True;self.heading=[]
        super().handle_starttag(tag,attrs)
    def handle_data(self,data):
        if self.in_heading:self.heading.append(data)
        super().handle_data(data)
    def handle_endtag(self,tag):
        if tag=='h3':self.in_heading=False;self.current=' '.join(' '.join(self.heading).split())
        if tag=='a' and self.anchor is not None and self.current:
            label=self.anchor.get('title') or ' '.join(self.text)
            href=self.anchor.get('href','')
            if safe_link(href) and any(x in label for x in ('rechtskräftigen Bebauungsplan','Bebauungsplan im Verfahren','Homepage der Gemeinde','Geoportal Hessen')):
                entry=self.entries.setdefault(self.current,{'name':self.current,'links':[]})
                entry['links'].append({'title':label,'url':href,'kind':'binding_plans' if 'rechtskräftig' in label else 'procedure' if 'im Verfahren' in label else 'municipality' if 'Homepage' in label else 'geoportal'})
        super().handle_endtag(tag)


def read_sources():
    try:
        report=json.loads(SNAPSHOT.read_text())
        stamp=datetime.fromisoformat(report['retrieved_at'])
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-stamp).total_seconds()
        report['age_hours']=round(max(age,0)/3600,1);report['max_age_hours']=24
        if age>86400 or age< -300:
            report['state']='stale'
            for source in [*report.get('sources',[]),*report.get('directory_status',[])]:
                if source.get('status')=='RETRIEVED':source['status']='STALE'
        return report
    except (OSError,ValueError,KeyError):return {'state':'missing','municipalities':[],'sources':[],'directory_status':[]}


def municipality_entry(name,snapshot):
    key=normalise(name or '')
    # Deliberately no fuzzy assignment: Neustadt, Hofheim etc. can be ambiguous.
    matches=[x for x in snapshot.get('municipalities',[]) if normalise(x['name'])==key]
    return matches[0] if len(matches)==1 else None


def refresh(fetcher):
    if not _LOCK.acquire(blocking=False):return {**read_sources(),'refresh_running':True}
    try:
        old=read_sources();previous={s['id']:s for s in old.get('sources',[])}
        def fetch(item):
            key,url=item
            r=fetcher.get('hessen-legal-'+key,url,{},86400,10,lambda b:len(b)>100)
            rec={'id':key,'url':url,'retrieved_at':now(),'status':'UNAVAILABLE' if r.body is None else 'STALE' if r.stale else 'RETRIEVED',
                 'error':r.error,'cached':r.cached}
            if r.body:rec.update(sha256=hashlib.sha256(r.body).hexdigest(),bytes=len(r.body),changed_since_previous=bool(previous.get(key,{}).get('sha256') and previous[key]['sha256']!=hashlib.sha256(r.body).hexdigest()))
            if r.body and not key.startswith('directory'):
                content=normalise(unescape(html_text(r.body)))
                markers={'hbo':['hessischebauordnung'],'bauvorlagen':['bauvorlagen'],'bautechnik':['technischebaubestimmungen'],
                  'baubehoerden':['baurecht'],'baugb':['baugesetzbuch'],'baunvo':['baunutzungsverordnung'],'geg':['gebaudeenergiegesetz','gebaudemodernisierungsgesetz'],
                  'bnatschg':['bundesnaturschutzgesetz'],'whg':['wasserhaushaltsgesetz']}
                valid=r.body.startswith(b'%PDF-') if key=='hbo_primary' else any(m in content for m in markers.get(key,[]))
                rec['content_check']='PLAUSIBLE_SOURCE' if valid else 'UNEXPECTED_CONTENT'
                if not valid:rec['status']='INVALID_CONTENT'
                if key=='hbo_primary':rec['matches_reviewed_rule_source']=rec.get('sha256')=='32b2708ac7fb2f1a433a04e1f0c54bd76e28f2790ed74565363be668eea1e437'

            return rec,r.body
        index,body=fetch(('directory',INDEX));parser=Links();parser.feed(html_text(body or b''))
        urls=sorted({urljoin(INDEX,l.get('href','')) for l in parser.links if re.fullmatch(r'/bebauungsplaene-in-hessen(?:-a-z)?/(?:a-c|d-f|g-i|j-l|m-o|p-r|s-u|v-z)',l.get('href',''))})
        directory=[];entries=[];records=[]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for rec,data in pool.map(fetch,[(f'directory-{i}',u) for i,u in enumerate(urls)]+[(k,v['url']) for k,v in SOURCE_DEFS.items()]):
                if rec['id'].startswith('directory-'):
                    directory.append(rec)
                    if data:
                        p=Municipalities();p.feed(html_text(data))
                        rec['parsed_municipalities']=len(p.entries)
                        rec['content_check']='PARSED' if len(p.entries)>=10 else 'UNEXPECTED_LAYOUT'
                        if len(p.entries)<10:rec['status']='INVALID_CONTENT'
                        for e in p.entries.values():entries.append({**e,'source':rec['url'],'retrieved_at':rec['retrieved_at']})
                else:records.append({**rec,'title':SOURCE_DEFS[rec['id']]['title'],'meaning':'Quellenabruf, keine automatische Rechtsstands- oder Anwendbarkeitsbestätigung.'})
        report={'schema':'archaitect.hessen-legal-sources/1','state':'parsed_directory' if len(urls)==8 and len({e['name'] for e in entries})>=350 and all(x['status']=='RETRIEVED' and x.get('parsed_municipalities',0)>=10 for x in directory) else 'partial',
                'retrieved_at':now(),'index':index,'directory_status':directory,'municipalities':list({e['name']:e for e in entries}.values()),'sources':records,
                'directory_note':'Zentrales Landesverzeichnis der kommunalen Zugänge. Kein Nachweis aller Pläne, Satzungen, Änderungen oder vollständig automatisierter Dokumentauswertung.'}
        SNAPSHOT.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        import uuid
        tmp=SNAPSHOT.with_name(SNAPSHOT.name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(report,ensure_ascii=False));tmp.chmod(0o600);tmp.replace(SNAPSHOT)
        return report
    finally:_LOCK.release()
