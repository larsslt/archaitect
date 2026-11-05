'use client';
import {useEffect,useRef,useState} from 'react';
type Doc={id:string;kind:string;url:string;status:string;pages?:number;sha256?:string;incomplete_extraction?:boolean;error?:string};
type Evidence={id:string;document_id:string;page:number;topic:string;quote:string;method:string};
type Plan={id:string;name:string;local_id:string;effective_date?:string;amendment?:string;municipality?:string;parcel_coverage:number;relation:string;documents:Doc[];source:string};
type Candidate={field:'grz'|'gfz';value:number;quote:string;document_id:string;page:number};
type Research={state:string;run?:string;stale_geometry?:boolean;error?:string;plans:Plan[];documents:Doc[];evidence:Evidence[];candidates:Candidate[];evidence_truncated?:boolean;candidates_truncated?:boolean;services?:{status:string;title?:string}[];coverage_note?:string;open_questions?:string[];started_at?:string};
const API=process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const running=(s:string)=>['queued','discovering','documents','running'].includes(s);
export default function PlanningResearch({pid,onCoverage,onCandidate}:{pid:string;onCoverage:(n:number)=>void;onCandidate?:(c:Candidate,source:string)=>void}) {
 const [data,setData]=useState<Research|null>(null),[error,setError]=useState(''),[topic,setTopic]=useState('alle'),[generation,setGeneration]=useState(0);
 const initiated=useRef('');
 const base=`${API}/siteintel/projects/${pid}/planning`;
 async function refresh(){setError('');try{const r=await fetch(base+'/refresh',{method:'POST'});if(!r.ok)throw Error('Recherche konnte nicht gestartet werden.');const j=await r.json();setData({state:j.state,run:j.run,plans:[],documents:[],evidence:[],candidates:[]});setGeneration(g=>g+1);}catch(e){setError(String(e));}}
 useEffect(()=>{let dead=false;let timer:ReturnType<typeof setTimeout>;
  async function poll(){try{const r=await fetch(base,{cache:'no-store'});if(!r.ok)throw Error('Planrecherche nicht erreichbar.');const j:Research=await r.json();if(dead)return;setData(j);onCoverage(j.plans?.length??0);
    if(j.state==='missing' && initiated.current!==pid){initiated.current=pid;await refresh();}
    else if(running(j.state))timer=setTimeout(poll,2000);
   }catch(e){if(!dead)setError(String(e));}}
  poll();return()=>{dead=true;clearTimeout(timer);};
 },[base,pid,generation,onCoverage]);
 const docs=new Map((data?.documents??[]).map(d=>[d.id,d]));
 const evidence=(data?.evidence??[]).filter(e=>topic==='alle'||e.topic===topic);
 return <section style={{border:'1px solid #353538',borderRadius:12,padding:16,margin:'16px 0'}}>
  <h3>Amtliche Pläne & konkrete Festsetzungen</h3>
    <button type="button" className="secondary" disabled={!!data&&running(data.state)} onClick={refresh}>{data&&running(data.state)?'Recherche läuft …':'Amtliche Unterlagen neu abrufen'}</button>
  {data&&running(data.state)&&<p role="status">{data.state==='documents'?'Originaldokumente und lokale Texterkennung werden verarbeitet.':'Kommunale Plankataloge werden räumlich abgefragt.'} Du kannst weiterarbeiten.</p>}
  {(error||data?.error)&&<p role="alert">{error||data?.error}</p>}
  {data?.stale_geometry&&<p role="alert">Flurstücksauswahl geändert. Recherche neu abrufen; alte Fundstellen werden nicht an die Planung übergeben.</p>}
  {data?.state==='done'&&<p>{data.plans.length} Planfassungen · {data.documents.filter(d=>d.status==='TEXT_READY').length} Dokumente mit Text · {data.evidence.length} Fundstellen. Recherche: {data.started_at&&new Date(data.started_at).toLocaleString('de-DE')}</p>}
  {data?.plans?.map(p=><article key={p.id} style={{borderTop:'1px solid #353538',marginTop:8,paddingTop:8,fontSize:13}}>
   <strong>{`${p.name} ${p.amendment||''}`.trim()}</strong>
   <div style={{opacity:.75,fontSize:12}}>{`${p.local_id} · ${p.relation==='related_amendment'&&p.parcel_coverage===0?'außerhalb des Flurstücks':`${(p.parcel_coverage*100).toFixed(0)} % des Flurstücks`}${p.effective_date?` · rechtskräftig ${p.effective_date}`:''}`}</div>
   <div style={{fontSize:12}}><a href={p.source} target="_blank" rel="noreferrer">Katalog</a>{p.documents.filter((d,i,all)=>all.findIndex(x=>x.id===d.id&&x.kind===d.kind)===i).map(d=>{const rec=docs.get(d.id);return <span key={`${d.id}:${d.kind}`}> · <a href={d.url} target="_blank" rel="noreferrer">{d.kind}</a>{rec?.sha256&&<> (<a href={`${base}/files/${data.run}/${d.id}.pdf`} target="_blank" rel="noreferrer">Kopie</a>)</>}</span>;})}</div>
  </article>)}
  {!!data?.candidates?.length&&<details><summary>{`Erkannte Zahlen für die Prüfung (${data.candidates.length})`}</summary><p>Die Zahlen können Beispiele oder Tabellenwerte anderer Teilgebiete sein. Fassung, Teilgebiet und Original prüfen; erst danach die tatsächlich geltenden Werte im Vorschriftenformular selbst eintragen.</p>{data.candidates.map((c,i)=><p key={i}><strong>{c.field.toUpperCase()} {c.value}</strong> · <a href={`${docs.get(c.document_id)?.url}#page=${c.page}`} target="_blank" rel="noreferrer">{`Original Seite ${c.page}`}</a> · „{c.quote}“ · ungeprüfte Fundstelle {onCandidate && !data.stale_geometry && <button className="secondary" onClick={() => onCandidate(c, `${docs.get(c.document_id)?.url ?? c.document_id} · Seite ${c.page} · ${c.quote}`)}>Im Vorschriftenformular prüfen</button>}</p>)}</details>}
  {!!data?.evidence?.length&&<details><summary>{`Zitierbare Fundstellen (${data.evidence.length})`}</summary>
   <label>Thema <select value={topic} onChange={e=>setTopic(e.target.value)}><option value="alle">Alle</option>{['mass','hoehe','dach','bauweise','erschliessung','umwelt','art_nutzung','gestaltung','stellplaetze','wasser','natur','denkmal','immissionsschutz','verfahren'].map(t=><option key={t}>{t}</option>)}</select></label>
   {evidence.length>60&&<p>Es werden die ersten 60 Treffer dieses Filters angezeigt; das Original enthält gegebenenfalls weitere Stellen.</p>}
   {evidence.slice(0,60).map((e,i)=><article key={`${e.id}:${i}`}><p><b>{e.topic}</b> · <a href={`${docs.get(e.document_id)?.url}#page=${e.page}`} target="_blank" rel="noreferrer">Seite {e.page}</a> · {e.method==='LOCAL_OCR_UNVERIFIED'?'OCR, am Original prüfen':'PDF-Text, am Original prüfen'}</p><blockquote style={{whiteSpace:'pre-wrap',fontSize:12}}>{e.quote}</blockquote></article>)}
  </details>}
 </section>;
}
