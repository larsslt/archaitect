/* Shared helpers of the Hessen pages: API base, Leaflet loader, official imagery layers (through our own proxy). */
/* eslint-disable @typescript-eslint/no-explicit-any */
export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const HESSEN_BOUNDS: [[number, number], [number, number]] = [[49.3953, 7.7725], [51.6578, 10.2365]];

export function loadLeaflet(): Promise<any> {
  const w = window as any;
  if (w.L) return Promise.resolve(w.L);
  return new Promise((resolve, reject) => {
    if (!document.querySelector('link[data-leaflet]')) {
      const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = '/vendor/leaflet/leaflet.css'; css.setAttribute('data-leaflet', '1'); document.head.appendChild(css);
    }
    const s = document.createElement('script'); s.src = '/vendor/leaflet/leaflet.js';
    s.onload = () => resolve(w.L); s.onerror = () => reject(new Error('Karte konnte nicht geladen werden')); document.head.appendChild(s);
  });
}

export type BaseKey = 'karte' | 'luftbild';
export const BASE_TITLE: Record<BaseKey, string> = {karte: 'Karte', luftbild: 'Luftbild'};
/* Attribution as required by the licence (HVGG §18/§24): source note, and it says when the data were modified (here: re-projected/re-tiled/filtered). */
const ATTR: Record<BaseKey, string> = {
  karte: 'Karte: Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (verändert)',
  luftbild: 'Luftbild: Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation (verändert)',
};

/* The browser never talks to the Hessen servers: every tile goes through /siteintel/imagery/wms (allow-listed layers, Hessen only, cached). */
export function officialLayer(L: any, key: BaseKey) {
  return L.tileLayer.wms(`${API}/siteintel/imagery/wms`, {
    layers: key, format: 'image/jpeg', version: '1.3.0', transparent: false, maxZoom: 19, maxNativeZoom: 19, attribution: ATTR[key], crossOrigin: true,
    bounds: [[49.3, 7.6], [51.75, 10.35]],
  });
}

export function save(name: string, data: unknown, type = 'application/json') {
  const blob = new Blob([typeof data === 'string' ? data : JSON.stringify(data, null, 2)], {type});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); URL.revokeObjectURL(a.href);
}

export const pct = (x: number) => `${Math.round(x * 100)} %`;
