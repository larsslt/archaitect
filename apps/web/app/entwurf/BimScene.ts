/* 360°-Szene des Entwurfs: das vorhandene Grundstück (SiteScene: DGM1-Gelände, Luftbild, Nachbarn, Grenze) plus das Haus und das
   angepasste Gelände (Aufschüttung/Abtrag) aus GET /bim/mesh. Das Netz liegt im Hausrahmen (x/y in m, Boden-Oberkante Fertigfußboden = 0);
   placement {x, y, rotation_deg} setzt es in den Projektrahmen, pad_z_abs_m ist die absolute Höhe des Fertigfußbodens. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {SiteScene, type SiteData} from '../studio/scene3d';
import {seamHeight} from './terrainSeam';

export type BimObject = {id: string; kind: string; label: string; bounds: number[]};
export type BimMesh = {
  objects?: BimObject[];
  parts: {name: string; obj?: string | null; vol?: string | null; color: number[]; opacity: number; positions: number[]; indices: number[]}[];
  bounds: number[];
  terrain: null | {pad_z_abs_m: number | null; cut_m3?: number; fill_m3?: number; max_cut_m?: number; max_fill_m?: number; natural_slope_pct?: number; notes_de?: string[]};
  version?: number;
};
export type Placement = {x: number; y: number; rotation_deg: number};

export class BimScene extends SiteScene {
  objGroups: Record<string, any> = {};
  live: Record<string, {dx: number; dy: number}> = {};
  bimGroup: any = null;                              // nur das Haus (wird beim Ziehen verschoben)
  terrainGroup: any = null;                          // angepasstes Gelände bleibt beim Ziehen stehen
  private clipped: any[] = [];

  constructor(T: any, el: HTMLElement, ev: any = {}) {
    super(T, el, ev);
    this.renderer.localClippingEnabled = true;
    this.selectFirst = true;                             // erst anklicken (auswählen), dann erst verschieben
  }

  async setSite(site: SiteData) {
    this.clearBim();
    await super.setSite(site);
  }

  clearBim() {
    this.clearLibraryPreview();
    this.explodeBands = []; this.explodeHidden = [];
    this.matchSkirt(null, null, null, 0);
    if (this.bimGroup) { this.scene.remove(this.bimGroup); this.dispose3(this.bimGroup); this.bimGroup = null; }
    if (this.terrainGroup) { this.scene.remove(this.terrainGroup); this.dispose3(this.terrainGroup); this.terrainGroup = null; }
    for (const m of this.clipped) { m.clippingPlanes = null; m.clipIntersection = false; m.needsUpdate = true; }
    this.clipped = [];
  }

  /** Zieh-Griff: jedes Objekt (Gebäude, Pool, Baum …) einzeln; das Gelände ist nicht greifbar. */
  pickVol(e: PointerEvent): any {
    if (!this.bimGroup) return null;
    const meshes: any[] = [];
    this.bimGroup.traverse((o: any) => { if (o.isMesh) meshes.push(o); });
    const hit = this.ray(e).intersectObjects(meshes, false)[0];
    if (!hit) return null;
    let o = hit.object; while (o && !o.userData?.objId) o = o.parent;
    return o ? {id: o.userData.objId, y: hit.point.y, vol: (hit.object as any).userData?.vol ?? null} : null;
  }

  private libraryPreview: any = null;
  clearLibraryPreview() {
    if (this.libraryPreview) { this.scene.remove(this.libraryPreview); this.dispose3(this.libraryPreview); this.libraryPreview = null; this.invalidate(); }
  }
  previewLibraryObject(kind: string, x: number, y: number) {
    this.clearLibraryPreview();
    const T = this.T, dims: Record<string, number[]> = {tree: [6, 9, 6], shrub: [1.4, 1, 1.4], bench: [1.6, .85, .6], garden_set: [4, 2.5, 4], garden_light: [.3, .8, .3], flowerbed: [3, .3, 1.2], pool: [8, .3, 4], pond: [8, .3, 5.5], sauna_hut: [3.8, 3, 4.5]};
    const d = dims[kind] ?? (kind === 'house' ? [12, 7, 9] : undefined); if (!d) return;
    const geo = kind === 'tree' || kind === 'shrub' ? new T.ConeGeometry(d[0] / 2, d[1], 12) : new T.BoxGeometry(...d);
    const m = new T.Mesh(geo, new T.MeshBasicMaterial({color: 0x58a6ff, transparent: true, opacity: .55, depthWrite: false}));
    m.position.set(x, this.heightAt(x, y) + d[1] / 2, -y);
    this.libraryPreview = m; this.scene.add(m); this.invalidate();
  }

  /** Pick the visible ground under a dragged library item in site coordinates. */
  siteAtScreen(clientX: number, clientY: number): {x: number; y: number} | null {
    const el = this.renderer.domElement, r = el.getBoundingClientRect();
    if (!r.width || !r.height) return null;
    const ray = new this.T.Raycaster();
    ray.setFromCamera(new this.T.Vector2((clientX - r.left) / r.width * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1), this.camera);
    const surfaces = [this.terrainGroup, this.groups.plot?.children?.[0]].filter(Boolean);
    const hit = ray.intersectObjects(surfaces, true)[0];
    return hit ? {x: hit.point.x, y: -hit.point.z} : null;
  }

  /** Vorschau beim Ziehen (Projektrahmen, m) nur für dieses Objekt; gespeichert wird erst beim Loslassen. */
  nudgeLive(dx: number, dy: number, id: string | null = this.selId) {
    const g = id ? this.objGroups[id] : null;
    if (!g) return;
    g.position.x += dx; g.position.z -= dy;
    const l = (this.live[id!] ??= {dx: 0, dy: 0}); l.dx += dx; l.dy += dy;
    this.updateRed();
  }
  /** Drehen um die Mitte des gewählten Hauses (Vorschau). Alle Objekte teilen den Projektrahmen und drehen deshalb um denselben Punkt. */
  rotPivot: any = null; rotTotal = 0;
  rotateLive(dDeg: number, id: string | null = this.selId) {
    const g = id ? this.objGroups[id] : null;
    if (!g) return;
    const T = this.T;
    if (!this.rotPivot) this.rotPivot = new T.Box3().setFromObject(g).getCenter(new T.Vector3());
    const c = this.rotPivot, d = (dDeg * Math.PI) / 180, up = new T.Vector3(0, 1, 0);
    for (const og of Object.values(this.objGroups) as any[]) {
      const p = og.position.clone().sub(c); p.applyAxisAngle(up, d);
      og.position.set(c.x + p.x, og.position.y, c.z + p.z); og.rotation.y += d;
    }
    this.rotTotal += dDeg;
    this.updateRed();
  }
  /** Ergebnis der Drehung als Platzierung im Projektrahmen (null, wenn nicht gedreht wurde). */
  takePlacement(): {x: number; y: number; rot: number} | null {
    const g: any = Object.values(this.objGroups)[0];
    const moved = Math.abs(this.rotTotal) > 1e-6;
    this.rotPivot = null; this.rotTotal = 0;
    if (!g || !moved) return null;
    return {x: g.position.x, y: -g.position.z, rot: (((g.rotation.y * 180) / Math.PI) % 360 + 360) % 360};
  }
  takeDelta(id: string): {dx: number; dy: number} { const l = this.live[id] ?? {dx: 0, dy: 0}; delete this.live[id]; return l; }

  /** Auswahl hervorheben (blau) und Objekte außerhalb des Grundstücks rot einfärben. */
  red = new Set<string>();
  /** Explosionsansicht: das Haus wird nach Geschossen in Bänder geteilt, die vertikal auseinanderfahren (f = 0 … 1). */
  explodeBands: any[] = []; explodeHidden: any[] = []; explodeF = 0; explodeSh = 3;
  setExplode(f: number, sh = this.explodeSh) {
    this.explodeF = f; this.explodeSh = sh;
    if (f > 0 && !this.explodeBands.length) this.buildBands(sh);
    for (const bm of this.explodeBands) bm.position.y = bm.userData.band * sh * 1.15 * f;
    if (f <= 0) this.clearBands();
    this.invalidate();
  }
  private clearBands() {
    for (const bm of this.explodeBands) { bm.parent?.remove(bm); bm.geometry.dispose(); }
    for (const m of this.explodeHidden) m.visible = true;
    this.explodeBands = []; this.explodeHidden = [];
  }
  private buildBands(sh: number) {
    const T = this.T, meshes: any[] = [];
    for (const id of Object.keys(this.objGroups)) if (id.startsWith('bld:')) this.objGroups[id].traverse((o: any) => { if (o.isMesh && o.geometry?.getAttribute('position')) meshes.push(o); });
    let minY = Infinity, maxY = -Infinity;
    for (const m of meshes) { const a = m.geometry.getAttribute('position').array; for (let i = 1; i < a.length; i += 3) { if (a[i] < minY) minY = a[i]; if (a[i] > maxY) maxY = a[i]; } }
    if (!Number.isFinite(minY)) return;
    const maxBand = Math.max(0, Math.ceil((maxY - minY) / sh) - 1);
    for (const m of meshes) {
      const pa = m.geometry.getAttribute('position').array, na = m.geometry.getAttribute('normal')?.array;
      const buckets = new Map<number, {p: number[]; n: number[]}>();
      const edge = (k: number) => minY + k * sh - 0.2;                // Bandgrenzen knapp unter den Geschossdecken
      const clip = (poly: number[][], lo: number, hi: number) => {       // Sutherland-Hodgman an y in [lo, hi]; je Ecke [x,y,z,nx,ny,nz]
        for (const [axis, lim, keepAbove] of [[1, lo, true], [1, hi, false]] as [number, number, boolean][]) {
          if (!Number.isFinite(lim)) continue;
          const out: number[][] = [];
          for (let q = 0; q < poly.length; q++) {
            const A = poly[q], B = poly[(q + 1) % poly.length], ain = keepAbove ? A[axis] >= lim : A[axis] <= lim, bin = keepAbove ? B[axis] >= lim : B[axis] <= lim;
            if (ain) out.push(A);
            if (ain !== bin) { const s = (lim - A[axis]) / (B[axis] - A[axis]); out.push(A.map((v, k) => v + (B[k] - v) * s)); }
          }
          poly = out;
          if (poly.length < 3) return poly;
        }
        return poly;
      };
      for (let t = 0; t + 8 < pa.length; t += 9) {
        const tri = [0, 1, 2].map((c) => [pa[t + c * 3], pa[t + c * 3 + 1], pa[t + c * 3 + 2], na ? na[t + c * 3] : 0, na ? na[t + c * 3 + 1] : 1, na ? na[t + c * 3 + 2] : 0]);
        const y0 = Math.min(tri[0][1], tri[1][1], tri[2][1]), y1 = Math.max(tri[0][1], tri[1][1], tri[2][1]);
        const b0 = Math.max(0, Math.min(maxBand, Math.floor((y0 - minY + 0.2) / sh))), b1 = Math.max(0, Math.min(maxBand, Math.floor((y1 - minY + 0.2) / sh)));
        for (let band = b0; band <= b1; band++) {
          const poly = b0 === b1 ? tri : clip(tri, band === 0 ? -Infinity : edge(band), band === maxBand ? Infinity : edge(band + 1));
          if (poly.length < 3) continue;
          let bk = buckets.get(band); if (!bk) { bk = {p: [], n: []}; buckets.set(band, bk); }
          for (let q = 1; q + 1 < poly.length; q++) for (const V of [poly[0], poly[q], poly[q + 1]]) { bk.p.push(V[0], V[1], V[2]); bk.n.push(V[3], V[4], V[5]); }
        }
      }
      for (const [band, bk] of buckets) {
        const geo = new T.BufferGeometry();
        geo.setAttribute('position', new T.Float32BufferAttribute(bk.p, 3));
        geo.setAttribute('normal', new T.Float32BufferAttribute(bk.n, 3));
        const bm = new T.Mesh(geo, m.material); bm.castShadow = m.castShadow; bm.receiveShadow = m.receiveShadow; bm.userData = {...m.userData, band};
        m.parent.add(bm); this.explodeBands.push(bm);
      }
      m.visible = false; this.explodeHidden.push(m);
    }
  }

  selVol: string | null = null;
  setSelected(id: string | null) { this.selId = id; this.refreshTint(); }
  setPartMode(on: boolean) { this.partMode = on; if (!on) this.selVol = null; this.refreshTint(); }
  setPartVol(v: string | null) { this.selVol = v; this.refreshTint(); }
  refreshTint() {
    for (const [k, g] of Object.entries(this.objGroups)) g.traverse((o: any) => {
      const m = o.material; if (!m?.emissive) return;
      const r = this.red.has(k);
      const part = !!this.selVol && o.userData?.vol === this.selVol;
      m.emissive.setHex(r ? 0xd01030 : part ? 0xe08a00 : k === this.selId ? 0x2a5fa8 : 0x000000); m.emissiveIntensity = r ? 0.75 : part ? 0.7 : k === this.selId && !this.partMode ? 0.55 : 0; m.needsUpdate = true;
    });
    this.invalidate();
  }
  /** Liegt ein Teil des Objekts außerhalb der amtlichen Flurstücksgrenze? (Stichprobe über die Eckpunkte der Netze, Projektrahmen) */
  outsideNow(id: string): boolean {
    const g = this.objGroups[id]; const ring = this.site?.site ? this.open(this.site.site) : null;
    if (!g || !ring) return false;
    g.updateMatrixWorld(true);
    const T = this.T, v = new T.Vector3();
    const inside = (x: number, y: number) => {
      let c = false;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j];
        if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c;
      }
      return c;
    };
    let out = false;
    g.traverse((o: any) => {
      if (out || !o.isMesh) return;
      const pos = o.geometry.attributes.position, step = Math.max(1, Math.floor(pos.count / 300));
      for (let i = 0; i < pos.count; i += step) {
        v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
        if (!inside(v.x, -v.z)) { out = true; return; }
      }
    });
    return out;
  }
  updateRed() {
    this.red = new Set(Object.keys(this.objGroups).filter((k) => this.outsideNow(k)));
    this.refreshTint();
  }
  /** Ausgangszustand (gespeicherte Lage): was dort schon rot war, wird nicht zurückgesetzt, sonst käme man nie heraus. */
  redBase = new Set<string>();
  /** Neu in den roten Bereich geraten? Dann Vorschau verwerfen und das Objekt auf den alten Platz zurücksetzen. */
  revertIfOutside(id: string | null): boolean {
    const ids = id ? [id] : Object.keys(this.objGroups);
    if (!ids.some((k) => this.red.has(k) && !this.redBase.has(k))) return false;
    if (id && this.live[id]) { const l = this.live[id]; this.nudgeLive(-l.dx, -l.dy, id); delete this.live[id]; }
    if (Math.abs(this.rotTotal) > 1e-6) this.rotateLive(-this.rotTotal);
    this.rotPivot = null; this.rotTotal = 0;
    this.updateRed();
    return true;
  }

  /** Haus + angepasstes Gelände zeigen. Das natürliche Gelände wird im Bereich des angepassten Geländes ausgeblendet (Clipping), damit Abtrag sichtbar ist. */
  applyMode() { super.applyMode(); for (const child of this.groups.plot?.children ?? []) if (child.isLineLoop) child.visible = false; (this as any).groups.labels.visible = false; (this as any).invalidate?.(); }
  houseFrame: {x: number; y: number; z: number; r: number} | null = null;
  setHouse(mesh: BimMesh | null, pl: Placement, reframe = false) {
    const T = this.T;
    const had = !!this.bimGroup;                       // erneutes Laden (z. B. nach Verschieben) lässt die Kamera stehen
    this.clearBim();
    if (!mesh || !mesh.parts?.length) { this.invalidate(); return; }
    const a = (pl.rotation_deg * Math.PI) / 180;
    const base = (mesh.terrain?.pad_z_abs_m ?? this.z0) - this.z0;              // Fertigfußboden in Szenehöhe
    const g = new T.Group();                           // Container ohne Transformation; jedes Objekt trägt Position und Drehung selbst
    this.objGroups = {}; this.live = {};
    const objGroup = (id: string) => {
      if (!this.objGroups[id]) { const og = new T.Group(); og.rotation.y = a; og.position.set(pl.x, base, -pl.y); og.userData.objId = id; this.objGroups[id] = og; g.add(og); }
      return this.objGroups[id];
    };
    const tg = new T.Group(); tg.rotation.y = a; tg.position.set(pl.x, base, -pl.y);
    let tpos: number[] | null = null;
    let tidx: number[] | null = null;
    let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    for (const p of mesh.parts) {
      const n = p.positions.length / 3, pos = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) { pos[i * 3] = p.positions[i * 3]; pos[i * 3 + 1] = p.positions[i * 3 + 2]; pos[i * 3 + 2] = -p.positions[i * 3 + 1]; }
      let geo = new T.BufferGeometry();
      geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setIndex(p.indices);
      const isTerrain = p.name === 'terrain';
      if (!isTerrain) geo = geo.toNonIndexed();        // Gebäudeteile: scharfe Kanten (verschweißte Eckpunkte würden Normalen über die Kanten mitteln → dunkle Streifen auf Dach/Balken)
      geo.computeVertexNormals();
      const mat = new T.MeshStandardMaterial({
        color: isTerrain ? new T.Color('#6d7f5f') : new T.Color(p.color[0], p.color[1], p.color[2]), roughness: isTerrain ? 1 : 0.85, metalness: 0,
        transparent: p.opacity < 1, opacity: p.opacity, side: T.DoubleSide,
        polygonOffset: isTerrain, polygonOffsetFactor: 2, polygonOffsetUnits: 2,      // Gelände weicht nach hinten: Wege/Beläge knapp über dem Boden bleiben auch aus der Ferne sichtbar
      });
      if (isTerrain && this.site) this.maskToParcel(geo, mat, p.positions, pl);       // Gelände nur innerhalb der echten Flurstücksgrenze, nicht als Rechteck
      const m = new T.Mesh(geo, mat); m.castShadow = !isTerrain; m.receiveShadow = true; m.userData.vol = p.vol ?? null;
      (isTerrain ? tg : objGroup(p.obj || 'house')).add(m);
      if (isTerrain) { tpos = p.positions; tidx = p.indices; }
      else for (let i = 0; i < p.positions.length; i += 3) for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], p.positions[i + k]); hi[k] = Math.max(hi[k], p.positions[i + k]); }
    }
    this.scene.add(g); this.bimGroup = g; this.scene.add(tg); this.terrainGroup = tg;
    if (this.selId && !this.objGroups[this.selId]) this.selId = null;
    this.updateRed();
    this.redBase = new Set(this.red);
    if (tpos && tidx) { this.clipNatural(tpos, pl, base); this.matchSkirt(tpos, tidx, pl, base); }
    const size = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]);       // Startabstand nach Hausgröße
    this.houseFrame = {x: pl.x, y: base + 2, z: -pl.y, r: Number.isFinite(size) ? Math.max(28, Math.min(120, size * 2.4)) : 60};
    if (this.explodeF > 0) this.setExplode(this.explodeF, this.explodeSh);
    if (!had || reframe) { this.frameHouse(); return; }
    this.placeCamera();
  }

  /** The earth wall follows the actual graded mesh wherever it reaches the parcel boundary. */
  private matchSkirt(positions: number[] | null, indices: number[] | null, pl: Placement | null, base: number) {
    const skirt = this.groups.plot?.children?.find((o: any) => o.userData?.parcelSkirt);
    if (!skirt) return;
    const attr = skirt.geometry.getAttribute('position');
    for (let i = 0; i < attr.count; i += 2) {
      const x = attr.getX(i), y = -attr.getZ(i);
      const z = positions && indices && pl ? seamHeight(positions, indices, x, y, pl, base) : null;
      attr.setY(i, z ?? this.heightAt(x, y));
    }
    attr.needsUpdate = true; skirt.geometry.computeVertexNormals(); skirt.geometry.computeBoundingSphere();
    for (const ch of this.groups.plot?.children ?? []) if (ch.isLineLoop || ch.isLine) ch.visible = false;      // keine weiße Randlinie (41667502)
  }

  /** Alpha-Maske aus dem Flurstücksring (Projektrahmen) + planare UVs: schneidet das angepasste Gelände an der Grenze aus. */
  private maskToParcel(geo: any, mat: any, positions: number[], pl: Placement) {
    const T = this.T, ring = this.open(this.site!.site);
    const xs = ring.map((r) => r[0]), ys = ring.map((r) => r[1]);
    const pad = 4, x0 = Math.min(...xs) - pad, x1 = Math.max(...xs) + pad, y0 = Math.min(...ys) - pad, y1 = Math.max(...ys) + pad;
    const N = 2048, cv = document.createElement('canvas'); cv.width = cv.height = N;
    const c = cv.getContext('2d')!; c.fillStyle = '#000'; c.fillRect(0, 0, N, N); c.fillStyle = '#fff'; c.beginPath();
    ring.forEach(([x, y], i) => { const px = ((x - x0) / (x1 - x0)) * N, py = (1 - (y - y0) / (y1 - y0)) * N; if (i) c.lineTo(px, py); else c.moveTo(px, py); });
    c.closePath(); c.fill();
    const tex = new T.CanvasTexture(cv); tex.flipY = true;
    const a = (pl.rotation_deg * Math.PI) / 180, ca = Math.cos(a), sa = Math.sin(a), n = positions.length / 3, uv = new Float32Array(n * 2);
    for (let i = 0; i < n; i++) {
      const lx = positions[i * 3], ly = positions[i * 3 + 1];
      const X = pl.x + lx * ca - ly * sa, Y = pl.y + lx * sa + ly * ca;
      uv[i * 2] = (X - x0) / (x1 - x0); uv[i * 2 + 1] = (Y - y0) / (y1 - y0);
    }
    geo.setAttribute('uv', new T.BufferAttribute(uv, 2));
    mat.alphaMap = tex; mat.alphaTest = 0.5; mat.needsUpdate = true;
  }

  /** Foto-Modus (Bilderwelt): feste Kamera aus dem Hausrahmen (m), nur die Szene (keine Bedienelemente), Nebelwand auf der Flurstücksgrenze.
      Die Aufnahme ist ein echter Screenshot dieses Viewers; Meta skaliert sie nur hoch. */
  shotMode(cam: {position: number[]; target: number[]; lens_mm: number}, W: number, H: number) {
    const T = this.T, tg = this.terrainGroup; if (!tg) return;
    this.ro?.disconnect(); this.autoRotate = false;
    tg.updateMatrixWorld(true);
    const toW = (p: number[]) => tg.localToWorld(new T.Vector3(p[0], p[2], -p[1]));
    for (const k of Object.keys(this.groups)) if (k !== 'terrain' && k !== 'plot') this.groups[k].visible = false;
    this.groups.plot.visible = false; this.groups.labels.visible = false;
    this.renderer.setPixelRatio(1); this.renderer.setSize(W, H, false);
    const cv = this.renderer.domElement; cv.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;display:block';
    const mist = '#d9e0e6';
    this.scene.background.set(mist); this.scene.fog.color.set(mist); 
    const pos = toW(cam.position), tgt = toW(cam.target);
    this.camera.aspect = W / H; this.camera.fov = (2 * Math.atan((36 * H / W) / 2 / cam.lens_mm) * 180) / Math.PI;
    this.camera.near = 0.3; this.camera.far = 3000; this.camera.updateProjectionMatrix();
    this.camera.up.set(0, 1, 0);
    { const ring = this.site ? this.open(this.site.site) : [];       // Nebel statt Wand: ab etwa Hausabstand + Grundstückshälfte löst sich alles in Dunst auf, die Grenze ist nicht zu sehen
      const R = ring.length ? Math.max(...ring.map(([x, y]) => Math.hypot(x - pl0(this).x, y - pl0(this).y))) : 60; const d = pos.distanceTo(tgt);
      this.scene.fog.near = d + 0.15 * R; this.scene.fog.far = d + 0.9 * R; }
    if (Math.abs(pos.x - tgt.x) < 0.01 && Math.abs(pos.z - tgt.z) < 0.01) pos.z += 0.01;
    this.camera.position.copy(pos); this.camera.lookAt(tgt);
    this.invalidate(); this.renderer.render(this.scene, this.camera);
  }

  /** Nebelbank: mehrere weiche Wände rund um das Flurstück verdecken alles dahinter (kein Gelände/Nachbarn sichtbar). */
  private addMist(color: string) {
    const T = this.T, ring = this.site ? this.open(this.site.site) : []; if (ring.length < 3) return;
    const cv = document.createElement('canvas'); cv.width = 1024; cv.height = 256;
    const c = cv.getContext('2d')!; const g = c.createLinearGradient(0, 256, 0, 0);
    g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.55, 'rgba(255,255,255,0.92)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = g; c.fillRect(0, 0, 1024, 256);
    let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
    c.globalCompositeOperation = 'destination-out';
    for (let i = 0; i < 90; i++) { const x = rnd() * 1024, y = 20 + rnd() * 200, r = 18 + rnd() * 46; const rg = c.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, `rgba(0,0,0,${0.10 + rnd() * 0.16})`); rg.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = rg; c.fillRect(x - r, y - r, 2 * r, 2 * r); }
    const tex = new T.CanvasTexture(cv); tex.wrapS = T.RepeatWrapping; tex.colorSpace = T.SRGBColorSpace;
    const cx = ring.reduce((s, p) => s + p[0], 0) / ring.length, cy = ring.reduce((s, p) => s + p[1], 0) / ring.length;
    const grp = new T.Group();
    [[1.0, 34], [1.05, 46], [1.11, 60]].forEach(([k, H], li) => {
      const pts = ring.map(([x, y]) => [cx + (x - cx) * k, cy + (y - cy) * k]);
      const P: number[] = [], U: number[] = [], I: number[] = []; let acc = 0;
      for (let i = 0; i <= pts.length; i++) {
        const [x, y] = pts[i % pts.length]; if (i) acc += Math.hypot(x - pts[i - 1][0], y - pts[i - 1][1]);
        const h = this.heightAt(x, y);
        const b = this.v3(x, y, h - 2), t = this.v3(x, y, h + H);
        P.push(b.x, b.y, b.z, t.x, t.y, t.z); U.push(acc / 40 + li * 0.37, 0, acc / 40 + li * 0.37, 1);
        if (i) { const a = (i - 1) * 2; I.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
      }
      const geo = new T.BufferGeometry(); geo.setAttribute('position', new T.Float32BufferAttribute(P, 3)); geo.setAttribute('uv', new T.Float32BufferAttribute(U, 2)); geo.setIndex(I);
      const m = new T.Mesh(geo, new T.MeshBasicMaterial({color, map: tex, transparent: true, opacity: 0.92, depthWrite: false, side: T.DoubleSide, fog: false}));
      m.renderOrder = 10 + li; grp.add(m);
    });
    this.scene.add(grp);
  }

  /** Kamera auf das Haus richten (Blickrichtung bleibt). */
  frameHouse() {
    const f = this.houseFrame; if (!f) return;
    this.target.set(f.x, f.y, f.z); this.sph.r = f.r; this.sph.theta = 1.0;
    this.placeCamera();
  }

  /** Rechteck (Hausrahmen) des angepassten Geländes in den Projektrahmen, dort das natürliche Gelände wegclippen. */
  private clipNatural(tpos: number[], pl: Placement, _base: number) {
    const T = this.T;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < tpos.length; i += 3) { x0 = Math.min(x0, tpos[i]); x1 = Math.max(x1, tpos[i]); y0 = Math.min(y0, tpos[i + 1]); y1 = Math.max(y1, tpos[i + 1]); }
    const e = 0.03; x0 += e; y0 += e; x1 -= e; y1 -= e;
    const a = (pl.rotation_deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a);
    const toSite = (x: number, y: number) => [pl.x + c * x - s * y, pl.y + s * x + c * y];
    const corners = [toSite(x0, y0), toSite(x1, y0), toSite(x1, y1), toSite(x0, y1)];
    const planes: any[] = [];
    for (let i = 0; i < 4; i++) {
      const p = corners[i], q = corners[(i + 1) % 4];
      let nx = q[1] - p[1], ny = -(q[0] - p[0]); const l = Math.hypot(nx, ny) || 1; nx /= l; ny /= l;   // nach außen (Rechteck gegen den Uhrzeigersinn)
      // Normale im Three-Raum (x, y=up, z=-Nord): (nx, 0, -ny); Abstand < 0 = innen
      planes.push(new T.Plane(new T.Vector3(nx, 0, -ny), -(nx * p[0] + ny * p[1])));
    }
    const meshes: any[] = [];
    const top = this.groups.plot?.children?.[0]; if (top?.isMesh && top.material) meshes.push(top);       // nur die Oberfläche; die Erdwand (Skirt) am Flurstücksrand bleibt stehen
    if (this.ground) meshes.push(this.ground);
    for (const m of meshes) {
      const mat = m.material;
      mat.clippingPlanes = planes; mat.clipIntersection = true; mat.needsUpdate = true; this.clipped.push(mat);
    }
  }
}

function pl0(s: any) { const g = s.terrainGroup; return {x: g.position.x, y: -g.position.z}; }
