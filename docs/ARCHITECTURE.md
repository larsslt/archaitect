## Ergänzung 2026-11-02 — Hessenweite baurechtliche Vorprüfung

Amtliches Gemeindeverzeichnis, zehn Rechts-/Verfahrensquellen, 27 Prüfbereiche, getrennte BIM-Rechenkontrollen und eine versionierte Nachweisakte sind eingebaut. Gemeindezugang bedeutet keine vollständige Satzungsabdeckung; die App erteilt keine automatische Rechtsfreigabe. Bedienung, Schnittstellen, Aktualitäts-/Änderungsregeln und verbleibende Datenlücken: [HESSEN_LEGAL_REVIEW.md](HESSEN_LEGAL_REVIEW.md).

## Ergänzung 2026-11-02 — Automatische kommunale Planrecherche

Grundstücksbezogene Plansuche, zusammengehörige Fassungen, gesicherte PDF-Originale, lokale OCR und zitierbarer BIM-Kontext sind angebunden. Keine automatische Verifikation von Rechtswerten. Bedienung, Grenzen, API und Einrichtung: [MUNICIPAL_PLANNING.md](MUNICIPAL_PLANNING.md).

# Aktueller Entwurfs- und Renderingpfad — 2026-11-01

Ein zusammenhängender Ablauf: Grundstück und Quellen (ALKIS, DGM1, Baurecht) → Haus per Text/Foto → IFC4 → 360°-Ansicht, Grundrisse und Cycles-Render. `/entwurf` ist die einzige Entwurfsseite.

**Eine Geometriequelle:** die Gebäudespezifikation (`archaitect/bim`, JSON, Hausrahmen, Fertigfußboden 0). `site.placement {x, y, rotation_deg}` setzt sie in den Projektrahmen. IFC4 (`ifcgen`), das Browser-Netz (`meshexport`), die Grundrisse (`plan`) und der Blender-Render (`blender/render_ifc.py`) werden alle daraus abgeleitet.

**Baurecht:** `siteintel/bim_bridge.py` macht aus den Volumen ein `massing.Massing` im Projektrahmen und lässt `regs.evaluate`/`limits` laufen; fehlende Eingaben bleiben UNKNOWN. Die Platzierung sucht ein Baufenster in `ctx.hard_region`.

**Gelände:** `bim/terrain.py` ebnet den Bauplatz aus dem DGM1 (Plateau, Böschung ≤ 1:2, Abtrag/Aufschüttung in m³). Das Ergebnis wird je Version berechnet und gecacht, nie in der Spezifikation gespeichert. Blender, Browser-Netz und Zusammenfassung nutzen dieselben Daten.

**API:** `siteintel/bim_api.py` (`/siteintel/projects/{pid}/bim/…`). Frontend: `apps/web/app/entwurf/page.tsx` mit `BimScene.ts` (erweitert `SiteScene` aus `app/studio/scene3d.ts`).

## Boundaries
- `models.py`: explicit contracts and versioning.
- `geometry.py`: metric coordinates, polygons, area and placement.
- `constraints.py`: three-valued result PASS/FAIL/UNKNOWN; uncertified regulatory inputs do not yield PASS.
- `fixtures.py`: mock parcel and mock planning regulations, meticulously marked DEMO_ASSUMPTION.
- `main.py`: HTTP API backed by the transactional SQLite revision store in `store.py`; single-service development/demo persistence.

## Geographic data
For real integration: authoritative ALKIS cadastral geometry and appropriate metric CRS; preserve source timestamp, license, and reconciliation to lot reference 2/10. Site imagery is only context, not the property boundary. Treat Bauleitplan version and date of entry into force as separate facts to verify.

## Eventual modules
Implemented prototype modules include bounded Meta command proposals, deterministic validation, schematic SVG 3D massing, solar-position approximation and JSON evidence reports. Real source/document ingestion, authoritative geodata and production operation remain future work. Local setup: `docs/LOCAL_SETUP.md`.

## Deployment
Web Vercel, FastAPI managed service, restricted CORS. Auth, upload scanning, rate limits, durable persistence, permissions and audit trails required before any public customer release.

## Proposed single-device rendering extension — 2026-10-27


Proposed local renderer: a pinned, tested Blender/Cycles worker invoked as a subprocess, with a CPU fallback and detected optional GPU acceleration. D5 is an optional Windows export/import adapter; Kling and Meta are explicit external API adapters. Local model rendering and a camera-animation path must remain usable without paid keys; live generative AI features still require their configured providers. No separate renderer repository, database, microservice fleet or mandatory second computer. Use the existing local persistence/job mechanisms before introducing a new broker.

