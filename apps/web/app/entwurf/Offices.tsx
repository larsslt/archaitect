'use client';

/** Zuständige Stellen für offene Daten; „Kontaktieren“ öffnet die Suche nach der Stelle (mit Flurstück). Es wird nichts gesendet. */
type Req = {label?: string | null; gemeinde?: string | null; address?: {strasse?: string | null; hausnummer?: string | null; plz?: string | null; ort?: string | null}; area_m2?: number | null;
  zaehler?: number | null; nenner?: number | null; flur?: number | null; gemarkung_nr?: string | null; national_reference?: string | null; protections?: string[]};

const BPLAN = 'https://bauleitplanung.hessen.de/interaktive-karten/interaktive-karte-bebauungsplaene';

const OFFICES = (r: Req) => {
  const where = r.gemeinde ?? r.address?.ort ?? '';
  const list = [
    {id: 'plan', title: 'Bauamt / Stadtplanung der Gemeinde', what: 'Gilt ein Bebauungsplan? GRZ, GFZ, Höhe, Dachform', find: `Bauamt Stadtplanung ${where} Bebauungsplan Auskunft`},
    {id: 'bauaufsicht', title: 'Untere Bauaufsicht', what: 'Bauvoranfrage, § 34, Baulasten, Abstandsflächen', find: `Untere Bauaufsichtsbehörde ${where}`},
  ];
  const pr = r.protections ?? [];
  if (pr.some((k) => k === 'denkmal' || k === 'archaeologie')) list.push({id: 'denkmal', title: 'Untere Denkmalschutzbehörde', what: 'Denkmalschutz auf oder neben dem Flurstück', find: `Untere Denkmalschutzbehörde ${where}`});
  if (pr.some((k) => k === 'hq100')) list.push({id: 'wasser', title: 'Untere Wasserbehörde', what: 'Überschwemmungsgebiet', find: `Untere Wasserbehörde ${where}`});
  return list;
};

export default function Offices({req}: {req: Req | null | undefined}) {
  if (!req || (!req.label && !req.zaehler)) return null;
  const nr = req.zaehler ? `${req.zaehler}${req.nenner ? `/${req.nenner}` : ''}` : req.label;
  return (
    <div className="entw-offices">
      <div className="entw-sub">Offene Daten beim Amt erfragen</div>
      <ul className="off-list">
        {OFFICES(req).map((o) => (
          <li key={o.id}>
            <b>{o.title}</b><span>{o.what}</span>
            <div className="off-btns">
              <a href={`https://www.google.com/search?q=${encodeURIComponent(`${o.find} Flurstück ${nr ?? ''}`.trim())}`} target="_blank" rel="noreferrer">Kontaktieren</a>
            </div>
          </li>
        ))}
      </ul>
      <div className="off-btns"><a href={BPLAN} target="_blank" rel="noreferrer">Bebauungspläne Hessen (Karte)</a></div>
    </div>
  );
}
