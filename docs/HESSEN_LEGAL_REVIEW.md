# Hessen: baurechtliche Vorprüfung und Nachweisakte

Stand: 02.11.2026. Implementierte Wohngebäude-Vorprüfung, **keine vollständige automatische Prüfung oder Genehmigung**. Die neue Nachweisakte ergänzt Geodaten, Planrecherche und BIM. Sie verändert keine Gebäudeversionen oder bestätigten Vorschriften.

## Was automatisch funktioniert

1. Amtliche Flurstücksdaten liefern die Landeszuordnung; Gemeinde aus vorhandener amtlicher Bodenrichtwertauskunft bzw. Projektmetadaten. Keine unscharfe Zuordnung zu ähnlich benannten Gemeinden.
2. Das zentrale Landesverzeichnis wird über seine acht Buchstabenseiten eingelesen. Live-Abnahme: **421 Gemeinde-Einträge**; links für rechtskräftige Pläne, laufende Verfahren und kommunale Portale bleiben getrennt. Dies erweitert die kommunale Erreichbarkeit, nicht die vollautomatische Volltextabdeckung auf alle Gemeinden.
3. Zehn feste amtliche Rechts-/Verfahrensquellen werden mit Abrufzeit, Inhaltshash und Inhaltsplausibilität erfasst. Keine beliebigen Links werden serverseitig verfolgt. Geänderte HTML-Strukturen oder Fehlerseiten erzeugen keine erfolgreiche leere Abdeckung. Der Snapshot wird nach 24 Stunden veraltet; beim Öffnen aktualisiert die Oberfläche fehlende/veraltete Quellen.
4. Die bestehende räumliche Planrecherche liefert Planfassungen, Dokumente und Seitenbelege (Details: [MUNICIPAL_PLANNING.md](MUNICIPAL_PLANNING.md)). Bekannte Abrufgrenzen bleiben bestehen. Es werden insbesondere nicht plötzlich alle kommunalen PDF-Hosts freigegeben.
5. Gespeichertes BIM wird in das vereinfachte Baukörpermodell überführt und mit bestehenden Rechen-/Geometrieprüfungen bewertet. Kein IFC-Neubau, kein Rendern und kein kostenpflichtiger Modellaufruf für die Prüfung.
6. Ein Katalog von 27 Prüfbereichen nennt konkret fehlende Nachweise. Zugeordnete Geodaten und Textbelege sind Hinweise, keine automatisch bestätigten Rechtsfeststellungen.
7. Ein expliziter Prüflauf archiviert den aktuellen Bericht lokal; ein Download liefert denselben aktuellen Berichtstyp als JSON. Fachliche Aussagen können mit Person, Dokument/Aktenzeichen, Fundstelle, Begründung und Gültigkeit dokumentiert werden.

## Prüfumfang

Rechtsstand/Übergangsrecht; Vorhaben/Gebäudeklasse/Sonderbau; §§ 30/34/35 BauGB; Planfassung/Teilgebiet; GRZ; GFZ/Vollgeschosse; Gebäudehöhe/Bezugspunkt; Dach/Gestaltung; Baugrenzen/Bauweise; Abstandsflächen; Baulasten/Rechte; Erschließung/Feuerwehr; Stellplätze; Brandschutz; Statik/Baugrund; Barrierefreiheit; Energie; Schall/Immissionen; Entwässerung; Hochwasser/Wasserrecht; Natur/Arten/Boden; Denkmalschutz; Altlasten; kommunale Satzungen; technische Baubestimmungen; Verfahren/Bauvorlagen; weitere fallbezogene Rechtsbereiche.

Dies ist ein erklärter Screening-Katalog für Wohngebäude, keine Kodifizierung sämtlicher bau- und nebenrechtlicher Vorschriften. Landesrechtliche Naturschutz-/Wasser-/Denkmalschutzvorschriften, Sonderfälle und örtliche Satzungen müssen projektbezogen zusätzlich bestimmt werden.

## Geodaten in der Vorprüfung

Die Bereiche Hochwasser, Naturschutz und Denkmal zeigen die konkreten Treffer der gespeicherten ursprünglichen Grundstücksanalyse sowie Status, Detail und Cachekennzeichnung des jeweiligen Geodatendienstes. Naturmonumente und Biosphärenreservate werden ebenfalls aufgeführt. Die Schutzgebietsermittlung ist ein Punkttest; nachträglich hinzugefügte Flurstücke werden nicht automatisch von dieser ursprünglichen Analyse erfasst. Analysezeit ist nicht der tatsächliche Datenstand, insbesondere bei Cache. Fehlende oder ausgefallene Dienste und fehlende Treffer belegen keine Beschränkungsfreiheit. Der Bericht ergänzt je Prüfbereich `geodata` mit `hits`, `sources` und `scope_notice`; Nicht-Geodatenthemen liefern `null`.

## Nachweis- und Änderungsregeln

- `MISSING`: kein ausreichender aktueller projektbezogener Nachweis dokumentiert.
- `DOCUMENTED`: Aussage der genannten Person dokumentiert; Identität, Berechtigung und sachliche Richtigkeit sind nicht automatisch verifiziert.
- `CONFLICT`: mindestens eine aktive Aussage meldet einen Widerspruch. Unabhängige Aussagen überschreiben einander nicht stillschweigend.
- `supersedes` ersetzt ausdrücklich einen Nachweis desselben Prüfbereichs. Beide bleiben archiviert. Ein ersetzter Nachweis lebt nach Ablauf des Nachfolgers nicht automatisch wieder auf.
- Nachweise sind an Flurstücksauswahl, Planinhalte, Gelände/Paket, geprüfte/eigene Vorgaben, Rechtsquellenstatus/-inhalt und relevante Programmversion gebunden. Gebäudebezogene Aussagen zusätzlich an die komplette gespeicherte Gebäudespezifikation.
- Nur Baulasten/Rechte, Altlasten und Planzuordnung erlauben Grundstücksbezug ohne Modell; alle anderen Bereiche benötigen einen gespeicherten Gebäudestand. Bei noch laufender Planrecherche können planabhängige Aussagen nicht gespeichert werden.
- Geänderte Grundlagen oder überschrittene Gültigkeit machen alte Nachweise sichtbar ungültig. Das ist eine konservative Wiedervorlage, keine automatische fachliche Neubewertung.
- Selbst 27 dokumentierte Aussagen ergeben nur `EXPERT_REVIEW_DOCUMENTED`. `legally_complete`, `permit_issued` und `automatic_legal_approval` bleiben immer `false`.

## GRZ/GFZ bei der Hausplanung (2026-11-04)

OCR-Fundzahlen werden als Fundstellen mit Originalseiten angezeigt; eine direkte Übernahme aus diesen Fundstellen ist nicht verfügbar. Der Mensch prüft das konkrete Baufeld, Planfassung und Normfassung und trägt einen tatsächlich geprüften Wert mit Quellenangabe unter „Vorschriften“ ein. Für das Bad-Nauheimer Beispiel sind mehrere gefundene 0,3/0,35/0,6 Werte Beispiele der Planlegende; 0,20 gehört zu einer Tabelle und ist nicht automatisch dem Flurstück zugeordnet. Ohne solche Zuordnung bleiben Werte offen.

Eingetragene Grenzen fließen in die vereinfachte Regelprüfung ein. Neue Bibliotheks- und generierte Entwürfe sowie automatische Neuplatzierungen werden bei harten Konflikten nicht gespeichert. Sie ersetzen keine vollständige Bauantragsprüfung. Die früher pauschal als hart angenommene Nebenanlagen-Grenze 1,5 × GRZ wird als UNKNOWN mit Orientierungswert angezeigt; Fassung und Ausnahmen müssen geprüft werden. Grundlage: [BVerwG zu BauNVO-Fassungen und Nebenanlagen](https://www.bverwg.de/160925U4CN2.24.0).

## Primärquelle und Grenzen der Rechenprüfung

Die Grundformel und Dachanrechnung in § 6 Abs. 4–5 HBO wurden am 02.11.2026 visuell gegen Seite 16 der amtlichen Broschüre geprüft. SHA-256 der geprüften Datei: `32b2708ac7fb2f1a433a04e1f0c54bd76e28f2790ed74565363be668eea1e437`. Ein abweichender späterer Quellenhash wird angezeigt. Diese Quellenprüfung bestätigt keine korrekte vollständige Anwendung auf ein bestimmtes Gebäude.

Die vorhandene Regelmaschine arbeitet mit Baukörpernäherungen. Insbesondere Vollgeschoss-/GFZ-Sonderregeln, Nebenanlagen, reale Baugrenzen, Dachaufbauten, Bezugshöhen, Bestand und Ausnahmen erfordern weitere fachliche Auswertung. Der aktuelle Straßenmittenansatz ist geschätzt. `PASS` in den Rechenzeilen bedeutet deshalb keine rechtliche Zulässigkeit. Weder fehlender Geodatentreffer noch fehlender B-Plan-Treffer beweisen, dass keine Beschränkung gilt.

Der aktuelle Bundesoriginaltext unter dem historischen URL-Pfad `/geg/` trägt bei der Abnahme die Bezeichnung GModG. Die Quellenprüfung akzeptiert aktuelle und historische Bezeichnungen, verlangt aber weiterhin die konkrete anwendbare Fassung und das Übergangsrecht.

## Bedienung

Projekt → Grundstück → Vorschriften & Quellen → **Baurechtliche Vorprüfung · Hessen**. Gemeindezugänge, Rechenkontrollen, Prüfbereiche und Rechtsquellen einzeln aufklappen. „Hessen-Quellen & Prüfung aktualisieren“ aktualisiert Quellen und archiviert den aktuellen Prüfstand. „Nachweis oder Fachprüfung dokumentieren“ nur mit tatsächlich vorliegender Prüfung nutzen. Keine Testattestate in echte Projekte eintragen.

## API und Ablage

Basis `/siteintel`:

- `GET /legal/sources`: Quellenstatus und Zahl der Gemeinden.
- `POST /legal/sources/refresh`: feste amtliche Quellen und Landesverzeichnis aktualisieren.
- `GET /projects/{pid}/legal-review`: aktuellen Bericht berechnen, ohne Netzabruf und ohne neues Gebäude.
- `POST /projects/{pid}/legal-review/run`: aktuellen Bericht unveränderlich archivieren.
- `GET /projects/{pid}/legal-review/export`: aktueller Bericht als JSON-Anhang.
- `POST /projects/{pid}/legal-review/evidence`: dokumentierte Aussage hinzufügen; optionale explizite Ersetzung.

Lokale, ignorierte Ablage: `.local/hessen-legal-sources.json`, pro Projekt `legal-review/evidence.json` und `legal-review/runs/<uuid>.json`. Keine externe Weitergabe. `evidence.json` ist ein atomar geschriebenes Append-Archiv, kein signiertes Behördenregister. Keine Identitätsprüfung oder manipulationssichere Beweiskette zugesagt. Testdaten werden ausschließlich in isolierten Testverzeichnissen angelegt.

## Was die vollständige Automatisierung noch verhindert

- Landesweite vollständige Plan-/Satzungsvolltexte, wirksame Änderungen und echte Baufenster sind nicht flächendeckend maschinenlesbar angebunden. 421 Portalzuordnungen schließen diese Lücke nicht.
- Baulasten, Grunddienstbarkeiten, aktuelle Altlastenauskünfte und bestehende Genehmigungen sind nicht vollständig offen verfügbar.
- Tragwerks-, Brandschutz-, Energie-, Baugrund- und weitere Fachnachweise werden nicht durch Geodaten oder ein Sprachmodell ersetzt.
- § 34/35, Befreiungen, Ermessensentscheidungen und Sonderfälle benötigen eine projektbezogene qualifizierte Bewertung bzw. Entscheidung der zuständigen Stelle.

## Amtliche Ausgangsquellen

- [Hessisches Gemeinde-/B-Plan-Verzeichnis](https://bauleitplanung.hessen.de/bebauungsplaene-in-hessen-a-z)
- [HBO und Änderungen](https://wirtschaft.hessen.de/wohnen-bauen/baurecht-und-bautechnik/hessische-bauordnung-hbo)
- [Geprüfte HBO-Broschüre](https://wirtschaft.hessen.de/sites/wirtschaft.hessen.de/files/2026-04/hbo_broschuere_stand_oktober_2025-baupaket_i.pdf#page=16)
- [Bauvorlagen/Nachweise](https://wirtschaft.hessen.de/wohnen-bauen/bauvorschriften/dokumente-und-vordrucke)
- [Bauaufsicht/Baunebenrecht](https://wirtschaft.hessen.de/wohnen-bauen/baurecht-und-bautechnik)
- [BauGB](https://www.gesetze-im-internet.de/bbaug/), [BauNVO](https://www.gesetze-im-internet.de/baunvo/), [Energierecht GModG](https://www.gesetze-im-internet.de/geg/)
