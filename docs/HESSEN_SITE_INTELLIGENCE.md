# Hessen-Standortprüfung (siteintel)

Stand 2026-10-28. Klick auf die Karte oder Ortssuche → Flurstück → amtliche Daten → Grundregeln → Übergabe an Entwurf/Architektur.
Orientierende Vorprüfung auf Open-Data-Basis, **keine** Baugenehmigung und keine Rechtsauskunft. Nichts wird je als „verifiziert“ ausgegeben, solange kein Mensch Werte aus Bebauungsplan/Behörde bestätigt hat.

## Ablauf eines Klicks
1. `GET /siteintel/assess/core?lat&lon` (Ziel < 1 s): ALKIS-Flurstück (sequentiell, ~0,01–0,4 s), danach parallel ALKIS-Bodennutzung (ELU), Gebäude, Bodenrichtwert (BORIS).
2. `GET /siteintel/assess?lat&lon` (Cache warm, ~0,3–1,6 s): zusätzlich Regionaler FNP, Landesentwicklungsplan, **nur** der Regionalplan der Planungsregion des Punktes, Denkmal (DenkXweb), Überschwemmungsgebiet HQ100, optional OSM.
3. Das Frontend zeigt Antwort 1 sofort und ersetzt sie durch Antwort 2 („Planung & Schutz laden“).
4. Übergabe: `GET /siteintel/dossier` (Vertrag `archaitect.site-dossier/1`), `GET /siteintel/parcel-input` (genau das `GeoJSONParcelInput` für `POST /geodata/validate`), `POST /siteintel/dossier/constraints` (einziger Weg zu `VERIFIED_BY_USER`).

Gemessen (Mac, live, kalt): Core 0,4–1,1 s, Full 0,3–1,6 s, wiederholt aus dem Cache < 0,4 s. Das Flurstück ist der einzige sequentielle Schritt; alles andere läuft auf einem gemeinsamen Thread-Pool (16) mit Zeitbudget (core 9 s, full 14 s).

## Warum früher überall „Entwurf gesperrt“ stand
Die Entscheidung hing an Overpass/OSM. War der Dienst langsam oder limitiert, wurde das Ergebnis UNKNOWN und der Entwurf gesperrt. Jetzt entscheiden die amtlichen Quellen. OSM ist eine optionale Verfeinerung (ein Endpunkt, 3,5 s Timeout, danach höchstens 0,6 s Nachlauf) und kann das Ergebnis nur ergänzen.

`design_mode`:
- `full` – nichts spricht dagegen (weiterhin unverifiziert).
- `exploration` – Entwurf mit sichtbarem Vorbehalt (eingeschränkt, unklar, Kernquelle ausgefallen).
- `blocked` – nur bei harter amtlicher Evidenz (nicht-wohnbare Nutzung wie Wald, Verkehr, Wasser, Verteidigung) oder ohne Flurstück. Ist die Sperre nur durch eine Quelle mittlerer Sicherheit begründet (z. B. OSM-Militär widerspricht ALKIS-Wohnen), ist `design_override_allowed` gesetzt und die UI bietet „als Studie trotzdem öffnen“.

## Quellen (alle live geprüft 2026-10-28, WFS 2.0.0 / GML 3.2 / EPSG:4326)
| id | Inhalt | Lizenz |
|---|---|---|
| alkis-inspire-he | Flurstücke (OGC-API) | DL-DE Zero 2.0 |
| elu | Bodennutzung INSPIRE ELU (HILUCS) | DL-DE Zero 2.0 |
| buildings | Gebäude 2D | DL-DE Zero 2.0 |
| boris | Bodenrichtwerte 2024 | DL-DE Zero 2.0 |
| regfnp | Regionaler FNP FrankfurtRheinMain | siehe Dienst |
| rp_sued / rp_mittel / rp_nord | Regionalpläne | dl-by-de/2.0 (Namensnennung) |
| lep | Landesentwicklungsplan | dl-by-de/2.0 (Namensnennung) |
| hq100 | Überschwemmungsgebiete HQ100 | DL-DE Zero 2.0, nicht rechtsverbindlich |
| denkmal | DenkXweb | siehe Dienst |
| osm-overpass | optional, Verfeinerung | ODbL |

Der Bezug der Hessen-Geobasisdaten ist automatisiert frei (§ 24 HVGG).

## Technische Erkenntnisse (wichtig für Betrieb)
- Serverseitiger Filter: `wfs:GetFeature` per **POST** mit `fes:Intersects` (Punkt oder Flurstückspolygon, GML 3.2, bei URN-CRS lat/lon-Reihenfolge) liefert genau die überdeckenden Objekte in 0,15–0,5 s. Bbox-GET lieferte bis 2,8 MB und konnte am `count`-Limit abschneiden. GET mit Filter ergibt 403 auf dem Landesplanungs-nginx. Gebäude (komplexer Geometriepfad) nutzen weiter Bbox-GET.
- Die Landesplanungs-Dienste liefern teils HTTP 200 mit abgeschnittenem XML (ohne schließendes `FeatureCollection`). `wfs.repair_truncated` repariert, unbrauchbare Antworten (Exception-Report, HTML, abgeschnitten) werden **nie** gecacht.
- Regionalpläne und große Waldflurstücke: Polygonabfrage dauerte bis 5 s, Punktabfrage 0,5 s. Daher `point_only` und Auswahl des Regionalplans über das Gemeindekennzeichen aus BORIS (4 Darmstadt, 5 Gießen, 6 Kassel).
- `PropertyName` verkleinert die Antwort nicht. Gelegentlich HTTP 500 (rp_mittel): ein Retry ist eingebaut.
- Persistenter SQLite-Cache (zlib) mit stale-if-error: amtliche 7 Tage, BORIS 30, HQ100 14. Pfad `ARCHAITECT_SITEINTEL_CACHE`, Standard `<repo>/.local/siteintel-cache.sqlite`. OSM abschaltbar mit `ARCHAITECT_SITEINTEL_OSM=0`.

## Regelwerk (Auszug, Quelle `decision.py`)
HILUCS per längstem Präfix: 1_2 Forst, 1_3 Bergbau, 3_3_1 Verwaltung/Verteidigung, 4_1 Verkehr, 4_3 Ver-/Entsorgung, 6_3_2 Wasser → NOT_BUILDABLE; 1_1 Landwirtschaft, 2 Industrie, 3 Dienstleistung/Gewerbe, 3_4 Erholung, 4 Sonstiges → RESTRICTED (Landwirtschaft/Gewerbe/Dienstleistung „weich“); 5 Wohnen → CANDIDATE.
- Jede NOT_BUILDABLE-Evidenz sperrt. Sicherheit HIGH bei zwei übereinstimmenden Quellen oder HIGH-Top-Befund, sonst MEDIUM.
- Weiche Einschränkungen heben sich auf CANDIDATE durch: BORIS Bauland, FNP Wohnen, Innenbereichs-Indiz (≥ 8 Wohngebäude im Umkreis, LOW), ELU-Wohnanteil ≥ 40 %.
- Harte Einschränkungen werden nie gehoben: HQ100, Regionalplan-Freiraum (Ziel ≥ 25 %), BORIS Außenbereich, BORIS nicht baureif, Sonderfläche, BORIS Gewerbe.
- BORIS-Ergänzung `MIL` → NOT_BUILDABLE (mittel; Bedeutung „Militär“ ist Annahme, ~85 % sicher). Denkmal ist Hinweis (`affects_verdict=false`).
- Widerspricht ein RESTRICTED-Befund einem CANDIDATE-Ergebnis (z. B. FNP „Bildung“), steht „Widerspruch beachten“ im Grund.
- „Grundlegende Vorschriften“ (`regulations`): Bauplanungsrecht, Bebauungsplan (**nicht angebunden**), FNP, Nutzung, Bodenrichtwert, Bestand, Denkmal, Hochwasser, Regionalplan, Abstandsflächen (**ungeprüfter Kandidat**, HBO 0,4 H, min. 2,5 m, nur Sekundärquelle), Ausnutzung (nicht angebunden).

## Übergabevertrag
`SiteDossier` enthält Gate (Modus, Verdict, Sicherheit, Override), Standort, MACE-Ausgabe (`parcel_geometry`, `architectural_constraints`, `pipeline_telemetry`), Vorschriften, Kontext, bekannte Constraints mit Status (`OFFICIAL_DATA` / `INDICATION` / `UNVERIFIED_CANDIDATE` / `VERIFIED_BY_USER`) und offene Fragen. `architectural_constraints` bleibt leer, bis `VerifiedConstraints` (verified_by + basis_de Pflicht) gesetzt ist; dann wird bei Abstand eine gleichmäßige Bauzone (Flurstück minus Abstand) abgeleitet, mit Flags `ENVELOPE_UNIFORM_SETBACK_ONLY` und `EASEMENTS_NOT_CONSIDERED`. Gesperrte Standorte werden nicht übernommen.

## Offene Punkte / Risiken
- Bebauungspläne der Gemeinden (GRZ/GFZ, Baugrenzen, Geschosse) sind nicht angebunden; ohne sie bleibt jedes Ergebnis eine Vorprüfung.
- Schutzgebiete (Natura 2000, NSG/LSG über HLNUG/NATUREG bzw. BfN) sind nicht angebunden; bodenviewer/geodienste-umwelt bieten `inspire/schutzgebiete` als Kandidat, nicht geprüft.
- Baulasten, Grunddienstbarkeiten, Leitungsrechte stehen nicht in Open Data.
- Die HBO-Werte sind nicht gegen den Primärtext geprüft. BORIS „MIL“ ist nicht dokumentiert.
- Die Cloud-Umgebung erreicht die Hessen-Dienste nicht; Tests laufen deshalb mit aufgezeichneten Antworten (`tests/fixtures_siteintel/wfs`), der Live-Rauchtest nur auf dem Mac.
- Overpass war am 2026-10-28 teils nicht erreichbar; das System liefert dann trotzdem vollständige amtliche Ergebnisse.

## Tests
`apps/api/tests/test_siteintel.py` (43 Tests): Parser, Achsenreihenfolge, abgeschnittene Antworten, Entscheidungsregeln, Router, Dossier, Hand-over zu `/geodata/validate`, OSM-Nachlauf. Gesamtsuite Mac: 115 bestanden. `next build` grün.

## Projektfluss und Hausplanung (Stand 2026-10-28, Mittag)
`/` Projektübersicht → `/hessen` Grundstück wählen → `/hessen/plan?p=<id>` Daten und Brief → `/studio?p=<id>` Hausplanung. Fortschritt (Grundstück, Daten, Programm, Anschlüsse, Vorschriften, Entwurf) berechnet `siteintel/progress.py`; die Karte nennt den nächsten Schritt samt Ziel.
Endpunkte: `GET /siteintel/projects` (Karten), `PUT /projects/{id}/meta`, `DELETE`, `POST /projects/{id}/duplicate`, `GET /projects/{id}/thumb.jpg`, `POST /projects/{id}/studio` (Entwurfsprojekt anlegen oder Kontext auffrischen), `POST /projects/{id}/studio/suggest` (Varianten, Ziele max_gfa, balanced, compact).
Regeln im Studio: VERIFIED nur aus `VerifiedConstraints`; ohne Eingabe bleibt alles UNKNOWN. Grenzen: Baufenster nur gleichmäßiger Abstand, Gebäudehöhen der Umgebung geschätzt, Gelände ohne Bäume, keine Leitungsverläufe, Entwurf ist Massing und keine Genehmigungsplanung.

## Regeln, KI-Entwurf und mehrere Flurstücke (Stand 2026-10-28, Nachmittag)
Regel-Arten: verbindlich (Flurstücksgrenze, erhaltener Bestand; B-Plan-Werte nach Eintrag mit Fundstelle), Hinweis (§ 6 HBO Abstandsflächen 0,4 H, mind. 2,50 m, je Wand inkl. Gelände und Dachanrechnung), Info (§ 34 BauGB Umgebung).
Endpunkte: `GET/POST /siteintel/projects/{id}/design[/check|/fit|/commit|/restore|/history|/generate]`, `GET/POST /projects/{id}/parcels`, `/projects/{id}/references[...]` (Upload als Base64, PNG/JPEG/WebP/PDF ≤ 12 MB, Signaturprüfung), `/projects/{id}/render` (Meta-Bild-API), `GET /siteintel/ai/status`.
KI-Konfiguration: `ARCHAITECT_AI_PROVIDER` (ollama|meta), `OLLAMA_HOST`, `ARCHAITECT_OLLAMA_MODEL`, `ARCHAITECT_OLLAMA_VISION`, `META_API_KEY`, `ARCHAITECT_META_MODEL`.

## Machbarkeit ganz Deutschland (Bewertung 2026-10-28)
Technisch ja, effizient nur als Länder-Adapter. Die EU-Durchführungsverordnung zu hochwertigen Datensätzen (HVD, anwendbar seit 09.06.2024) verlangt offene Geobasisdaten wie Flurstücke, Gebäude, Orthofotos und Höhenmodelle; laut CISS-Übersicht haben die meisten Länder ALKIS (ohne Eigentümer) seitdem geöffnet, Bayern nur eingeschränkt (Parzellenkarte, DOP40, DGM1), Saarland und Sachsen-Anhalt waren zum Stichtag noch in Planung (zu prüfen).
Pro Land nötig: Dienst-Adapter (WFS/OGC-API, Formate, Lizenztext, Attribution), Bauordnung als Regelmodul (Abstandsflächen-Faktor und Mindestmaß unterscheiden sich je Land), Planungsdaten (Regional-/Landesplanung, Schutzgebiete). Bebauungspläne bleiben kommunal und uneinheitlich (XPlanung nur teilweise), daher weiter Eingabe mit Fundstelle.
Aufwand-Schätzung: je Land 1–3 Tage für Geobasisdaten-Adapter + Tests, 1–2 Tage für das Bauordnungsmodul; Reihenfolge nach Datenlage (NRW, Niedersachsen, Baden-Württemberg, Rheinland-Pfalz zuerst). Architektur ist vorbereitet: Quellen in `sources.py`, Regeln in `regs.py` (HBO-Konstanten als Modul auslagern).
Quellen: WIK-Kurzstudie Offene Katasterdaten (12/2022), CISS „Open Data ab dem 09.06.2024“.
