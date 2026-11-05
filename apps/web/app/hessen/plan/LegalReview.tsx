'use client';
import {useCallback,useEffect,useState} from 'react';
const API=process.env.NEXT_PUBLIC_API_URL||'http://127.0.0.1:8000';
type Evidence={id:string;checked_by:string;document_ref:string;reason:string;valid_until:string;outcome:string};
type GeoData={hits:{kind:string;label_de:string;name:string|null;on_parcel:boolean;distance_m:number|null;share:number|null}[];sources:{id:string;status:string;detail:string|null;cached:boolean;reference:{name:string;retrieved:string|null}|null}[];scope_notice:string};
type Topic={id:string;title:string;status:string;finding:string;required_evidence:string;source:{title?:string;url?:string;status?:string};evidence:Evidence[];geodata:GeoData|null};
type Review={overall:string;model_present:boolean;municipality:string|null;municipal_entry:{name:string;source:string;links:{title:string;url:string}[]}|null;directory_entries:number;directory_state:string;generated_at:string;review_topics:Topic[];invalidated_evidence:(Evidence&{invalid_reason:string})[];summary:{topics:number;missing:number;documented:number;calculation_conflicts:number;evidence_conflicts:number};calculated_checks:{id:string;label_de:string;status:string;message_de:string;source_de?:string;meaning:string}[];limitations:string[];plan_data:{planfassungen:number;dokumente:number;fundstellen:number};source_receipts:{id:string;title:string;url:string;status:string;retrieved_at?:string;changed_since_previous?:boolean;matches_reviewed_rule_source?:boolean}[]};
const LABELS:Record<string,string>={MISSING:'Nachweis offen',DOCUMENTED:'Fachliche Aussage dokumentiert',CONFLICT:'Dokumentierter Widerspruch',REVIEW_INCOMPLETE:'Prüfung unvollständig',CONFLICTS_FOUND:'Widersprüche festgestellt',EXPERT_REVIEW_DOCUMENTED:'Fachprüfung dokumentiert',OUT_OF_SCOPE:'Außerhalb des Prüfumfangs'};
const PARCEL=['easements','contamination','plan_scope'];
export default function LegalReview({pid}:{pid:string}) {
 const base=`${API}/siteintel/projects/${pid}/legal-review`;
 const [data,setData]=useState<Review|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[note,setNote]=useState('');
 const [form,setForm]=useState({topic:'easements',outcome:'reviewed',checked_by:'',document_ref:'',locator:'',source_url:'',reason:'',valid_until:'',supersedes:''});
 const load=useCallback(async()=>{const r=await fetch(base,{cache:'no-store'});if(!r.ok)throw Error('Prüfbericht nicht erreichbar.');return r.json() as Promise<Review>;},[base]);
 useEffect(()=>{let dead=false;async function run(){try{let r=await load();if(dead)return;setData(r);
   if(['missing','stale'].includes(r.directory_state)){setBusy(true);const response=await fetch(`${API}/siteintel/legal/sources/refresh`,{method:'POST'});if(!response.ok)throw Error('Hessen-Quellen konnten nicht aktualisiert werden.');r=await load();if(!dead)setData(r);}
  }catch(e){if(!dead)setError(String(e));}finally{if(!dead)setBusy(false);}}
  run();const timer=setInterval(()=>load().then(r=>{if(!dead)setData(r);}).catch(()=>{}),20000);
  return()=>{dead=true;clearInterval(timer);};},[load]);
 async function refresh(){setBusy(true);setError('');try{const s=await fetch(`${API}/siteintel/legal/sources/refresh`,{method:'POST'});if(!s.ok)throw Error('Quellenabruf fehlgeschlagen.');const r=await fetch(base+'/run',{method:'POST'});if(!r.ok)throw Error('Prüfung fehlgeschlagen.');setData(await r.json());setNote('Aktuellen Prüfstand lokal archiviert.');}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function save(e:React.FormEvent){e.preventDefault();setBusy(true);setError('');setNote('');try{
  const body={...form,source_url:form.source_url||null,supersedes:form.supersedes||null,scope:PARCEL.includes(form.topic)?'parcel':'model'};
  const r=await fetch(base+'/evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const j=await r.json();
  if(!r.ok)throw Error(typeof j.detail==='string'?j.detail:'Bitte alle Nachweisfelder, Datum und Fundstelle prüfen.');setData(j.review);setNote('Aussage mit Quelle, prüfender Person und Prüfstand gespeichert. Sie ist keine automatische Freigabe.');setForm(f=>({...f,reason:'',supersedes:''}));
 }catch(e){setError(String(e));}finally{setBusy(false);}}
 const selected=data?.review_topics.find(t=>t.id===form.topic);
 return <section style={{border:'1px solid #353538',borderRadius:12,padding:16,margin:'16px 0'}}>
  <h3>Baurechtliche Vorprüfung · Hessen</h3>
  <p>Landesweiter Prüfablauf mit Rechenkontrollen und nachvollziehbarer Nachweisakte. Kein automatischer Genehmigungs- oder Vollständigkeitsnachweis.</p>
  <button type="button" className="secondary" disabled={busy} onClick={refresh}>{busy?'Quellen und Prüfstand werden geprüft …':'Hessen-Quellen & Prüfung aktualisieren'}</button>
  {error&&<p role="alert">{error}</p>}{note&&<p role="status">{note}</p>}
  {data&&<>
   <p>{data.plan_data.planfassungen} Planfassungen · {data.plan_data.dokumente} Dokumente · {data.plan_data.fundstellen} Fundstellen. Diese Anzahl sagt nichts über eine rechtliche Vollständigkeit aus.</p>
   <details><summary>Kommunaler Zugang: {data.municipality||'Gemeinde noch nicht zugeordnet'}</summary>
    <p>{data.directory_entries} Einträge aus dem zentralen Landesverzeichnis erfasst. Das ist eine Linkzuordnung, keine vollständig automatisierte Auswertung aller Gemeindesatzungen.</p>
    {data.municipal_entry?<ul>{data.municipal_entry.links.map((l,i)=><li key={i}><a href={l.url} target="_blank" rel="noreferrer">{l.title}</a></li>)}</ul>:<p>Keine eindeutige Zuordnung. Gemeindenamen und Datenabdeckung prüfen; es wird keine Kommune geraten.</p>}
   </details>
   <details><summary>{`Rechen- und Geometrieprüfungen (${data.calculated_checks.length})`}</summary>
    <p>Baukörpernäherung; ein grünes Rechenergebnis ist keine vollständige Rechtsprüfung.</p>
    {data.calculated_checks.map(c=><article key={c.id}><b>{c.label_de} · {c.status}</b><p>{c.message_de}</p><small>{c.meaning}</small></article>)}
   </details>
   <details><summary>Nachweis oder Fachprüfung dokumentieren</summary>
    <p>Nur tatsächlich vorliegende Auskünfte und Prüfungen eintragen. Die App bestätigt weder Identität noch fachliche Berechtigung der genannten Person. Gebäudebezogene Aussagen benötigen einen gespeicherten Entwurf.</p>
    <form onSubmit={save} className="form">
     <label>Prüfbereich<select value={form.topic} onChange={e=>setForm({...form,topic:e.target.value,supersedes:''})}>{data.review_topics.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
     <label>Ergebnis<select value={form.outcome} onChange={e=>setForm({...form,outcome:e.target.value})}><option value="reviewed">Fachlich geprüft / Aussage dokumentiert</option><option value="conflict">Widerspruch festgestellt</option><option value="not_applicable">Mit Begründung nicht anwendbar</option></select></label>
     <label>Geprüft von<input required minLength={3} maxLength={120} value={form.checked_by} onChange={e=>setForm({...form,checked_by:e.target.value})}/></label>
     <label>Dokument / Aktenzeichen<input required minLength={8} maxLength={500} value={form.document_ref} onChange={e=>setForm({...form,document_ref:e.target.value})}/></label>
     <label>Seite / genaue Fundstelle<input required minLength={3} maxLength={300} value={form.locator} onChange={e=>setForm({...form,locator:e.target.value})}/></label>
     <label>HTTPS-Quelle (optional)<input type="url" value={form.source_url} onChange={e=>setForm({...form,source_url:e.target.value})}/></label>
     <label>Nachweis gültig bis<input type="date" required value={form.valid_until} onChange={e=>setForm({...form,valid_until:e.target.value})}/></label>
     <label>Begründung und geprüfter Umfang<textarea required minLength={20} maxLength={4000} rows={4} value={form.reason} onChange={e=>setForm({...form,reason:e.target.value})}/></label>
     <label>Frühere Aussage ausdrücklich ersetzen<select value={form.supersedes} onChange={e=>setForm({...form,supersedes:e.target.value})}><option value="">Keine – zusätzliche Aussage</option>{selected?.evidence.map(r=><option key={r.id} value={r.id}>{r.checked_by} · {r.document_ref}</option>)}</select></label>
     <button type="submit" disabled={busy||(!PARCEL.includes(form.topic)&&!data.model_present)}>Nachweis nachvollziehbar speichern</button>
    </form>
   </details>
   <details><summary>Rechtsquellen, Aktualität und Systemgrenzen</summary>
    <p>Abrufdatum ist kein Nachweis der vollständig erfassten Rechtslage. Frühere Planfassungen können andere Rechtsgrundlagen erfordern.</p>
    <ul>{data.source_receipts.map(s=><li key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.title}</a> · {s.status}{s.retrieved_at?` · Abruf/Cache-Lesung ${new Date(s.retrieved_at).toLocaleString('de-DE')}`:''}{s.changed_since_previous?' · Inhalt geändert, Rechtsstand erneut prüfen':''}{s.matches_reviewed_rule_source===false?' · HBO-Quelldatei weicht von der geprüften Rechenbasis ab':''}</li>)}</ul>
    <ul>{data.limitations.map(t=><li key={t}>{t}</li>)}</ul>
   </details>
   {!!data.invalidated_evidence.length&&<details><summary>{`Ersetzte oder veraltete Nachweise (${data.invalidated_evidence.length})`}</summary>{data.invalidated_evidence.map(r=><p key={r.id}>{r.document_ref}: {r.invalid_reason}</p>)}</details>}
   <p><a href={base+'/export'} onClick={e=>{e.currentTarget.href=base+'/export?lang='+(document.documentElement.lang==='en'?'en':'de')}}>Prüfbericht mit Grundlagen herunterladen · JSON</a></p>
  </>}
 </section>;
}
