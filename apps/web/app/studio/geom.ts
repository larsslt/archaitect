/* Massing model of the studio (mirrors apps/api/archaitect/siteintel/massing.py) and the client-side hard-limit check used while dragging and sliding.
   The server stays the authority (regs.evaluate); this file only keeps the editor from ever showing a state that leaves the plot or breaks a
   verified B-Plan value. Local frame: x East, y North, metres. */

export type RoofType = 'flach' | 'sattel' | 'walm' | 'pult' | 'zelt' | 'kegel';
export type Shape = 'rect' | 'round' | 'poly';
export type Role = 'main' | 'annex' | 'garage';
export type Volume = {
  id: string; name: string; role: Role; shape: Shape; cx: number; cy: number; width_m: number; depth_m: number; rotation_deg: number; points: number[][] | null;
  elevation_m: number; storeys: number; storey_height_m: number; roof: RoofType; roof_pitch_deg: number; ridge_along: 'width' | 'depth'; facade_de: string; roof_material_de: string;
};
export type Massing = {version: number; volumes: Volume[]; demolish: string[]; source: 'manual' | 'ai' | 'suggest' | 'initial'; prompt_de: string; notes_de: string[]};
export type Limits = {
  region: number[][][]; holes: number[][][]; site_area_m2: number; max_footprint_main_m2: number | null; max_footprint_all_m2: number | null; max_gfa_m2: number | null;
  max_storeys: number | null; max_height_m: number | null; max_eave_m: number | null; roofs_allowed: string[] | null; pitch_min_deg: number | null; pitch_max_deg: number | null;
  basis?: Record<string, 'BPLAN_VERIFIED' | 'USER_LIMIT' | null>;
};
export type RuleResult = {id: string; label_de: string; status: 'PASS' | 'FAIL' | 'WARN' | 'UNKNOWN' | 'INFO'; basis: 'PARCEL_GEOMETRY' | 'BPLAN_VERIFIED' | 'USER_LIMIT' | 'HBO_DERIVED' | 'CONTEXT'; hard: boolean; message_de: string; source_de: string | null};
export type Check = {
  overall: 'PASS' | 'FAIL' | 'WARN' | 'UNKNOWN'; hard_ok: boolean; results: RuleResult[];
  metrics: {footprint_m2: number; footprint_main_m2: number; gross_floor_area_m2: number; max_storeys: number; top_m: number; volumes: number; site_area_m2: number; grz: number; gfz: number; kept_existing_footprint_m2: number};
  overlays: {abstandsflaechen: {volume_id: string; ring: number[][]; H_m: number; depth_m: number; ok: boolean}[]; violations: number[][][]; road_allowance: number[][][]};
  limits: Limits; disclaimer_de: string;
};

export const ROOF_DE: Record<RoofType, string> = {flach: 'Flachdach', sattel: 'Satteldach', walm: 'Walmdach', pult: 'Pultdach', zelt: 'Zeltdach', kegel: 'Kegeldach'};
export const ROOFS_BY_SHAPE: Record<Shape, RoofType[]> = {rect: ['sattel', 'walm', 'pult', 'zelt', 'flach'], round: ['kegel', 'flach'], poly: ['flach']};
export const PLINTH_M = 0.3;

export function footprint(v: Volume): number[][] {
  if (v.shape === 'poly' && v.points && v.points.length >= 3) return v.points.map((p) => [p[0], p[1]]);
  if (v.shape === 'round') {
    const r = v.width_m / 2; const n = 64;
    return Array.from({length: n}, (_, i) => [v.cx + r * Math.cos((2 * Math.PI * i) / n), v.cy + r * Math.sin((2 * Math.PI * i) / n)]);
  }
  const a = (v.rotation_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a), w = v.width_m / 2, d = v.depth_m / 2;
  return [[-w, -d], [w, -d], [w, d], [-w, d]].map(([x, y]) => [v.cx + x * c - y * s, v.cy + x * s + y * c]);
}
export const eave = (v: Volume) => PLINTH_M + v.storeys * v.storey_height_m;
export function span(v: Volume): number {
  if (v.shape === 'round') return v.width_m / 2;
  if (v.shape === 'poly') return 0;
  const perp = v.ridge_along === 'width' ? v.depth_m : v.width_m;
  if (v.roof === 'sattel' || v.roof === 'walm') return perp / 2;
  if (v.roof === 'pult') return perp;
  if (v.roof === 'zelt') return Math.min(v.width_m, v.depth_m) / 2;
  return 0;
}
export const rise = (v: Volume) => (v.roof === 'flach' ? 0 : Math.tan((v.roof_pitch_deg * Math.PI) / 180) * span(v));
export const top = (v: Volume) => v.elevation_m + eave(v) + rise(v);
export function area(r: number[][]): number { let s = 0; for (let i = 0; i < r.length; i++) { const [x1, y1] = r[i], [x2, y2] = r[(i + 1) % r.length]; s += x1 * y2 - x2 * y1; } return Math.abs(s) / 2; }

function inRing(x: number, y: number, r: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
    const [xi, yi] = r[i], [xj, yj] = r[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function cross(a: number[], b: number[], c: number[], d: number[]): boolean {
  const o = (p: number[], q: number[], r: number[]) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const e = 1e-9; const d1 = o(c, d, a), d2 = o(c, d, b), d3 = o(a, b, c), d4 = o(a, b, d);
  return ((d1 > e && d2 < -e) || (d1 < -e && d2 > e)) && ((d3 > e && d4 < -e) || (d3 < -e && d4 > e));
}
function ringsCross(a: number[][], b: number[][]): boolean {
  for (let i = 0; i < a.length; i++) for (let j = 0; j < b.length; j++) if (cross(a[i], a[(i + 1) % a.length], b[j], b[(j + 1) % b.length])) return true;
  return false;
}
/** Footprint completely inside one region polygon and outside every hole (kept buildings). Shrinks the footprint by 2 cm like the server tolerance. */
export function insideRegion(fp: number[][], lim: Limits): boolean {
  const cx = fp.reduce((s, p) => s + p[0], 0) / fp.length, cy = fp.reduce((s, p) => s + p[1], 0) / fp.length;
  const f = fp.map(([x, y]) => { const dx = x - cx, dy = y - cy, l = Math.hypot(dx, dy) || 1; const k = Math.max(0, l - 0.02) / l; return [cx + dx * k, cy + dy * k]; });
  const outer = lim.region.map((r) => (r.length > 1 && r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1] ? r.slice(0, -1) : r));
  const host = outer.find((r) => f.every(([x, y]) => inRing(x, y, r)) && !ringsCross(f, r));
  if (!host) return false;
  for (const h of lim.holes) { if (ringsCross(f, h) || f.some(([x, y]) => inRing(x, y, h)) || h.some(([x, y]) => inRing(x, y, f))) return false; }
  return true;
}

/** Vollgeschosse counted from the ground (mirrors massing.effective_storeys): a raised volume adds its storeys to the highest support below it. */
export function effectiveStoreys(vols: Volume[]): Record<string, number> {
  const order = [...vols].sort((a, b) => a.elevation_m - b.elevation_m);
  const fp = Object.fromEntries(vols.map((v) => [v.id, footprint(v)]));
  const eff: Record<string, number> = {};
  for (const v of order) {
    let base = 0;
    if (v.elevation_m > 0.5) {
      for (const w of order) {
        if (w.id === v.id || !(w.id in eff) || w.elevation_m >= v.elevation_m) continue;
        if (overlaps(fp[w.id], fp[v.id]) && w.elevation_m + eave(w) <= v.elevation_m + 0.6) base = Math.max(base, eff[w.id]);
      }
      if (base === 0) base = Math.floor(Math.max(0, v.elevation_m - PLINTH_M) / 2.4);
    }
    eff[v.id] = base + v.storeys;
  }
  return eff;
}
function overlaps(a: number[][], b: number[][]): boolean { return ringsCross(a, b) || a.some(([x, y]) => inRing(x, y, b)) || b.some(([x, y]) => inRing(x, y, a)); }

const src = (lim: Limits, k: string) => (lim.basis?.[k] === 'USER_LIMIT' ? 'eigene Vorgabe' : 'Bebauungsplan');

/** All hard-rule violations the editor can decide on its own (geometry + per-volume numbers). GRZ/GFZ come from the server check. */
export function violations(m: Massing, lim: Limits | null): string[] {
  if (!lim) return [];
  const out: string[] = [];
  const eff = effectiveStoreys(m.volumes);
  for (const v of m.volumes) {
    if (!insideRegion(footprint(v), lim)) out.push(`${v.name} läge außerhalb des bebaubaren Bereichs (Flurstück, Bestand, Baufenster).`);
    if (lim.max_storeys && eff[v.id] > lim.max_storeys) out.push(`Höchstens ${lim.max_storeys} Vollgeschosse (${src(lim, 'max_storeys')})${eff[v.id] > v.storeys ? ' – gestapelte Baukörper zählen zusammen' : ''}.`);
    if (lim.max_height_m && top(v) > lim.max_height_m + 1e-6) out.push(`Gebäudehöhe höchstens ${lim.max_height_m.toFixed(1).replace('.', ',')} m (${src(lim, 'max_height_m')}).`);
    if (lim.max_eave_m && v.elevation_m + eave(v) > lim.max_eave_m + 1e-6) out.push(`Traufhöhe höchstens ${lim.max_eave_m.toFixed(1).replace('.', ',')} m (${src(lim, 'max_eave_m')}).`);
    if (v.role !== 'garage' && lim.roofs_allowed && !lim.roofs_allowed.includes(v.roof)) out.push(`${ROOF_DE[v.roof]} ist nicht zulässig (${src(lim, 'roofs_allowed')}).`);
    if (v.role !== 'garage' && v.roof !== 'flach' && lim.pitch_min_deg != null && v.roof_pitch_deg < lim.pitch_min_deg - 1e-6) out.push(`Dachneigung mindestens ${lim.pitch_min_deg}° (${src(lim, 'pitch')}).`);
    if (v.role !== 'garage' && v.roof !== 'flach' && lim.pitch_max_deg != null && v.roof_pitch_deg > lim.pitch_max_deg + 1e-6) out.push(`Dachneigung höchstens ${lim.pitch_max_deg}° (${src(lim, 'pitch')}).`);
  }
  return out;
}
export function localViolation(m: Massing, lim: Limits | null): string | null { return violations(m, lim)[0] ?? null; }

const NUM: (keyof Volume)[] = ['cx', 'cy', 'width_m', 'depth_m', 'rotation_deg', 'elevation_m', 'storey_height_m', 'roof_pitch_deg'];
function lerpVol(a: Volume, b: Volume, t: number): Volume {
  const o: any = {...b}; // eslint-disable-line @typescript-eslint/no-explicit-any
  for (const k of NUM) o[k] = (a[k] as number) + ((b[k] as number) - (a[k] as number)) * t;
  if (a.points && b.points && a.points.length === b.points.length) o.points = a.points.map((p, i) => [p[0] + (b.points![i][0] - p[0]) * t, p[1] + (b.points![i][1] - p[1]) * t]);
  return o;
}
/** Apply a change but stop at the limit: valid -> as is; continuous change -> the furthest valid point on the way (bisection); otherwise rejected. */
export function clampChange(prev: Massing, next: Massing, lim: Limits | null): {m: Massing; blocked: string | null} {
  const nv = violations(next, lim), why = nv[0] ?? null;
  if (!why) return {m: next, blocked: null};
  // Already in violation (limits changed after the design was made): a change is allowed only if it removes violations and adds none,
  // so the user can walk back into the rules but never further out.
  const pv = violations(prev, lim);
  if (pv.length) return nv.length <= pv.length && nv.every((x) => pv.includes(x)) ? {m: next, blocked: null} : {m: prev, blocked: why};
  if (prev.volumes.length !== next.volumes.length || prev.volumes.some((v, i) => v.id !== next.volumes[i].id || v.shape !== next.volumes[i].shape || v.roof !== next.volumes[i].roof || v.storeys !== next.volumes[i].storeys)) {
    return {m: prev, blocked: why};
  }
  let lo = 0, hi = 1;
  const at = (t: number): Massing => ({...next, volumes: next.volumes.map((v, i) => lerpVol(prev.volumes[i], v, t))});
  for (let k = 0; k < 18; k++) { const mid = (lo + hi) / 2; if (localViolation(at(mid), lim)) hi = mid; else lo = mid; }
  return {m: at(lo), blocked: why};
}

export function moveVolume(v: Volume, dx: number, dy: number): Volume {
  return {...v, cx: v.cx + dx, cy: v.cy + dy, points: v.points ? v.points.map(([x, y]) => [x + dx, y + dy]) : null};
}

let seq = 0;
export function newVolume(kind: 'annex' | 'garage' | 'tower' | 'main', near: Volume | undefined, ids: string[]): Volume {
  let id = '';
  do { seq += 1; id = `v${Date.now().toString(36).slice(-3)}${seq}`; } while (ids.includes(id));
  const base: Volume = {id, name: 'Anbau', role: 'annex', shape: 'rect', cx: near ? near.cx : 0, cy: near ? near.cy : 0, width_m: 6, depth_m: 5, rotation_deg: near?.rotation_deg ?? 0, points: null,
    elevation_m: 0, storeys: 1, storey_height_m: 2.9, roof: 'flach', roof_pitch_deg: 0, ridge_along: 'width', facade_de: near?.facade_de ?? '', roof_material_de: ''};
  if (kind === 'garage') return {...base, name: 'Garage', role: 'garage', width_m: 6, depth_m: 3.5, storey_height_m: 2.6};
  if (kind === 'tower') return {...base, name: 'Turm', role: 'main', shape: 'round', width_m: 4.5, depth_m: 4.5, storeys: Math.max(2, (near?.storeys ?? 2) + 1), roof: 'kegel', roof_pitch_deg: 45};
  if (kind === 'main') return {...base, name: 'Baukörper', role: 'main', width_m: 10, depth_m: 8, storeys: 2, roof: 'sattel', roof_pitch_deg: 35};
  return base;
}
