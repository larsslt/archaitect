# Öffentliche BIM-Bibliotheken – Lizenzprüfung (2026-11-02)

Regel: nur importieren, was CC0/CC-BY/MIT o.ä. ist. Unklar = nicht importieren.

| Quelle | Inhalt | Lizenz (geprüft) | Status |
|---|---|---|---|
| Poly Haven (polyhaven.com/license) | HDRIs, Texturen, 3D-Modelle | CC0, kommerziell frei, keine Namensnennung; Scraping der Website nur mit Erlaubnis, API eigene Bedingungen | geeignet für Materialien (library.json), einzeln/manuell oder per API laden |
| Innerscene Library (innerscene.com/tools/library) | ca. 5.000 Teile (Möbel, Hardware) + 1.600 Zeichnungen, u.a. IFC | CC0 | geeignet; Gebäudeteile (Tür/Fenster) nicht benannt, vor Import einzeln sichten |
| Innerscene "Small house with gable roof" | 1 Haus, 28 KB IFC | CC0 | Testfall für IFC-Import, geringer Qualitätsgewinn |
| buildingSMART Sample-Test-Files / IFC4.x-specification-models | Lehr-/Zertifizierungsmodelle | Copyright buildingSMART; Spezifikationsmodelle CC BY-ND 4.0 (noch nicht final) | nicht übernehmen (ND = keine Bearbeitung) |
| ABCon-Tech/Sample-Test-Files | Fork der Zertifizierungsdaten | README: CC BY 4.0, LICENSE-Text nicht verifiziert, Herkunft je Ordner offen | erst nach Prüfung der Ordner-READMEs |
| viktor-platform/ifc-sample-models | 5 Demo-IFCs | keine Lizenz angegeben | nicht übernehmen |
| Formeo/residential-ifc4 (Hugging Face) | synthetische Mehrfamilienhäuser | CC BY-NC 4.0, Zugang auf Anfrage | nicht übernehmen (NC, kein Einfamilienhaus) |
| BIMobject, Polantis, BIMstore, National BIM Library, Hilti u.a. | Herstellerobjekte | keine freie Lizenz, meist Registrierung | nicht übernehmen |
| FreeCAD BIM Library (wiki.freecad.org) | Bauteile | Seite per Bot-Schutz nicht abrufbar, Lizenz unbestätigt | manuell prüfen |

Fazit: Es gibt kaum frei lizenzierte, qualitativ hochwertige Gebäudekomponenten/Häuser als IFC.
Der größte Hebel ist Poly Haven (CC0) für Materialien. Unsere Specs sind parametrisch (JSON),
fremde IFCs wären Mesh/Brep und bräuchten einen eigenen Importpfad.
