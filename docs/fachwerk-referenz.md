# Fachwerk-Referenz (Altstadt-Gasthaus)

Analyse des Referenzbildes als Eingabe für Generator, Bibliothek und Prompt. Nur beobachtet, nichts ergänzt.

## Gebälk
- **Jedes Gefach ist anders**: einfache Diagonalstreben, Fuß- und Kopfbänder (kurze 45°-Streben an Schwelle und Rähm), Andreaskreuze, „Mann“-Figuren (zwei Streben treffen sich in Feldmitte), und **geschwungene Schweifstreben** (kleine Bögen an den Ständern).
- **Raster**: senkrechte Ständer im gleichmäßigen Abstand, zusätzliche Ständer neben jedem Fenster; Fenster sitzen in Riegelrahmen (Sturz- und Brüstungsriegel).
- **Brüstungsfelder** unter den Fenstern haben meist ein Andreaskreuz oder einen Zierriegel.
- **Stockwerke**: waagerechte Schwellbalken, kräftig profiliert; Obergeschoss kragt leicht vor, Knaggen/Bügen stützen es.
- **Giebel**: Ständer, Spannriegel, Fußbänder; Gauben mit eigenem Gebälk.
- **Farbe**: dunkles Braun (Eiche, gealtert) gegen weißen/hellen Putz.

## Sockel und Tür
- Erdgeschoss steht auf einem **Bruchsteinsockel** aus unregelmäßigen Lagen (Steinformat ca. 0,3–0,8 m lang, 0,15–0,3 m hoch, verschiedene Töne von Sand bis Grau, Fugen sichtbar).
- Die **Haustür bricht den Sockel auf**: kein Stein in der Öffnung, Tür aus Holz mit geschnitzter Füllung, Rahmen aus kräftigem Holz mit Sturz (im Foto leicht gerundet), davor eine Steinstufe.

## Zierde
- Aushängeschild an Ausleger, Schild mit Jahreszahl über der Tür, Gasthausschild am Sockel.
- Straßenlaternen, Wandlaterne an der Fassade, Fahrrad, Pflanzkübel, Blumenkästen unter jedem Fenster, Spaliere/Rosen am Haus.
- Eisengeländer am kleinen Balkon, Fensterläden, Sprossenfenster, Vorhänge hinter den Scheiben.
- Pflaster (Kopfstein) vor dem Haus, Rinne/Fallrohre in Zink.

## Umsetzung im Code
| Beobachtung | Umsetzung |
|---|---|
| vielseitiges Gebälk | `fachwerk.plan_wall(..., pattern="mixed")`, deterministisch gewürfelt je Gefach (Strebe, Fußband, Mann, Andreaskreuz, `_curve`) |
| geschwungene Streben | `fachwerk._curve` (Bogen aus sieben Balkenstücken) |
| Natursteinsockel | `ifcgen._plinth`: einzelne Steine in Lagen, 7 Steintöne, wechselnde Tiefe |
| Tür bricht Sockel auf | Sockelspannen minus Türintervalle; `Türrahmen` aus Eiche mit Sturz |
| Laterne beidseits | `logic._door_lamps` |
| Prompt | `interpreter/SYSTEM_PROMPT.md`, Abschnitt Fachwerk |

## Noch nicht umgesetzt
Auskragende Stockwerke mit Knaggen, Rundbogen-Türsturz, Blumenkästen/Läden als Standard an historischen Häusern (Katalog kennt `shutters`, `flower_box`; der Prompt setzt sie noch nicht automatisch), Kopfsteinpflaster-Material.
