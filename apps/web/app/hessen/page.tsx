'use client';
import {useCallback, useEffect, useRef, useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {ArrowLeft, Check, Download, FileJson, Loader2, MapPin, PencilRuler, Search, ShieldAlert} from 'lucide-react';
import {API, BASE_TITLE, HESSEN_BOUNDS, loadLeaflet, officialLayer, pct, save, type BaseKey} from './shared';
import './hessen.css';

type Verdict = 'NOT_BUILDABLE' | 'RESTRICTED' | 'CANDIDATE' | 'UNKNOWN';
type Confidence = 'HIGH' | 'MEDIUM' | 'LOW';
type DesignMode = 'full' | 'exploration' | 'blocked';
type Finding = {rule_id: string; verdict: Verdict; title_de: string; reason_de: string; evidence: string; confidence: Confidence; affects_verdict: boolean};
type Regulation = {id: string; label_de: string; value_de: string; status: string; source_id: string | null};
type Share = {code: string; name_de: string; group_de: string; share: number; area_m2: number};
type Parcel = {label: string; gemarkung_nr: string | null; flur: number | null; national_reference: string; area_alkis_m2: number | null; ring_lonlat: [number, number][]};
type Planning = {layer: string; code: string; label_de: string; nature_de: string | null; share: number | null; effect: string};
type Protection = {kind: string; label_de: string; name: string | null; on_parcel: boolean; distance_m: number | null; share: number | null};
type Status = {source_id: string; status: string; detail: string | null; ms: number | null; cached: boolean};
type Assessment = {
  stage: 'core' | 'full'; lat: number; lon: number; in_hessen: boolean; verdict: Verdict; confidence: Confidence; headline_de: string;
  design_mode: DesignMode; design_reason_de: string; design_allowed: boolean; design_override_allowed: boolean;
  findings: Finding[]; regulations: Regulation[]; parcel: Parcel | null; land_use_shares: Share[];
  buildings: {on_parcel: number; on_parcel_footprint_m2: number; max_floors_on_parcel: number | null; nearby_residential: number; nearby_radius_m: number} | null;
  land_value: {eur_per_m2: number | null; stichtag: string | null; nutzung_de: string | null; gemeinde: string | null} | null;
  planning: Planning[]; protections: Protection[]; data_status: Status[]; timings_ms: Record<string, number>;
  sources: {id: string; name: string; licence: string; url: string | null; attribution: string | null}[]; disclaimer_de: string;
  mace: {pipeline_telemetry: {geometry_confidence: number; flags: string[]; manual_review_required: boolean}} | null;
};
type Place = {name: string; lat: number; lon: number};

const LABEL: Record<Verdict, string> = {NOT_BUILDABLE: 'Nicht bebaubar', RESTRICTED: 'Eingeschränkt', CANDIDATE: 'Bebauung denkbar', UNKNOWN: 'Unklar'};
const COLOR: Record<Verdict, string> = {NOT_BUILDABLE: '#ff7b7b', RESTRICTED: '#f2b84b', CANDIDATE: '#47a5fa', UNKNOWN: '#9fa4ab'};
const CONF: Record<Confidence, string> = {HIGH: 'Sicherheit hoch', MEDIUM: 'Sicherheit mittel', LOW: 'Sicherheit niedrig'};
const REG_STATUS: Record<string, string> = {OFFICIAL_DATA: 'amtliche Daten', INDICATION: 'Hinweis', UNVERIFIED_CANDIDATE: 'ungeprüft', NOT_CONNECTED: 'nicht angebunden'};
/* eslint-disable @typescript-eslint/no-explicit-any */

export default function HessenPage() {
  const mapEl = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const layers = useRef<{L: any; marker?: any; parcel?: any; base?: any}>({L: null});
  const [ready, setReady] = useState(false);
  const [result, setResult] = useState<Assessment | null>(null);
  const [busy, setBusy] = useState(false);       // nothing to show yet
  const [completing, setCompleting] = useState(false); // core is shown, planning/protection still loading
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [places, setPlaces] = useState<Place[]>([]);
  const [searchNote, setSearchNote] = useState('');
  const [showRaw, setShowRaw] = useState(false);
  const [override, setOverride] = useState(false);
  const [handover, setHandover] = useState<{state: 'idle' | 'busy' | 'ok' | 'error'; text?: string}>({state: 'idle'});
  const seq = useRef(0);
  const router = useRouter();
  const [base, setBase] = useState<BaseKey>('karte');
  const [plan, setPlan] = useState<{state: 'idle' | 'busy' | 'error'; text?: string}>({state: 'idle'});

  const draw = useCallback((data: Assessment, fit: boolean) => {
    const L = layers.current.L; if (!L || !map.current) return;
    if (layers.current.parcel) { map.current.removeLayer(layers.current.parcel); layers.current.parcel = undefined; }
    if (!data.parcel) return;
    const col = COLOR[data.verdict];
    const ring = data.parcel.ring_lonlat.map(([x, y]) => [y, x]);
    layers.current.parcel = L.polygon(ring, {color: col, weight: 2, fillColor: col, fillOpacity: 0.22}).addTo(map.current);
    if (fit && map.current.getZoom() < 17) map.current.fitBounds(layers.current.parcel.getBounds(), {maxZoom: 18, padding: [80, 80]});
  }, []);

  const assess = useCallback(async (lat: number, lon: number) => {
    const L = layers.current.L; if (!L || !map.current) return;
    const mine = ++seq.current;
    setBusy(true); setCompleting(false); setError(''); setShowRaw(false); setOverride(false); setHandover({state: 'idle'}); setPlan({state: 'idle'}); setResult(null);
    if (layers.current.marker) map.current.removeLayer(layers.current.marker);
    if (layers.current.parcel) { map.current.removeLayer(layers.current.parcel); layers.current.parcel = undefined; }
    layers.current.marker = L.circleMarker([lat, lon], {radius: 6, color: '#f2f4f6', weight: 2, fillColor: '#0064e0', fillOpacity: 1}).addTo(map.current);
    const q = `lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}`;
    try {
      // 1) fast answer: parcel + official land use + buildings + land value
      const r = await fetch(`${API}/siteintel/assess/core?${q}`);
      if (!r.ok) throw new Error(`API ${r.status}`);
      const core: Assessment = await r.json();
      if (mine !== seq.current) return;
      setResult(core); setBusy(false); draw(core, true);
      // 2) complete answer: + regional plans, flood zones, monuments (the shared cache makes the core part instant)
      setCompleting(true);
      try {
        const f = await fetch(`${API}/siteintel/assess?${q}`);
        if (f.ok) { const full: Assessment = await f.json(); if (mine === seq.current) { setResult(full); draw(full, false); } }
      } catch { /* the core answer stays; the data-status block shows what is missing */ }
      if (mine === seq.current) setCompleting(false);
    } catch (e) {
      if (mine !== seq.current) return;
      setResult(null); setBusy(false);
      setError(e instanceof Error && e.message.startsWith('API') ? `Auswertung fehlgeschlagen (${e.message}).` : 'Die API ist nicht erreichbar. Läuft das Backend auf Port 8000?');
    }
  }, [draw]);

  useEffect(() => {
    let dead = false;
    loadLeaflet().then(async (L) => {
      if (dead || !mapEl.current || map.current) return;
      layers.current.L = L;
      const m = L.map(mapEl.current, {zoomControl: false, minZoom: 7, maxZoom: 19, maxBounds: [[48.6, 6.6], [52.4, 11.4]], attributionControl: true});
      m.attributionControl.setPrefix(false);
      L.control.zoom({position: 'bottomright'}).addTo(m);
      layers.current.base = officialLayer(L, 'karte').addTo(m);
      m.attributionControl.addAttribution('Daten: Geoportal Hessen, HLNUG, Landesplanung (DL-DE Zero / dl-by-de) · Ortssuche © OpenStreetMap-Mitwirkende');
      m.fitBounds(HESSEN_BOUNDS, {padding: [20, 20]});
      m.on('click', (e: any) => assess(e.latlng.lat, e.latlng.lng));
      map.current = m;
      try {
        const g = await (await fetch('/data/hessen-outline.geojson')).json();
        const world = [[-90, -180], [-90, 180], [90, 180], [90, -180]];
        const holes = g.geometry.coordinates.map((poly: number[][][]) => poly[0].map(([x, y]) => [y, x]));
        L.polygon([world, ...holes], {stroke: false, fillColor: '#111112', fillOpacity: 0.62, interactive: false}).addTo(m);
        L.geoJSON(g, {style: {color: '#47a5fa', weight: 1.5, fill: false}, interactive: false}).addTo(m);
      } catch { /* outline is cosmetic */ }
      setReady(true);
    }).catch((e) => setError(String(e.message || e)));
    return () => { dead = true; if (map.current) { map.current.remove(); map.current = null; } };
  }, [assess]);

  const switchBase = (k: BaseKey) => {
    const L = layers.current.L; if (!L || !map.current || k === base) return;
    if (layers.current.base) map.current.removeLayer(layers.current.base);
    layers.current.base = officialLayer(L, k).addTo(map.current); layers.current.base.bringToBack();
    setBase(k);
  };

  useEffect(() => {
    const q = query.trim();
    if (q.length < 3) { setPlaces([]); setSearchNote(''); return; }
    const t = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/siteintel/geocode?q=${encodeURIComponent(q)}`);
        const j = await r.json();
        setPlaces(j.results || []); setSearchNote(j.error || (j.results?.length ? '' : 'Kein Treffer in Hessen'));
      } catch { setPlaces([]); setSearchNote('Ortssuche nicht erreichbar'); }
    }, 450);
    return () => clearTimeout(t);
  }, [query]);

  const go = (p: Place, zoom = 17) => { map.current?.setView([p.lat, p.lon], zoom); assess(p.lat, p.lon); };
  const pick = (p: Place) => { setPlaces([]); setQuery(p.name.split(',').slice(0, 2).join(',')); go(p); };

  const takeOver = async () => {
    if (!result) return;
    setHandover({state: 'busy'});
    try {
      const pi = await fetch(`${API}/siteintel/parcel-input?lat=${result.lat.toFixed(6)}&lon=${result.lon.toFixed(6)}`);
      if (!pi.ok) throw new Error((await pi.json().catch(() => ({}))).detail || `API ${pi.status}`);
      const payload = await pi.json();
      const v = await fetch(`${API}/geodata/validate`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      if (!v.ok) throw new Error(`Prüfung der Geometrie fehlgeschlagen (${v.status})`);
      const j = await v.json();
      try { sessionStorage.setItem('archaitect.siteParcel', JSON.stringify({payload, parcel: j.parcel, verdict: result.verdict, design_mode: result.design_mode, override})); } catch { /* optional */ }
      setHandover({state: 'ok', text: `Flurstück ${result.parcel?.label} geprüft (${Math.round(j.parcel.advertised_area_m2)} m², ${j.parcel.coordinate_system}). Nicht an ein Projekt gebunden, Nachweis von Identität und Zonierung steht aus.`});
    } catch (e) { setHandover({state: 'error', text: e instanceof Error ? e.message : 'Übernahme fehlgeschlagen'}); }
  };
  const startPlan = async (target: 'plan' | 'studio' = 'plan') => {
    if (!result) return;
    setPlan({state: 'busy'});
    try {
      const r = await fetch(`${API}/siteintel/projects`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({lat: result.lat, lon: result.lon, override})});
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `API ${r.status}`);
      const p = await r.json();
      router.push(target === 'studio' ? `/studio?p=${encodeURIComponent(p.id)}` : `/hessen/plan?p=${encodeURIComponent(p.id)}`);
    } catch (e) { setPlan({state: 'error', text: e instanceof Error ? e.message : 'Projekt konnte nicht angelegt werden'}); }
  };
  const dossier = async () => {
    if (!result) return;
    const r = await fetch(`${API}/siteintel/dossier?lat=${result.lat.toFixed(6)}&lon=${result.lon.toFixed(6)}`);
    if (r.ok) save(`dossier-${result.parcel?.label.replace('/', '-') ?? 'standort'}.json`, await r.json());
  };

  const r = result;
  const blocked = r?.design_mode === 'blocked' && !override;
  const mode: DesignMode | null = r ? (override ? 'exploration' : r.design_mode) : null;
  const decisive = r ? r.findings.filter((f) => f.affects_verdict) : [];
  const notes = r ? r.findings.filter((f) => !f.affects_verdict) : [];
  return (
    <main className="hessen">
      <div ref={mapEl} className={`hessen-map base-${base}`} aria-label="Karte von Hessen" />
      <div className="hessen-base" role="group" aria-label="Kartengrundlage">
        {(['karte', 'luftbild'] as BaseKey[]).map((k) => <button key={k} className={base === k ? 'on' : ''} onClick={() => switchBase(k)}>{BASE_TITLE[k]}</button>)}
      </div>
      <aside className="hessen-panel" aria-live="polite">
        <div className="hessen-top">
          <Link href="/" className="hessen-back"><ArrowLeft size={14} />Projekte</Link>
          <span className="eyebrow">Neues Projekt · Schritt 1: Grundstück wählen</span>
        </div>
        <h1>Wo soll gebaut werden?</h1>
        <div className="hessen-search">
          <Search size={16} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ort oder Adresse in Hessen" aria-label="Ort suchen" />
        </div>
        {places.length > 0 && <ul className="hessen-places">{places.map((p) => <li key={`${p.lat},${p.lon}`}><button onClick={() => pick(p)}><MapPin size={14} />{p.name}</button></li>)}</ul>}
        {searchNote && <p className="hint">{searchNote}</p>}
        {!r && !busy && !error && (
          <>
            <p className="hint">{ready ? 'Auf die Karte klicken oder einen Ort suchen. Das System identifiziert das Flurstück, holt die amtlichen Daten und zeigt die Grundregeln.' : 'Karte wird geladen …'}</p>
          </>
        )}
        {busy && <p className="hint busy"><Loader2 size={14} className="spin" />Flurstück und amtliche Daten werden abgefragt …</p>}
        {error && <p className="hessen-error"><ShieldAlert size={14} />{error}</p>}

        {r && (
          <section className="hessen-result">
            <div className="chips">
              <span className="verdict" style={{['--v' as string]: COLOR[r.verdict]}}>{LABEL[r.verdict]}</span>
              <span className="conf">{CONF[r.confidence]}</span>
              {completing && <span className="conf loading"><Loader2 size={11} className="spin" />Planung &amp; Schutz laden</span>}
            </div>
            <h2>{r.headline_de}</h2>
            {r.parcel ? (
              <dl className="facts">
                <div><dt>Flurstück</dt><dd>{r.parcel.label}</dd></div>
                <div><dt>Fläche (ALKIS)</dt><dd>{r.parcel.area_alkis_m2 ? `${Math.round(r.parcel.area_alkis_m2).toLocaleString('de-DE')} m²` : '–'}</dd></div>
                <div><dt>Gemeinde</dt><dd>{r.land_value?.gemeinde ?? '–'}</dd></div>
                <div><dt>Flur · Gemarkung</dt><dd>{r.parcel.flur ?? '–'} · {r.parcel.gemarkung_nr ?? '–'}</dd></div>
              </dl>
            ) : <p className="hint">Kein Flurstück an diesem Punkt.</p>}

            <div className={`gate ${blocked ? 'closed' : mode === 'full' ? 'open' : 'caveat'}`}>
              <strong>{blocked ? 'Entwurf gesperrt' : mode === 'full' ? 'Entwurf möglich' : override ? 'Entwurf als Studie geöffnet' : 'Entwurf mit Vorbehalt'}</strong>
              <span>{override ? 'Du hast die Sperre bewusst übergangen. Der Entwurf ist eine Studie und trägt den Hinweis dauerhaft.' : r.design_reason_de}</span>
              {blocked && r.design_override_allowed && <button className="secondary" onClick={() => setOverride(true)}>Als Studie trotzdem öffnen</button>}
              {!blocked && r.parcel && (
                <button className="primary" onClick={() => startPlan('plan')} disabled={plan.state === 'busy'}>
                  {plan.state === 'busy' ? <Loader2 size={14} className="spin" /> : <PencilRuler size={14} />}Grundstück planen
                </button>
              )}
              {!blocked && r.parcel && (
                <button className="secondary" onClick={() => startPlan('studio')} disabled={plan.state === 'busy'} title="Legt das Projekt an und öffnet sofort die Hausplanung; Programm und Vorschriften lassen sich später ergänzen.">
                  Gleich entwerfen
                </button>
              )}
              {plan.text && <small className="bad">{plan.text}</small>}
              {handover.text && <small className={handover.state === 'error' ? 'bad' : ''}>{handover.text}</small>}
            </div>

            {r.regulations.length > 0 && (<>
              <h3>Grundlegende Vorschriften</h3>
              <ul className="regs">
                {r.regulations.map((x) => (
                  <li key={x.id}>
                    <div><b>{x.label_de}</b><span className={`tag ${x.status}`}>{REG_STATUS[x.status] ?? x.status}</span></div>
                    <p>{x.value_de}</p>
                  </li>
                ))}
              </ul>
            </>)}

            {r.land_use_shares.length > 0 && (<>
              <h3>Flächennutzung auf dem Flurstück</h3>
              <ul className="shares">
                {r.land_use_shares.slice(0, 5).map((s) => (
                  <li key={s.code}><div><span>{s.name_de}</span><b>{pct(s.share)}</b></div><i style={{width: `${Math.max(2, s.share * 100)}%`}} /></li>
                ))}
              </ul>
            </>)}

            {(r.buildings || r.land_value?.eur_per_m2) && (
              <dl className="facts small">
                {r.land_value?.eur_per_m2 != null && <div><dt>Bodenrichtwert{r.land_value.stichtag ? ` (${r.land_value.stichtag.slice(0, 4)})` : ''}</dt><dd>{Math.round(r.land_value.eur_per_m2).toLocaleString('de-DE')} €/m²</dd></div>}
                {r.buildings && <div><dt>Gebäude auf dem Flurstück</dt><dd>{r.buildings.on_parcel}{r.buildings.max_floors_on_parcel ? ` · bis ${r.buildings.max_floors_on_parcel} Geschosse` : ''}</dd></div>}
                {r.buildings && <div><dt>{`Wohngebäude im Umkreis ${r.buildings.nearby_radius_m} m`}</dt><dd>{r.buildings.nearby_residential}</dd></div>}
              </dl>
            )}

            {(r.planning.length > 0 || r.protections.length > 0) && (<>
              <h3>Planung &amp; Schutz</h3>
              <ul className="plain">
                {r.planning.map((p, i) => <li key={`${p.layer}${p.code}${i}`}><b>{p.label_de}</b>{p.nature_de ? ` · ${p.nature_de}` : ''}{p.share != null ? ` · ${pct(p.share)} des Flurstücks` : ''}<small>{p.layer}{p.effect === 'restrict' ? ' · schränkt ein' : ''}</small></li>)}
                {r.protections.map((p, i) => <li key={`${p.kind}${i}`}><b>{p.label_de}</b>{p.name ? ` · ${p.name}` : ''}{p.on_parcel ? ' · auf dem Flurstück' : p.distance_m != null ? ` · ${Math.round(p.distance_m)} m entfernt` : ''}</li>)}
              </ul>
            </>)}

            <h3>Begründung</h3>
            <ul className="findings">
              {decisive.map((f, i) => (
                <li key={f.rule_id + i}>
                  <span className="dot" style={{background: COLOR[f.verdict]}} />
                  <div><b>{f.title_de}</b><p>{f.reason_de}</p><small>{f.evidence}</small></div>
                </li>
              ))}
            </ul>
            {notes.length > 0 && (<>
              <h3>Hinweise</h3>
              <ul className="findings">
                {notes.map((f, i) => <li key={f.rule_id + i}><span className="dot" style={{background: '#9fa4ab'}} /><div><b>{f.title_de}</b><p>{f.reason_de}</p></div></li>)}
              </ul>
            </>)}

            <details className="devtools">
              <summary>Export &amp; Datenquellen</summary>
              <div className="actions">
                {!blocked && r.parcel && <button className="secondary" onClick={takeOver} disabled={handover.state === 'busy'} title="Übergabe an das alte Demo-Modell, ohne Projekt">{handover.state === 'busy' ? <Loader2 size={14} className="spin" /> : handover.state === 'ok' ? <Check size={14} /> : null}In Demo-Modell übernehmen</button>}
                <button className="secondary" onClick={dossier}><FileJson size={14} />Dossier (JSON)</button>
                {r.mace && <button className="secondary" onClick={() => save(`mace-${r.parcel?.label.replace('/', '-') ?? 'flurstueck'}.json`, {site_assessment_verdict: r.verdict, ...r.mace})}><Download size={14} />MACE-JSON</button>}
              </div>
              <button className="link" onClick={() => setShowRaw((s) => !s)}>{showRaw ? 'Datenquellen ausblenden' : `Datenquellen & Zeiten${r.timings_ms.total ? ` (${(r.timings_ms.total / 1000).toFixed(1)} s)` : ''}`}</button>
              {showRaw && (
                <div className="raw">
                  <ul>{r.data_status.map((d) => <li key={d.source_id} className={d.status === 'UNAVAILABLE' ? 'bad' : ''}><b>{d.source_id}</b> {d.status}{d.ms != null ? ` · ${d.ms} ms` : ''}{d.cached ? ' · Cache' : ''}{d.detail ? ` · ${d.detail}` : ''}</li>)}</ul>
                  <ul>{r.sources.map((s) => <li key={s.id}>{s.attribution ?? s.name} · {s.licence}</li>)}</ul>
                </div>
              )}
            </details>
            <p className="disclaimer">{r.disclaimer_de}</p>
          </section>
        )}
      </aside>
    </main>
  );
}
