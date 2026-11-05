"""Municipal plan evidence. Discovery is automatic; legal interpretation is never auto-verified."""
from __future__ import annotations
import hashlib
import io
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
from xml.etree import ElementTree as ET
from urllib.parse import urlparse, unquote
from shapely.geometry import mapping
from . import sources, wfs

CATALOG = 'https://www.geoportal.hessen.de/spatial-objects/'
NS = 'http://www.esdi-humboldt.eu/hale/gpkg'
DOC_FIELDS = {'PLAN_GES':'Planblatt', 'PLANZEICHN':'Planzeichnung', 'PLANTEXT':'Textliche Festsetzungen', 'BEGRUEND':'Begründung', 'NEBENBEST':'Nebenbestimmungen', 'ZUS_ERKL':'Zusammenfassende Erklärung'}
# Download only official hosts verified for this connector. Other URLs remain visible, never fetched blindly.
DOCUMENT_HOSTS = {'filetransfer.hochtaunuskreis.de', 'gis.wetterau.de'}
OCR = Path(__file__).resolve().parents[4] / '.local/tools/planning-ocr'
TEXT_CACHE = Path(__file__).resolve().parents[4] / '.local/planning-text-cache'
TOPICS = {
 'mass':'GRZ|GFZ|Grundflächenzahl|Geschossflächenzahl|Geschoßflächenzahl',
 'hoehe':'Firsthöhe|Traufhöhe|Wandhöhe|Attika|Rohboden|Straßenniveau|Strassenniveau',
 'dach':'Dachneigung|Dachflächen|Dachform|Flachdach|Pultdach',
 'bauweise':'Bauweise|Baugrenze|Baulinie|Vollgeschoss|Vollgeschoß|Wohnungen',
 'erschliessung':'Stellplätz|Stellplatz|Garagen|Zufahrt',
 'umwelt':'Begrünung|begrünt|Pflanz|Niederschlag|Versicker|Bodenverunreinig|Altlast|Bodenaushub',
 'art_nutzung':'Art der baulichen Nutzung|Allgemeines Wohngebiet|Reines Wohngebiet|Mischgebiet|Dorfgebiet|zulässige Nutzung|unzulässig',
 'gestaltung':'Gestaltungssatzung|Fassaden|Dacheindeckung|Einfriedung|Werbeanlagen|Materialien',
 'stellplaetze':'Stellplatzsatzung|Stellplätz|Garagen|Carport|Fahrradabstell',
 'wasser':'Überschwemmungsgebiet|Hochwasser|Gewässerrandstreifen|Starkregen|Entwässerung|Regenwasser|Versickerung',
 'natur':'Artenschutz|Naturschutz|Baumschutz|Eingriff|Ausgleichsmaßnahme|Pflanzgebot|Bodenschutz',
 'denkmal':'Denkmalschutz|Kulturdenkmal|Bodendenkmal|Archäologie|archäolog',
 'immissionsschutz':'Immissionsschutz|Lärmschutz|Schallschutz|Geruch|Emission',
 'verfahren':'Befreiung|Ausnahme|Veränderungssperre|Genehmigung|Satzung',
}


def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds')


def catalog(fetcher):
    r = fetcher.get('planning-catalog', CATALOG, {'f':'json'}, 86400, 12, lambda b:b.lstrip().startswith(b'{'))
    if r.body is None: raise ValueError('Amtlicher Plankatalog nicht erreichbar: '+str(r.error))
    data = json.loads(r.body)
    services = [s for s in data.get('service', []) if 'Kommunale Boden- und Raumplanung' in s.get('title','')
                and not any(w in s['title'] for w in ('INSPIRE','XPlan')) and re.fullmatch(r'\d+',str(s.get('id','')))
                and urlparse(s.get('accessUrl','')).hostname == 'www.gdi-inspireumsetzer.de']
    return services[:30], {'url':CATALOG,'retrieved_at':stamp(),'cached':r.cached,'stale':r.stale,'error':r.error}


def _source(s):
    return sources.WfsSource('municipal-'+s['id'],s['title'],s['accessUrl'],('ft1:Planung',),{'ft1':s.get('namespace',NS)},'ft1:geometry',
         s.get('license','Lizenz siehe Dienst'),CATALOG+s['id'],s.get('provider','Amtlicher Plankatalog'),ttl_s=86400,timeout_s=6,count=50)


def _plan(f, service, parcel, relation='intersects'):
    p=f.props
    def val(k): return f.get(k)
    geom=f.geometry
    share = geom.intersection(parcel).area/parcel.area if geom is not None and parcel.area else 0
    pid=val('LOKAL_ID') or f.gml_id
    documents=[]
    for field,label in DOC_FIELDS.items():
        url=val(field)
        if url and url.startswith('https://'):
            documents.append({'id':hashlib.sha256(url.encode()).hexdigest()[:16],'kind':label,'url':url})
    return {'id':service['id']+':'+pid,'local_id':pid,'name':val('NAME') or pid,'amendment':val('NAME_A'),
            'type':val('TYP'),'kind':val('ART'),'municipality':val('GEMEINDE'),'district':val('KREIS'),
            'effective_date':val('RECHTSKR'),'data_date':val('AKT_DATENS'),'catalog_date':val('AKT_DATENB'),
            'relation':relation,'parcel_coverage':round(share,5),'geometry':mapping(geom) if geom is not None else None,
            'documents':documents,'source':CATALOG+service['id'],'licence':service.get('license'),
            'applicability':'SCOPE_REVIEW_REQUIRED','status':'OFFICIAL_CATALOG_ENTRY'}


def discover(fetcher, parcel):
    services, cat = catalog(fetcher)
    def query(s):
        try:
            schema=fetcher.get('planning-schema',s['accessUrl'],{'SERVICE':'WFS','VERSION':'2.0.0','REQUEST':'DescribeFeatureType','TYPENAMES':'ft1:Planung'},604800,6)
            if schema.body is None:raise ValueError('Planschema nicht erreichbar.')
            ns=ET.fromstring(schema.body).attrib.get('targetNamespace')
            if not ns:raise ValueError('Kein standardisiertes Planschema.')
            s={**s,'namespace':ns}
            out=sources.query(_source(s),fetcher,parcel)
            return s,out
        except Exception as exc:return s,exc
    plans={};statuses=[];found=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for s,out in pool.map(query,services):
            if isinstance(out,Exception):
                statuses.append({'id':s['id'],'title':s['title'],'status':'UNAVAILABLE','detail':type(out).__name__});continue
            statuses.append({'id':s['id'],'title':s['title'],'geometry_used':out.geometry_used,'possibly_truncated':len(out.features)>=50,**out.status.model_dump()})
            for f in out.features:
                if f.geometry is None or not f.geometry.is_valid or not f.geometry.intersects(parcel):continue
                p=_plan(f,s,parcel);plans[p['id']]=p;found.append((s,p))
    # Related amendments may cover a different part of the original plan. Retrieve, retain their own scope.
    for s,p in found[:12]:
        family=re.sub(r'_\d+$','',p['local_id'])
        if not re.fullmatch(r'[\w-]{2,79}\d',family):continue
        if any(x.get('family_query')==s['id']+family for x in statuses):continue
        xml=(f'<wfs:GetFeature service="WFS" version="2.0.0" count="50" xmlns:wfs="http://www.opengis.net/wfs/2.0" '
             f'xmlns:fes="http://www.opengis.net/fes/2.0" xmlns:ft1="{s.get('namespace',NS)}"><wfs:Query typeNames="ft1:Planung" srsName="urn:ogc:def:crs:EPSG::4326">'
             '<fes:Filter><fes:PropertyIsLike wildCard="*" singleChar="?" escapeChar="!">'
             f'<fes:ValueReference>ft1:LOKAL_ID</fes:ValueReference><fes:Literal>{escape(family)}*</fes:Literal>'
             '</fes:PropertyIsLike></fes:Filter></wfs:Query></wfs:GetFeature>')
        r=fetcher.post_xml('planning-family',s['accessUrl'],xml,86400,6)
        statuses.append({'family_query':s['id']+family,'status':'UNAVAILABLE' if r.body is None else 'QUERIED','stale':r.stale,'detail':r.error})
        if r.body:
            for f in wfs.parse_features(r.body):
                fp=_plan(f,s,parcel,'related_amendment')
                if re.sub(r'_\d+$','',fp['local_id'])==family:plans.setdefault(fp['id'],fp)
    return {'catalog':cat,'services':statuses,'plans':sorted(plans.values(),key=lambda p:(p['effective_date'] or '',p['id'])),
            'coverage_note':'Automatische Abfrage der im Hessen-Katalog gefundenen standardisierten kommunalen GDI-Dienste. Kein vollständiges Register aller Kommunen. Kein Treffer bedeutet nicht: kein Bebauungsplan.'}


def pages_from_pdf(data:bytes, path:Path):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data))
    if reader.is_encrypted:raise ValueError('Verschlüsseltes PDF: manuelle Prüfung erforderlich.')
    pages=[];ocr_pages=0;started=time.monotonic()
    for i,page in enumerate(reader.pages[:40]):
        text=(page.extract_text() or '')[:50000]
        method='PDF_TEXT'
        if len(text.strip())<160 and OCR.is_file() and (ocr_pages>=3 or time.monotonic()-started>180):
            method='OCR_LIMIT'
        elif len(text.strip())<160 and OCR.is_file():
            ocr_pages+=1
            try:
                r=subprocess.run([str(OCR),str(path),str(i+1)],capture_output=True,text=True,timeout=90,check=True)
                text=r.stdout[:50000];method='LOCAL_OCR_UNVERIFIED'
            except (subprocess.SubprocessError,OSError):method='OCR_FAILED'
        elif len(text.strip())<160:method='OCR_REQUIRED'
        pages.append({'page':i+1,'method':method,'text':text})
    return pages,len(reader.pages)>40


def findings(pages, doc_id):
    chunks=[];candidates=[]
    for page in pages:
        text=page['text']
        # Windows keep neighbouring clauses and units; layout/OCR is not a legal interpretation.
        for topic,pat in TOPICS.items():
            matches=list(re.finditer(pat,text,re.I))[:12]
            for match in matches:
                start=max(0,match.start()-100);end=min(len(text),match.end()+650)
                quote=text[start:end].strip()
                cid=hashlib.sha256(f'{doc_id}:{page["page"]}:{match.start()}:{topic}'.encode()).hexdigest()[:16]
                chunks.append({'id':cid,'document_id':doc_id,'page':page['page'],'topic':topic,'quote':quote,'method':page['method'],'status':'UNVERIFIED_EXTRACT'})
        # Only an immediately adjacent ratio is suggested. Tables and inferred heights are deliberately not guessed.
        for m in re.finditer(r'\b(GRZ|GFZ|Grundflächenzahl|Geschossflächenzahl)\s*(?:\([^)]{0,40}\))?\s*[:=]?\s*([0-4][,.]\d{1,2})\b',text,re.I):
            field='grz' if m[1].lower() in ('grz','grundflächenzahl') else 'gfz'
            value=float(m[2].replace(',','.'))
            if not (0 < value <= (1 if field == 'grz' else 4)):continue
            candidates.append({'field':field,'value':value,'document_id':doc_id,'page':page['page'],
                'quote':m[0],'status':'REVIEW_REQUIRED','height_reference':None})
    # Interleave topics so a long document cannot fill the budget before later topics are represented.
    by_topic={topic:[c for c in chunks if c['topic']==topic] for topic in TOPICS}
    balanced=[]
    while len(balanced)<100 and any(by_topic.values()):
        for topic in TOPICS:
            if by_topic[topic] and len(balanced)<100:balanced.append(by_topic[topic].pop(0))
    return balanced,candidates[:30]


def public_document_url(url):
    try:
        u=urlparse(url)
        path=unquote(u.path)
        return (u.scheme=='https' and u.hostname in DOCUMENT_HOSTS and u.port in (None,443) and u.username is None and u.password is None
                and path.lower().endswith('.pdf') and '..' not in path.split('/')
                and (u.hostname!='gis.wetterau.de' or (not u.query and not u.fragment and bool(re.fullmatch(r'/pdf/[A-Za-z0-9_-]+\.pdf',u.path,re.I)))))
    except ValueError:
        return False


def download_pdf(url, destination):
    import httpx
    if not public_document_url(url):raise ValueError('Dokumenthost noch nicht für automatischen Download freigegeben; Original-Link nutzbar.')
    # Redirects are not followed: an official catalogue must not turn into an arbitrary network fetch.
    try:
        with httpx.Client(follow_redirects=False,timeout=20) as client:
            with client.stream('GET',url) as r:
                r.raise_for_status();size=0
                with destination.open('wb') as f:
                    for chunk in r.iter_bytes():
                        size+=len(chunk)
                        if size>30_000_000:raise ValueError('PDF größer als 30 MB: manuell prüfen.')
                        f.write(chunk)
    except httpx.ConnectError as exc:
        if sys.platform!='darwin' or 'CERTIFICATE_VERIFY_FAILED' not in str(exc):raise
        # macOS curl uses the system trust chain; certificate verification remains enabled.
        subprocess.run(['/usr/bin/curl','--fail','--silent','--show-error','--proto','=https','--retry','1','--retry-delay','1','--retry-all-errors','--max-time','45',
          '--max-filesize','30000000','--output',str(destination),url],check=True,timeout=95,capture_output=True)
    if destination.stat().st_size>30_000_000:raise ValueError('PDF größer als 30 MB.')
    destination.chmod(0o600)
    if destination.read_bytes()[:5]!=b'%PDF-':raise ValueError('Quelle lieferte kein PDF.')


def enrich_documents(report, folder, download=download_pdf, on_progress=None):
    docs={};all_chunks=[];all_candidates=[];document_evidence_limit=False;document_candidate_limit=False;download_attempts=0
    ordered_plans=sorted(report['plans'],key=lambda p:(bool((p.get('parcel_coverage') or 0)>0),p.get('effective_date') or ''),reverse=True)
    for plan in ordered_plans:
        for d in sorted(plan['documents'],key=lambda d: 0 if d['kind'] in ('Planblatt','Textliche Festsetzungen','Planzeichnung') else 1):
            if d['id'] in docs:continue
            rec={**d,'status':'PENDING','retrieved_at':stamp()};docs[d['id']]=rec
            if download is download_pdf and not public_document_url(d['url']):
                rec.update(status='UNAVAILABLE',error='Dokumenthost noch nicht für automatischen Download freigegeben; Original-Link nutzbar.')
                continue
            if download_attempts>=8:rec.update(status='LIMIT',error='Maximal acht Dokumente pro Abruf.');continue
            download_attempts+=1
            path=folder/(d['id']+'.pdf')
            try:
                download(d['url'],path)
                data=path.read_bytes();rec['sha256']=hashlib.sha256(data).hexdigest();rec['bytes']=len(data)
                cache=TEXT_CACHE/(rec['sha256']+'-ocr1.json')
                try:
                    cached=json.loads(cache.read_text());pages=cached['pages'];truncated=cached['truncated']
                except (OSError,ValueError,KeyError):
                    pages,truncated=pages_from_pdf(data,path)
                    if pages and all(p['text'].strip() and p['method'] in ('PDF_TEXT','LOCAL_OCR_UNVERIFIED') for p in pages):
                        TEXT_CACHE.mkdir(parents=True,exist_ok=True,mode=0o700)
                        import uuid
                        tmp=cache.with_suffix('.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps({'pages':pages,'truncated':truncated},ensure_ascii=False));tmp.chmod(0o600);tmp.replace(cache)
                rec['pages']=len(pages);rec['truncated']=truncated
                rec['incomplete_extraction']=truncated or any(p['method'] in ('OCR_LIMIT','OCR_FAILED','OCR_REQUIRED') for p in pages)
                rec['status']='TEXT_READY' if any(p['text'].strip() for p in pages) else 'OCR_REQUIRED'
                rec['extraction_methods']=sorted({p['method'] for p in pages})
                (folder/(d['id']+'.text.json')).write_text(json.dumps(pages,ensure_ascii=False),encoding='utf-8')
                (folder/(d['id']+'.text.json')).chmod(0o600)
                chunks,candidates=findings(pages,d['id']);all_chunks+=chunks
                document_evidence_limit=document_evidence_limit or len(chunks)>=100
                document_candidate_limit=document_candidate_limit or len(candidates)>=30
                if d['kind'] in ('Planblatt','Textliche Festsetzungen'):all_candidates+=candidates
            except Exception as exc:
                message='Originaldokument nicht abrufbar; Quelle prüfen oder Recherche erneut starten.' if isinstance(exc,(subprocess.SubprocessError,OSError)) else str(exc)[:240]
                if rec.get('sha256') and path.exists():
                    rec.update(status='ORIGINAL_ONLY',error=message,diagnostic=type(exc).__name__)
                else:
                    rec.pop('sha256',None);rec.update(status='UNAVAILABLE',error=message,diagnostic=type(exc).__name__);path.unlink(missing_ok=True)
            report.update(documents=list(docs.values()),evidence=all_chunks[:300],candidates=all_candidates[:80],evidence_truncated=document_evidence_limit or len(all_chunks)>300,candidates_truncated=document_candidate_limit or len(all_candidates)>80,extraction_bounded=True)
            if on_progress:on_progress()
    report.update(documents=list(docs.values()),evidence=all_chunks[:300],candidates=all_candidates[:80],evidence_truncated=document_evidence_limit or len(all_chunks)>300,candidates_truncated=document_candidate_limit or len(all_candidates)>80,extraction_bounded=True)
    return report
