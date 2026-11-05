# Kommunale Planrecherche — 2026-11-02

## Ziel und Bedienung

Die Grundstücksseite lädt beim ersten Öffnen automatisch eine vertiefte Recherche. Unter **Amtliche Pläne & konkrete Festsetzungen** stehen die gefundenen Planfassungen, Rechtskraftdaten laut Katalog, Original-Links, gesicherte PDF-Kopien und Fundstellen mit Seitenzahl. **Neu abrufen** legt eine neue Recherche an; frühere Läufe bleiben erhalten. Die übrige App bleibt benutzbar.

## Datenweg

1. Amtlichen Hessen-Katalog `https://www.geoportal.hessen.de/spatial-objects/?f=json` täglich zwischenspeichern. Aktuell 18 standardisierte kommunale GDI-Dienste gefunden (unter anderem Hochtaunus-, Wetterau-, Bergstraße-, Odenwald-, Groß-Gerau-Kreis und einzelne Gemeinden). Das sind nicht alle hessischen Kommunen.
2. `DescribeFeatureType` je Dienst laden: Namespace und Schema unterscheiden sich (gpkg/shp). Räumliches `Intersects` gegen die konkrete Flurstücksgeometrie, anschließend geometrisch nachfiltern. Fehler, Point-Fallback und mögliche 50-Feature-Grenze bleiben sichtbar.
3. Zugehörige Fassungen anhand konservativer Katalog-ID-Familien nachladen; jede Fassung behält eigenen Geltungsbereich, Rechtskraft- und Aktualitätsdatum. Eine Änderung außerhalb des Grundstücks wird nicht automatisch auf dessen Haus angewendet. Nicht allein nach dem jüngsten Datum auswählen.
4. Dokumentlinks aus Planblatt, Planzeichnung, textlichen Festsetzungen, Begründung, Nebenbestimmungen und zusammenfassender Erklärung erfassen. Automatischer PDF-Download für den verifizierten amtlichen Hochtaunuskreis-Host und den amtlichen Wetterau-GIS-Pfad `/pdf/` (enge Dateinamenprüfung); andere Hosts bleiben als Original-Link/manuelle Lücke sichtbar. Textergebnisse werden nach PDF-Inhaltshash wiederverwendet. Keine ungeprüften URLs, Weiterleitungen oder deaktivierte TLS-Prüfung. Bei Python-Zertifikatsproblemen nutzt macOS seinen regulär verifizierenden `/usr/bin/curl`.
5. PDF-Text mit pypdf, für textarme Scans lokale Apple-Vision-OCR (de/en). Jeder Absatz behält Dokument-ID, Seite, Auslesemethode und Status UNVERIFIED_EXTRACT. Gruppierung zusätzlich nach Nutzung, Gestaltung, Stellplätzen, Wasser, Natur, Denkmal, Immissionen und Verfahren; die Suche ist begrenzt und nicht vollständig. Keine stillschweigende Tabellen- oder Rechtsauslegung.
6. Nur unmittelbar neben GRZ/GFZ stehende Zahlen werden als Vorschläge erkannt. Im Prüfformular vormerken, Original/Fassung/Teilgebiet prüfen und ausdrücklich als eigene bzw. geprüfte Vorgabe speichern. Bestehende bestätigte Werte werden vom Abruf nie verändert. Dachabhängige Höhen und Bezugsniveaus werden als Textbelege übergeben; sie passen noch nicht vollständig in den vereinfachten Regelvertrag.
7. `/context` enthält municipal_planning; BIM-Erzeugung und Textänderungen erhalten geprüfte Grenzen, eigene Vorgaben, Grundstücks-/Geländedaten sowie bis zu 16 zitierte Belege (aktuelle räumlich treffende Fassungen zuerst, Themen gemischt). Zitate sind Quelldaten, keine ausführbaren Anweisungen. Die deterministische BIM-Regelprüfung bleibt maßgeblich; offene Planprüfung erscheint als UNKNOWN.

## Grenzen und Verlässlichkeit

- Kein vollständiges Deutschland-/Hessen-Planregister und keine Vollständigkeitsgarantie für spätere Satzungen/Befreiungen.
- Räumlicher Plangeltungsbereich ist weder Baufenster noch Untergebiet. Rasterpläne werden nicht automatisch in maßgenaue Baugrenzen verwandelt.
- OCR kann Fehler erzeugen; Original und Seitenbezug bleiben verfügbar. Widersprüchliche Fassungen werden nicht automatisch verschmolzen.
- Unterschiedliche Höhenbezüge (Rohboden, Straße, Gelände), wohnflächenfremde GFZ-Anrechnungen, Dachausnahmen, Stellplatzsatzung und Pflanzgebote erfordern zusätzliche strukturierte Auswertung/Prüfung. Sie werden nicht als bereits umfassend modelliert verkauft.
- Baulasten, Grunddienstbarkeiten, Leitungsrechte und aktuelle grundstücksbezogene Altlastenauskünfte sind hier keine offenen Massendaten. Historische Begründung ist kein heutiger Negativnachweis.
- Zwei Rechercheworker, maximal vier aktive/wartende Projekte, sechs parallele Quellabfragen je Recherche. Maximal acht Downloadversuche je Lauf; Grundstücksüberdeckung und neuere Fassungen erhalten Vorrang, nicht zugelassene Hosts verbrauchen keinen Versuch. Maximal 30 MB je PDF, 40 Seiten je PDF, 90 s OCR je Seite, maximal drei OCR-Seiten und 180 s vor Start einer weiteren OCR-Seite je Dokument; abgeschnittene/fehlende Dokumente werden gekennzeichnet. Mehrere Scans können einige Minuten dauern.
- Ablage `.local/siteintel-projects/<pid>/planning/<run>/`: report.json, PDF, Textseiten. Neuester Bericht zusätzlich planning/report.json. Dateien 0600, neue Ordner 0700, keine Git-Aufnahme. Flurstückswechsel invalidiert alte Belege; Dienstneustart wird als interrupted angezeigt.

## API

`GET /siteintel/projects/{pid}/planning`: Zustand missing/queued/discovering/documents/done/failed/interrupted, run, site_signature/stale_geometry, plans, documents, evidence, candidates, Quellenstatus und offene Fragen.

`POST /siteintel/projects/{pid}/planning/refresh`: 202 mit run/state; bestehender aktiver Lauf wird wiederverwendet, Queue voll → 429. Keine bezahlte API.

`GET /siteintel/projects/{pid}/planning/files/{run}/{document_id}.pdf`: gesicherte Originalkopie, nur bekannte IDs mit PDF-Nachweis, 404 sonst.

## Lokale OCR einrichten

```sh
mkdir -p .local/tools .local/swift-module-cache
swiftc -module-cache-path .local/swift-module-cache scripts/planning-ocr.swift -o .local/tools/planning-ocr -framework Vision -framework PDFKit -framework AppKit
```

Auf diesem Mac kompiliert und an den tatsächlichen Planblättern geprüft. Andere Betriebssysteme benötigen noch einen OCR-Adapter; ohne OCR bleiben Text-PDFs lesbar und Scans sichtbar als OCR_REQUIRED. Keine kostenpflichtige Modellanfrage erforderlich.

## Nachweise

- Live-Katalog/Schema/Planrecherche unter `.local/planning-probe`: Ursprung WH100-030 (2002-03-23), WH100-030_1 (2003-04-07), verwandte räumlich separate WH100-030_2 (2004-06-25).
- Originale erneut vom amtlichen Host heruntergeladen, SHA-256 je PDF, Text und OCR lokal.
- Offline-Regressionsfixture `tests/fixtures_siteintel/planning_sample.xml`: amtlicher WFS-Ausschnitt, Abruf 02.11.2026, GDI-Südhessen/Hochtaunuskreis, Datenlizenz Deutschland Namensnennung 2.0; nur für reproduzierbare Tests, keine garantierte Aktualität.

## Ergänzung 2026-11-03 — Wetterau-GIS und robustere Fundstellen

Der amtliche Wetteraukreis nennt `gis.wetterau.de` als GIS-Dienst ([Kreis-Seite](https://wetteraukreis.de/wetterau/kreiskarten/wms-dienste)). Für URLs mit exakt diesem HTTPS-Host und dem engen Muster `/pdf/<ASCII-Dateiname>.pdf` ist der automatische PDF-Abruf ergänzt; Credentials, abweichende Ports, Query-Parameter und Weiterleitungen bleiben ausgeschlossen. Eine Originaldatei der zweiten Änderung „Im Sichler“ wurde mit 13.863.291 Bytes und PDF-Signatur live abgerufen. Das Größenlimit beträgt jetzt 30 MB; OCR-/Seitenlimits bleiben unverändert.

Planfassungen mit Grundstücksüberdeckung und neueren Katalogdaten werden beim Abruf bevorzugt; dies stellt keine automatische Aussage zur Rechtskraft oder zum gültigen Teilgebiet dar. Nicht freigegebene Hosts verbrauchen keinen der acht Downloadversuche. Themen werden bei der begrenzten Fundstellenauswahl durchmischt; dennoch ist die Texterkennung stets unvollständig möglich. Bei mehr als 60 angezeigten Treffern bzw. erschöpften Extraktionsgrenzen zeigt die Oberfläche Hinweise. Gleiche Dokumente können mehrere Katalogrollen haben; jede Rolle erscheint einmal mit eigenem React-Schlüssel. Identische frühere Fundstellen-IDs werden in der Oberfläche abgefedert, neue IDs berücksichtigen die genaue Trefferposition.
