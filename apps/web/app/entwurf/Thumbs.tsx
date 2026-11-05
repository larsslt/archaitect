'use client';
/* Vorschaubilder der Bibliothek: dasselbe 3D-Modell wie im Entwurf (GET /bim/thumb/<id>), einmal isometrisch mit transparentem Hintergrund gerendert
   und als PNG zwischengespeichert. Kein Emoji, kein Platzhalter: was man in der Bibliothek sieht, ist das, was auf dem Grundstück steht. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import {useEffect, useState} from 'react';
import {loadThree} from '../studio/scene3d';

const GEN = 't4';
const mem = new Map<string, string>();
const pending = new Map<string, Promise<string | null>>();
let renderer: any = null;
let chain: Promise<unknown> = Promise.resolve();

function stored(key: string): string | null {
  try { return window.localStorage.getItem(`archaitect-thumb-${GEN}-${key}`); } catch { return null; }
}
function store(key: string, v: string) {
  try { window.localStorage.setItem(`archaitect-thumb-${GEN}-${key}`, v); } catch { /* voll oder gesperrt: dann eben nur im Speicher */ }
}

async function draw(T: any, mesh: any, w: number, h: number): Promise<string | null> {
  if (!mesh?.parts?.length) return null;
  if (!renderer) {
    renderer = new T.WebGLRenderer({antialias: true, alpha: true, preserveDrawingBuffer: true});
    renderer.setPixelRatio(1);
    renderer.setClearColor(0x000000, 0);
    if ('outputColorSpace' in renderer && T.SRGBColorSpace) renderer.outputColorSpace = T.SRGBColorSpace;
  }
  renderer.setSize(w, h, false);
  const scene = new T.Scene();
  const g = new T.Group();
  for (const p of mesh.parts) {
    if (p.name === 'terrain') continue;
    const n = p.positions.length / 3, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = p.positions[i * 3]; pos[i * 3 + 1] = p.positions[i * 3 + 2]; pos[i * 3 + 2] = -p.positions[i * 3 + 1]; }
    let geo = new T.BufferGeometry();
    geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.setIndex(p.indices);
    geo = geo.toNonIndexed(); geo.computeVertexNormals();
    const mat = new T.MeshStandardMaterial({color: new T.Color(p.color[0], p.color[1], p.color[2]), roughness: 0.85, metalness: 0, side: T.DoubleSide,
      transparent: p.opacity < 1, opacity: p.opacity});
    g.add(new T.Mesh(geo, mat));
  }
  scene.add(g);
  scene.add(new T.HemisphereLight(0xffffff, 0x8a8f98, 1.55));
  const sun = new T.DirectionalLight(0xfff4e0, 2.2); sun.position.set(-4, 9, 6); scene.add(sun);
  const box = new T.Box3().setFromObject(g);
  const c = box.getCenter(new T.Vector3()), s = box.getSize(new T.Vector3());
  const r = Math.max(0.5, Math.hypot(s.x, s.y, s.z) / 2);
  const cam = new T.PerspectiveCamera(26, w / h, 0.1, r * 40);
  const dist = (r / Math.sin((26 / 2) * Math.PI / 180)) * 0.92;
  const dir = new T.Vector3(1, 0.78, 1.12).normalize();
  cam.position.copy(c).addScaledVector(dir, dist); cam.lookAt(c);
  renderer.render(scene, cam);
  const url: string = renderer.domElement.toDataURL('image/png');
  g.traverse((o: any) => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
  return url;
}

/** Vorschaubild als Data-URL (oder null, wenn der Server das Element nicht bauen kann). Läuft nacheinander, damit ein einziger GL-Kontext reicht. */
export function thumbnail(base: string, id: string): Promise<string | null> {
  const key = id;
  const hit = mem.get(key) ?? stored(key);
  if (hit) { mem.set(key, hit); return Promise.resolve(hit); }
  const run = pending.get(key);
  if (run) return run;
  const job = (chain = chain.then(async () => {
    try {
      const res = await fetch(`${base}/thumb/${id}`);
      if (!res.ok) return null;
      const T = await loadThree();
      const url = await draw(T, await res.json(), 640, 480);
      if (url) { mem.set(key, url); store(key, url); }
      return url;
    } catch { return null; }
  }).finally(() => pending.delete(key)) as Promise<string | null>);
  pending.set(key, job);
  return job;
}

export function Thumb({base, id, label}: {base: string; id: string; label: string}) {
  const [src, setSrc] = useState<string | null>(() => mem.get(id) ?? null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    void thumbnail(base, id).then((u) => { if (!live) return; if (u) setSrc(u); else setFailed(true); });
    return () => { live = false; };
  }, [base, id]);
  if (src) return <img className="lib-thumb" src={src} alt={label} draggable={false} />;
  return <div className={`lib-thumb ph${failed ? ' fail' : ''}`} role="img" aria-label={label}>{failed ? '' : <i />}</div>;
}
