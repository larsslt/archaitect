/* 3D scene of the studio. Two views:
   - 'umgebung': official aerial image (DOP20) draped on the DGM1 terrain, neighbours, existing buildings, connection points, the massing; orbit around freely.
   - 'grundstueck': only the plot, cut out along its exact ALKIS boundary (terrain + aerial clipped, earth skirt), edge lengths labelled, the massing on it.
   three.js is vendored (public/vendor/three, MIT) and loaded on demand. World: three X = East, Y = up, Z = -North (project local frame). */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {eave, footprint, rise, type Massing, type Volume} from './geom';

export type SiteData = {
  site: number[][];                                    // exact plot ring (union of the selected parcels)
  envelope: number[][] | null;
  neighbours: number[][][];
  buildings: {id: string; ring: number[][]; height_m: number | null; on_site: boolean}[];
  terrain: {x_west_local: number; y_north_local: number; cell_m: number; cols: number; rows: number; heights_m: (number | null)[][]; z_origin_m: number | null} | null;
  ortho: {url: string; bbox_local: number[]} | null;
  connections: {id: string; kind: string; xy: number[]}[];
  extent: number[];
};
export type Layers = {aerial: boolean; neighbours: boolean; existing: boolean; surroundings: boolean; connections: boolean; envelope: boolean; boundary: boolean; abstand: boolean; labels: boolean};
export type ViewMode = 'umgebung' | 'grundstueck';
export type SceneEvents = {onPart?: (vol: string | null, obj: string) => void; onSelect?: (id: string | null) => void; onDrag?: (id: string, dx: number, dy: number) => void; onDragEnd?: (id?: string) => void};
export type AF = {volume_id: string; ring: number[][]; ok: boolean}[];

const KIND_COLOR: Record<string, string> = {wasser: '#47a5fa', abwasser: '#a1745a', regenwasser: '#4fc3b7', gas: '#f2d04b', strom: '#f28c4b', telekom: '#b58cf2', fernwaerme: '#ff7b7b'};
const KIND_LETTER: Record<string, string> = {wasser: 'W', abwasser: 'A', regenwasser: 'R', gas: 'G', strom: 'S', telekom: 'T', fernwaerme: 'F'};

export async function loadThree(): Promise<any> {
  const url = '/vendor/three/three.module.min.js';
  return import(/* webpackIgnore: true */ url);
}

function facadeColor(s: string): {wall: string; frame: string} {
  const t = s.toLowerCase();
  if (/holz|lärche|douglas|zeder/.test(t)) return {wall: '#a77b52', frame: '#3b2c20'};
  if (/klinker|backstein|ziegel/.test(t)) return {wall: '#9c4f3a', frame: '#2d2a28'};
  if (/sichtbeton|beton/.test(t)) return {wall: '#a9aaa6', frame: '#2b2e33'};
  if (/anthrazit|dunkel|schwarz/.test(t)) return {wall: '#454950', frame: '#1c1e22'};
  if (/glas/.test(t)) return {wall: '#9fb9c9', frame: '#2b3540'};
  if (/naturstein|sandstein/.test(t)) return {wall: '#c8b28f', frame: '#3a332a'};
  return {wall: '#ecebe6', frame: '#38404a'};
}
function roofColor(v: Volume): string {
  const t = v.roof_material_de.toLowerCase();
  if (/grün|begrünt|extensiv/.test(t)) return '#6f8b4c';
  if (/schiefer|anthrazit|dunkel|schwarz/.test(t)) return '#3c4047';
  if (/zink|metall|blech|kupfer/.test(t)) return /kupfer/.test(t) ? '#5e9c86' : '#8d949c';
  if (/ziegel|rot|terracotta/.test(t)) return '#9d4a35';
  return v.roof === 'flach' ? '#7b8088' : '#7a3d30';
}

export class SiteScene {
  T: any; el: HTMLElement; renderer: any; scene: any; camera: any; raf = 0; disposed = false; ev: SceneEvents;
  site: SiteData | null = null; groups: Record<string, any> = {}; houseGroup: any; sunLight: any; hemi: any; ground: any = null; aerialMap: any = null; plot: any = null;
  target: any; sph = {r: 90, theta: 0.9, phi: 2.2}; z0 = 0; zMinSite = 0; heightAt: (x: number, y: number) => number = () => 0; ro: ResizeObserver | null = null; dirty = true;
  dragging: null | {mode: 'rotate' | 'pan' | 'vol'; x: number; y: number; sx?: number; sy?: number; id?: string; last?: any; plane?: number; moved?: boolean} = null;
  pointers = new Map<number, {x: number; y: number}>(); pinch = 0; mode: ViewMode = 'umgebung'; layers: Layers | null = null; demolish = new Set<string>();
  selectFirst = false; selId: string | null = null; pendingSel: string | null = null; selected: string | null = null; massing: Massing | null = null; autoRotate = false; lastT = 0; volMeshes: any[] = [];
  flightKeys = new Set<string>();
  partMode = false; pendingVol: string | null = null;

  constructor(T: any, el: HTMLElement, ev: SceneEvents = {}) {
    this.T = T; this.el = el; this.ev = ev;
    const renderer = new T.WebGLRenderer({antialias: true, preserveDrawingBuffer: true, powerPreference: 'high-performance'});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    renderer.outputColorSpace = T.SRGBColorSpace; renderer.toneMapping = T.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
    el.appendChild(renderer.domElement);
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none;cursor:grab';
    renderer.domElement.tabIndex = 0;
    renderer.domElement.setAttribute('aria-label', '3D-Ansicht: W A S D bewegen, Leertaste aufsteigen, Umschalt absteigen');
    this.renderer = renderer;
    this.scene = new T.Scene(); this.scene.background = new T.Color('#b9c6d3'); this.scene.fog = new T.Fog('#b9c6d3', 300, 1000);
    this.camera = new T.PerspectiveCamera(38, 1, 0.3, 3000);
    this.target = new T.Vector3(0, 0, 0);
    this.hemi = new T.HemisphereLight('#e4edf7', '#5a6270', 0.8); this.scene.add(this.hemi);
    this.sunLight = new T.DirectionalLight('#fff3dc', 2.2); this.sunLight.castShadow = true;
    this.sunLight.shadow.mapSize.set(4096, 4096); this.sunLight.shadow.bias = -0.0003; this.sunLight.shadow.normalBias = 0.04;
    this.scene.add(this.sunLight, this.sunLight.target);
    for (const k of ['terrain', 'plot', 'surroundings', 'existing', 'neighbours', 'boundary', 'envelope', 'connections', 'abstand', 'labels']) { this.groups[k] = new T.Group(); this.scene.add(this.groups[k]); }
    this.houseGroup = new T.Group(); this.scene.add(this.houseGroup);
    this.ro = new ResizeObserver(() => this.resize()); this.ro.observe(el); this.resize();
    const d = renderer.domElement;
    d.addEventListener('pointerdown', this.down); d.addEventListener('pointermove', this.move); d.addEventListener('pointerup', this.up); d.addEventListener('pointercancel', this.up);
    d.addEventListener('wheel', this.wheel, {passive: false}); d.addEventListener('contextmenu', (e: Event) => e.preventDefault());
    window.addEventListener('keydown', this.keyMove);
    window.addEventListener('keyup', this.keyUp); window.addEventListener('blur', this.clearFlight);
    const loop = (t: number) => {
      if (this.disposed) return;
      const elapsed = Math.min(0.05, Math.max(0, (t - (this.lastT || t)) / 1000));
      this.fly(elapsed);
      if (this.autoRotate && !this.dragging) { const dt = Math.min(0.05, (t - (this.lastT || t)) / 1000); this.sph.phi += dt * 0.25; this.placeCamera(); }
      this.lastT = t;
      if (this.dirty) { this.dirty = false; this.renderer.render(this.scene, this.camera); }
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }

  // ------------------------------------------------------------------ helpers
  v3(x: number, y: number, z: number) { return new this.T.Vector3(x, z, -y); }
  invalidate() { this.dirty = true; }
  resize() { const w = this.el.clientWidth || 1, h = this.el.clientHeight || 1; this.renderer.setSize(w, h, false); this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this.invalidate(); }
  placeCamera() {
    const {r, theta, phi} = this.sph; const t = Math.max(0.0001, Math.min(1.52, theta));
    this.camera.position.set(this.target.x + r * Math.sin(t) * Math.sin(phi), this.target.y + r * Math.cos(t), this.target.z + r * Math.sin(t) * Math.cos(phi));
    this.camera.position.y = Math.max(this.camera.position.y, this.heightAt(this.camera.position.x, -this.camera.position.z) + 0.5);
    this.camera.lookAt(this.target); this.invalidate();
  }
  open(r: number[][]) { return r.length > 1 && r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1] ? r.slice(0, -1) : r; }
  dispose3(o: any) { o.traverse?.((c: any) => { c.geometry?.dispose?.(); if (c.material) (Array.isArray(c.material) ? c.material : [c.material]).forEach((m: any) => { if (m.map && m.map !== this.aerialMap) m.map.dispose?.(); m.alphaMap?.dispose?.(); m.bumpMap?.dispose?.(); m.dispose?.(); }); }); }
  clear(g: any) { while (g.children.length) { const c = g.children.pop(); this.dispose3(c); } }

  // ------------------------------------------------------------------ site
  async setSite(site: SiteData) {
    this.site = site;
    for (const k of Object.keys(this.groups)) this.clear(this.groups[k]);
    const tr = site.terrain; this.z0 = tr?.z_origin_m ?? 0;
    if (tr) {
      const H = tr.heights_m.map((row) => row.map((v) => (v == null ? this.z0 : v)));
      this.heightAt = (x, y) => {
        const fx = (x - tr.x_west_local) / tr.cell_m, fy = (tr.y_north_local - y) / tr.cell_m;
        const c = Math.max(0, Math.min(tr.cols - 1.001, fx)), r = Math.max(0, Math.min(tr.rows - 1.001, fy));
        const c0 = Math.floor(c), r0 = Math.floor(r), tx = c - c0, ty = r - r0;
        return (H[r0][c0] * (1 - tx) + H[r0][c0 + 1] * tx) * (1 - ty) + (H[r0 + 1][c0] * (1 - tx) + H[r0 + 1][c0 + 1] * tx) * ty - this.z0;
      };
    } else this.heightAt = () => 0;
    const ring = this.open(site.site);
    this.zMinSite = Math.min(...ring.map(([x, y]) => this.heightAt(x, y)));
    if (site.ortho) {
      try {
        this.aerialMap = await new Promise((res, rej) => { const l = new this.T.TextureLoader(); l.setCrossOrigin('anonymous'); l.load(site.ortho!.url, res, undefined, rej); });
        this.aerialMap.colorSpace = this.T.SRGBColorSpace; this.aerialMap.anisotropy = this.renderer.capabilities.getMaxAnisotropy?.() ?? 8;
      } catch { this.aerialMap = null; }
    }
    this.buildTerrain(site); this.buildPlot(site); this.buildSurroundings(site);
    this.buildOutline('boundary', site.site, '#47a5fa', 0.9);
    if (site.envelope) this.buildOutline('envelope', site.envelope, '#6bd68a', 0.6);
    for (const n of site.neighbours) this.addLine('neighbours', n, '#f2f4f6', 0.45);
    this.buildConnections(site); this.buildLabels(site);
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length, cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
    this.target.copy(this.v3(cx, cy, this.heightAt(cx, cy)));
    const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]); const size = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    this.sph.r = Math.max(55, size * 2.2); this.sph.theta = 0.85;
    const s = size * 1.2 + 45; const sc = this.sunLight.shadow.camera; sc.left = -s; sc.right = s; sc.top = s; sc.bottom = -s; sc.near = 1; sc.far = 800; sc.updateProjectionMatrix();
    this.applyMode(); this.updateSun(); this.placeCamera();
  }

  terrainGeometry(site: SiteData) {
    const T = this.T, tr = site.terrain!, ob = site.ortho?.bbox_local ?? site.extent;
    const pos = new Float32Array(tr.cols * tr.rows * 3), uv = new Float32Array(tr.cols * tr.rows * 2);
    for (let r = 0; r < tr.rows; r++) for (let c = 0; c < tr.cols; c++) {
      const x = tr.x_west_local + c * tr.cell_m, y = tr.y_north_local - r * tr.cell_m, i = r * tr.cols + c;
      pos.set([x, this.heightAt(x, y), -y], i * 3); uv.set([(x - ob[0]) / (ob[2] - ob[0]), (y - ob[1]) / (ob[3] - ob[1])], i * 2);
    }
    const idx: number[] = [];
    for (let r = 0; r < tr.rows - 1; r++) for (let c = 0; c < tr.cols - 1; c++) { const a = r * tr.cols + c, b = a + 1, d = a + tr.cols, e = d + 1; idx.push(a, d, b, b, d, e); }
    const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setAttribute('uv', new T.BufferAttribute(uv, 2)); geo.setIndex(idx); geo.computeVertexNormals();
    return geo;
  }
  flatGeometry(site: SiteData) {
    const ob = site.ortho?.bbox_local ?? site.extent; const g = new this.T.PlaneGeometry(ob[2] - ob[0], ob[3] - ob[1], 1, 1);
    g.rotateX(-Math.PI / 2); g.translate((ob[0] + ob[2]) / 2, 0, -(ob[1] + ob[3]) / 2); return g;
  }
  buildTerrain(site: SiteData) {
    const geo = site.terrain ? this.terrainGeometry(site) : this.flatGeometry(site);
    const mat = new this.T.MeshStandardMaterial({map: this.aerialMap, color: this.aerialMap ? '#ffffff' : '#5b6b57', roughness: 1, metalness: 0});
    const mesh = new this.T.Mesh(geo, mat); mesh.receiveShadow = true; this.ground = mesh; this.groups.terrain.add(mesh);
  }

  /** Plot cut out along the exact boundary: same terrain/aerial with an alpha mask drawn from the plot ring, plus an earth skirt below the edge. */
  buildPlot(site: SiteData) {
    const T = this.T, ob = site.ortho?.bbox_local ?? site.extent, ring = this.open(site.site);
    const N = 2048, cv = document.createElement('canvas'); cv.width = cv.height = N; const g = cv.getContext('2d')!;
    g.fillStyle = '#000'; g.fillRect(0, 0, N, N); g.fillStyle = '#fff'; g.beginPath();
    ring.forEach(([x, y], i) => { const px = ((x - ob[0]) / (ob[2] - ob[0])) * N, py = (1 - (y - ob[1]) / (ob[3] - ob[1])) * N; if (i) g.lineTo(px, py); else g.moveTo(px, py); });
    g.closePath(); g.fill();
    const alpha = new T.CanvasTexture(cv); alpha.flipY = true;
    const geo = site.terrain ? this.terrainGeometry(site) : this.flatGeometry(site);
    const mat = new T.MeshStandardMaterial({map: this.aerialMap, color: this.aerialMap ? '#ffffff' : '#6d7f5f', alphaMap: alpha, alphaTest: 0.5, roughness: 1, side: T.DoubleSide});
    const top = new T.Mesh(geo, mat); top.receiveShadow = true; top.position.y = 0.01; this.groups.plot.add(top);
    // skirt
    const pts: number[][] = [];
    for (let i = 0; i < ring.length; i++) { const a = ring[i], b = ring[(i + 1) % ring.length]; const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25)); for (let k = 0; k < n; k++) pts.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]); }
    const bottom = this.zMinSite - 6, pos: number[] = [], idx: number[] = [];
    pts.forEach(([x, y], i) => { pos.push(x, this.heightAt(x, y), -y, x, bottom, -y); const j = (i + 1) % pts.length; idx.push(i * 2, i * 2 + 1, j * 2, j * 2, i * 2 + 1, j * 2 + 1); });
    const sg = new T.BufferGeometry(); sg.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); sg.setIndex(idx); sg.computeVertexNormals();
    const skirt = new T.Mesh(sg, new T.MeshStandardMaterial({color: '#9a7b57', emissive: '#2a1f14', roughness: 1, side: T.DoubleSide})); skirt.userData.parcelSkirt = true; this.groups.plot.add(skirt);
    const shape = new T.Shape(); ring.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
    const base = new T.Mesh(new T.ShapeGeometry(shape), new T.MeshStandardMaterial({color: '#4f3f30', roughness: 1, side: T.DoubleSide})); base.rotation.x = -Math.PI / 2; base.position.y = bottom; this.groups.plot.add(base);
    this.groups.plot.add(new T.LineLoop(new T.BufferGeometry().setFromPoints(pts.map(([x, y]) => this.v3(x, y, this.heightAt(x, y) + 0.04))), new T.LineBasicMaterial({color: '#ffffff'})));
  }

  /** Edge lengths of the exact plot boundary (ALKIS coordinates, metres with two decimals). */
  buildLabels(site: SiteData) {
    const ring = this.open(site.site); const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length, cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i], b = ring[(i + 1) % ring.length]; const L = Math.hypot(b[0] - a[0], b[1] - a[1]); if (L < 1.5) continue;
      const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2; const dx = mx - cx, dy = my - cy, dl = Math.hypot(dx, dy) || 1;
      const sp = this.textSprite(`${L.toFixed(2).replace('.', ',')} m`); sp.position.copy(this.v3(mx + (dx / dl) * 1.6, my + (dy / dl) * 1.6, this.heightAt(mx, my) + 1.2)); this.groups.labels.add(sp);
    }
  }
  textSprite(text: string, bg = 'rgba(17,17,18,.82)', fg = '#ffffff') {
    const T = this.T, cv = document.createElement('canvas'), g = cv.getContext('2d')!; const f = 34; g.font = `600 ${f}px system-ui, sans-serif`;
    const w = Math.ceil(g.measureText(text).width) + 28; cv.width = w; cv.height = f + 22; g.font = `600 ${f}px system-ui, sans-serif`;
    g.fillStyle = bg; const r = 14; g.beginPath(); g.roundRect?.(0, 0, w, cv.height, r); if (!g.roundRect) g.rect(0, 0, w, cv.height); g.fill();
    g.fillStyle = fg; g.textBaseline = 'middle'; g.fillText(text, 14, cv.height / 2 + 1);
    const tex = new T.CanvasTexture(cv); tex.colorSpace = T.SRGBColorSpace;
    const sp = new T.Sprite(new T.SpriteMaterial({map: tex, depthTest: false, transparent: true})); const h = 1.15; sp.scale.set((h * w) / cv.height, h, 1); sp.renderOrder = 20; return sp;
  }

  buildSurroundings(site: SiteData) {
    const T = this.T;
    const nm = new T.MeshStandardMaterial({color: '#d9dde3', roughness: 0.95});
    for (const b of site.buildings) {
      const ring = this.open(b.ring); if (ring.length < 3) continue;
      const base = Math.min(...ring.map(([x, y]) => this.heightAt(x, y))); const h = b.height_m ?? 7;
      const shape = new T.Shape(); ring.forEach(([x, y], i) => (i ? shape.lineTo(x, y) : shape.moveTo(x, y)));
      const geo = new T.ExtrudeGeometry(shape, {depth: h + 1.2 + (Math.max(...ring.map(([x, y]) => this.heightAt(x, y))) - base), bevelEnabled: false});
      geo.rotateX(-Math.PI / 2); geo.translate(0, base - 1.2, 0);
      const mat = b.on_site ? new T.MeshStandardMaterial({color: '#e9c46a', roughness: 0.9, transparent: true, opacity: 0.55, depthWrite: false}) : nm;
      const m = new T.Mesh(geo, mat); m.castShadow = !b.on_site; m.receiveShadow = !b.on_site; m.userData = {existing: b.id, on_site: b.on_site};
      const e = new T.LineSegments(new T.EdgesGeometry(geo, 30), new T.LineBasicMaterial({color: b.on_site ? '#8a6d1e' : '#1a1f27', transparent: true, opacity: 0.55}));
      const grp = new T.Group(); grp.add(m, e); grp.userData = {existing: b.id, on_site: b.on_site};
      this.groups[b.on_site ? 'existing' : 'surroundings'].add(grp);
    }
  }
  addLine(group: string, ring: number[][], color: string, opacity: number, lift = 0.08) {
    const pts = ring.map(([x, y]) => this.v3(x, y, this.heightAt(x, y) + lift));
    this.groups[group].add(new this.T.LineLoop(new this.T.BufferGeometry().setFromPoints(pts), new this.T.LineBasicMaterial({color, transparent: true, opacity})));
  }
  buildOutline(group: string, ring0: number[][], color: string, height: number) {
    const T = this.T, g = this.groups[group], r = this.open(ring0), pts: number[][] = [];
    for (let i = 0; i < r.length; i++) { const a = r[i], b = r[(i + 1) % r.length]; const n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 2)); for (let k = 0; k < n; k++) pts.push([a[0] + ((b[0] - a[0]) * k) / n, a[1] + ((b[1] - a[1]) * k) / n]); }
    const pos: number[] = [], idx: number[] = [];
    pts.forEach(([x, y], i) => { const h = this.heightAt(x, y); pos.push(x, h + 0.05, -y, x, h + height, -y); const j = (i + 1) % pts.length; idx.push(i * 2, j * 2, i * 2 + 1, i * 2 + 1, j * 2, j * 2 + 1); });
    const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); geo.setIndex(idx);
    g.add(new T.Mesh(geo, new T.MeshBasicMaterial({color, transparent: true, opacity: 0.2, side: T.DoubleSide, depthWrite: false})));
    g.add(new T.LineLoop(new T.BufferGeometry().setFromPoints(pts.map(([x, y]) => this.v3(x, y, this.heightAt(x, y) + 0.12))), new T.LineBasicMaterial({color})));
  }
  buildConnections(site: SiteData) {
    const T = this.T;
    for (const c of site.connections) {
      const [x, y] = c.xy; const h = this.heightAt(x, y); const col = KIND_COLOR[c.kind] ?? '#fff';
      const pole = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 2.6, 8), new T.MeshBasicMaterial({color: col})); pole.position.copy(this.v3(x, y, h + 1.3));
      const sp = this.textSprite(KIND_LETTER[c.kind] ?? '?', col, '#0b0b0c'); sp.scale.multiplyScalar(1.4); sp.position.copy(this.v3(x, y, h + 3.2));
      this.groups.connections.add(pole, sp);
    }
  }

  // ------------------------------------------------------------------ massing
  facadeTexture(widthM: number, v: Volume) {
    const T = this.T, cv = document.createElement('canvas'); cv.width = 128; cv.height = 128; const g = cv.getContext('2d')!; const c = facadeColor(v.facade_de);
    g.fillStyle = c.wall; g.fillRect(0, 0, 128, 128);
    const glass = /glas/.test(v.facade_de.toLowerCase());
    if (v.role === 'garage') { g.fillStyle = '#5c6066'; g.fillRect(14, 30, 100, 98); g.fillStyle = '#6c7076'; for (let k = 0; k < 6; k++) g.fillRect(14, 34 + k * 16, 100, 3); }
    else {
      g.fillStyle = c.frame; g.fillRect(30, glass ? 8 : 24, 68, glass ? 112 : 78); g.fillStyle = '#8fb3d3'; g.fillRect(34, glass ? 12 : 28, 60, glass ? 104 : 70);
      g.fillStyle = 'rgba(255,255,255,.25)'; g.fillRect(36, glass ? 14 : 30, 24, glass ? 40 : 24); g.fillStyle = c.frame; g.fillRect(62, glass ? 12 : 28, 4, glass ? 104 : 70);
      g.fillStyle = 'rgba(0,0,0,.08)'; g.fillRect(0, 122, 128, 6);
    }
    const t = new T.CanvasTexture(cv); t.wrapS = t.wrapT = T.RepeatWrapping; t.colorSpace = T.SRGBColorSpace; t.anisotropy = 8;
    t.repeat.set(Math.max(1, Math.round(widthM / 3.3)), v.storeys); return t;
  }

  setMassing(m: Massing, selected: string | null) {
    this.massing = m; this.selected = selected;
    this.clear(this.houseGroup); this.volMeshes = [];
    const fps = m.volumes.map((v) => footprint(v)); const all = fps.flat();
    const base = all.length ? Math.min(...all.map(([x, y]) => this.heightAt(x, y))) : 0;
    for (let i = 0; i < m.volumes.length; i++) this.buildVolume(m.volumes[i], fps[i], base);
    this.applyDemolish(); this.invalidate();
  }

  buildVolume(v: Volume, fp: number[][], base: number) {
    const T = this.T; const sel = v.id === this.selected; const e = eave(v); const rs = rise(v);
    const wallMat = (w: number) => new T.MeshStandardMaterial({map: this.facadeTexture(w, v), roughness: 0.85});
    const plain = new T.MeshStandardMaterial({color: facadeColor(v.facade_de).wall, roughness: 0.9, side: T.DoubleSide});
    const roofMat = new T.MeshStandardMaterial({color: roofColor(v), roughness: 0.8, side: T.DoubleSide});
    const grp = new T.Group(); grp.userData = {vol: v.id};
    // plinth from the base down into the terrain so nothing floats
    if (v.elevation_m === 0) {
      const sh = new T.Shape(); fp.forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y)));
      const g0 = new T.ExtrudeGeometry(sh, {depth: 0.62, bevelEnabled: false}); g0.rotateX(-Math.PI / 2); g0.translate(0, base - 0.32, 0);
      const pl = new T.Mesh(g0, new T.MeshStandardMaterial({color: '#8b8882', roughness: 1})); pl.castShadow = true; pl.receiveShadow = true; grp.add(pl);
    }
    const y0 = base + v.elevation_m;
    if (v.shape === 'rect') {
      const inner = new T.Group(); inner.position.copy(this.v3(v.cx, v.cy, y0)); inner.rotation.y = (v.rotation_deg * Math.PI) / 180;
      const W = v.width_m, D = v.depth_m;
      const box = new T.Mesh(new T.BoxGeometry(W, e, D), [wallMat(D), wallMat(D), plain, plain, wallMat(W), wallMat(W)]);
      box.position.y = e / 2; box.castShadow = true; box.receiveShadow = true; box.userData = {vol: v.id}; inner.add(box); this.volMeshes.push(box);
      const roof = this.rectRoof(v, W, D, e, rs, roofMat, plain); roof.traverse((o: any) => { o.userData = {vol: v.id}; if (o.isMesh) this.volMeshes.push(o); }); inner.add(roof);
      const edge = new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(W, e, D)), new T.LineBasicMaterial({color: sel ? '#47a5fa' : '#1d2128', transparent: !sel, opacity: sel ? 1 : 0.45})); edge.position.y = e / 2; inner.add(edge);
      grp.add(inner);
    } else if (v.shape === 'round') {
      const r = v.width_m / 2;
      const cyl = new T.Mesh(new T.CylinderGeometry(r, r, e, 48, 1, false), wallMat(Math.PI * v.width_m)); cyl.position.copy(this.v3(v.cx, v.cy, y0 + e / 2)); cyl.castShadow = true; cyl.receiveShadow = true; cyl.userData = {vol: v.id};
      grp.add(cyl); this.volMeshes.push(cyl);
      if (v.roof === 'kegel' && rs > 0.01) { const cone = new T.Mesh(new T.ConeGeometry(r + 0.35, rs + 0.35 * Math.tan((v.roof_pitch_deg * Math.PI) / 180), 48), roofMat); cone.position.copy(this.v3(v.cx, v.cy, y0 + e + (rs - 0.35 * Math.tan((v.roof_pitch_deg * Math.PI) / 180)) / 2)); cone.castShadow = true; cone.userData = {vol: v.id}; grp.add(cone); this.volMeshes.push(cone); }
      else { const cap = new T.Mesh(new T.CylinderGeometry(r + 0.15, r + 0.15, 0.3, 48), roofMat); cap.position.copy(this.v3(v.cx, v.cy, y0 + e + 0.15)); cap.castShadow = true; cap.userData = {vol: v.id}; grp.add(cap); this.volMeshes.push(cap); }
      if (sel) { const ring = new T.LineLoop(new T.BufferGeometry().setFromPoints(fp.map(([x, y]) => this.v3(x, y, y0 + e + 0.02))), new T.LineBasicMaterial({color: '#47a5fa'})); grp.add(ring); }
    } else {
      const sh = new T.Shape(); fp.forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y)));
      const per = fp.reduce((s, p, i) => s + Math.hypot(fp[(i + 1) % fp.length][0] - p[0], fp[(i + 1) % fp.length][1] - p[1]), 0);
      const g1 = new T.ExtrudeGeometry(sh, {depth: e, bevelEnabled: false}); g1.rotateX(-Math.PI / 2); g1.translate(0, y0, 0);
      const mesh = new T.Mesh(g1, [roofMat, wallMat(per / 4)]); mesh.castShadow = true; mesh.receiveShadow = true; mesh.userData = {vol: v.id}; grp.add(mesh); this.volMeshes.push(mesh);
      grp.add(new T.LineSegments(new T.EdgesGeometry(g1, 20), new T.LineBasicMaterial({color: sel ? '#47a5fa' : '#1d2128', transparent: !sel, opacity: sel ? 1 : 0.45})));
    }
    this.houseGroup.add(grp);
  }

  /** Roof of a rectangular volume in the volume frame (x along width, z = -depth axis, y up). Ridge along width unless ridge_along = 'depth'. */
  rectRoof(v: Volume, W0: number, D0: number, e: number, rs: number, roofMat: any, wallMat: any) {
    const T = this.T, g = new T.Group(); const ov = 0.4;
    if (v.roof === 'flach' || rs < 0.01) {
      const slab = new T.Mesh(new T.BoxGeometry(W0 + 0.3, 0.35, D0 + 0.3), roofMat); slab.position.y = e + 0.17; slab.castShadow = true; slab.receiveShadow = true; g.add(slab); return g;
    }
    const swap = v.ridge_along === 'depth' && v.roof !== 'zelt';
    const W = swap ? D0 : W0, D = swap ? W0 : D0;           // W along the ridge, D across
    const k = Math.tan((v.roof_pitch_deg * Math.PI) / 180);
    const tri = (pts: number[][], mat: any) => { const pos: number[] = []; pts.forEach((p) => pos.push(...p)); const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); geo.computeVertexNormals(); const m = new T.Mesh(geo, mat); m.castShadow = true; m.receiveShadow = true; g.add(m); };
    const hw = W / 2, hd = D / 2;
    // coordinates (x along ridge, y up, z across); overhang continues the slope downwards
    if (v.roof === 'sattel') {
      const top = e + rs, low = e - ov * k, X = hw + ov, Z = hd + ov;
      tri([[-X, low, Z], [X, low, Z], [X, top, 0], [-X, low, Z], [X, top, 0], [-X, top, 0]], roofMat);
      tri([[X, low, -Z], [-X, low, -Z], [-X, top, 0], [X, low, -Z], [-X, top, 0], [X, top, 0]], roofMat);
      tri([[-hw, e, hd], [-hw, e + rs, 0], [-hw, e, -hd]], wallMat); tri([[hw, e, -hd], [hw, e + rs, 0], [hw, e, hd]], wallMat);
    } else if (v.roof === 'walm') {
      const top = e + rs, low = e - ov * k, X = hw + ov, Z = hd + ov, rx = Math.max(0, hw - hd);
      tri([[-X, low, Z], [X, low, Z], [rx, top, 0], [-X, low, Z], [rx, top, 0], [-rx, top, 0]], roofMat);
      tri([[X, low, -Z], [-X, low, -Z], [-rx, top, 0], [X, low, -Z], [-rx, top, 0], [rx, top, 0]], roofMat);
      tri([[X, low, Z], [X, low, -Z], [rx, top, 0]], roofMat); tri([[-X, low, -Z], [-X, low, Z], [-rx, top, 0]], roofMat);
    } else if (v.roof === 'pult') {
      // rises towards -z (= +depth in the local frame after the rotation below)
      const lowZ = hd + ov, highZ = -hd - ov, lowY = e - ov * k, highY = e + rs + ov * k, X = hw + ov;
      tri([[-X, lowY, lowZ], [X, lowY, lowZ], [X, highY, highZ], [-X, lowY, lowZ], [X, highY, highZ], [-X, highY, highZ]], roofMat);
      tri([[-hw, e, hd], [-hw, e + rs, -hd], [-hw, e, -hd]], wallMat); tri([[hw, e, -hd], [hw, e + rs, -hd], [hw, e, hd]], wallMat);
      tri([[-hw, e, -hd], [-hw, e + rs, -hd], [hw, e + rs, -hd], [-hw, e, -hd], [hw, e + rs, -hd], [hw, e, -hd]], wallMat);
    } else if (v.roof === 'zelt') {
      const X = hw + ov, Z = hd + ov, top = e + rs, low = e - ov * k;
      tri([[-X, low, Z], [X, low, Z], [0, top, 0]], roofMat); tri([[X, low, Z], [X, low, -Z], [0, top, 0]], roofMat);
      tri([[X, low, -Z], [-X, low, -Z], [0, top, 0]], roofMat); tri([[-X, low, -Z], [-X, low, Z], [0, top, 0]], roofMat);
    }
    if (swap) g.rotation.y = -Math.PI / 2;   // ridge/rise along the depth axis; for pult the high side ends up at +width as in massing.py
    return g;
  }

  setAbstand(af: AF, violations: number[][][]) {
    const T = this.T; const g = this.groups.abstand; this.clear(g);
    const poly = (ring: number[][], color: string, opacity: number, lift: number) => {
      const r = this.open(ring); if (r.length < 3) return;
      const sh = new T.Shape(); r.forEach(([x, y], i) => (i ? sh.lineTo(x, y) : sh.moveTo(x, y)));
      const geo = new T.ShapeGeometry(sh); const p = geo.attributes.position;
      for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i); p.setXYZ(i, x, this.heightAt(x, y) + lift, -y); }
      geo.computeVertexNormals();
      const m = new T.Mesh(geo, new T.MeshBasicMaterial({color, transparent: true, opacity, depthWrite: false, side: T.DoubleSide})); m.renderOrder = 5; g.add(m);
      g.add(new T.LineLoop(new T.BufferGeometry().setFromPoints(r.map(([x, y]) => this.v3(x, y, this.heightAt(x, y) + lift + 0.01))), new T.LineBasicMaterial({color, transparent: true, opacity: 0.9})));
    };
    for (const a of af) if (a.ring) poly(a.ring, a.ok ? '#6bd68a' : '#f2b84b', 0.16, 0.06);
    for (const v of violations) poly(v, '#ff5d5d', 0.45, 0.09);
    this.invalidate();
  }

  setDemolish(ids: string[]) { this.demolish = new Set(ids); this.applyDemolish(); }
  applyDemolish() {
    for (const grp of this.groups.existing.children) {
      const gone = this.demolish.has(grp.userData.existing);
      grp.children.forEach((c: any) => { if (c.isMesh) { c.material.opacity = gone ? 0.08 : 0.55; c.material.color.set(gone ? '#ff7b7b' : '#e9c46a'); } else c.material.color.set(gone ? '#ff7b7b' : '#8a6d1e'); });
    }
    this.invalidate();
  }

  // ------------------------------------------------------------------ sun, layers, modes, views
  sun = {az: 180, el: 40, on: true};
  setSun(az: number, el: number, on: boolean) { this.sun = {az, el, on}; this.updateSun(); }
  updateSun() {
    const {az, el, on} = this.sun, T = this.T; const e = (Math.max(el, 0) * Math.PI) / 180, a = (az * Math.PI) / 180;
    const dir = new T.Vector3(Math.cos(e) * Math.sin(a), Math.sin(e), -Math.cos(e) * Math.cos(a));
    this.sunLight.position.copy(this.target).addScaledVector(dir, 300); this.sunLight.target.position.copy(this.target);
    this.sunLight.visible = on && el > 0; this.sunLight.intensity = on ? 0.5 + Math.min(1, Math.sin(e) * 1.6) * 2.0 : 0;
    this.hemi.intensity = on ? 0.35 + Math.min(1, Math.sin(e) * 1.4) * 0.6 : 0.95;
    const sky = this.mode === 'grundstueck' ? '#e7eaee' : on ? (el > 8 ? '#b9c6d3' : el > 0 ? '#cfae8e' : '#161b24') : '#b9c6d3';
    this.scene.background.set(sky); this.scene.fog.color.set(sky); this.invalidate();
  }
  setLayers(l: Layers) { this.layers = l; this.applyMode(); }
  setMode(m: ViewMode) { this.mode = m; this.applyMode(); this.updateSun(); }
  applyMode() {
    const l = this.layers, plotOnly = this.mode === 'grundstueck';
    if (this.ground) { this.ground.visible = !plotOnly; this.ground.material.map = l?.aerial === false ? null : this.aerialMap; this.ground.material.color.set(l?.aerial === false || !this.aerialMap ? '#5b6b57' : '#ffffff'); this.ground.material.needsUpdate = true; }
    const pm = this.groups.plot.children[0]; if (pm) { pm.material.map = l?.aerial === false ? null : this.aerialMap; pm.material.color.set(l?.aerial === false || !this.aerialMap ? '#6d7f5f' : '#ffffff'); pm.material.needsUpdate = true; }
    this.groups.plot.visible = plotOnly;
    this.groups.surroundings.visible = !plotOnly && (l?.surroundings ?? true);
    this.groups.neighbours.visible = !plotOnly && (l?.neighbours ?? true);
    this.groups.existing.visible = l?.existing ?? true;
    this.groups.connections.visible = l?.connections ?? true;
    this.groups.envelope.visible = l?.envelope ?? true;
    this.groups.boundary.visible = !plotOnly && (l?.boundary ?? true);
    this.groups.abstand.visible = l?.abstand ?? true;
    this.groups.labels.visible = plotOnly || (l?.labels ?? false);
    this.scene.fog.near = plotOnly ? 2000 : 300; this.scene.fog.far = plotOnly ? 3000 : 1000;
    this.invalidate();
  }
  houseCenter() {
    if (!this.massing?.volumes.length) return this.target.clone();
    const pts = this.massing.volumes.flatMap((v) => footprint(v)); const x = pts.reduce((s, p) => s + p[0], 0) / pts.length, y = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    return this.v3(x, y, this.heightAt(x, y) + 3);
  }
  view(kind: 'top' | 'persp' | 'house' | 'n' | 's' | 'e' | 'w') {
    if (kind === 'top') this.sph.theta = 0.0001;
    else if (kind === 'persp') { this.sph.theta = 0.9; this.sph.phi = 2.4; }
    else if (kind === 'house') { this.target.copy(this.houseCenter()); const pts = this.massing?.volumes.flatMap((v) => footprint(v)) ?? []; const s = pts.length ? Math.max(Math.max(...pts.map((p) => p[0])) - Math.min(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[1])) - Math.min(...pts.map((p) => p[1]))) : 12; this.sph.r = Math.max(26, s * 2.6); this.sph.theta = 1.15; }
    else { this.target.copy(this.houseCenter()); this.sph.theta = 1.32; this.sph.phi = {s: 0, e: Math.PI / 2, n: Math.PI, w: -Math.PI / 2}[kind]; }
    this.updateSun(); this.placeCamera();
  }
  setAutoRotate(on: boolean) { this.autoRotate = on; this.lastT = 0; }
  snapshot(scale = 2): string {
    const w = this.el.clientWidth, h = this.el.clientHeight, pr = this.renderer.getPixelRatio();
    this.renderer.setPixelRatio(scale); this.renderer.setSize(w, h, false); this.renderer.render(this.scene, this.camera);
    const url = this.renderer.domElement.toDataURL('image/png'); this.renderer.setPixelRatio(pr); this.renderer.setSize(w, h, false); this.invalidate(); return url;
  }

  // ------------------------------------------------------------------ interaction
  ndc(e: PointerEvent | WheelEvent) { const r = this.renderer.domElement.getBoundingClientRect(); return new this.T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); }
  ray(e: PointerEvent) { const rc = new this.T.Raycaster(); rc.setFromCamera(this.ndc(e), this.camera); return rc; }
  planeHit(e: PointerEvent, y: number) { const p = new this.T.Plane(new this.T.Vector3(0, 1, 0), -y); const out = new this.T.Vector3(); return this.ray(e).ray.intersectPlane(p, out) ? out : null; }
  pickVol(e: PointerEvent): {id: string; y: number} | null { const hit = this.ray(e).intersectObjects(this.volMeshes, false)[0]; return hit ? {id: hit.object.userData.vol, y: hit.point.y} : null; }
  down = (e: PointerEvent) => {
    const d = this.renderer.domElement; d.setPointerCapture(e.pointerId); this.pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    d.focus({preventScroll: true});
    if (this.pointers.size === 2) { const [a, b] = [...this.pointers.values()]; this.pinch = Math.hypot(a.x - b.x, a.y - b.y); this.dragging = null; return; }
    if (e.button === 0 && !e.shiftKey) {
      const hit = this.pickVol(e);
      if (hit && !this.partMode && (!this.selectFirst || hit.id === this.selId)) { const p = this.planeHit(e, hit.y); this.dragging = {mode: 'vol', x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, id: hit.id, last: p, plane: hit.y, moved: false}; d.style.cursor = 'move'; if (!this.selectFirst) this.ev.onSelect?.(hit.id); return; }
      if (hit) { this.pendingSel = hit.id; this.pendingVol = (hit as any).vol ?? null; }       // first click only selects (see up); dragging before release orbits the camera
    }
    this.dragging = {mode: e.button === 2 || e.shiftKey ? 'pan' : 'rotate', x: e.clientX, y: e.clientY, moved: false, sx: e.clientX, sy: e.clientY}; d.style.cursor = 'grabbing';
  };
  move = (e: PointerEvent) => {
    const d = this.renderer.domElement;
    if (this.pointers.has(e.pointerId)) this.pointers.set(e.pointerId, {x: e.clientX, y: e.clientY});
    if (this.pointers.size === 2) { const [a, b] = [...this.pointers.values()]; const n = Math.hypot(a.x - b.x, a.y - b.y); if (this.pinch) { this.sph.r = Math.max(6, Math.min(800, this.sph.r * (this.pinch / n))); this.placeCamera(); } this.pinch = n; return; }
    if (!this.dragging) { if (e.buttons === 0) { const h = this.pickVol(e); d.style.cursor = h ? (h.id === this.selId ? 'move' : 'pointer') : 'grab'; } return; }
    const dx = e.clientX - this.dragging.x, dy = e.clientY - this.dragging.y; this.dragging.x = e.clientX; this.dragging.y = e.clientY;
    if (Math.abs(e.clientX - (this.dragging.sx ?? this.dragging.x)) + Math.abs(e.clientY - (this.dragging.sy ?? this.dragging.y)) > 4) this.dragging.moved = true;
    if (this.dragging.mode === 'rotate') { this.sph.phi -= dx * 0.006; this.sph.theta = Math.max(0.0001, Math.min(1.52, this.sph.theta - dy * 0.006)); this.placeCamera(); }
    else if (this.dragging.mode === 'pan') {
      const k = this.sph.r * 0.0016; const right = new this.T.Vector3(); this.camera.getWorldDirection(right); right.cross(this.camera.up).normalize();
      const fwd = new this.T.Vector3(-Math.sin(this.sph.phi), 0, -Math.cos(this.sph.phi));
      this.target.addScaledVector(right, -dx * k).addScaledVector(fwd, dy * k); this.updateSun(); this.placeCamera();
    } else if (this.dragging.mode === 'vol' && this.dragging.id) {
      const p = this.planeHit(e, this.dragging.plane!); if (p && this.dragging.last) { this.ev.onDrag?.(this.dragging.id, p.x - this.dragging.last.x, -(p.z - this.dragging.last.z)); this.dragging.last = p; }
    }
  };
  up = (e: PointerEvent) => {
    const was = this.dragging; this.pointers.delete(e.pointerId); this.pinch = 0; this.dragging = null; this.renderer.domElement.style.cursor = 'grab';
    const pend = this.pendingSel; this.pendingSel = null;
    if (was?.mode === 'vol') { if (!this.selectFirst || was.moved) this.ev.onDragEnd?.(was.id); }
    else if (was && !was.moved && e.button === 0) { if (this.partMode) { if (pend) this.ev.onPart?.(this.pendingVol, pend); } else { this.selId = pend; this.ev.onSelect?.(pend); } }
  };
  wheel = (e: WheelEvent) => { e.preventDefault(); const d = Math.max(-80, Math.min(80, e.deltaY * (e.deltaMode === 1 ? 16 : 1))); this.sph.r = Math.max(6, Math.min(800, this.sph.r * Math.exp(d * 0.0016))); this.placeCamera(); };
  private typing(e: KeyboardEvent): boolean {
    const t = e.target as HTMLElement | null;
    return !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.tagName === 'BUTTON' || t.tagName === 'A' || t.isContentEditable);
  }
  keyMove = (e: KeyboardEvent) => {
    if (this.typing(e) || e.metaKey || e.ctrlKey || e.altKey) return;
    const key = e.key.toLowerCase();
    if (!['w','a','s','d','q','e','arrowup','arrowdown','arrowleft','arrowright','shift',' '].includes(key)) return;
    e.preventDefault(); this.flightKeys.add(key);
  };
  keyUp = (e: KeyboardEvent) => { this.flightKeys.delete(e.key.toLowerCase()); };
  clearFlight = () => { this.flightKeys.clear(); };
  private vel: any = null;
  /** Minecraft-Flug: Wunsch-Geschwindigkeit aus den Tasten, die wirkliche Geschwindigkeit gleitet weich dorthin (kein Ruckeln, kein abruptes Stoppen). */
  fly(dt: number) {
    const T = this.T;
    if (!this.vel) this.vel = new T.Vector3();
    const k = this.flightKeys;
    if (!k.size && this.vel.lengthSq() < 1e-6) return;
    const want = new T.Vector3();
    if (k.size) {
      const forward = new T.Vector3(-Math.sin(this.sph.phi), 0, -Math.cos(this.sph.phi));
      const right = new T.Vector3(Math.cos(this.sph.phi), 0, -Math.sin(this.sph.phi));
      if (k.has('w') || k.has('arrowup')) want.add(forward);
      if (k.has('s') || k.has('arrowdown')) want.sub(forward);
      if (k.has('d') || k.has('arrowright')) want.add(right);
      if (k.has('a') || k.has('arrowleft')) want.sub(right);
      if (k.has('e') || k.has(' ')) want.y += 1;
      if (k.has('q') || k.has('shift')) want.y -= 1;
      if (want.lengthSq() > 0) want.normalize();
    }
    const speed = Math.max(16, Math.min(90, 10 + this.sph.r * 0.4));      // ~2.5x schneller als zuvor
    want.multiplyScalar(speed);
    this.vel.lerp(want, 1 - Math.exp(-dt * (k.size ? 14 : 14)));
    if (!k.size && this.vel.lengthSq() < 0.01) this.vel.set(0, 0, 0);
    this.target.addScaledVector(this.vel, dt);
    this.target.y = Math.max(this.target.y, this.heightAt(this.target.x, -this.target.z) + 0.5);
    this.updateSun(); this.placeCamera();
  }

  dispose() {
    this.disposed = true; cancelAnimationFrame(this.raf); this.ro?.disconnect();
    const d = this.renderer.domElement; d.removeEventListener('pointerdown', this.down); d.removeEventListener('pointermove', this.move); d.removeEventListener('pointerup', this.up); d.removeEventListener('pointercancel', this.up); d.removeEventListener('wheel', this.wheel); window.removeEventListener('keydown', this.keyMove);
    window.removeEventListener('keyup', this.keyUp); window.removeEventListener('blur', this.clearFlight); this.clearFlight();
    this.dispose3(this.scene); this.aerialMap?.dispose?.(); this.renderer.dispose(); d.remove();
  }
}
