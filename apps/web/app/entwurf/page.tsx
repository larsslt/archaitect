'use client';
/* Entwurf: Text/Foto -> Haus (Gebäudespezifikation -> IFC) auf dem echten Grundstück. Regeln (Baurecht) und Gelände (DGM1, Aufschüttung/Abtrag)
   kommen aus dem Backend; die 360°-Ansicht zeigt das Haus auf dem angepassten Gelände, Fotos rendert Blender lokal (kein Cloud-Dienst). */
import {Suspense, useCallback, useEffect, useRef, useState} from 'react';
import Limits from './Limits';
import Offices from './Offices';
import {useSearchParams} from 'next/navigation';
import {API} from '../hessen/shared';
import ProjectSteps from '../components/ProjectSteps';
import {loadThree, type SiteData} from '../studio/scene3d';
import {BimScene, type BimMesh, type BimObject} from './BimScene';
import {Thumb} from './Thumbs';
import './entwurf.css';

/* eslint-disable @typescript-eslint/no-explicit-any */

async function jfetch(url: string, init?: RequestInit) {
  let r: Response;
  try { r = await fetch(url, init); } catch { throw new Error('Backend nicht erreichbar. Läuft die API auf Port 8000?'); }
  let bad = false;
  const j = await r.json().catch(() => { bad = true; return {}; });
  if (r.ok && bad) throw new Error('Antwort der API ist kein gültiges JSON.');
  if (!r.ok) {
    const d = (j as any).detail;
    const msg = typeof d === 'string' ? d : (d?.message ?? d?.message_de ?? `API ${r.status}`);
    const err = new Error(msg + (Array.isArray(d?.problems) && d.problems.filter((x: string) => !String(msg).includes(x)).length ? ' – ' + d.problems.filter((x: string) => !String(msg).includes(x)).slice(0, 3).join('; ') : '')) as any;
    err.status = r.status;
    throw err;
  }
  return j;
}
const post = (url: string, body: unknown) => jfetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body ?? {})});
const PS = ProjectSteps as unknown as (p: any) => React.JSX.Element;

/** Kurztext einer Baurecht-Prüfung: „Ist 14,1 m – keine Grenze festgelegt“ statt langer Erklärung. */
function ruleText(r: any): string {
  const m = String(r.message_de ?? '');
  const g = m.match(/^Keine Grenze festgelegt \(Ist-Wert ([^·)]+?)(?: ·[^)]*)?\)/);
  if (g) return `Ist ${g[1].trim()} – keine Grenze festgelegt`;
  if (/^Keine Grenze festgelegt/.test(m)) return 'Keine Grenze festgelegt';
  const first = m.split(/(?<=[.!?])\s/)[0] ?? m;
  return first.length > 150 ? first.slice(0, 147) + '…' : first;
}

type Msg = {role: 'user' | 'arch'; text: string; questions?: string[]};
const QUALITIES: [string, string][] = [['sketch', 'Skizze (schnell)'], ['draft', 'Entwurf'], ['preview', 'Vorschau'], ['final', 'Final']];
const OBJECT_CATEGORIES = [
  {name: 'Nebengebäude', items: [['sauna_hut', '', 'Saunahaus'], ['parking_2', '', 'Stellplatz (2)'], ['parking_4', '', 'Stellplätze (4)']]},
  {name: 'Wasser & Pool', items: [['pool', '', 'Pool'], ['pool_small', '', 'Kleiner Pool'], ['pond', '', 'Teich'], ['pond_small', '', 'Kleiner Teich']]},
  {name: 'Pflanzen', items: [['tree', '', 'Laubbaum'], ['tree_small', '', 'Obstbaum'], ['conifer', '', 'Nadelbaum'], ['shrub', '', 'Strauch'], ['shrub_pot', '', 'Kübelpflanze'], ['flowerbed', '', 'Blumenbeet'], ['flowerbed_long', '', 'Langes Beet']]},
  {name: 'Möbel & Licht', items: [['bench', '', 'Gartenbank'], ['bench_long', '', 'Lange Bank'], ['garden_set', '', 'Sitzgruppe'], ['garden_light', '', 'Gartenleuchte'], ['garden_light_low', '', 'Pollerleuchte']]},
];
const CAT_ORDER = ['Nebengebäude', 'Terrasse & Sitzen', 'Wasser & Pool', 'Pflanzen', 'Möbel & Licht', 'Dekoration', 'Spiel & Sport', 'Mobilität'];
const catsOf = (objs: any[]) => { const m: Record<string, string[][]> = {}; for (const o of objs ?? []) (m[o.category] ??= []).push([o.id, '', o.label]); return [...CAT_ORDER.filter((n) => m[n]), ...Object.keys(m).filter((n) => !CAT_ORDER.includes(n))].map((name) => ({name, items: m[name]})); };
const STATUS_DE: Record<string, string> = {PASS: 'erfüllt', WARN: 'Hinweis', FAIL: 'verletzt', UNKNOWN: 'unbekannt'};

function Workspace({pid}: {pid: string}) {
  const base = `${API}/siteintel/projects/${pid}`;
  const bim = `${base}/bim`;
  const box = useRef<HTMLDivElement>(null);
  const sc = useRef<any>(null);
  const siteRef = useRef<SiteData | null>(null);
  const dragEnd = useRef<(id?: string) => void>(() => {});
  const [objs, setObjs] = useState<BimObject[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [showPlans, setShowPlans] = useState(false);
  const [st, setSt] = useState<any>(null);
  const [siteName, setSiteName] = useState('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState('Arbeite');
  const [busyT0, setBusyT0] = useState(0);
  const [nowT, setNowT] = useState(0);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [pendingQ, setPendingQ] = useState<string[] | null>(null);
  const lastReq = useRef('');
  const [refSel, setRefSel] = useState<string[]>([]);
  const [showRules, setShowRules] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);
  const [meshErr, setMeshErr] = useState<string | null>(null);
  const [meshBusy, setMeshBusy] = useState(false);
  const [renders, setRenders] = useState<any[]>([]);
  const [quality, setQuality] = useState('preview');
  const [camera, setCamera] = useState('');
  const [plans, setPlans] = useState<any[] | null>(null);
  const reframe = useRef(false);
  const [view, setView] = useState<'umgebung' | 'grundstueck'>('grundstueck');
  const [spin, setSpin] = useState(false);
  const [showRender, setShowRender] = useState(false);
  const [bigId, setBigId] = useState<string | null>(null);
  const [lib, setLib] = useState<any[]>([]);
  const [showDesigns, setShowDesigns] = useState(false);
  const libraryDrag = useRef<string | null>(null);
  const [showObjects, setShowObjects] = useState(false);
  const [explode, setExplode] = useState(false);
  const expRaf = useRef(0);
  const toggleExplode = () => {
    const to = explode ? 0 : 1, from = explode ? 1 : 0, t0 = performance.now(), sh = Number(st?.spec?.storey_height) || 3;
    cancelAnimationFrame(expRaf.current); setExplode(!explode);
    const step = (now: number) => { const k = Math.min(1, (now - t0) / 900), e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2; sc.current?.setExplode?.(from + (to - from) * e, sh); if (k < 1) expRaf.current = requestAnimationFrame(step); };
    expRaf.current = requestAnimationFrame(step);
  };
  const [partMode, setPartMode] = useState(false);
  const [partVol, setPartVol] = useState<string | null>(null);
  const [panel, setPanel] = useState<'chat' | 'site' | 'lib' | null>('chat');
  const [libTab, setLibTab] = useState('Gebäude');
  const [cats, setCats] = useState(OBJECT_CATEGORIES);
  const [objectCategory, setObjectCategory] = useState('Pflanzen');
  const [vers, setVers] = useState<any[]>([]);
  const [showPhotos, setShowPhotos] = useState(false);
  const [photos, setPhotos] = useState<any>(null);
  const [planUrl, setPlanUrl] = useState<string | null>(null);
  const [zoomImg, setZoomImg] = useState<string | null>(null);

  const version: number = st?.version ?? 0;
  const hasHouse = !!st?.exists;

  // ---- Zustand + Grundstück laden
  const loadSite = useCallback(async () => {
    const [d, pk, cx] = await Promise.all([jfetch(`${base}/design`), jfetch(`${base}/sitepack`), jfetch(`${base}/context`)]);
    const site = d.site ?? {};
    setSiteName(String(site.name ?? 'Entwurf'));
    const ids = new Set((site.parcel_ids ?? []) as string[]);
    const data = {
      site: site.ring, envelope: site.envelope,
      neighbours: (pk.parcels as any[]).filter((p) => !ids.has(p.id)).map((p) => p.ring),
      buildings: (pk.buildings as any[]).map((b) => ({id: b.id, ring: b.ring, height_m: b.height_est_m, on_site: (site.existing ?? []).some((e: any) => e.id === b.id)})),
      terrain: pk.terrain?.status === 'OK' ? {...pk.terrain.grid, z_origin_m: pk.terrain.z_origin_m} : null,
      ortho: null,
      connections: (cx.geometry?.connections_local ?? []).map((c: any) => ({id: c.id, kind: c.kind, xy: c.xy})),
      extent: pk.extent.bbox_local,
    } as unknown as SiteData;
    siteRef.current = data;
    document.title = `Entwurf · ${site.name ?? ''}`;
    try { await sc.current?.setSite(data); } catch { /* Szene noch nicht bereit */ }
  }, [base]);

  const loadState = useCallback(async () => {
    const s = await jfetch(bim);
    setSt(s);
    if (s.cameras?.length) setCamera((c) => (s.cameras.includes(c) ? c : s.cameras[0]));
    return s;
  }, [bim]);

  const showMesh = useCallback(async (s: any) => {
    setMeshErr(null);
    if (!sc.current) return;
    if (!s?.exists) { sc.current.setHouse(null, {x: 0, y: 0, rotation_deg: 0}); return; }
    setMeshBusy(true);
    try {
      const m: BimMesh = await jfetch(`${bim}/mesh`);
      setObjs(m.objects ?? []);
      sc.current.setHouse(m, s.placement ?? {x: 0, y: 0, rotation_deg: 0}, reframe.current);
      reframe.current = false;
      { const cm = new URLSearchParams(window.location.search).get('cam'); if (cm) { const v = cm.split(',').map(Number); if (v.length >= 7 && v.every(Number.isFinite)) sc.current.shotMode({position: v.slice(0, 3), target: v.slice(3, 6), lens_mm: v[6]}, window.innerWidth, window.innerHeight); } }       // Bilderwelt: feste Kamera aus dem Hausrahmen
      const far = Number(new URLSearchParams(window.location.search).get('far')); if (far > 0) { sc.current.sph.r = far; const th = Number(new URLSearchParams(window.location.search).get('th')); if (th > 0) sc.current.sph.theta = th; const ph = new URLSearchParams(window.location.search).get('ph'); if (ph !== null) sc.current.sph.phi = Number(ph); sc.current.placeCamera(); } if (new URLSearchParams(window.location.search).get('dbg')) { const g = sc.current.groups.plot; document.title = `DBG zMin=${sc.current.zMinSite} z0=${sc.current.z0} plot=${g.visible} kids=${g.children.length} ` + g.children.map((c: any) => `${c.type}:${c.geometry?.attributes?.position?.count}:${Number.isNaN(c.geometry?.boundingSphere?.radius ?? c.geometry?.computeBoundingSphere?.())}`).join(','); }       // Diagnose: ?far=<m> zeigt das ganze Flurstück
    } catch (e: any) { setMeshErr(e.message ?? '3D-Modell konnte nicht geladen werden.'); } finally { setMeshBusy(false); }
  }, [bim]);

  useEffect(() => {
    (async () => {
      try { await loadSite(); await loadState(); } catch (e: any) { setErr(e.message ?? 'Laden fehlgeschlagen.'); }
      setLoading(false);
    })();
  }, [loadSite, loadState]);

  // ---- Szene
  useEffect(() => {
    if (loading || !box.current || sc.current) return;
    let cancelled = false;
    (async () => {
      try {
        const T = await loadThree();
        if (cancelled || !box.current) return;
        sc.current = new BimScene(T, box.current, {
          onDrag: (id: string, dx: number, dy: number) => sc.current?.nudgeLive(dx, dy, id),
          onDragEnd: (id?: string) => dragEnd.current(id),
          onSelect: (id: string | null) => { setSelId(id); sc.current?.setSelected?.(id); },
          onPart: (vol: string | null, obj: string) => { setPartVol(vol); setSelId(obj); sc.current?.setPartVol?.(vol); },
        });
        sc.current.setLayers({aerial: false, neighbours: false, existing: false, surroundings: false, connections: false, envelope: false, boundary: true, abstand: false, labels: false});   // nur Grundstück + Haus
        if (siteRef.current) await sc.current.setSite(siteRef.current);
        if (cancelled) return;
        setSceneReady(true);
      } catch (e: any) { if (!cancelled) setMeshErr(e.message ?? 'Szene konnte nicht aufgebaut werden.'); }
    })();
    return () => { cancelled = true; };
  }, [loading]);
  useEffect(() => () => { sc.current?.dispose?.(); sc.current = null; }, []);
  useEffect(() => { if (sceneReady && st) void showMesh(st); }, [sceneReady, st?.version, st?.placement?.x, st?.placement?.y, st?.placement?.rotation_deg]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { sc.current?.setMode?.(view); }, [view, sceneReady]);
  useEffect(() => { if (sc.current) sc.current.setAutoRotate?.(spin); }, [spin, sceneReady]);

  useEffect(() => { if (panel === 'lib' && !lib.length) jfetch(`${bim}/library`).then((r) => { setLib(r.houses ?? []); if (r.objects?.length) setCats(catsOf(r.objects)); }).catch(() => {}); }, [panel]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (st && !st.exists) jfetch(`${bim}/library`).then((r) => { setLib(r.houses ?? []); if (r.objects?.length) setCats(catsOf(r.objects)); }).catch(() => {}); }, [st?.exists]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Render-Aufträge
  useEffect(() => { if (!showRender) window.dispatchEvent(new Event('resize')); }, [showRender]);
  const loadRenders = useCallback(async () => {
    try { setRenders((await jfetch(`${bim}/renders`)).renders ?? []); } catch { /* optional */ }
  }, [bim]);
  useEffect(() => { if (hasHouse) void loadRenders(); }, [hasHouse, loadRenders]);
  useEffect(() => {
    if (!renders.some((r) => r.status === 'queued' || r.status === 'running')) return;
    const t = setTimeout(() => void loadRenders(), 3000);
    return () => clearTimeout(t);
  }, [renders, loadRenders]);

  // ---- Aktionen
  useEffect(() => { if (!busy) return; const t = window.setInterval(() => setNowT(Date.now()), 400); return () => window.clearInterval(t); }, [busy]);
  const run = async (fn: () => Promise<void>, label = 'Arbeite') => {
    setBusyLabel(label); setBusyT0(Date.now()); setNowT(Date.now());
    setBusy(true); setErr(null);
    try { await fn(); } catch (e: any) { setErr(e.message ?? 'Fehlgeschlagen.'); } finally { setBusy(false); }
  };
  const apply = (s: any) => { setSt(s); if (s.cameras?.length) setCamera((c) => (s.cameras.includes(c) ? c : s.cameras[0])); setPlans(null); setPlanUrl(null); };

  const send = () => run(async () => {
    const t = text.trim();
    if (!t && !refSel.length) return;
    setMsgs((m) => [...m, {role: 'user', text: t || '(Foto)'}]);
    setText('');
    // a reply to a clarifying question is meaningless alone: send the original request, the question and the answer together
    const full = pendingQ && lastReq.current ? `${lastReq.current}\n\nRückfrage: ${pendingQ.join(' ')}\nAntwort des Nutzers: ${t}`.slice(0, 2900) : t;
    if (!pendingQ) lastReq.current = t;
    const res = !hasHouse || refSel.length
      ? await post(`${bim}/create`, {text: full, reference_ids: refSel, answers: pendingQ ? t : undefined})
      : await post(`${bim}/revise`, {text: full});
    if (res.status === 'questions') { setPendingQ(res.questions ?? []); setMsgs((m) => [...m, {role: 'arch', text: 'Dazu brauche ich noch eine Angabe:', questions: res.questions ?? []}]); return; }
    setPendingQ(null); setRefSel([]);
    reframe.current = true;
    apply(res);
    setMsgs((m) => [...m, {role: 'arch', text: [res.summary, ...(res.notes_de ?? [])].filter(Boolean).join(' ') || `Version ${res.version} gespeichert.`}]);
  }, 'Haus wird entworfen');
  const fromLib = (id: string, at?: {x: number; y: number}) => run(async () => { let res = await post(`${bim}/library/${id}`, {}); if (res.status === 'questions') { lastReq.current = `Haus im Stil der Vorlage ${lib.find((h) => h.id === id)?.name ?? id}, passend zum Grundstück`; setPendingQ(res.questions ?? []); setMsgs((m) => [...m, {role: 'arch', text: 'Zur passenden Hausvorlage fehlt noch eine Angabe:', questions: res.questions ?? []}]); return; } if (at) res = await post(`${bim}/place`, {x: at.x, y: at.y, center: true}); reframe.current = !at; apply(res); setMsgs((m) => [...m, {role: 'arch', text: `Beispielhaus „${res.name}“ gesetzt. ${(res.notes_de ?? []).join(' ')}`}]); });
  const place = (body: any) => run(async () => { apply(await post(`${bim}/place`, body)); });
  const holdT = useRef<any>(null);
  const startRot = (dir: number) => {
    if (!sc.current || holdT.current) return;
    let n = 0;
    const tick = () => { n++; sc.current?.rotateLive(dir * (n < 20 ? 0.5 : n < 40 ? 1 : 2)); };
    tick(); holdT.current = setInterval(tick, 50);
  };
  const stopRot = () => {
    if (!holdT.current) return;
    clearInterval(holdT.current); holdT.current = null;
    if (sc.current?.revertIfOutside(null)) { setMsgs((m) => [...m, {role: 'arch', text: 'Dort läge das Haus außerhalb des Grundstücks – die Drehung wurde zurückgesetzt.'}]); return; }
    const pl = sc.current?.takePlacement();
    if (pl) void place({x: Math.round(pl.x * 100) / 100, y: Math.round(pl.y * 100) / 100, rotation_deg: Math.round(pl.rot * 100) / 100});
  };
  const nudge = (dx: number, dy: number, dr = 0) => {
    const p = st?.placement ?? {x: 0, y: 0, rotation_deg: 0};
    return place({x: Math.round((p.x + dx) * 10) / 10, y: Math.round((p.y + dy) * 10) / 10, rotation_deg: (p.rotation_deg + dr + 360) % 360});
  };
  dragEnd.current = (id?: string) => {
    if (!id || !sc.current) return;
    if (sc.current.revertIfOutside(id)) { setMsgs((m) => [...m, {role: 'arch', text: 'Dort liegt das Objekt außerhalb des Grundstücks – es bleibt auf dem alten Platz.'}]); return; }
    const d = sc.current.takeDelta(id);
    if (Math.abs(d.dx) + Math.abs(d.dy) < 0.05) return;
    void run(async () => {
      try { apply(await post(`${bim}/objects/${encodeURIComponent(id)}/move`, {dx: d.dx, dy: d.dy})); }
      catch (e: any) { if (st) await showMesh(st); throw e; }       // Kollision: Objekt springt zurück, Meldung bleibt stehen
    });
  };
  const turnSel = (q: number) => { if (!selId) return; void run(async () => { try { apply(await post(`${bim}/objects/${encodeURIComponent(selId)}/rotate`, {quarters: q})); } catch (e: any) { if (st) await showMesh(st); throw e; } }); };
  const removeSel = () => {
    if (!selId) return;
    const o = objs.find((x) => x.id === selId);
    run(async () => { apply(await jfetch(`${bim}/objects/${encodeURIComponent(selId)}`, {method: 'DELETE'})); setSelId(null); sc.current?.setSelected?.(null); setMsgs((m) => [...m, {role: 'arch', text: `„${o?.label ?? 'Objekt'}“ gelöscht.`}]); });
  };
  const openDesigns = () => {
    setShowDesigns((v) => !v);
    setShowPhotos(false);
    jfetch(`${bim}/versions`).then((r) => setVers(r.versions ?? [])).catch(() => {});
    if (!lib.length) jfetch(`${bim}/library`).then((r) => { setLib(r.houses ?? []); if (r.objects?.length) setCats(catsOf(r.objects)); }).catch(() => {});
  };
  const loadPhotos = () => jfetch(`${bim}/photos`).then((r) => setPhotos(r)).catch(() => {});
  const openPhotos = () => { setShowPhotos((v) => !v); setShowDesigns(false); void loadPhotos(); };
  const makePhotos = (shots?: string[]) => run(async () => { setPhotos(await post(`${bim}/photos`, shots ? {shots} : {})); });
  useEffect(() => {
    if (!showPhotos || photos?.status !== 'running') return;
    const t = setInterval(() => { void loadPhotos(); }, 4000);
    return () => clearInterval(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showPhotos, photos?.status]);
  const restore = (v: number) => run(async () => { reframe.current = true; apply(await post(`${bim}/restore/${v}`, {})); setShowDesigns(false); });
  const undo = () => run(async () => { apply(await post(`${bim}/undo`, {})); });
  const startRender = () => run(async () => { setShowRender(true); await post(`${bim}/renders`, {quality, camera}); await loadRenders(); });
  const cancelRender = (id: string) => run(async () => { await post(`${bim}/renders/${id}/cancel`, {}); await loadRenders(); });
  const loadPlans = () => run(async () => { setPlans((await jfetch(`${bim}/plans`)).plans ?? []); });
  useEffect(() => { if (showPlans && plans?.length && !planUrl) { const f = String(plans[0].svg ?? '').split('/').pop(); if (f) setPlanUrl(`${bim}/plans/${version}/${f}?lang=${typeof document !== 'undefined' && document.documentElement.lang === 'de' ? 'de' : 'en'}`); } }, [showPlans, plans]); // eslint-disable-line react-hooks/exhaustive-deps
  const printPlans = async () => {
    const w = window.open('', '_blank');
    if (!w) { setErr('Das Pop-up wurde blockiert. Bitte Pop-ups für diese Seite erlauben.'); return; }
    try {
      const svgs = await Promise.all((plans ?? []).map(async (pl: any) => { const f = String(pl.svg ?? '').split('/').pop(); return f ? await (await fetch(`${bim}/plans/${version}/${f}?lang=${typeof document !== 'undefined' && document.documentElement.lang === 'de' ? 'de' : 'en'}`)).text() : ''; }));
      const title = (st?.name || siteName || 'Entwurf').replace(/[<>&]/g, '');
      w.document.write(`<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Grundrisse ${title}</title><style>@page{size:A3 landscape;margin:12mm}body{margin:0;font-family:-apple-system,Helvetica,Arial,sans-serif}.pg{page-break-after:always;display:flex;align-items:center;justify-content:center;height:272mm}.pg svg{max-width:100%;max-height:100%;width:auto;height:auto}</style></head><body>${svgs.filter(Boolean).map((s: string) => `<div class="pg">${s}</div>`).join('')}</body></html>`);
      w.document.close(); w.focus(); setTimeout(() => w.print(), 400);
    } catch { w.close(); setErr('Grundrisse konnten nicht für den PDF-Export geladen werden.'); }
  };

  const ORDER: Record<string, number> = {FAIL: 0, WARN: 1, UNKNOWN: 2, INFO: 3, PASS: 4};
  const rules: any[] = [...(st?.check?.results ?? [])].sort((a, b) => (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9));
  const cnt = rules.reduce((a, r) => { a[r.status] = (a[r.status] ?? 0) + 1; return a; }, {} as Record<string, number>);
  const tr = st?.terrain;
  const stl = (v: any) => (typeof v === 'number' ? v.toFixed(0) : '–');

  return (
    <main className="entw">
      <PS pid={pid} active="entwurf" name={siteName} />
      {err && <div className="entw-error" role="alert">{err}</div>}
      <div className="entw-cols">
        <nav className="entw-rail" aria-label="Seitenleisten" data-open={panel ?? 'none'}>
          <button className={panel === 'chat' ? 'on' : ''} aria-pressed={panel === 'chat'} onClick={() => setPanel((p) => (p === 'chat' ? null : 'chat'))} title="Chat und Bauvorgaben">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H10l-4.5 3.5V17H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" /><circle cx="8.5" cy="11" r="1.1" /><circle cx="12" cy="11" r="1.1" /><circle cx="15.5" cy="11" r="1.1" /></svg>
            <span>Chat</span>
          </button>
          <button className={panel === 'site' ? 'on' : ''} aria-pressed={panel === 'site'} onClick={() => setPanel((p) => (p === 'site' ? null : 'site'))} title="Grundstücksdaten und Bauvorgaben">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5 10 5l5 2.5L20 5v11.5L15 19l-5-2.5L4 19V7.5Z" /><path d="M10 5v11.5M15 7.5V19" /></svg>
            <span>Grundstück</span>
          </button>
          <button className={panel === 'lib' ? 'on' : ''} aria-pressed={panel === 'lib'} onClick={() => setPanel((p) => (p === 'lib' ? null : 'lib'))} title="Bibliothek: Häuser und Objekte">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 3 7.5v9L12 21l9-4.5v-9L12 3Z" /><path d="M3 7.5 12 12l9-4.5M12 12v9" /></svg>
            <span>Bibliothek</span>
          </button>
        </nav>
        <section className={`entw-chat entw-panel${panel === 'chat' ? ' open' : ''}`} aria-label="Entwurf" aria-hidden={panel !== 'chat'}>
          <div className="entw-chead">
            <div className="entw-title">{siteName || st?.name || 'Entwurf'}{version ? ` · Version ${version}` : ''}</div>
          </div>

          <div className="entw-thread">
            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                <div className="bubble-text">{m.text}</div>
                {m.questions?.map((q, k) => <div key={k} className="bubble-q"><span>{q}</span></div>)}
              </div>
            ))}
            {busy && <div className="bubble arch pulse">Arbeite …</div>}
          </div>

          {!hasHouse && (st?.references ?? []).length > 0 && (
            <div className="entw-pending">
              {st.references.map((r: any) => (
                <label key={r.id} className="chip">
                  <input type="checkbox" checked={refSel.includes(r.id)} onChange={(e) => setRefSel((s) => (e.target.checked ? [...s, r.id].slice(0, 4) : s.filter((x) => x !== r.id)))} />
                  {r.name || r.id}
                </label>
              ))}
            </div>
          )}
          <div className="entw-input">
            <textarea value={text} placeholder={hasHouse ? 'Änderung beschreiben …' : 'Haus beschreiben …'} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void send(); }} disabled={busy} />
            <button className="iconbtn primary" onClick={() => void send()} disabled={busy || (!text.trim() && !refSel.length)} aria-label="Senden">➤</button>
          </div>
          {st && !st.engine?.llm && <div className="entw-hint">Kein Sprachmodell erreichbar (Ollama oder BIMRENDER_LLM_URL). Text-Entwurf und Änderungen gehen erst nach der Einrichtung.</div>}

        </section>

        <aside className={`entw-panel entw-sitepanel${panel === 'site' ? ' open' : ''}`} aria-label="Grundstück" aria-hidden={panel !== 'site'}>
          <div className="entw-ptitle">Grundstück</div>
          {(() => {
            const sf = st?.site;
            const eff = sf?.effective ?? {};
            const ref = sf?.reference;
            const LBL: Record<string, string> = {max_storeys: 'Geschosse (max.)', max_height_m: 'Gebäudehöhe (max.)', setback_m: 'Grenzabstand', grz: 'GRZ', gfz: 'GFZ', roof_types: 'Dachform', max_eave_height_m: 'Traufhöhe (max.)', roof_pitch_min_deg: 'Dachneigung ab', roof_pitch_max_deg: 'Dachneigung bis'};
            const UNIT: Record<string, string> = {max_height_m: ' m', setback_m: ' m', max_eave_height_m: ' m', roof_pitch_min_deg: '°', roof_pitch_max_deg: '°'};
            const ROOF_DE: Record<string, string> = {flach: 'Flachdach', sattel: 'Satteldach', walm: 'Walmdach', pult: 'Pultdach', zelt: 'Zeltdach', kegel: 'Kegeldach'};
            const ex: any[] = sf?.existing ?? [];
            return <>
              <div className="entw-sub">Flurstück</div>
              <dl className="entw-facts">
                <dt>Fläche</dt><dd>{sf ? `${Math.round(sf.area_m2).toLocaleString('de-DE')} m²` : '–'}</dd>
                <dt>Flurstücke</dt><dd>{sf?.parcels ?? '–'}</dd>
                <dt>Bestand auf dem Grundstück</dt><dd>{ex.length ? `${ex.length} Gebäude, ${Math.round(ex.reduce((a, e) => a + e.footprint_m2, 0))} m²` : 'keiner'}</dd>
                <dt>Gebäude im Umkreis (60 m)</dt><dd>{sf?.neighbours_60m ?? '–'}</dd>
              </dl>
              {tr && <>
                <div className="entw-sub">Gelände</div>
                <dl className="entw-facts">
                  <dt>Natürliches Gefälle</dt><dd>{typeof tr.natural_slope_pct === 'number' ? `${tr.natural_slope_pct.toLocaleString('de-DE')} %` : '–'}</dd>
                  <dt>Abtrag / Aufschüttung</dt><dd>{typeof tr.cut_m3 === 'number' ? `${stl(tr.cut_m3)} / ${stl(tr.fill_m3)} m³` : '–'}</dd>
                  <dt>Höhenbezug</dt><dd>{tr.height_reference ?? '–'}</dd>
                </dl>
              </>}
              <div className="entw-sub">Rahmen für den Entwurf</div>
              {Object.keys(eff).length ? (
                <ul className="entw-frame">
                  {Object.entries(eff).map(([k, v]: [string, any]) => (
                    <li key={k} className={v.binding ? 'bind' : 'ref'}><b>{LBL[k] ?? k}</b><span>{Array.isArray(v.value) ? v.value.map((x: string) => ROOF_DE[x] ?? x).join(', ') : String(v.value)}{UNIT[k] ?? ''}</span><i>{v.basis === 'USER_LIMIT' ? 'eigene Vorgabe' : v.binding ? 'verbindlich' : 'Richtwert Umgebung'}</i></li>
                  ))}
                </ul>
              ) : <p className="entw-hint">Keine verbindlichen Werte und keine ableitbaren Richtwerte. Unbekannt bleibt unbekannt.</p>}
              <Limits base={base} limits={sf?.limits ?? null} onSaved={() => void jfetch(bim).then(apply).catch(() => {})} />
              <Offices req={sf?.request} />
              {ref?.sources?.length ? <ul className="entw-srcs">{ref.sources.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul> : null}
              <div className="entw-sub">Bauvorgaben – Prüfung des Entwurfs{hasHouse ? ` (${['FAIL', 'WARN', 'UNKNOWN', 'PASS'].filter((k) => cnt[k]).map((k) => `${cnt[k]} ${STATUS_DE[k]}`).join(', ')})` : ''}</div>
              {hasHouse ? (
                <ul className="entw-rules">
                  {rules.map((r) => <li key={r.id} className={`st-${r.status}`}><b>{r.label_de}</b><span>{ruleText(r)}</span></li>)}
                </ul>
              ) : <p className="entw-hint">Die Prüfung erscheint, sobald ein Haus entworfen ist.</p>}
            </>;
          })()}
        </aside>

        <aside className={`entw-panel entw-libpanel${panel === 'lib' ? ' open' : ''}`} aria-label="Bibliothek" aria-hidden={panel !== 'lib'}>
          <div className="entw-ptitle">Bibliothek</div>
          <nav className="entw-libtabs" aria-label="Kategorien">
            {['Gebäude', ...cats.map((c) => c.name)].map((n) => <button key={n} aria-pressed={libTab === n} onClick={() => setLibTab(n)}>{n}</button>)}
          </nav>
          <div className="entw-libgrid">
            {libTab === 'Gebäude'
              ? lib.map((h) => (
                <button key={h.id} className="lib-card" disabled={busy} draggable={!busy} title={`${h.description} – klicken oder auf das Grundstück ziehen`} onDragStart={(e) => { libraryDrag.current = 'house'; e.dataTransfer.setData('application/x-archaitect-house', h.id); e.dataTransfer.effectAllowed = 'copy'; }} onDragEnd={() => { libraryDrag.current = null; sc.current?.clearLibraryPreview(); }} onClick={() => { setPanel(null); void fromLib(h.id); }}>
                  <Thumb base={bim} id={h.id} label={h.name} /><span>{h.name}</span>
                </button>
              ))
              : cats.find((c) => c.name === libTab)?.items.map(([kind, , label]) => (
                <div key={kind} className={`lib-card${hasHouse && !busy ? ' drag' : ' off'}`} draggable={hasHouse && !busy} title={`${label} auf das Grundstück ziehen`}
                  onDragEnd={() => { libraryDrag.current = null; sc.current?.clearLibraryPreview(); }}
                  onDragStart={(e) => { libraryDrag.current = kind; e.dataTransfer.setData('application/x-archaitect-object', kind); e.dataTransfer.effectAllowed = 'copy'; const im = e.currentTarget.querySelector('img'); if (im) e.dataTransfer.setDragImage(im, 60, 45); }}>
                  <Thumb base={bim} id={kind} label={label} /><span>{label}</span>
                </div>
              ))}
          </div>
        </aside>

        <section className="entw-view" aria-label="360°-Ansicht">
          <div className="entw-vhead">
            <div className="seg">
              <button className={spin ? 'on' : ''} onClick={() => setSpin((v) => !v)}>Drehen</button>
              {hasHouse && <button onClick={() => sc.current?.frameHouse?.()}>Haus</button>}
              {hasHouse && <button className={explode ? 'on' : ''} onClick={toggleExplode} title="Geschosse und Dach auseinanderfahren">Auseinander</button>}
              {hasHouse && <button onClick={() => { setShowPlans(true); if (!plans) void loadPlans(); }}>Grundrisse</button>}
              {hasHouse && <button className={showPhotos ? 'on' : ''} onClick={openPhotos}>Bilderwelt</button>}
              <button className={showDesigns ? 'on' : ''} onClick={openDesigns}>Versionen</button>
            </div>
          </div>
          {hasHouse && <button className="entw-undo" disabled={busy || version < 2} onClick={() => void undo()} title="Rückgängig" aria-label="Rückgängig">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5" /><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11" /></svg>
          </button>}
          {showPhotos && (
            <div className="entw-designs entw-photos">
              <div className="entw-lib-h">Bilderwelt – 4 Bilder in 4K</div>
              <p className="entw-phint">Hauptansicht, zwei Close-ups, Lageansicht. Das Meta-Bildmodell macht aus dem maßgenauen 3D-Modell Fotos; am Grundstücksrand liegt Nebel. Dauer je Bild etwa 30–60 s.</p>
              <div className="entw-pgrid">
                {['main', 'close1', 'close2', 'aerial'].map((id) => {
                  const s = photos?.shots?.[id] ?? {};
                  const lab = photos?.labels?.[id];
                  return (
                    <div key={id} className="entw-pslot">
                      <div className="entw-pimg">
                        {s.image ? <img src={`${bim}/photos/${id}?t=${Math.round(s.time ?? 0)}`} alt={lab?.label} onClick={() => setZoomImg(`${bim}/photos/${id}?t=${Math.round(s.time ?? 0)}`)} /> : <span>{s.status && s.status !== 'queued' || photos?.status === 'running' ? 'wird erzeugt …' : 'noch kein Bild'}</span>}
                      </div>
                      <div className="entw-pcap"><b>{lab?.label ?? id}</b>
                        {s.status === 'failed' && <i title={s.error}> Fehler</i>}
                        {s.image && <a href={`${bim}/photos/${id}`} download={`${id}_4k.jpg`}> ⬇</a>}
                        <button disabled={busy || photos?.status === 'running'} onClick={() => void makePhotos([id])} title="Nur dieses Bild neu erzeugen">neu</button>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="entw-pbtns">
                <button disabled={busy || photos?.status === 'running'} onClick={() => void makePhotos()}>{photos?.status === 'running' ? 'Erzeuge …' : 'Alle 4 Bilder erzeugen'}</button>
                {Object.values(photos?.shots ?? {}).some((x: any) => x?.image) && <a className="seg-link" href={`${bim}/photos/export`}>Alle als ZIP exportieren</a>}
              </div>
              {photos?.error && <p className="entw-phint">{photos.error}</p>}
              {photos?.version && photos?.current_version && photos.version !== photos.current_version && <p className="entw-phint">Die Bilder stammen von Version {photos.version}, der Entwurf ist inzwischen Version {photos.current_version}.</p>}
            </div>
          )}
          {showDesigns && (
            <div className="entw-designs">
              <div className="entw-lib-h">{`Versionen (${vers.length})`}</div>
              <div className="entw-dlist">
                {vers.map((v) => (
                  <button key={v.version} disabled={busy || v.version === version} onClick={() => void restore(v.version)} title={v.time}>
                    <b>Version {v.version}{v.version === version ? ' (aktuell)' : ''}</b> {v.note || '–'}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="entw-stage" style={showRender ? {display: 'none'} : undefined}>
            <div className="entw-canvas" ref={box} onDragOver={(e) => { if (e.dataTransfer.types.includes('application/x-archaitect-house')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; const point = sc.current?.siteAtScreen(e.clientX, e.clientY); if (point) sc.current?.previewLibraryObject('house', point.x, point.y); else sc.current?.clearLibraryPreview(); return; } if (e.dataTransfer.types.includes('application/x-archaitect-object')) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; const point = sc.current?.siteAtScreen(e.clientX, e.clientY); if (point && libraryDrag.current) sc.current?.previewLibraryObject(libraryDrag.current, point.x, point.y); else sc.current?.clearLibraryPreview(); } }} onDragLeave={() => sc.current?.clearLibraryPreview()} onDrop={(e) => {
              sc.current?.clearLibraryPreview();
              const houseId = e.dataTransfer.getData('application/x-archaitect-house');
              if (houseId && !busy) {
                e.preventDefault();
                const hp = sc.current?.siteAtScreen(e.clientX, e.clientY);
                if (!hp) { setErr('Bitte das Haus auf dem sichtbaren Grundstück ablegen.'); return; }
                void fromLib(houseId, hp);
                return;
              }
              const kind = e.dataTransfer.getData('application/x-archaitect-object');
              if (!cats.some((c) => c.items.some((item) => item[0] === kind)) || busy) return;
              e.preventDefault();
              const point = sc.current?.siteAtScreen(e.clientX, e.clientY);
              if (!point) { setErr('Bitte das Objekt auf dem sichtbaren Grundstück ablegen.'); return; }
              void run(async () => { apply(await post(`${bim}/objects`, {kind, ...point})); });
            }} />
            {selId && (() => {
              const o = objs.find((x) => x.id === selId);
              return (
                <div className="entw-sel" role="toolbar" aria-label="Auswahl">
                  <b>{o?.label ?? 'Objekt'}</b>
                  {o?.kind === 'house' && <>
                    <button disabled={busy} className="rot" onPointerDown={() => startRot(1)} onPointerUp={stopRot} onPointerLeave={stopRot} onPointerCancel={stopRot} title="Gedrückt halten: gegen den Uhrzeigersinn drehen (erst langsam, dann schneller)">⟲</button>
                    <button disabled={busy} className="rot" onPointerDown={() => startRot(-1)} onPointerUp={stopRot} onPointerLeave={stopRot} onPointerCancel={stopRot} title="Gedrückt halten: im Uhrzeigersinn drehen (erst langsam, dann schneller)">⟳</button>
                    <button disabled={busy} className={partMode ? 'on' : ''} onClick={() => { const v = !partMode; setPartMode(v); setPartVol(null); sc.current?.setPartMode?.(v); sc.current && (sc.current.partMode = v); }} title="Einzelne Bauteile anklicken (z. B. Dachaufbau, Garage)">Bauteil</button>
                    {partMode && partVol && <>
                      <button disabled={busy} onClick={() => run(async () => { apply(await jfetch(`${bim}/volumes/${encodeURIComponent(partVol)}/delete`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})); setPartVol(null); sc.current?.setPartVol?.(null); })}>Bauteil löschen</button>
                      <button disabled={busy} onClick={() => run(async () => { apply(await jfetch(`${bim}/volumes/${encodeURIComponent(partVol)}/detach`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})); setPartVol(null); sc.current?.setPartVol?.(null); })}>Eigenes Gebäude</button>
                    </>}
                  </>}
                  {o?.kind === 'sauna_hut' && <>
                    <button disabled={busy} className="rot" onClick={() => turnSel(1)} title="Um 90° gegen den Uhrzeigersinn drehen (Tür zeigt dann in die nächste Richtung)">⟲</button>
                    <button disabled={busy} className="rot" onClick={() => turnSel(-1)} title="Um 90° im Uhrzeigersinn drehen">⟳</button>
                  </>}
                  <button disabled={busy} onClick={removeSel} title="Objekt löschen">Löschen</button>
                  <button onClick={() => { setSelId(null); sc.current?.setSelected?.(null); }} title="Auswahl aufheben" aria-label="Auswahl aufheben">✕</button>
                </div>
              );
            })()}
            {(loading || busy || meshBusy) && (
              <div className="entw-loading">
                {busy && !loading ? (() => {
                  const el = Math.max(0, (nowT - busyT0) / 1000), design = busyLabel === 'Haus wird entworfen';
                  const pct = Math.min(95, Math.round(100 * (1 - Math.exp(-el / (design ? 30 : 5)))));
                  return (
                    <div className="entw-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                      <div>{busyLabel} … {Math.round(el)} s{design ? ' (meist 30–60 s)' : ''}</div>
                      <div className="entw-bar"><span style={{width: `${pct}%`}} /></div>
                    </div>
                  );
                })() : loading ? 'Laden …' : '3D-Modell lädt …'}
              </div>
            )}
          </div>
          {meshErr && <div className="entw-error">{meshErr}</div>}
          {showRender && <>
          {hasHouse && (
            <div className="entw-vfoot">
              <select value={camera} onChange={(e) => setCamera(e.target.value)} aria-label="Kamera">
                {(st?.cameras ?? []).map((c: string) => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={quality} onChange={(e) => setQuality(e.target.value)} aria-label="Qualität">
                {QUALITIES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
              <button className="primary" disabled={busy || !st?.engine?.blender} onClick={() => void startRender()}>Foto rendern (Blender)</button>
              {!st?.engine?.blender && <span className="entw-hint">Blender nicht gefunden.</span>}
            </div>
          )}
          {(() => {
            const done = renders.filter((r) => r.status === 'done');
            const open = renders.filter((r) => r.status !== 'done' && r.status !== 'cancelled');
            const big = done.find((r) => r.id === bigId) ?? done[0];
            return (
              <div className="entw-renders">
                {open.map((r) => (
                  <div key={r.id} className="entw-rjob">
                    {r.status === 'failed' ? `Fehler: ${r.error ?? ''}` : r.status === 'running' ? `Render läuft … (v${r.version} · ${r.camera})` : 'Render wartet …'}
                    {(r.status === 'queued' || r.status === 'running') && <button className="linkbtn" onClick={() => void cancelRender(r.id)}>Abbrechen</button>}
                  </div>
                ))}
                {big ? (
                  <figure className="entw-rbig">
                    <button onClick={() => setZoomImg(`${bim}/renders/${big.id}/image`)} title="Vollbild">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`${bim}/renders/${big.id}/image`} alt={`Render Version ${big.version}`} />
                    </button>
                    <figcaption>v{big.version} · {big.camera} · {big.quality} · {big.seconds ?? '?'} s · Klick = Vollbild</figcaption>
                  </figure>
                ) : <div className="entw-hint">Noch kein Render – „Foto rendern“ starten.</div>}
                {done.length > 1 && (
                  <div className="entw-rthumbs">
                    {done.slice(0, 12).map((r) => (
                      <button key={r.id} className={r.id === big?.id ? 'on' : ''} onClick={() => setBigId(r.id)} title={`v${r.version} · ${r.camera} · ${r.quality}`}>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={`${bim}/renders/${r.id}/image`} alt={`v${r.version}`} />
                        <span>v{r.version} · {r.camera}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}
          </>}
        </section>
      </div>
      {showPlans && (
        <div className="entw-loading entw-modal" role="dialog" aria-label="Grundrisse" onClick={() => { setShowPlans(false); setPlanUrl(null); }}>
          <div className="entw-win plan-win" onClick={(e) => e.stopPropagation()}>
            <div className="plan-main">
              <div className="entw-winhead"><b>Grundrisse</b><span className="plan-gap" />
                <button className="secondary" disabled={!plans?.length} onClick={() => void printPlans()}>Als PDF sichern</button>
                <button className="secondary" onClick={() => { setShowPlans(false); setPlanUrl(null); }}>Schließen</button></div>
              {planUrl ? /* eslint-disable-next-line @next/next/no-img-element */ <img className="entw-plan" src={planUrl} alt="Grundriss" /> : <div className="entw-hint">{plans ? 'Plan wählen.' : 'Lade …'}</div>}
            </div>
            <nav className="plan-side" aria-label="Geschosse">
              {[...(plans ?? [])].map((p: any, i: number) => ({p, i})).reverse().map(({p, i}) => { const f = String(p.svg ?? '').split('/').pop(); const url = f ? `${bim}/plans/${version}/${f}?lang=${typeof document !== 'undefined' && document.documentElement.lang === 'de' ? 'de' : 'en'}` : null; return url ? <button key={i} className={planUrl === url ? 'on' : ''} onClick={() => setPlanUrl(url)}>{p.storey ?? `Plan ${i + 1}`}</button> : null; })}
            </nav>
          </div>
        </div>
      )}
      {zoomImg && (
        <div className="entw-loading" style={{position: 'fixed', zIndex: 50, cursor: 'zoom-out'}} onClick={() => setZoomImg(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={zoomImg} alt="Render" style={{maxWidth: '96vw', maxHeight: '94vh'}} />
        </div>
      )}
    </main>
  );
}

function Keyed() {
  const pid = useSearchParams().get('p') ?? '';
  if (!pid) return <main className="entw"><p>Kein Projekt gewählt.</p></main>;
  return <Workspace key={pid} pid={pid} />;
}

export default function Page() {
  return (
    <Suspense fallback={<main className="entw"><p>Laden …</p></main>}>
      <Keyed />
    </Suspense>
  );
}
