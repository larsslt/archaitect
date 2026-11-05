'use client';
import {useEffect, useState} from 'react';

/** Eigene Bauvorgaben (GRZ, GFZ, Höhe, Geschosse, Dachform ...) aus dem Bebauungsplan oder einer Auskunft des Bauamts.
 *  Wird als „eigene Planungsvorgabe, nicht als Bebauungsplan geprüft“ gespeichert und im Entwurf geprüft. Leer lassen = unbekannt. */
const ROOFS: [string, string][] = [['flach', 'Flachdach'], ['sattel', 'Satteldach'], ['walm', 'Walmdach'], ['pult', 'Pultdach'], ['zelt', 'Zeltdach']];

type Lim = {grz?: number | null; gfz?: number | null; max_building_height_meters?: number | null; max_stories?: number | null; max_eave_height_meters?: number | null;
  setback_lines_offset_meters?: number | null; roof_types_allowed?: string[]; roof_pitch_min_deg?: number | null; roof_pitch_max_deg?: number | null; note_de?: string} | null;

const num = (s: string): number | null => { const v = parseFloat(s.replace(',', '.')); return Number.isFinite(v) ? v : null; };
const txt = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v).replace('.', ','));

export default function Limits({base, limits, onSaved}: {base: string; limits: Lim; onSaved: () => void}) {
  const [f, setF] = useState<Record<string, string>>({});
  const [roofs, setRoofs] = useState<string[]>([]);
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setF({grz: txt(limits?.grz), gfz: txt(limits?.gfz), h: txt(limits?.max_building_height_meters), st: txt(limits?.max_stories), eave: txt(limits?.max_eave_height_meters),
      sb: txt(limits?.setback_lines_offset_meters), pmin: txt(limits?.roof_pitch_min_deg), pmax: txt(limits?.roof_pitch_max_deg), note: limits?.note_de ?? ''});
    setRoofs(limits?.roof_types_allowed ?? []);
  }, [limits]);
  const set = (k: string, v: string) => setF((s) => ({...s, [k]: v}));
  const save = async (clear = false) => {
    setBusy(true); setMsg('');
    const body = clear ? {} : {grz: num(f.grz ?? ''), gfz: num(f.gfz ?? ''), max_building_height_meters: num(f.h ?? ''), max_stories: num(f.st ?? '') !== null ? Math.round(num(f.st)!) : null,
      max_eave_height_meters: num(f.eave ?? ''), setback_lines_offset_meters: num(f.sb ?? ''), roof_types_allowed: roofs, roof_pitch_min_deg: num(f.pmin ?? ''), roof_pitch_max_deg: num(f.pmax ?? ''), note_de: (f.note ?? '').slice(0, 300)};
    try {
      const r = await fetch(`${base}/limits`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (!r.ok) { const j = await r.json().catch(() => ({})); throw new Error(typeof j.detail === 'string' ? j.detail : 'Werte nicht gespeichert (Wertebereich prüfen).'); }
      setMsg(clear ? 'Eigene Vorgaben entfernt.' : 'Gespeichert. Der Entwurf wird damit geprüft.'); onSaved();
    } catch (e: any) { setMsg(e.message || 'Nicht gespeichert.'); }
    setBusy(false);
  };
  const field = (k: string, lbl: string, ph: string) => (
    <label className="lim-f"><span>{lbl}</span><input inputMode="decimal" value={f[k] ?? ''} placeholder={ph} onChange={(e) => set(k, e.target.value)} /></label>
  );
  return (
    <div className="entw-limits">
      <div className="entw-sub">Eigene Bauvorgaben</div>
      <p className="entw-hint">Aus dem Bebauungsplan oder einer Auskunft des Bauamts selbst eintragen. Wird als „eigene Vorgabe, nicht geprüft“ geführt. Leer = unbekannt.</p>
      <button type="button" className="lim-toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>{open ? 'Eingabe schließen' : 'Werte eintragen'}</button>
      {open && <div className="lim-form">
        <div className="lim-grid">
          {field('grz', 'GRZ', 'z. B. 0,4')}
          {field('gfz', 'GFZ', 'z. B. 1,2')}
          {field('h', 'Gebäudehöhe max. (m)', 'z. B. 10')}
          {field('st', 'Vollgeschosse max.', 'z. B. 2')}
          {field('eave', 'Traufhöhe max. (m)', '')}
          {field('sb', 'Grenzabstand (m)', '')}
          {field('pmin', 'Dachneigung ab (°)', '')}
          {field('pmax', 'Dachneigung bis (°)', '')}
        </div>
        <div className="lim-roofs">
          <span>Zulässige Dachformen</span>
          {ROOFS.map(([k, n]) => <label key={k} className="chip"><input type="checkbox" checked={roofs.includes(k)} onChange={(e) => setRoofs((s) => (e.target.checked ? [...s, k] : s.filter((x) => x !== k)))} />{n}</label>)}
        </div>
        <label className="lim-f wide"><span>Quelle (z. B. B-Plan Nr., Datum der Auskunft)</span><input value={f.note ?? ''} maxLength={300} onChange={(e) => set('note', e.target.value)} /></label>
        <div className="lim-actions">
          <button type="button" disabled={busy} onClick={() => void save(false)}>Speichern</button>
          <button type="button" disabled={busy} onClick={() => void save(true)}>Zurücksetzen</button>
        </div>
      </div>}
      {msg && <p className="entw-hint" role="status">{msg}</p>}
    </div>
  );
}
