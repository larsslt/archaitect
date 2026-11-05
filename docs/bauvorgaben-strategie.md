# Bauvorgaben im Entwurf: Strategie (Stand 04.11.2026)

Ziel: Das Haus wird innerhalb des baurechtlichen Rahmens entworfen, ohne fehlende Rechtswerte zu erfinden.

## Stufen der Werte (Herkunft entscheidet über die Wirkung)
1. **Verbindlich eingetragen** (Vorschriften-Formular, geprüfte Bebauungsplan-Fundstelle): GRZ, GFZ, Vollgeschosse, Höhe, Dachform/-neigung, Baufenster. Wirken hart: Generierungsbrief, Vorabprüfung expliziter Nutzerzahlen (z. B. „7 Etagen“ bei Grenze 5), Regelprüfung, Editor-Grenzen.
2. **HBO § 6 (Abstandsflächen)**: Grundformel (0,4 H, mindestens 3 m) wird als Platzbedarf im Entwurf reserviert und geprüft. Projektbezogene Ausnahmen bleiben offen, daraus wird keine Baugrenze abgeleitet.
3. **Richtwert-Rahmen aus der Umgebung (§ 34 BauGB)** (`siteintel/reference.py`, `ctx.reference`, nie verbindlich): maximale Geschosse und geschätzte Höhe der Nachbargebäude im Umkreis von 60 m (ALKIS), Geschosszahl (und GFZ/GRZ, falls angegeben) der Bodenrichtwertzone (BORIS, Gutachterausschuss), üblicher Grenzabstand (unteres Quartil der nächsten Nachbargebäude). Wirkung: Generierungsbrief (`design_frame`), automatische Reduktion von Geschossen/Höhe auf den Rahmen (nur wenn der Nutzer keine Geschosszahl nennt), Prüfzeilen mit Status PASS/WARN („über dem Richtwert: vermutlich Genehmigung bzw. Befreiung nötig“). Eingetragene Werte (Stufe 1) ersetzen den Richtwert je Feld.
4. **Unbekannt**: bleibt UNKNOWN. Nicht „unbegrenzt“, nicht „genehmigt“. Ungeprüfte Planfundstellen werden nicht automatisch verbindlich.

## Ablauf bei der Generierung
1. Brief aus Stufe 1–3 + freie Polygonfläche (Bestand und Aussparungen abgezogen).
2. Vorabprüfung expliziter numerischer Nutzerangaben gegen Stufe 1 vor dem Modellaufruf.
3. Modell → Referenz-/Geometrieprüfung vor IFC → ein gezielter Reparaturversuch → Platzierung gegen echtes Polygon (feste Bauteile; Gartenelemente blockieren nicht) → Regelprüfung.
4. Passt es nicht: ein Korrekturversuch, danach konkrete Rückfrage (auch zum Abriss, nur auf ausdrücklichen Wunsch wird abgerissen).

## Anpassung des Entwurfs
- `autofit.shrink_to_fit`: passt der Entwurf nicht auf die freie Fläche, wird der Grundriss in 5-%-Schritten verkleinert (Höhen bleiben, Öffnungen und Anbauten folgen), bis Platzierung und harte Prüfungen bestehen (Untergrenze: Hauptbaukörper kurze Seite ~3,5 m, mindestens 50 %). Nicht bei ausdrücklichen Nutzermaßen.
- `autofit.reduce_to_frame`: entfernt oberste Geschosse samt Öffnungen, bis Geschosszahl/Höhe im Rahmen liegen; verwirft die Reduktion, wenn die Spezifikation danach ungültig wäre.

## Datenquellen (geprüft 04.11.2026)
- Bebauungspläne: Abfrage der kommunalen Dienste im Geoportal Hessen ist angebunden (`planning.py`); für Flurstück 8/106 ohne Treffer, einzelne Dienste nicht erreichbar.
- BORIS Hessen (WFS): Zonenattribute Geschosszahl, Tiefe; GFZ/GRZ/Bauweise nur, wenn der Gutachterausschuss sie angibt. Werden jetzt übernommen (neue Projekte; bestehende Projekte nach Neuabruf).
- LoD2-Gebäudemodelle (HVBG): enthalten relative Gebäudehöhe und Dachform, aber nur über das Downloadcenter (gds.hessen.de), kein bekannter ATOM-/WFS-Zugang. Möglicher späterer Ausbau für echte Nachbarhöhen.

## Offen
- Automatische Übernahme von Bebauungsplan-Festsetzungen hängt an der Quelle (kommunale Dienste im Geoportal, teils nicht erreichbar oder ohne Treffer). Ohne Treffer: manuelle Eingabe.
- Nachbarhöhen sind Schätzungen aus Geschosszahlen (2,9 m je Geschoss + 1,5 m); fehlen die Geschosszahlen (wie in Flurstück 8/106), fehlt auch der Höhenrahmen.
