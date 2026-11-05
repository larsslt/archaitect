'use client';
/* Start page: all projects at a glance — where each one stands, what to do next, and the way to start a new one (map → plot → planning). */
import {useCallback, useEffect, useMemo, useState} from 'react';
import Link from 'next/link';
import {ArrowRight, Building2, Check, Copy, FileJson, FolderOpen, Layers, MapPin, MoreHorizontal, Pencil, Pin, PinOff, Plus, Search, ShieldAlert, Trash2} from 'lucide-react';
import './dashboard.css';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Step = {key: string; label_de: string; done: boolean};
type Card = {
  has_drawing?: boolean; drawing_version?: number | null; id: string; name: string; title?: string; created_at: string; updated_at: string; lat: number; lon: number; parcel_label: string | null; verdict: string; design_mode: 'full' | 'exploration' | 'blocked';
  gemeinde: string | null; address?: {ort?: string; ortsteil?: string; strasse?: string; hausnummer?: string; plz?: string} | null; area_m2: number | null; pinned?: boolean; headline_de?: string;
  has_thumb?: boolean; thumb?: {bbox_local: number[]; ring: number[][]; w: number; h: number}; override_blocked?: boolean; has_studio?: boolean; design_version?: number | null; has_house?: boolean; bim_version?: number | null; connections?: number; verified?: boolean;
  program?: {occupants: number | null; living_area_target_m2: number | null; stories: number | null};
  progress?: {steps: Step[]; done: number; total: number; next: {key: string; label_de: string; page: 'plan' | 'studio'; tab: string | null} | null};
  error?: string;
};

type Filter = 'all' | 'prep' | 'ready' | 'study';
type Sort = 'recent' | 'name' | 'progress';
const VERDICT: Record<string, string> = {CANDIDATE: 'Bebauung denkbar', RESTRICTED: 'Eingeschränkt', NOT_BUILDABLE: 'Nicht bebaubar', UNKNOWN: 'Unklar'};
const VCOLOR: Record<string, string> = {CANDIDATE: '#47a5fa', RESTRICTED: '#f2b84b', NOT_BUILDABLE: '#ff7b7b', UNKNOWN: '#9fa4ab'};

const ago = (iso: string) => {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return 'gerade eben';
  if (s < 3600) return `vor ${Math.floor(s / 60)} Min.`;
  if (s < 86400) return `vor ${Math.floor(s / 3600)} Std.`;
  if (s < 86400 * 7) return `vor ${Math.floor(s / 86400)} Tg.`;
  return new Date(iso).toLocaleDateString('de-DE', {day: '2-digit', month: 'short', year: 'numeric'});
};
const place = (c: Card) => {
  const a = c.address;
  const street = a?.strasse ? `${a.strasse}${a.hausnummer ? ' ' + a.hausnummer : ''}` : null;
  return [street, a?.ort ?? c.gemeinde].filter(Boolean).join(', ') || `${c.lat.toFixed(4)} N, ${c.lon.toFixed(4)} O`;
};
const href = (c: Card) => c.design_mode==='blocked' && !c.override_blocked ? `/hessen/plan?p=${c.id}` : `/entwurf?p=${c.id}`;

function Thumb({c}: {c: Card}) {
  const t = c.thumb;
  if (!c.has_thumb || !t) return <div className="thumb empty"><MapPin size={22} /></div>;
  const [x0, y0, x1, y1] = t.bbox_local;
  const w = x1 - x0, h = y1 - y0;
  const pts = t.ring.map(([x, y]) => `${(((x - x0) / w) * 100).toFixed(2)},${((1 - (y - y0) / h) * 100).toFixed(2)}`).join(' ');
  return (
    <div className="thumb">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`${API}/siteintel/projects/${c.id}/thumb.jpg`} alt={`Luftbild ${c.name}`} loading="lazy" />
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polygon points={pts} /></svg>
    </div>
  );
}

function Pipeline({steps}: {steps: Step[]}) {
  return <ol className="pipe" aria-label="Fortschritt">{steps.map((s) => <li key={s.key} className={s.done ? 'done' : ''} title={`${s.label_de}${s.done ? ' · erledigt' : ''}`}><i /><span>{s.label_de}</span></li>)}</ol>;
}

export default function Home() {
  const [cards, setCards] = useState<Card[] | null>(null);
  const [offline, setOffline] = useState(false);
  const [q, setQ] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const [sort, setSort] = useState<Sort>('recent');
  const [menu, setMenu] = useState<string | null>(null);
  const [rename, setRename] = useState<{id: string; value: string} | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState('');

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/siteintel/projects`);
      if (!r.ok) throw new Error(`API ${r.status}`);
      const data:Card[]=await r.json();
      setCards(data.map(c=>{ const hs=!!c.has_house; return {...c,progress:{steps:[{key:'site',label_de:'Grundstück',done:!c.error},{key:'drawing',label_de:'Entwurf',done:hs}],done:hs?2:1,total:2,next:{key:'drawing',label_de:hs?'Entwurf überarbeiten oder rendern':'Haus entwerfen',page:'studio',tab:null}}}; })); setOffline(false);
    } catch { setOffline(true); setCards((c) => c ?? []); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);
  useEffect(() => { const close = () => setMenu(null); window.addEventListener('click', close); return () => window.removeEventListener('click', close); }, []);

  const list = useMemo(() => {
    let l = (cards ?? []).filter((c) => !c.error);
    const s = q.trim().toLowerCase();
    if (s) l = l.filter((c) => `${c.name} ${place(c)} ${c.parcel_label ?? ''} ${c.gemeinde ?? ''}`.toLowerCase().includes(s));
    if (filter === 'prep') l = l.filter((c) => (c.progress?.done ?? 0) < (c.progress?.total ?? 6));
    if (filter === 'ready') l = l.filter((c) => c.progress && c.progress.done >= c.progress.total);
    if (filter === 'study') l = l.filter((c) => c.design_mode !== 'full');
    const by = {recent: (a: Card, b: Card) => b.updated_at.localeCompare(a.updated_at), name: (a: Card, b: Card) => a.name.localeCompare(b.name, 'de'), progress: (a: Card, b: Card) => (b.progress?.done ?? 0) - (a.progress?.done ?? 0)}[sort];
    return [...l].sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned) || by(a, b));
  }, [cards, q, filter, sort]);

  const stats = useMemo(() => {
    const l = (cards ?? []).filter((c) => !c.error);
    return {n: l.length, inDesign: l.filter((c) => c.has_house).length, tasks: l.filter((c) => c.progress?.next).length, area: l.reduce((s, c) => s + (c.area_m2 ?? 0), 0)};
  }, [cards]);
  const tasks = useMemo(() => (cards ?? []).filter((c) => c.progress?.next).sort((a, b) => b.updated_at.localeCompare(a.updated_at)).slice(0, 5), [cards]);

  async function act(id: string, fn: () => Promise<Response>, okText: string) {
    setBusy(id);
    try { const r = await fn(); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `API ${r.status}`); setNote(okText); await load(); }
    catch (e) { setNote(e instanceof Error ? `Fehlgeschlagen: ${e.message}` : 'Fehlgeschlagen'); }
    finally { setBusy(null); setMenu(null); setConfirm(null); setRename(null); }
  }
  const doRename = (id: string, name: string) => act(id, () => fetch(`${API}/siteintel/projects/${id}/meta`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})}), 'Umbenannt.');
  const doPin = (c: Card) => act(c.id, () => fetch(`${API}/siteintel/projects/${c.id}/meta`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pinned: !c.pinned})}), c.pinned ? 'Nicht mehr angeheftet.' : 'Angeheftet.');
  const doDup = (c: Card) => act(c.id, () => fetch(`${API}/siteintel/projects/${c.id}/duplicate`, {method: 'POST'}), 'Projekt dupliziert (ohne Entwurf, Programm und Anschlüsse bleiben erhalten).');
  const doDel = (c: Card) => act(c.id, () => fetch(`${API}/siteintel/projects/${c.id}`, {method: 'DELETE'}), 'Projekt gelöscht.');
  const doRepair = (c: Card) => act(c.id, async () => {
    const r = await fetch(`${API}/siteintel/projects/${c.id}/repair`, {method: 'POST'});
    if (r.ok) { const j = await r.json(); if (!j.terrain_ok || !j.ortho_ok) return new Response(JSON.stringify({detail: `${!j.terrain_ok ? 'Gelände' : 'Luftbild'} ist weiterhin nicht abrufbar (Dienst gerade nicht erreichbar?). Später erneut versuchen.`}), {status: 502}); }
    return r;
  }, 'Daten neu geladen.');
  const doDossier = async (c: Card) => {
    const r = await fetch(`${API}/siteintel/projects/${c.id}/dossier`);
    if (r.ok) { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(await r.json(), null, 2)], {type: 'application/json'})); a.download = `dossier-${c.id}.json`; a.click(); URL.revokeObjectURL(a.href); }
    setMenu(null);
  };

  const empty = cards !== null && (cards.length === 0);
  return (
    <main className="dash">
      <header className="dash-head">
        <div className="brand"><div className="brand-icon"><Building2 size={22} /></div><div><strong>ArchAItect</strong><small>Vom Grundstück zum Haus</small></div></div>
        <div className="dash-head-right">
          <span className={`connection ${offline ? 'off' : 'on'}`}><i className="dot" />{offline ? 'API nicht erreichbar' : 'API verbunden'}</span>
          <Link href="/hessen" className="btn primary"><Plus size={16} />Neues Projekt</Link>
        </div>
      </header>

      <section className="dash-hero">
        <div>
          <span className="eyebrow">Projekte</span>
          <h1>Deine Grundstücke und Häuser</h1>
          <p>Jedes Projekt startet mit einem echten Flurstück in Hessen: amtliches Luftbild, Gelände, Nachbarschaft und Regeln werden vorbereitet. Darauf planst du dein Haus.</p>
        </div>
        <dl className="stats">
          <div><dt>Projekte</dt><dd>{stats.n}</dd></div>
          <div><dt>Im Entwurf</dt><dd>{stats.inDesign}</dd></div>
          <div><dt>Nächste Schritte offen</dt><dd>{stats.tasks}</dd></div>
          <div><dt>Grundstücksfläche</dt><dd>{stats.area ? `${Math.round(stats.area).toLocaleString('de-DE')} m²` : '–'}</dd></div>
        </dl>
      </section>

      {offline && <p className="dash-alert"><ShieldAlert size={15} />Die API ist nicht erreichbar. Starte das Backend (Port 8000), dann erscheinen die Projekte hier.</p>}
      {note && <p className="dash-note" role="status">{note}<button onClick={() => setNote('')} aria-label="Hinweis schließen">×</button></p>}

      {cards === null && <p className="dash-loading">Projekte werden geladen …</p>}

      {empty && !offline && (
        <section className="dash-empty">
          <div className="empty-ill" aria-hidden="true"><MapPin size={30} /></div>
          <h2>Dein erstes Projekt</h2>
          <p>Wähle ein Grundstück in Hessen per Adresse oder Klick auf die Karte. Danach liegt es vorbereitet vor dir: Luftbild, Gelände, Nachbarn, Vorschriften.</p>
          <ol className="how">
            <li><b>1</b><span>Grundstück wählen</span><small>Adresse oder Karte, Flurstück wird erkannt</small></li>
            <li><b>2</b><span>Daten &amp; Wünsche</span><small>Programm, Anschlüsse, Bebauungsplan</small></li>
            <li><b>3</b><span>Haus planen</span><small>3D auf dem echten Luftbild, Regeln live geprüft</small></li>
          </ol>
          <Link href="/hessen" className="btn primary big"><Plus size={18} />Grundstück wählen</Link>
        </section>
      )}

      {cards && cards.length > 0 && (
        <div className="dash-body">
          <section className="dash-main">
            <div className="toolbar">
              <label className="search"><Search size={15} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Projekt, Adresse oder Flurstück suchen" aria-label="Projekte durchsuchen" /></label>
              <div className="pills" role="group" aria-label="Filter">
                {([['all', 'Alle'], ['prep', 'In Vorbereitung'], ['ready', 'Entwurf fertig vorbereitet'], ['study', 'Mit Vorbehalt']] as [Filter, string][]).map(([k, l]) => <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{l}</button>)}
              </div>
              <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sortierung"><option value="recent">Zuletzt bearbeitet</option><option value="name">Name</option><option value="progress">Fortschritt</option></select>
            </div>

            <div className="cards">
              {list.map((c) => {
                const p = c.progress;
                const done = p ? p.done >= p.total : false;
                return (
                  <article key={c.id} className={`pcard${busy === c.id ? ' busy' : ''}`}>
                    <Link href={href(c)} className="thumb-link" aria-label={`${c.name} öffnen`}><Thumb c={c} /></Link>
                    {c.pinned && <span className="pin" title="Angeheftet"><Pin size={12} /></span>}
                    <div className="pbody">
                      <div className="ptop">
                        {rename?.id === c.id ? (
                          <form onSubmit={(e) => { e.preventDefault(); if (rename.value.trim()) doRename(c.id, rename.value.trim()); }} className="rename">
                            <input autoFocus value={rename.value} maxLength={120} onChange={(e) => setRename({id: c.id, value: e.target.value})} onKeyDown={(e) => { if (e.key === 'Escape') setRename(null); }} aria-label="Neuer Name" />
                            <button className="icon" aria-label="Speichern"><Check size={14} /></button>
                          </form>
                        ) : <h3><Link href={href(c)}>{c.name}</Link></h3>}
                        <div className="menu-wrap" onClick={(e) => e.stopPropagation()}>
                          <button className="icon" aria-label="Aktionen" aria-expanded={menu === c.id} onClick={() => { setMenu(menu === c.id ? null : c.id); setConfirm(null); }}><MoreHorizontal size={16} /></button>
                          {menu === c.id && (
                            <div className="menu" role="menu">
                              <button role="menuitem" onClick={() => { setRename({id: c.id, value: c.name}); setMenu(null); }}><Pencil size={14} />Umbenennen</button>
                              <button role="menuitem" onClick={() => doPin(c)}>{c.pinned ? <><PinOff size={14} />Lösen</> : <><Pin size={14} />Anheften</>}</button>
                              <button role="menuitem" onClick={() => doDup(c)}><Copy size={14} />Duplizieren</button>
                              <button role="menuitem" onClick={() => doDossier(c)}><FileJson size={14} />Dossier (JSON)</button>
                              <a role="menuitem" href={`${API}/siteintel/projects/${c.id}/sitepack.zip`} onClick={e=>{e.currentTarget.href=`${API}/siteintel/projects/${c.id}/sitepack.zip?lang=`+(document.documentElement.lang==='en'?'en':'de')}}><FolderOpen size={14} />Site-Pack (ZIP)</a>
                              {confirm === c.id ? <button role="menuitem" className="danger" onClick={() => doDel(c)}><Trash2 size={14} />Ja, endgültig löschen</button> : <button role="menuitem" className="danger" onClick={() => setConfirm(c.id)}><Trash2 size={14} />Löschen …</button>}
                            </div>
                          )}
                        </div>
                      </div>
                      <p className="where"><MapPin size={12} />{place(c)}</p>
                      <p className="meta">Flurstück {c.parcel_label ?? '–'}{c.area_m2 ? ` · ${Math.round(c.area_m2).toLocaleString('de-DE')} m²` : ''}</p>
                      <div className="chips">
                        <span className="vchip" style={{['--v' as string]: VCOLOR[c.verdict] ?? '#9fa4ab'}}>{VERDICT[c.verdict] ?? c.verdict}</span>
                        {c.design_mode !== 'full' && <span className="mchip">{c.design_mode === 'blocked' ? 'Studie' : 'Vorbehalt'}</span>}
                        {c.verified && <span className="mchip ok"><Check size={10} />Regeln geprüft</span>}
                        {c.has_house && <span className="mchip"><Layers size={10} />Haus v{c.bim_version}</span>}
                      </div>
                      {p && <Pipeline steps={p.steps} />}
                      <div className="pfoot">
                        <span className="next">{p?.next ? <><b>Nächster Schritt</b>{p.next.label_de}</> : <><b>Vorbereitet</b>Weiter an der Hausplanung</>}</span>
                        {p?.next?.key === 'data'
                          ? <button className="btn small" disabled={busy === c.id} onClick={() => doRepair(c)}>{busy === c.id ? 'Lädt …' : 'Daten neu laden'}</button>
                          : <Link href={href(c)} className="btn small">{done ? 'Planen' : 'Weiter'}<ArrowRight size={14} /></Link>}
                      </div>
                      <p className="stamp">{`Bearbeitet ${ago(c.updated_at)}`}</p>
                    </div>
                  </article>
                );
              })}
              <Link href="/hessen" className="pcard add"><Plus size={22} /><span>Neues Projekt</span><small>Adresse oder Punkt auf der Karte</small></Link>
            </div>
            {list.length === 0 && <p className="dash-loading">Keine Projekte für diese Auswahl.</p>}
          </section>

          <aside className="dash-side">
            <section className="side-card">
              <h2>Als Nächstes</h2>
              {tasks.length === 0 ? <p className="muted">Alles Wichtige ist vorbereitet.</p> : (
                <ul className="tasks">{tasks.map((c) => <li key={c.id}><Link href={href(c)}><b>{c.name}</b><span>{c.progress!.next!.label_de}</span></Link></li>)}</ul>
              )}
            </section>
            <section className="side-card">
              <h2>So entsteht ein Projekt</h2>
              <ol className="how side">
                <li><b>1</b><span>Karte</span><small>Grundstück per Adresse oder Klick wählen</small></li>
                <li><b>2</b><span>Daten</span><small>Grundstücksgrenze, Gelände und verfügbare Vorschriften prüfen</small></li>
                <li><b>3</b><span>Hausplanung</span><small>Haus beschreiben, in 3D prüfen, als IFC speichern und mit Blender rendern</small></li>
              </ol>
            </section>
            <section className="side-card">
              <h2>Datenbasis</h2>
              <p className="muted">Flurstücke, Gebäude, Bodennutzung, Luftbild (20 cm) und Gelände (1 m) stammen von den hessischen Geodiensten. Leitungen (Wasser, Gas, Strom) sind kein Open Data: Anschlüsse trägst du selbst ein. Alles ist eine Vorprüfung, keine Baugenehmigung.</p>

            </section>
          </aside>
        </div>
      )}
    </main>
  );
}
