'use client';
/**
 * UI language layer. The source strings are German; the English UI is produced by a dictionary (i18n-en.json, German → English).
 * Default language: English (override per machine with NEXT_PUBLIC_DEFAULT_LANG=de in .env.local). The choice is stored in localStorage.
 * Text nodes and the attributes placeholder/title/aria-label/alt are translated after hydration and kept in sync by a MutationObserver.
 * Strings that are assembled at runtime (with numbers or names) or come from the API stay German unless the dictionary has them verbatim.
 */
import {useEffect, useState} from 'react';
import EN from './i18n-en.json';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type Lang = 'en' | 'de';
const KEY = 'archaitect.lang';
const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
const DICT = new Map<string, string>(Object.entries(EN as Record<string, string>).map(([k, v]) => [k.replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim(), v]));
// strings assembled at runtime (counts, versions, parcel names, ages)
const UNIT: Record<string, string> = {'Min.': 'min', 'Std.': 'h', 'Tag': 'd', 'Tagen': 'd'};
const RULES: [RegExp, (m: RegExpExecArray) => string][] = [
  [/^Für das Haus \(Grundfläche (\d+) m², etwa (\d+) × (\d+) m\) wurde auf dem Suchraster kein passender Standort in der geometrisch freien Fläche gefunden \((\d+) m², etwa (\d+) × (\d+) m nach Abzug von Bestand und gegebenenfalls einem eingetragenen Baufenster\)\. Versuche einen kompakteren Entwurf; ein Bestandsgebäude lässt sich in den Projektdaten als Abriss annehmen, wenn dies tatsächlich vorgesehen ist\.(?: – .*)?$/, (m) => `No suitable location was found on the search grid for the house (footprint ${m[1]} m², about ${m[2]} × ${m[3]} m) within the geometrically free area (${m[4]} m², about ${m[5]} × ${m[6]} m after subtracting existing buildings and any recorded building window). Try a more compact design; an existing building can be assumed demolished in the project data if that is actually intended.`],
  [/^Bearbeitet vor (\d+) (Min\.|Std\.|Tagen|Tag)$/, (m) => `Edited ${m[1]} ${UNIT[m[2]]} ago`],
  [/^(\d+) Gebäude$/, (m) => `${m[1]} ${m[1] === '1' ? 'building' : 'buildings'}`],
  [/^(\d+) Gebäude, (.+)$/, (m) => `${m[1]} ${m[1] === '1' ? 'building' : 'buildings'}, ${m[2]}`],
  [/^Haus v(\d+)$/, (m) => `House v${m[1]}`],
  [/^Flurstück (.+) öffnen$/, (m) => `Open parcel ${m[1]}`],
  [/^Flurstück (.+)$/, (m) => `Parcel ${m[1]}`],
  [/^Flurstücke \((\d+) von (\d+)\)$/, (m) => `Parcels (${m[1]} of ${m[2]})`],
  [/^(\d+) Planfassungen · (\d+) Dokumente mit Text · (\d+) Fundstellen\. Recherche: (.+)$/, (m) => `${m[1]} plan versions · ${m[2]} documents with text · ${m[3]} passages found. Research: ${m[4]}`],
  [/^Nach den angebundenen Quellen spricht nichts Hartes gegen einen Wohnhaus-Entwurf\. Bebauungsplan und Abstandsrecht sind trotzdem noch zu prüfen\.(?: Widerspruch beachten: (.+?)\.?)?$/, (m) => 'According to the connected sources nothing hard speaks against a residential design. Development plan and setback rules still have to be checked.' + (m[1] ? ` Note the conflict: ${m[1].replace('Flächennutzungsplan', 'Land-use plan').replace('Öffentliche Einrichtung', 'Public facility')}.` : '')],
];

// ---- dynamic German (API texts, assembled sentences): translated on demand by the backend (cached on disk there and in localStorage here)
const DYN = new Map<string, string>();
const DKEY = 'archaitect.i18n.dyn.v2';
try { const o = JSON.parse(localStorage.getItem(DKEY) || '{}'); for (const k of Object.keys(o)) DYN.set(k, o[k]); } catch { /* none */ }
const pending = new Set<string>();
const asked = new Set<string>();
const done = new Set<string>();      // answered (translated or unchanged): never hide again
let timer: ReturnType<typeof setTimeout> | null = null;
let refresh: (() => void) | null = null;
/** numbers become {0},{1}… so one translated template serves all numeric variants of a sentence */
function templ(core: string): {s: string; nums: string[]} {
  const nums: string[] = [];
  const s = core.replace(/\d+(?:[.,]\d+)?/g, (m) => { nums.push(m); return `{${nums.length - 1}}`; });
  return {s, nums};
}
const fill = (en: string, nums: string[]) => en.replace(/\{(\d+)\}/g, (_m, i) => nums[+i] ?? '');
const GERMAN = /[äöüÄÖÜß]|\b(und|der|die|das|für|nicht|mit|oder|wird|werden|ein|eine|einen|im|auf|zu|von|bei|noch|keine|kein|Haus|Flurstück|Gebäude|Grundstück)\b/;
function enqueue(core: string, el?: Element | null): boolean {
  if (core.length < 8 || core.length > 2000 || !GERMAN.test(core) || !/[a-zA-Z]{3}/.test(core)) return false;
  const key = templ(core).s;
  if (DYN.has(key) || done.has(key)) return false;
  if (el) { el.classList.add('i18n-wait'); setTimeout(() => el.classList.remove('i18n-wait'), 10000); }   // hide German until the translation arrives (max 10 s)
  if (asked.has(key)) return true;
  asked.add(key); pending.add(key);
  if (!timer) timer = setTimeout(flush, 250);
  return true;
}
async function flush() {
  timer = null;
  const batch = [...pending].slice(0, 30); batch.forEach((b) => pending.delete(b));
  if (pending.size) timer = setTimeout(flush, 200);
  if (!batch.length) return;
  try {
    const r = await fetch(`${API}/siteintel/i18n/en`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({texts: batch})});
    if (!r.ok) { document.querySelectorAll('.i18n-wait').forEach((e) => e.classList.remove('i18n-wait')); batch.forEach((k) => asked.delete(k)); return; }
    const j = await r.json(); let n = 0;
    for (const [k, v] of Object.entries(j.map ?? {})) if (typeof v === 'string' && v && v !== k) { DYN.set(k, v); n++; }
    for (const k of batch) done.add(k);
    if (!pending.size) document.querySelectorAll('.i18n-wait').forEach((e) => e.classList.remove('i18n-wait'));
    if (n) { try { localStorage.setItem(DKEY, JSON.stringify(Object.fromEntries([...DYN].slice(-1500)))); } catch { /* full */ } refresh?.(); }
  } catch { document.querySelectorAll('.i18n-wait').forEach((e) => e.classList.remove('i18n-wait')); /* offline: stays German */ }
}
const defaultLang = (): Lang => (process.env.NEXT_PUBLIC_DEFAULT_LANG === 'de' ? 'de' : 'en');

function readLang(): Lang {
  try { const v = localStorage.getItem(KEY); if (v === 'en' || v === 'de') return v; } catch { /* storage unavailable */ }
  return defaultLang();
}

const origText = new WeakMap<Node, string>();
const shownText = new WeakMap<Node, string>();
const origAttr = new WeakMap<Element, Record<string, string>>();
const shownAttr = new WeakMap<Element, Record<string, string>>();

function tr(s: string): string | null {
  const m = /^(\s*)([\s\S]*?)(\s*)$/.exec(s);
  if (!m || !m[2]) return null;
  const core = m[2].replace(/\s+/g, ' ');
  let en = DICT.get(core);
  if (!en) for (const [re, f] of RULES) { const r = re.exec(core); if (r) { en = f(r); break; } }
  if (!en) { const t = templ(core); const e = DYN.get(t.s); if (e) en = fill(e, t.nums); }
  return en ? m[1] + en + m[3] : null;
}

function skip(el: Element | null): boolean {
  return !!el && !!el.closest('script,style,textarea,[data-no-i18n]');
}

function applyText(n: Node, lang: Lang) {
  if (skip(n.parentElement)) return;
  const cur = n.nodeValue ?? '';
  if (shownText.get(n) !== cur) origText.set(n, cur);       // React (or the page) wrote a new value: that is the new German original
  const orig = origText.get(n) ?? cur;
  let out = orig;
  if (lang === 'en') { const t = tr(orig); if (t) { out = t; n.parentElement?.classList.remove('i18n-wait'); } else if (!n.parentElement?.closest('.bubble.user,input,textarea,[data-no-i18n]')) enqueue(orig.replace(/\s+/g, ' ').trim(), n.parentElement); }
  if (out !== cur) n.nodeValue = out;
  shownText.set(n, out);
}

function applyAttrs(el: Element, lang: Lang) {
  if (el.closest('script,style,[data-no-i18n]')) return;
  const o = origAttr.get(el) ?? {};
  const s = shownAttr.get(el) ?? {};
  for (const a of ATTRS) {
    const cur = el.getAttribute(a);
    if (cur == null) continue;
    if (s[a] !== cur) o[a] = cur;
    const orig = o[a] ?? cur;
    let out = orig;
    if (lang === 'en') { const t = tr(orig); if (t) out = t; else enqueue(orig.replace(/\s+/g, ' ').trim()); }
    if (out !== cur) el.setAttribute(a, out);
    s[a] = out;
  }
  origAttr.set(el, o);
  shownAttr.set(el, s);
}

function walk(root: Node, lang: Lang) {
  if (root.nodeType === Node.TEXT_NODE) { applyText(root, lang); return; }
  if (root.nodeType !== Node.ELEMENT_NODE) return;
  applyAttrs(root as Element, lang);
  const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) (n.nodeType === Node.TEXT_NODE ? applyText(n, lang) : applyAttrs(n as Element, lang));
}

export default function I18n() {
  const [lang, setLang] = useState<Lang>(defaultLang());
  useEffect(() => { setLang(readLang()); }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
    walk(document.body, lang);
    refresh = () => walk(document.body, lang);
    const w = window as any;
    if (!w.__i18nDialogs) {
      w.__i18nDialogs = true;
      for (const fn of ['alert', 'confirm', 'prompt']) { const orig = w[fn].bind(w); w[fn] = (msg?: any, ...r: any[]) => orig(typeof msg === 'string' && document.documentElement.lang === 'en' ? (tr(msg) ?? msg) : msg, ...r); }
    }
    const ti = document.querySelector('title');
    if (ti && lang === 'en') { const t = tr(document.title); if (t) document.title = t; }
    const mo = new MutationObserver((list) => {
      mo.disconnect();
      for (const m of list) {
        if (m.type === 'characterData') applyText(m.target, lang);
        else if (m.type === 'attributes') applyAttrs(m.target as Element, lang);
        else m.addedNodes.forEach((n) => walk(n, lang));
      }
      mo.observe(document.body, cfg);
    });
    const cfg: MutationObserverInit = {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS};
    mo.observe(document.body, cfg);
    return () => mo.disconnect();
  }, [lang]);
  const pick = (l: Lang) => { setLang(l); try { localStorage.setItem(KEY, l); } catch { /* ignore */ } };
  return (
    <div className="lang-switch" data-no-i18n role="group" aria-label="Language">
      {(['en', 'de'] as Lang[]).map((l) => <button key={l} type="button" aria-pressed={lang === l} onClick={() => pick(l)}>{l.toUpperCase()}</button>)}
    </div>
  );
}
