'use client';
/* Planning workspace for one plot: map with official aerial image + parcel + neighbours + connection points on the right,
   structured brief (everything the AI later retrieves) on the left. State lives in the API (projects store); the brief autosaves. */
import PlanningResearch from './PlanningResearch';
import LegalReview from './LegalReview';
import Offices from '../../entwurf/Offices';
import Limits from '../../entwurf/Limits';
import {Suspense, useCallback, useEffect, useMemo, useRef, useState} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import ProjectSteps from '../../components/ProjectSteps';
import {ArrowLeft, ArrowRight, Check, Download, FileJson, Loader2, MapPinPlus, Package, Plus, ShieldAlert, Trash2, TriangleAlert} from 'lucide-react';
import {API, BASE_TITLE, loadLeaflet, officialLayer, save, type BaseKey} from '../shared';
import '../hessen.css';
import './plan.css';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Kind = 'wasser' | 'abwasser' | 'regenwasser' | 'gas' | 'strom' | 'telekom' | 'fernwaerme';
type ConnStatus = 'USER_SUPPLIED' | 'AUTHORITY_PLAN' | 'ESTIMATE';
type Conn = {id: string; kind: Kind; lon: number; lat: number; status: ConnStatus; note_de: string; depth_m: number | null; diameter_mm: number | null};
type Room = {name: string; area_m2: number | null; count: number; notes_de: string};
type Program = {
  occupants: number | null; bedrooms: number | null; bathrooms: number | null; home_office: boolean | null; living_area_target_m2: number | null; stories: number | null;
  basement: 'none' | 'partial' | 'full' | 'unknown'; roof_types: string[]; garages: number | null; carports: number | null; style_keywords_de: string[]; materials_de: string[];
  energy_standard: string; heating: string; accessibility: string; budget_eur_max: number | null; rooms: Room[];
};
type Brief = {
  schema_version: string; title: string; program: Program; wishes_de: string; avoid_de: string;
  orientation: {living_towards: string; garden_side: string; entrance_from_street: boolean};
  connections: Conn[]; utilities_enquiry: {status: 'not_requested' | 'requested' | 'received'; via: string; note_de: string}; notes_de: string; updated_at: string;
};
type Regulation = {id: string; label_de: string; value_de: string; status: string};
type Assessment = {
  verdict: string; headline_de: string; design_mode: 'full' | 'exploration' | 'blocked'; design_reason_de: string; regulations: Regulation[];
  parcel: {label: string; area_alkis_m2: number | null} | null; land_value: {gemeinde: string | null; eur_per_m2: number | null} | null;
};
type ProjectResp = {project: {id: string; name: string; lat: number; lon: number; override_blocked: boolean; parcel_label: string | null}; brief: Brief; assessment: Assessment; verified: unknown};
type Fact = {id: string; topic: string; text_de: string; source: string; status: string; confidence: string};
type Context = {facts: Fact[]; retrieval_chunks: unknown[]; open_questions_de: string[]; verified_constraints: Record<string, unknown> | null; geometry: {buildable_envelope_local: unknown[] | null}; attribution: {text: string}[]};

const KINDS: {k: Kind; label: string; color: string; letter: string}[] = [
  {k: 'wasser', label: 'Trinkwasser', color: '#47a5fa', letter: 'W'}, {k: 'abwasser', label: 'Schmutzwasser', color: '#a1745a', letter: 'A'},
  {k: 'regenwasser', label: 'Regenwasser', color: '#4fc3b7', letter: 'R'}, {k: 'gas', label: 'Gas', color: '#f2d04b', letter: 'G'},
  {k: 'strom', label: 'Strom', color: '#f28c4b', letter: 'S'}, {k: 'telekom', label: 'Telekom/Glasfaser', color: '#b58cf2', letter: 'T'},
  {k: 'fernwaerme', label: 'Fernwärme', color: '#ff7b7b', letter: 'F'},
];
const KIND = Object.fromEntries(KINDS.map((x) => [x.k, x])) as Record<Kind, (typeof KINDS)[number]>;
const ROOFS = [['sattel', 'Satteldach'], ['walm', 'Walmdach'], ['pult', 'Pultdach'], ['flach', 'Flachdach'], ['zelt', 'Zeltdach'], ['kruppelwalm', 'Krüppelwalm'], ['egal', 'egal']];
const DIRS = ['egal', 'N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW'];
const TABS = [['site', 'Grundstück'], ['rules', 'Vorschriften & Quellen']] as const;
type Tab = 'site'|'rules'|'program'|'wishes'|'utilities'|'ai';
const STATUS_DE: Record<string, string> = {OFFICIAL_DATA: 'amtlich', INDICATION: 'Hinweis', UNVERIFIED_CANDIDATE: 'ungeprüft', NOT_CONNECTED: 'nicht angebunden', USER_SUPPLIED: 'vom Nutzer', AUTHORITY_PLAN: 'Behördenplan', ESTIMATE: 'Schätzung', VERIFIED_BY_USER: 'geprüft', NOT_OPEN_DATA: 'kein Open Data', NOTE: 'Notiz'};

const EMPTY_VC = {verified_by: '', basis_de: '', grz: '', gfz: '', h: '', st: '', sb: '', roofs: '', pmin: '', pmax: '', eave: ''};
const str = (x: unknown) => (x === null || x === undefined ? '' : String(x).replace('.', ','));
const csv = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

function Num({value, onChange, min, max, step = 1, placeholder}: {value: number | null; onChange: (v: number | null) => void; min?: number; max?: number; step?: number; placeholder?: string}) {
  return <input type="number" inputMode="decimal" value={value ?? ''} min={min} max={max} step={step} placeholder={placeholder ?? '–'} onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />;
}
function Field({label, children, wide}: {label: string; children: React.ReactNode; wide?: boolean}) {
  return <label className={`fld${wide ? ' wide' : ''}`}><span>{label}</span>{children}</label>;
}

function PlanWorkspace() {
  const sp = useSearchParams();
  const pid = sp.get('p') ?? '';
  const mapEl = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const L = useRef<any>(null);
  const groups = useRef<Record<string, any>>({});
  const baseLayer = useRef<any>(null);
  const placing = useRef<Kind | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [data, setData] = useState<ProjectResp | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [overlay, setOverlay] = useState<any>(null);
  const [ctx, setCtx] = useState<Context | null>(null);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<Tab>(() => { const t = sp.get('tab'); return (TABS.some(([k]) => k === t) ? t : 'site') as Tab; });
  const [saveState, setSaveState] = useState<{s: 'idle' | 'saving' | 'saved' | 'error'; text?: string}>({s: 'idle'});
  const [base, setBase] = useState<BaseKey>('luftbild');
  const [show, setShow] = useState({neighbours: true, buildings: true, landuse: false});
  const [placingKind, setPlacingKind] = useState<Kind | null>(null);
  const [parcels, setParcels] = useState<{max: number; selected: string[]; primary_id: string; parcels: {id: string; label: string; area_m2: number | null; selected: boolean; adjacent: boolean}[]} | null>(null);
  const [addMode, setAddMode] = useState(false);
  const addModeRef = useRef(false);
  const [parcelBusy, setParcelBusy] = useState<string | null>(null);
  const [parcelMsg, setParcelMsg] = useState<string | null>(null);
  const loaded = useRef(false);

  // ---------------------------------------------------------------- load
  const loadOverlay = useCallback(async () => {
    const r = await fetch(`${API}/siteintel/projects/${pid}/overlay`); if (r.ok) setOverlay(await r.json());
  }, [pid]);
  const loadCtx = useCallback(async () => {
    const r = await fetch(`${API}/siteintel/projects/${pid}/context`); if (r.ok) setCtx(await r.json());
  }, [pid]);
  const [vc, setVc] = useState(EMPTY_VC);
  const [vcSaved, setVcSaved] = useState(JSON.stringify(EMPTY_VC));
  const [planCount,setPlanCount]=useState(0);
  const [rulesActive, setRulesActive] = useState<{verified: any; limits: any} | null>(null);
  const [vcState, setVcState] = useState<{s: 'idle' | 'busy' | 'ok' | 'error'; text?: string}>({s: 'idle'});
  const num = (s: string) => (s.trim() === '' ? null : Number(s.replace(',', '.')));
  /** Form = own limits, overlaid by verified values (a verified value wins per field, exactly like the studio). */
  const loadRules = useCallback(async () => {
    const r = await fetch(`${API}/siteintel/projects/${pid}/limits`); if (!r.ok) return;
    const j = await r.json(); setRulesActive(j);
    const f: any = {...EMPTY_VC};
    for (const src of [j.limits, j.verified]) {
      if (!src) continue;
      const map: [string, unknown][] = [['grz', src.grz], ['gfz', src.gfz], ['h', src.max_building_height_meters], ['st', src.max_stories], ['sb', src.setback_lines_offset_meters], ['pmin', src.roof_pitch_min_deg], ['pmax', src.roof_pitch_max_deg], ['eave', src.max_eave_height_meters]];
      for (const [k, v] of map) if (v !== null && v !== undefined) f[k] = str(v);
      if (src.roof_types_allowed?.length) f.roofs = src.roof_types_allowed.join(', ');
    }
    if (j.verified) { f.verified_by = j.verified.verified_by; f.basis_de = j.verified.basis_de; } else if (j.limits?.note_de) f.basis_de = j.limits.note_de;
    setVc(f); setVcSaved(JSON.stringify(f));
  }, [pid]);
  const loadParcels = useCallback(async () => {
    const r = await fetch(`${API}/siteintel/projects/${pid}/parcels`); if (r.ok) setParcels(await r.json());
  }, [pid]);
  useEffect(() => {
    if (!pid) { setError('Kein Projekt gewählt. Auf der Karte ein Grundstück wählen und „Grundstück planen“ drücken.'); return; }
    let dead = false;
    (async () => {
      try {
        const r = await fetch(`${API}/siteintel/projects/${pid}`);
        if (!r.ok) throw new Error(r.status === 404 ? 'Projekt nicht gefunden.' : `API ${r.status}`);
        const j: ProjectResp = await r.json();
        if (dead) return;
        setData(j); setBrief(j.brief); loaded.current = true;
        await Promise.all([loadOverlay(), loadCtx(), loadParcels(), loadRules()]);
      } catch (e) { if (!dead) setError(e instanceof Error && !e.message.startsWith('API') ? e.message : 'Die API ist nicht erreichbar. Läuft das Backend auf Port 8000?'); }
    })();
    return () => { dead = true; };
  }, [pid, loadOverlay, loadCtx, loadParcels]);

  // ---------------------------------------------------------------- autosave of the brief
  const first = useRef(true);
  useEffect(() => {
    if (!brief || !loaded.current) return;
    if (first.current) { first.current = false; return; }
    setSaveState({s: 'saving'});
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/siteintel/projects/${pid}/brief`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(brief)});
        if (!r.ok) {
          const j = await r.json().catch(() => ({}));
          const d = Array.isArray(j.detail) ? j.detail.map((x: any) => `${(x.loc || []).slice(1).join('.')}: ${x.msg}`).join(' · ') : j.detail || `API ${r.status}`;
          throw new Error(d);
        }
        setSaveState({s: 'saved'});
        if (tab === 'ai') loadCtx();
      } catch (e) { setSaveState({s: 'error', text: e instanceof Error ? e.message : 'Speichern fehlgeschlagen'}); }
    }, 800);
    return () => clearTimeout(t);
  }, [brief, pid, tab, loadCtx]);
  useEffect(() => { if (tab === 'ai') loadCtx(); }, [tab, loadCtx]);

  const upd = useCallback((f: (b: Brief) => Brief) => setBrief((b) => (b ? f(b) : b)), []);
  const setProg = <K extends keyof Program>(k: K, v: Program[K]) => upd((b) => ({...b, program: {...b.program, [k]: v}}));

  // ---------------------------------------------------------------- map
  useEffect(() => {
    if (!data) return;
    let dead = false;
    loadLeaflet().then((Lf) => {
      if (dead || !mapEl.current || map.current) return;
      L.current = Lf;
      const m = Lf.map(mapEl.current, {zoomControl: false, minZoom: 14, maxZoom: 20, attributionControl: true});
      m.attributionControl.setPrefix(false);
      Lf.control.zoom({position: 'bottomright'}).addTo(m);
      Lf.control.scale({metric: true, imperial: false, position: 'bottomleft'}).addTo(m);
      baseLayer.current = officialLayer(Lf, 'luftbild').addTo(m);
      m.setView([data.project.lat, data.project.lon], 19);
      for (const k of ['landuse', 'neighbours', 'site', 'buildings', 'envelope', 'conns']) groups.current[k] = Lf.layerGroup().addTo(m);
      m.on('click', (e: any) => {
        const k = placing.current; if (!k) return;
        const id = `${k}-${Math.random().toString(36).slice(2, 7)}`;
        upd((b) => ({...b, connections: [...b.connections, {id, kind: k, lon: +e.latlng.lng.toFixed(7), lat: +e.latlng.lat.toFixed(7), status: 'USER_SUPPLIED', note_de: '', depth_m: null, diameter_mm: null}]}));
        placing.current = null; setPlacingKind(null); m.getContainer().style.cursor = '';
      });
      map.current = m; setMapReady(true);
    }).catch((e) => setError(String(e.message || e)));
    return () => { dead = true; if (map.current) { try { map.current.stop(); } catch { /* ignore */ } map.current.remove(); map.current = null; } };
  }, [data, upd]);

  const switchBase = (k: BaseKey) => {
    if (!map.current || !L.current || k === base) return;
    if (baseLayer.current) map.current.removeLayer(baseLayer.current);
    baseLayer.current = officialLayer(L.current, k).addTo(map.current); baseLayer.current.bringToBack(); setBase(k);
  };

  // static overlay: land use, parcels, buildings, buildable envelope
  useEffect(() => {
    const Lf = L.current; if (!mapReady || !Lf || !overlay) return;
    const g = groups.current;
    for (const k of ['landuse', 'neighbours', 'site', 'buildings', 'envelope']) g[k].clearLayers();
    const feats: any[] = overlay.features;
    const poly = (f: any) => f.geometry.coordinates[0].map(([x, y]: number[]) => [y, x]);
    let siteBounds: any = null;
    for (const f of feats) {
      const p = f.properties;
      if (p.kind === 'landuse') g.landuse.addLayer(Lf.polygon(poly(f), {color: '#9fa4ab', weight: 1, fillColor: '#9fa4ab', fillOpacity: 0.12, dashArray: '4 4'}).bindTooltip(p.label));
      else if (p.kind === 'parcel') {
        const pl = Lf.polygon(poly(f), {color: '#f2f4f6', weight: 1, fillColor: '#47a5fa', fillOpacity: 0, opacity: 0.6}).bindTooltip(`Flurstück ${p.label}`);
        pl.on('click', (ev: any) => { if (!addModeRef.current) return; Lf.DomEvent.stopPropagation(ev); changeParcel(p.id, 'add'); });
        pl.on('mouseover', () => { if (addModeRef.current) pl.setStyle({fillOpacity: 0.25}); });
        pl.on('mouseout', () => pl.setStyle({fillOpacity: 0}));
        g.neighbours.addLayer(pl);
      }
      else if (p.kind === 'parcel_site') { const pl = Lf.polygon(poly(f), {color: '#47a5fa', weight: 3, fillColor: '#47a5fa', fillOpacity: 0.12}).bindTooltip(`Ihr Grundstück ${p.label}`); g.site.addLayer(pl); siteBounds = siteBounds ? siteBounds.extend(pl.getBounds()) : pl.getBounds(); }
      else if (p.kind === 'building') g.buildings.addLayer(Lf.polygon(poly(f), {color: p.on_site ? '#f2b84b' : '#ff9b6b', weight: 1.5, fillColor: p.on_site ? '#f2b84b' : '#ff9b6b', fillOpacity: 0.3}).bindTooltip(`${p.on_site ? 'Bestand auf dem Grundstück' : 'Nachbargebäude'}${p.floors ? ` · ${p.floors} Geschosse` : ''}${p.height_est_m ? ` · Höhe ca. ${p.height_est_m} m (Schätzung)` : ''}`));
      else if (p.kind === 'envelope') g.envelope.addLayer(Lf.polygon(poly(f), {color: '#6bd68a', weight: 2.5, fillColor: '#6bd68a', fillOpacity: 0.18}).bindTooltip('Baufenster (Flurstück abzüglich Abstand, ohne Baulasten)'));
    }
    if (siteBounds && !map.current.__fitted) { map.current.fitBounds(siteBounds, {padding: [60, 60], maxZoom: 20}); map.current.__fitted = true; }
  }, [overlay, mapReady]);

  // layer toggles
  useEffect(() => {
    if (!mapReady) return;
    const g = groups.current; const m = map.current;
    const set = (k: string, on: boolean) => { if (on && !m.hasLayer(g[k])) g[k].addTo(m); if (!on && m.hasLayer(g[k])) m.removeLayer(g[k]); };
    set('landuse', show.landuse); set('buildings', show.buildings); set('neighbours', show.neighbours); set('site', true); set('envelope', true); set('conns', true);
  }, [show, mapReady, overlay]);

  // connection markers (editable by dragging)
  useEffect(() => {
    const Lf = L.current; if (!mapReady || !Lf || !brief) return;
    const g = groups.current.conns; g.clearLayers();
    for (const c of brief.connections) {
      const meta = KIND[c.kind];
      const icon = Lf.divIcon({className: 'conn-pin', html: `<span style="background:${meta.color}">${meta.letter}</span>`, iconSize: [26, 26], iconAnchor: [13, 13]});
      const mk = Lf.marker([c.lat, c.lon], {icon, draggable: true}).bindTooltip(`${meta.label} · ${STATUS_DE[c.status]}`);
      mk.on('dragend', () => { const p = mk.getLatLng(); upd((b) => ({...b, connections: b.connections.map((x) => (x.id === c.id ? {...x, lat: +p.lat.toFixed(7), lon: +p.lng.toFixed(7)} : x))})); });
      g.addLayer(mk);
    }
  }, [brief?.connections, mapReady, upd]); // eslint-disable-line react-hooks/exhaustive-deps

  const startPlace = (k: Kind) => {
    const on = placing.current === k ? null : k; placing.current = on; setPlacingKind(on);
    if (map.current) map.current.getContainer().style.cursor = on ? 'crosshair' : '';
  };

  // ---------------------------------------------------------------- rules (verified constraints)
  const changeParcel = async (id: string, action: 'add' | 'remove') => {
    setParcelBusy(id); setParcelMsg(null);
    try {
      const r = await fetch(`${API}/siteintel/projects/${pid}/parcels`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({parcel_id: id, action})});
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : `API ${r.status}`);
      setParcels(j); addModeRef.current = false; setAddMode(false);
      const pr = await fetch(`${API}/siteintel/projects/${pid}`); if (pr.ok) setData(await pr.json());
      await Promise.all([loadOverlay(), loadCtx()]);
      setParcelMsg(action === 'add' ? 'Flurstück hinzugefügt; Luftbild und Gelände wurden für die gemeinsame Fläche neu geladen.' : 'Flurstück entfernt.');
    } catch (e) { setParcelMsg(e instanceof Error ? e.message : 'Fehler'); } finally { setParcelBusy(null); }
  };
  const toggleAdd = () => { const on = !addModeRef.current; addModeRef.current = on; setAddMode(on); };
  const vcDirty = JSON.stringify(vc) !== vcSaved;
  const vcValues = () => ({grz: num(vc.grz), gfz: num(vc.gfz), max_building_height_meters: num(vc.h), max_stories: num(vc.st), setback_lines_offset_meters: num(vc.sb), roof_types_allowed: csv(vc.roofs),
    roof_pitch_min_deg: num(vc.pmin), roof_pitch_max_deg: num(vc.pmax), max_eave_height_meters: num(vc.eave)});
  const canVerify = vc.verified_by.trim().length >= 2 && vc.basis_de.trim().length >= 3;
  const submitVc = async (mode: 'own' | 'verified') => {
    setVcState({s: 'busy'});
    try {
      const vals = vcValues();
      if (Object.values(vals).some((x) => typeof x === 'number' && Number.isNaN(x))) throw new Error('Bitte nur Zahlen eintragen (Komma oder Punkt).');
      const r = mode === 'verified'
        ? await fetch(`${API}/siteintel/projects/${pid}/constraints`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({verified_by: vc.verified_by, basis_de: vc.basis_de, ...vals})})
        : await fetch(`${API}/siteintel/projects/${pid}/limits`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...vals, note_de: vc.basis_de.slice(0, 300)})});
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(Array.isArray(j.detail) ? j.detail.map((x: any) => `${(x.loc || []).slice(-1)}: ${x.msg}`).join(' · ') : j.detail || `API ${r.status}`); }
      await Promise.all([loadOverlay(), loadCtx(), loadRules()]);
      setVcState({s: 'ok', text: (mode === 'verified' ? 'Als geprüfte Festsetzung gespeichert.' : 'Als eigene Vorgabe gespeichert.') + ' Die Hausplanung hält diese Grenzen jetzt hart ein.' + (vals.setback_lines_offset_meters != null ? ' Das Baufenster ist grün eingezeichnet.' : '')});
    } catch (e) { setVcState({s: 'error', text: e instanceof Error ? e.message : 'Fehler'}); }
  };

  // ---------------------------------------------------------------- derived
  const a = data?.assessment;
  const terrain = ctx?.facts.find((f) => f.id === 'terrain');
  const frontage = ctx?.facts.find((f) => f.id === 'frontage');
  const checks = useMemo(() => {
    if (!brief || !ctx) return [];
    const p = brief.program;
    return [
      {ok: !!a?.parcel, label: 'Flurstück identifiziert (ALKIS)'},
      {ok: ctx.facts.some((f) => f.id === 'terrain'), label: 'Geländemodell (DGM1) vorhanden'},
      {ok: !!(p.occupants && p.living_area_target_m2 && p.stories), label: 'Bauprogramm: Personen, Wohnfläche, Geschosse'},
      {ok: brief.connections.length > 0, label: 'Mindestens ein Anschlusspunkt gesetzt'},
      {ok: brief.utilities_enquiry.status === 'received', label: 'Leitungsauskunft liegt vor'},
      {ok: !!ctx.verified_constraints, label: 'Bebauungsplan-Werte von Person geprüft'},
      {ok: !!ctx.geometry.buildable_envelope_local, label: 'Baufenster berechnet'},
    ];
  }, [brief, ctx, a]);

  if (error) return <main className="plan-fallback"><p className="hessen-error"><ShieldAlert size={14} />{error}</p><Link href="/hessen" className="hessen-back"><ArrowLeft size={14} />Zur Karte</Link></main>;
  if (!data || !brief) return <main className="plan-fallback"><p className="hint busy"><Loader2 size={14} className="spin" />Projekt wird geladen …</p></main>;
  const p = brief.program;
  const gateCls = a?.design_mode === 'full' ? 'open' : a?.design_mode === 'blocked' ? 'closed' : 'caveat';

  const planningEl = (<PlanningResearch key={pid} pid={pid} onCoverage={setPlanCount} onCandidate={(candidate, source) => { setVc((old) => ({...old, [candidate.field]: String(candidate.value), basis_de: source})); setTab('rules'); setVcState({s: 'idle', text: 'Fundstelle ins Formular übernommen, noch nicht gespeichert. Teilgebiet, Planfassung und Original prüfen; danach als eigene Vorgabe oder mit Nachweis als geprüft speichern.'}); }} />);
  const legalEl = <LegalReview key={pid} pid={pid} />;
  return (
    <main className="plan">
      <aside className="plan-panel">
        <div className="plan-top">
          <ProjectSteps pid={pid} active="plan" />
          <span className={`save ${saveState.s}`}>{saveState.s === 'saving' ? <><Loader2 size={11} className="spin" />speichert …</> : saveState.s === 'saved' ? <><Check size={11} />gespeichert</> : saveState.s === 'error' ? <><TriangleAlert size={11} />nicht gespeichert</> : ''}</span>
        </div>
        <input className="title" value={brief.title} onChange={(e) => upd((b) => ({...b, title: e.target.value}))} aria-label="Projektname" maxLength={120} />
        <p className="sub">{(data.project as any).parcel_ids?.length > 1 ? `Flurstücke ${(data.project as any).parcel_label}` : `Flurstück ${a?.parcel?.label ?? '–'}`}{a?.land_value?.gemeinde ? ` · ${a.land_value.gemeinde}` : ''}{((data.project as any).area_m2 ?? a?.parcel?.area_alkis_m2) ? ` · ${Math.round((data.project as any).area_m2 ?? a?.parcel?.area_alkis_m2).toLocaleString('de-DE')} m²` : ''}</p>
        <Link href={`/entwurf?p=${pid}`} className="cta-studio">Weiter: Haus entwerfen<ArrowRight size={15} /></Link>
        {saveState.s === 'error' && <p className="hessen-error"><ShieldAlert size={14} />{saveState.text}</p>}
        <nav className="tabs" role="tablist">{TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}</nav>


        {tab === 'site' && a && (
          <section>
            <div className={`gate ${gateCls}`}>
              <strong>{a.design_mode === 'full' ? 'Entwurf möglich' : a.design_mode === 'blocked' ? 'Entwurf als Studie geöffnet' : 'Entwurf mit Vorbehalt'}</strong>
              <span>{a.design_reason_de}</span>
            </div>
            <h3>{`Flurstücke (${parcels?.selected.length ?? 1} von ${parcels?.max ?? 5})`}</h3>
            <ul className="plist">
              {parcels?.parcels.filter((x) => x.selected).map((x) => (
                <li key={x.id}><b>{x.label}</b><span>{x.area_m2 ? `${Math.round(x.area_m2).toLocaleString('de-DE')} m²` : ''}</span>
                  {x.id !== parcels.primary_id ? <button className="icon" aria-label={`Flurstück ${x.label} entfernen`} disabled={!!parcelBusy} onClick={() => changeParcel(x.id, 'remove')}>{parcelBusy === x.id ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}</button> : <em>Ausgang</em>}</li>
              ))}
            </ul>
            {parcels && parcels.selected.length < parcels.max && (
              <button className={`secondary${addMode ? ' on' : ''}`} onClick={toggleAdd} disabled={!!parcelBusy}><Plus size={14} />{addMode ? 'Auf ein angrenzendes Flurstück in der Karte klicken …' : 'Angrenzendes Flurstück hinzufügen'}</button>
            )}
            {parcelBusy && <p className="hint busy"><Loader2 size={13} className="spin" />Flurstück wird amtlich geprüft und Grundstücksdaten neu geladen …</p>}
            {parcelMsg && <p className="hint" role="status">{parcelMsg}</p>}
            <h3>Gelände &amp; Lage</h3>
            <ul className="plain compact">
              {terrain && <li>{terrain.text_de}</li>}
              {frontage && <li>{frontage.text_de}</li>}
              {ctx?.facts.find((f) => f.id === 'neighbours') && <li>{ctx.facts.find((f) => f.id === 'neighbours')!.text_de}</li>}
              {ctx?.facts.find((f) => f.id === 'orientation') && <li>{ctx.facts.find((f) => f.id === 'orientation')!.text_de}</li>}
            </ul>
            <h3>Amtliche Daten</h3>
            <ul className="regs compact">{a.regulations.map((original) => original.id === 'bebauungsplan' && planCount ? {...original, status: 'OFFICIAL_DATA', value_de: `${planCount} Planfassungen gefunden, Originale unten.`} : original)
              .filter((x) => ['OFFICIAL_DATA', 'INDICATION', 'AUTHORITY_PLAN'].includes(x.status) && x.value_de && !/nicht (angebunden|erfasst|verfügbar|abrufbar)/i.test(x.value_de))
              .map((x) => <li key={x.id}><div><b>{x.label_de}</b>{x.id !== 'bebauungsplan' && <span className={`tag ${x.status}`}>{STATUS_DE[x.status] ?? x.status}</span>}</div><p>{x.value_de}</p></li>)}</ul>
            {planningEl}
            {(() => { const qs = (ctx?.open_questions_de ?? []).filter((q) => /erfrag|einhol|Bauamt|Bauaufsicht|Auskunft|Grundbuch/i.test(q) && !(planCount && q.startsWith('Bebauungsplan der Gemeinde einholen'))); return qs.length > 0 && (<><h3>Beim Amt nachfragen</h3><ul className="plain compact">{qs.map((q) => <li key={q}>{q}</li>)}</ul></>); })()}
            <Offices req={{label: a?.parcel?.label, gemeinde: a?.land_value?.gemeinde, area_m2: a?.parcel?.area_alkis_m2}} />
            <Limits base={`${API}/siteintel/projects/${pid}`} limits={rulesActive?.limits ?? null} onSaved={() => void loadRules()} />
          </section>
        )}

        {tab === 'program' && (
          <section className="form">
            <div className="grid">
              <Field label="Personen"><Num value={p.occupants} onChange={(v) => setProg('occupants', v)} min={1} max={30} /></Field>
              <Field label="Schlafzimmer"><Num value={p.bedrooms} onChange={(v) => setProg('bedrooms', v)} min={0} max={20} /></Field>
              <Field label="Bäder"><Num value={p.bathrooms} onChange={(v) => setProg('bathrooms', v)} min={0} max={10} /></Field>
              <Field label="Wohnfläche Ziel (m²)"><Num value={p.living_area_target_m2} onChange={(v) => setProg('living_area_target_m2', v)} min={21} max={1500} /></Field>
              <Field label="Geschosse"><Num value={p.stories} onChange={(v) => setProg('stories', v)} min={1} max={8} /></Field>
              <Field label="Keller">
                <select value={p.basement} onChange={(e) => setProg('basement', e.target.value as Program['basement'])}>
                  <option value="unknown">offen</option><option value="none">kein Keller</option><option value="partial">Teilkeller</option><option value="full">Vollkeller</option>
                </select>
              </Field>
              <Field label="Garagen"><Num value={p.garages} onChange={(v) => setProg('garages', v)} min={0} max={6} /></Field>
              <Field label="Carports"><Num value={p.carports} onChange={(v) => setProg('carports', v)} min={0} max={6} /></Field>
              <Field label="Budget max. (€)"><Num value={p.budget_eur_max} onChange={(v) => setProg('budget_eur_max', v)} min={1} step={10000} /></Field>
              <Field label="Homeoffice">
                <select value={p.home_office === null ? '' : p.home_office ? 'y' : 'n'} onChange={(e) => setProg('home_office', e.target.value === '' ? null : e.target.value === 'y')}>
                  <option value="">offen</option><option value="y">ja</option><option value="n">nein</option>
                </select>
              </Field>
              <Field label="Energiestandard">
                <select value={p.energy_standard} onChange={(e) => setProg('energy_standard', e.target.value)}>
                  <option value="unknown">offen</option><option value="geg">GEG-Standard</option><option value="kfw55">Effizienzhaus 55</option><option value="kfw40">Effizienzhaus 40</option><option value="passivhaus">Passivhaus</option>
                </select>
              </Field>
              <Field label="Heizung">
                <select value={p.heating} onChange={(e) => setProg('heating', e.target.value)}>
                  <option value="unknown">offen</option><option value="waermepumpe">Wärmepumpe</option><option value="fernwaerme">Fernwärme</option><option value="gas">Gas</option><option value="pellets">Pellets</option><option value="strom">Strom</option>
                </select>
              </Field>
              <Field label="Zugänglichkeit" wide>
                <select value={p.accessibility} onChange={(e) => setProg('accessibility', e.target.value)}>
                  <option value="standard">Standard</option><option value="barrierearm">barrierearm</option><option value="barrierefrei">barrierefrei</option>
                </select>
              </Field>
            </div>
            {(() => { const mx = rulesActive?.verified?.max_stories ?? rulesActive?.limits?.max_stories; return mx && p.stories && p.stories > mx ? <p className="hessen-error"><ShieldAlert size={14} />Gewünscht sind {p.stories} Geschosse, die Vorschriften erlauben höchstens {mx}. Die Hausplanung hält {mx} ein.</p> : null; })()}
            {(() => { const al: string[] = (rulesActive?.verified?.roof_types_allowed?.length ? rulesActive.verified.roof_types_allowed : rulesActive?.limits?.roof_types_allowed) ?? []; const w = p.roof_types[0]; return w && w !== 'egal' && al.length && !al.includes(w) ? <p className="hessen-error"><ShieldAlert size={14} />Die gewünschte Dachform ist laut Vorschriften nicht zulässig (zulässig: {al.join(', ')}).</p> : null; })()}
            <h3>Dachform <small>(eine Wahl)</small></h3>
            <div className="chipsel" role="radiogroup" aria-label="Gewünschte Dachform">{ROOFS.map(([k, l]) => <button key={k} role="radio" aria-checked={p.roof_types[0] === k} className={p.roof_types[0] === k ? 'on' : ''} onClick={() => setProg('roof_types', p.roof_types[0] === k ? [] : [k])}>{l}</button>)}</div>
            <Field label="Stil (Stichworte, kommagetrennt)" wide><input defaultValue={p.style_keywords_de.join(', ')} onBlur={(e) => setProg('style_keywords_de', csv(e.target.value).slice(0, 12))} placeholder="modern, hell, klare Linien" /></Field>
            <Field label="Materialien (kommagetrennt)" wide><input defaultValue={p.materials_de.join(', ')} onBlur={(e) => setProg('materials_de', csv(e.target.value).slice(0, 12))} placeholder="Putz, Holz, Klinker" /></Field>
            <h3>Räume</h3>
            <ul className="rooms">
              {p.rooms.map((r, i) => (
                <li key={i}>
                  <input value={r.name} onChange={(e) => setProg('rooms', p.rooms.map((x, j) => (j === i ? {...x, name: e.target.value} : x)))} placeholder="Raum" aria-label="Raumname" />
                  <Num value={r.area_m2} onChange={(v) => setProg('rooms', p.rooms.map((x, j) => (j === i ? {...x, area_m2: v} : x)))} min={1} max={500} placeholder="m²" />
                  <Num value={r.count} onChange={(v) => setProg('rooms', p.rooms.map((x, j) => (j === i ? {...x, count: v ?? 1} : x)))} min={1} max={20} placeholder="×" />
                  <button className="icon" aria-label="Raum entfernen" onClick={() => setProg('rooms', p.rooms.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
                </li>
              ))}
            </ul>
            <button className="secondary" onClick={() => setProg('rooms', [...p.rooms, {name: '', area_m2: null, count: 1, notes_de: ''}])}><Plus size={14} />Raum hinzufügen</button>
          </section>
        )}

        {tab === 'wishes' && (
          <section className="form">
            <Field label="Das wünsche ich mir" wide><textarea rows={6} value={brief.wishes_de} maxLength={4000} onChange={(e) => upd((b) => ({...b, wishes_de: e.target.value}))} placeholder="Offene Küche zum Garten, viel Licht, Arbeitszimmer im Obergeschoss …" /></Field>
            <Field label="Das möchte ich vermeiden" wide><textarea rows={3} value={brief.avoid_de} maxLength={2000} onChange={(e) => upd((b) => ({...b, avoid_de: e.target.value}))} placeholder="Keine Fenster zur Straße im Schlafbereich …" /></Field>
            <div className="grid">
              <Field label="Wohnbereich Richtung"><select value={brief.orientation.living_towards} onChange={(e) => upd((b) => ({...b, orientation: {...b.orientation, living_towards: e.target.value}}))}>{DIRS.map((d) => <option key={d} value={d}>{d}</option>)}</select></Field>
              <Field label="Gartenseite"><select value={brief.orientation.garden_side} onChange={(e) => upd((b) => ({...b, orientation: {...b.orientation, garden_side: e.target.value}}))}>{DIRS.map((d) => <option key={d} value={d}>{d}</option>)}</select></Field>
            </div>
            <label className="check"><input type="checkbox" checked={brief.orientation.entrance_from_street} onChange={(e) => upd((b) => ({...b, orientation: {...b.orientation, entrance_from_street: e.target.checked}}))} />Eingang von der Straße</label>
            <Field label="Weitere Hinweise" wide><textarea rows={4} value={brief.notes_de} maxLength={4000} onChange={(e) => upd((b) => ({...b, notes_de: e.target.value}))} /></Field>
            <p className="hint">Die Himmelsrichtungen beziehen sich auf geografisch Nord. {frontage ? frontage.text_de : ''}</p>
          </section>
        )}

        {tab === 'utilities' && (
          <section className="form">
            <div className="note">
              <b>Leitungen sind kein Open Data.</b> Wasser-, Gas- und Stromleitungen liegen bei den Netzbetreibern. Die Karte kann sie nicht zeigen; du setzt hier die Hausanschlusspunkte, die du kennst, und holst die Leitungsauskunft ein.
              {' '}<a href="https://bil-leitungsauskunft.de/" target="_blank" rel="noreferrer">BIL-Leitungsauskunft ↗</a>
            </div>
            <h3>Punkt auf der Karte setzen</h3>
            <div className="place">
              {KINDS.map((x) => <button key={x.k} className={placingKind === x.k ? 'on' : ''} onClick={() => startPlace(x.k)}><i style={{background: x.color}} />{x.label}</button>)}
            </div>
            {placingKind && <p className="hint busy"><MapPinPlus size={14} />Jetzt auf die Karte klicken, um {KIND[placingKind].label} zu setzen. Der Punkt lässt sich danach verschieben.</p>}
            <ul className="conns">
              {brief.connections.map((c) => (
                <li key={c.id}>
                  <div className="row"><i style={{background: KIND[c.kind].color}} /><b>{KIND[c.kind].label}</b>
                    <select value={c.status} onChange={(e) => upd((b) => ({...b, connections: b.connections.map((x) => (x.id === c.id ? {...x, status: e.target.value as ConnStatus} : x))}))}>
                      <option value="USER_SUPPLIED">vom Nutzer</option><option value="AUTHORITY_PLAN">Behördenplan</option><option value="ESTIMATE">Schätzung</option>
                    </select>
                    <button className="icon" aria-label="Punkt entfernen" onClick={() => upd((b) => ({...b, connections: b.connections.filter((x) => x.id !== c.id)}))}><Trash2 size={14} /></button>
                  </div>
                  <div className="row">
                    <Num value={c.depth_m} onChange={(v) => upd((b) => ({...b, connections: b.connections.map((x) => (x.id === c.id ? {...x, depth_m: v} : x))}))} min={0} max={10} step={0.1} placeholder="Tiefe m" />
                    <Num value={c.diameter_mm} onChange={(v) => upd((b) => ({...b, connections: b.connections.map((x) => (x.id === c.id ? {...x, diameter_mm: v} : x))}))} min={0} max={2000} placeholder="DN mm" />
                    <input value={c.note_de} maxLength={300} onChange={(e) => upd((b) => ({...b, connections: b.connections.map((x) => (x.id === c.id ? {...x, note_de: e.target.value} : x))}))} placeholder="Notiz" />
                  </div>
                </li>
              ))}
              {brief.connections.length === 0 && <li className="empty">Noch keine Anschlusspunkte.</li>}
            </ul>
            <h3>Leitungsauskunft</h3>
            <div className="grid">
              <Field label="Stand">
                <select value={brief.utilities_enquiry.status} onChange={(e) => upd((b) => ({...b, utilities_enquiry: {...b.utilities_enquiry, status: e.target.value as Brief['utilities_enquiry']['status']}}))}>
                  <option value="not_requested">nicht angefragt</option><option value="requested">angefragt</option><option value="received">liegt vor</option>
                </select>
              </Field>
              <Field label="Über"><input value={brief.utilities_enquiry.via} maxLength={80} onChange={(e) => upd((b) => ({...b, utilities_enquiry: {...b.utilities_enquiry, via: e.target.value}}))} placeholder="BIL / Stadtwerke …" /></Field>
            </div>
          </section>
        )}

        {tab === 'rules' && (
          <section className="form">
            {planningEl}
            {legalEl}
            <div className="note"><b>Diese Grenzen hält die Hausplanung hart ein.</b> „Eigene Vorgabe“ speichert sofort (z. B. Werte, die du gelesen, aber noch nicht geprüft hast, oder eigene Wünsche). „Geprüft“ braucht Name und Fundstelle und kennzeichnet die Werte als Bebauungsplan-Festsetzung.</div>
            <p className={`rules-state ${rulesActive?.verified ? 'v' : rulesActive?.limits ? 'u' : ''}`}>{rulesActive?.verified ? `Aktiv: geprüft (${rulesActive.verified.basis_de})${rulesActive.limits ? ' + eigene Vorgaben' : ''}` : rulesActive?.limits ? 'Aktiv: eigene Vorgaben (nicht als B-Plan geprüft)' : 'Noch keine örtlichen Grenzwerte gespeichert. Grundstück, Bestand und HBO-Abstandshinweise werden trotzdem geprüft.'}{vcDirty ? ' · Änderungen noch nicht gespeichert' : ''}</p>
            <div className="grid">
              <Field label="GRZ"><input value={vc.grz} onChange={(e) => setVc({...vc, grz: e.target.value})} placeholder="0,4" inputMode="decimal" /></Field>
              <Field label="GFZ"><input value={vc.gfz} onChange={(e) => setVc({...vc, gfz: e.target.value})} placeholder="0,8" inputMode="decimal" /></Field>
              <Field label="Max. Höhe (m)"><input value={vc.h} onChange={(e) => setVc({...vc, h: e.target.value})} placeholder="9,5" inputMode="decimal" /></Field>
              <Field label="Max. Geschosse"><input value={vc.st} onChange={(e) => setVc({...vc, st: e.target.value})} placeholder="2" inputMode="numeric" /></Field>
              <Field label="Abstand zur Grenze (m)" wide><input value={vc.sb} onChange={(e) => setVc({...vc, sb: e.target.value})} placeholder="3" inputMode="decimal" /></Field>
              <Field label="Max. Traufhöhe (m)"><input value={vc.eave} onChange={(e) => setVc({...vc, eave: e.target.value})} placeholder="6,5" inputMode="decimal" /></Field>
              <Field label="Dachneigung von–bis (°)"><span className="pair"><input value={vc.pmin} onChange={(e) => setVc({...vc, pmin: e.target.value})} placeholder="25" inputMode="decimal" aria-label="Dachneigung von" /><input value={vc.pmax} onChange={(e) => setVc({...vc, pmax: e.target.value})} placeholder="45" inputMode="decimal" aria-label="Dachneigung bis" /></span></Field>
            </div>
            <h3>Zulässige Dachformen <small>(mehrere möglich, wenn der Plan mehrere erlaubt)</small></h3>
            <div className="chipsel">{ROOFS.filter(([k]) => k !== 'egal').map(([k, l]) => { const on = csv(vc.roofs).includes(k); return <button key={k} className={on ? 'on' : ''} onClick={() => setVc({...vc, roofs: (on ? csv(vc.roofs).filter((x) => x !== k) : [...csv(vc.roofs), k]).join(', ')})}>{l}</button>; })}</div>
            <p className="hint">Leer lassen, was der Plan nicht festsetzt – dann bleibt die Regel „nicht festgelegt“. Eingetragene Werte gelten im Studio als harte Grenze.</p>
            <div className="note"><b>Abstandsflächen (§ 6 HBO)</b> berechnet das Studio automatisch für jede Wand: 0,4 H, mindestens 2,50 m (Fassung Baupaket I, GVBl. 2025 Nr. 66). Sie werden als Hinweis angezeigt und nicht erzwungen, weil Ausnahmen, Baulasten und Festsetzungen abweichen können.</div>
            <h3>Nachweis (nur für „geprüft“)</h3>
            <div className="grid">
              <Field label="Geprüft von"><input value={vc.verified_by} onChange={(e) => setVc({...vc, verified_by: e.target.value})} placeholder="Name / Rolle" /></Field>
              <Field label="Fundstelle / Notiz"><input value={vc.basis_de} onChange={(e) => setVc({...vc, basis_de: e.target.value})} placeholder="B-Plan Nr. 12, Festsetzung 2.1" /></Field>
            </div>
            <div className="actions rules-actions">
              <button className="primary" onClick={() => submitVc('own')} disabled={vcState.s === 'busy'}>{vcState.s === 'busy' ? <Loader2 size={14} className="spin" /> : <Check size={14} />}Als eigene Vorgabe übernehmen</button>
              <button className="secondary" onClick={() => submitVc('verified')} disabled={vcState.s === 'busy' || !canVerify} title={canVerify ? '' : 'Name und Fundstelle eintragen'}><ShieldAlert size={14} />Als geprüft übernehmen</button>
            </div>
            {vcState.text && <p className={vcState.s === 'error' ? 'hessen-error' : 'hint'}>{vcState.text}</p>}
            <p className="hint">Das Baufenster ist nur der gleichmäßige Abstand zur Grenze. Baugrenzen, Baulinien, Baulasten und Leitungsrechte sind darin nicht enthalten.</p>
          </section>
        )}

        {tab === 'ai' && (
          <section>
            <h3>Bereit für die Generierung?</h3>
            <ul className="checks">{checks.map((c) => <li key={c.label} className={c.ok ? 'ok' : ''}>{c.ok ? <Check size={13} /> : <span className="dash">–</span>}{c.label}</li>)}</ul>
            <p className="hint">Fehlendes bleibt „unbekannt“; die KI erhält die Lücken als offene Punkte und erfindet nichts.</p>
            <div className="actions">
              <a className="secondary" href={`${API}/siteintel/projects/${pid}/sitepack.zip`} onClick={e=>{e.currentTarget.href=`${API}/siteintel/projects/${pid}/sitepack.zip?lang=`+(document.documentElement.lang==='en'?'en':'de')}}><Package size={14} />Site-Pack (ZIP)</a>
              <button className="secondary" onClick={() => ctx && save(`context-${pid}.json`, ctx)}><FileJson size={14} />Kontext (JSON)</button>
              <button className="secondary" onClick={async () => { const r = await fetch(`${API}/siteintel/projects/${pid}/dossier`); if (r.ok) save(`dossier-${pid}.json`, await r.json()); }}><Download size={14} />Dossier</button>
            </div>
            <h3>{`Fakten, die die KI abruft (${ctx?.facts.length ?? 0})`}</h3>
            <ul className="facts-list">
              {ctx?.facts.map((f) => (
                <li key={f.id}><div><b>{f.topic}</b><span className={`tag ${f.status}`}>{STATUS_DE[f.status] ?? f.status}</span></div><p>{f.text_de}</p><small>{f.id} · {f.source} · Sicherheit {f.confidence}</small></li>
              ))}
            </ul>
            {ctx && <p className="disclaimer">{ctx.attribution.map((x) => x.text).join(' · ')}</p>}
          </section>
        )}
      </aside>

      <div ref={mapEl} className={`plan-map base-${base}`} aria-label="Grundstück auf der Karte" />
      <div className="plan-tools">
        <div className="seg">{(['luftbild', 'karte'] as BaseKey[]).map((k) => <button key={k} className={base === k ? 'on' : ''} onClick={() => switchBase(k)}>{BASE_TITLE[k]}</button>)}</div>
        <div className="seg stack">
          <label><input type="checkbox" checked={show.neighbours} onChange={(e) => setShow({...show, neighbours: e.target.checked})} />Nachbarflurstücke</label>
          <label><input type="checkbox" checked={show.buildings} onChange={(e) => setShow({...show, buildings: e.target.checked})} />Gebäude</label>
          <label><input type="checkbox" checked={show.landuse} onChange={(e) => setShow({...show, landuse: e.target.checked})} />Bodennutzung</label>
        </div>
      </div>
      <div className="north" title="Geografisch Nord" aria-label="Nordpfeil"><svg viewBox="0 0 24 32" width="22" height="30"><path d="M12 1 L20 25 L12 19 L4 25 Z" fill="#f2f4f6" stroke="#0b0b0c" strokeWidth="1" /></svg><span>N</span></div>
    </main>
  );
}

export default function PlanPage() {
  return <Suspense fallback={<main className="plan-fallback"><p className="hint busy"><Loader2 size={14} className="spin" />Lädt …</p></main>}><PlanWorkspace /></Suspense>;
}
