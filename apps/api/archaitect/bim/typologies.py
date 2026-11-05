"""Building typologies: what the interpreter should recognise and which catalog recipe fits.

Each entry: label, cues (what to look for in a photo/text), typ (typical dimensions/geometry),
recipe (volumes/roof/facade/components/materials to use), watch (typical mistakes / limits).
`prompt_table()` renders this for the LLM; `KEYS` feeds the schema enum of `building_type`.
"""
from __future__ import annotations

T: dict[str, dict] = {
    "efh_satteldach": dict(
        label="Einfamilienhaus mit Satteldach",
        cues="1-2 Geschosse + Dach, Giebel zur Straße oder Traufseite, Putzfassade, Ziegel-/Betondachsteine, Fenster einzeln gereiht",
        typ="Grundriss 8-12 x 9-13 m, Geschosshöhe 2,6-2,8 m, Dach 30-45°, Traufe 0,4-0,6 m Überstand",
        recipe="1 Volumen, roof gable; Fenster mit repeat/storeys; Haustür mit canopy oder steps; gutter+downpipe; optional chimney, dormer, bay",
        watch="Garage als zweites Volumen (door_type sectional) statt Fenster; Dachfläche nicht mit Fenstern belegen, sondern skylight/dormer"),
    "doppel_reihenhaus": dict(
        label="Doppel-/Reihenhaus",
        cues="mehrere gleiche schmale Einheiten nebeneinander, Brandwand, gespiegelte Eingänge",
        typ="je Einheit 5-6 m breit, 9-10 m tief, 2-3 Geschosse; Gesamtbreite = Einheiten x Breite",
        recipe="je Einheit ein Volumen mit Stoß an Stoß (gleiche Höhe), Satteldach/Pultdach durchgehend; repeat für Fenster- und Türachsen",
        watch="Einheiten nicht überlappen lassen; Versatz in Tiefe oder Farbe über unterschiedliche Fassadenmaterialien zeigen"),
    "stadtvilla_walmdach": dict(
        label="Stadtvilla / Walmdachhaus",
        cues="quadratischer Grundriss, Walmdach, 2 Vollgeschosse, symmetrische Fassade, oft Erker oder Eingangsvorbau",
        typ="10-12 x 10-12 m, Dach 25-35°",
        recipe="roof hip; bay oder canopy am Eingang; quoins/cornice optional; Fenster storeys [0,1] mit surround",
        watch=""),
    "bungalow_flach": dict(
        label="Bungalow / Flachdachhaus",
        cues="eingeschossig, flaches oder flach geneigtes Dach, lange Fassade, große Fenster",
        typ="12-20 x 8-12 m, Höhe 3-3,5 m; Dach flat oder shed 3-8°",
        recipe="roof flat (mit Attika) oder shed; full_glass-Türen, ribbon windows (repeat mit kleinem pitch), canopy, terrace",
        watch=""),
    "antiker_tempel": dict(
        label="Antiker griechischer Tempel",
        cues="Säulenreihe (dorisch) vor der Giebelseite, Gebälk mit Triglyphenfries, flacher Giebel (Pediment), Stufenunterbau (Stylobat), weißer Marmor, Cella ohne Fenster",
        typ="Cella 9-12 x 16-24 m, Säulenhöhe 5-6 m (Radius 0,45-0,55, Achsabstand 2,2-3,0 m), Giebelneigung 14-18°, 3 Stufen (rise 0,2, tread 0,4) über die ganze Front",
        recipe="1 Volumen storeys 1, storey_height 6, roof gable ridge zur Säulenseite hin (Giebel an der Front), material stone_marble_white, facade stone_marble_white; "
               "column mit order doric, count = geforderte Anzahl (genau!), spacing 2,5-3, distance 2,0 (frei vor der Wand), z0 0, z1 = Höhe bis Unterkante Gebälk, u = Fassadenmitte; "
               "entablature gleiche side/u, span = (count-1)*spacing + 1,6, z = z1 der Säulen, distance wie die Säulen; steps width = Säulenbreite; eine hohe Tür in der Cella; "
               "KEINE Fenster, KEINE Laternen, KEIN Vordach, KEINE Dachrinne",
        watch="Die Säulenanzahl nicht verändern (bei ungerader Anzahl steht eine Säule vor der Tür - das ist gewollt, die Tür liegt dahinter); Säulen stehen frei vor der Wand, nicht in der Wand"),
    "fachwerkhaus": dict(
        label="Fachwerkhaus",
        cues="Holzständer sichtbar, helle Gefache, Geschoss-Überstand, steiles Satteldach, Schiefer oder Tonziegel",
        typ="8-10 x 9-12 m, 2-3 Geschosse, Dach 45-55°",
        recipe="facade_detail.timber_frame mit pattern (k_brace, st_andrew, man ...); Gefache plaster_white; Fenster casement mit shutters; bargeboard; chimney",
        watch="Holzfarbe über Materialschlüssel aus Gruppe Holz/Fachwerk wählen"),
    "bauernhaus_scheune": dict(
        label="Bauernhaus / Scheune / Landwirtschaft",
        cues="große Dachfläche, Tore, Holzverschalung, Gambrel- oder tiefes Satteldach, Nebengebäude",
        typ="Scheune 10-15 x 15-30 m, Traufe 4-6 m; gambrel oder gable",
        recipe="roof gambrel oder gable; plank-Türen (door_type plank, Breite 3-4 m); Holz-Verschalung (Material wood_*); fence",
        watch="Giebelfenster fehlen bei gambrel/mansard (bekannte Grenze)"),
    "reetdachhaus": dict(
        label="Reetdach-/Landhaus",
        cues="dicke geschwungene Dachhaut aus Reet, Ziegelwand, Sprossenfenster, Gauben",
        typ="12-18 x 8-10 m, Dach 45-55°, Traufe tief",
        recipe="roof gable/hip mit Material thatch_*; brick_*-Fassade; Fenster mit bars; chimney",
        watch="Eingedeckte Gauben nur als Standard-Gaube"),
    "villa_historisch": dict(
        label="Historische Villa / Gründerzeit / Herrenhaus",
        cues="Sockel, Gesimse, Eckquader, Fensterverdachungen, Mittelrisalit, Turm oder Erker, Mansard-/Walmdach",
        typ="12-25 m breit, 2-4 Geschosse, Geschosshöhe 3-4 m",
        recipe="rustication im Sockel, quoins, cornice, dentil, pilaster; Fenster surround+shutters; tower, bay, canopy/column am Portal; roof hip/mansard",
        watch="Ornamente über Katalog annähern und in limitations nennen"),
    "mehrfamilienhaus": dict(
        label="Mehrfamilienhaus / Wohnblock (Putz)",
        cues="4-6 Geschosse, regelmäßige Fensterraster, Balkone, Treppenhaus, Flachdach oder flaches Satteldach",
        typ="Breite 15-40 m, Tiefe 12-14 m, Geschosshöhe 2,8-3 m",
        recipe="Fenster mit storeys + repeat; balconies mit Brüstungstyp; Treppenhaus-Fenster als eigene Achse; Flachdach mit solar/technical_box; entrance canopy",
        watch="Balkone nicht über Öffnungen anderer Achsen legen"),
    "blockrand_gruenderzeit": dict(
        label="Blockrand / Altbau-Stadthaus",
        cues="geschlossene Straßenfront, 4-6 Geschosse, Stuck, Erker, Mansarddach, Tordurchfahrt",
        typ="Fassadenbreite 15-30 m, Tiefe 12-15 m, Geschosshöhe 3,2-3,6 m",
        recipe="Sockel rustication, cornice je Geschoss, bay über mehrere Geschosse, mansard; Fenster mit surround lintel",
        watch=""),
    "plattenbau": dict(
        label="Plattenbau / Zeilenbau",
        cues="lange Scheibe, 5-11 Geschosse, Betonfertigteile, Fugenraster, Loggien",
        typ="Länge 60-80 m, Tiefe 11-12 m, Geschosshöhe 2,8 m",
        recipe="concrete/plaster-Fassade; Fenster storeys + repeat pitch 3,0-3,6; loggia/balcony; flat roof",
        watch="Bei Länge > 40 m repeat nutzen"),
    "buero_glas": dict(
        label="Bürogebäude mit Glasfassade / Vorhangfassade",
        cues="durchgehende Glasflächen, Bandfenster, Stützenraster, Flachdach mit Technik",
        typ="Raster 1,35 m, Geschosshöhe 3,6-4,0 m, 4-12 Geschosse",
        recipe="Fenster full-height (sill 0, fixed) mit repeat pitch 1,35-2,7 und storeys; metal_panel-Brüstungen; roof flat + technical_box; entrance canopy",
        watch="Glas als Kind glass-Materialien mit Tint"),
    "buero_beton": dict(
        label="Bürogebäude / Verwaltung mit Putz- oder Betonfassade",
        cues="Lochfassade, Betonbrüstungen, Lamellen, Flachdach",
        typ="Geschosshöhe 3,3-3,6 m",
        recipe="Fenster fixed + repeat; Fassadenbänder; cornice als Auskragung; canopy",
        watch=""),
    "gewerbehalle": dict(
        label="Halle / Gewerbe / Industrie",
        cues="große Kubatur, Trapezblech, Sektionaltore, Oberlichtband, Flachdach oder Sheddach",
        typ="30-100 x 20-60 m, Traufe 6-10 m, Dach 3-8° oder sawtooth",
        recipe="roof shed/flat/sawtooth; Fassade metal_corrugated; door_type sectional repeat; skylight-Band; ramp, canopy",
        watch=""),
    "supermarkt_handel": dict(
        label="Supermarkt / Handelsbau",
        cues="flacher Kasten, Schaufensterfront, Eingangsvordach, Parkplatz",
        typ="40-80 x 30-50 m, Höhe 5-7 m",
        recipe="Flachdach, full_glass door + fixed Fenster, canopy, sign, lamp, Pylon über sign",
        watch="Parkplatz: paving-Fläche als Volumen mit sehr geringer Höhe"),
    "schule_kita": dict(
        label="Schule / Kita / öffentliches Gebäude",
        cues="2-3 Geschosse, Fensterbänder, Pausenhof, Eingangshalle",
        typ="Flügel 12-14 m tief, bis 80 m lang, Geschosshöhe 3,5-3,8 m",
        recipe="mehrere Volumen (Flügel) L/U; Fensterbänder repeat; canopy/arcade; steps+ramp",
        watch="Barrierefreiheit: ramp neben steps"),
    "kirche": dict(
        label="Kirche / Kapelle",
        cues="Langhaus, Turm mit Spitze, Spitz-/Rundbogenfenster, steiles Dach",
        typ="Langhaus 10-14 x 25-40 m, Traufe 8-12 m, Turm 25-60 m",
        recipe="Langhaus gable, tower cone/onion, pointed_arch-Fenster, steps, oculus im Giebel, buttress via pilaster",
        watch="Gewölbe/Innen nicht abgebildet"),
    "moderner_kubus": dict(
        label="Moderner Kubus / Architektenhaus",
        cues="reduzierte Form, Flachdach, große Glasflächen, Holz- oder Putzflächen, Auskragungen",
        typ="Kuben 8-12 m, Geschosshöhe 3 m; Versatz von Volumen",
        recipe="mehrere Volumen versetzt; roof flat; full_glass; canopy auskragend; cladding Holz/metal_panel; terrace",
        watch="Villa Kubus als Referenzspec"),
    "hochhaus_turm": dict(
        label="Hochhaus / Turm",
        cues="über 12 Geschosse, schlanker Körper, Kern, Glas",
        typ="Grundfläche 25-40 m, Höhe 40-200 m",
        recipe="Volumen mit repeat storeys; drum möglich; Fenster als Band",
        watch="Sehr hohe Geschosszahlen: storeys-Liste statt Einzelöffnungen"),
    "hotel": dict(
        label="Hotel / Pension",
        cues="4-8 Geschosse, regelmäßige Zimmerfenster mit Balkonen, Haupteingang mit Vordach/Portal, Schild, oft Sockelgeschoss",
        typ="Riegel 14-18 x 30-70 m, Geschosshöhe 3,0-3,2 m, Flachdach oder flaches Walmdach",
        recipe="1-2 Volumen (Riegel + Flügel), roof flat mit Attika; Fensterreihen storeys/repeat; canopy groß am Eingang, sign; loggia oder terrace als Balkone; steps+ramp; parking",
        watch="Zimmerfenster nie einzeln auflisten; Sockelzone (Erdgeschoss) mit Glas absetzen"),
    "krankenhaus": dict(
        label="Krankenhaus / Klinik / Pflegeheim",
        cues="langgestreckte Flügel, 3-6 Geschosse, Fensterbänder, überdachte Vorfahrt, Hubschrauberlandeplatz optional, viele Parkplätze",
        typ="Flügel 15-18 m tief, 40-120 m lang, Geschosshöhe 3,6-4 m, Flachdach",
        recipe="mehrere Volumen (T/H/U), roof flat; Fensterbänder repeat; canopy sehr tief an der Vorfahrt; ramp; parking; technical_box auf dem Dach",
        watch="Innen nicht abgebildet; Barrierefreiheit durch ramp zeigen"),
    "sporthalle": dict(
        label="Sporthalle / Turnhalle / Schwimmhalle",
        cues="große ungegliederte Halle, hohe Oberlichtbänder, Flachdach oder flach geneigtes Bogen-/Pultdach, Nebenbau mit Eingang",
        typ="Halle 27-30 x 45-60 m, Höhe 7-9 m; Nebenbau 8-10 m tief, 1-2 Geschosse",
        recipe="Volumen Halle roof shed oder flat; hohes Fensterband oben (repeat); skylight; Anbau mit canopy und Tür; fence; parking",
        watch="Wenige Fenster im unteren Bereich, Hallenwand bleibt geschlossen"),
    "museum_kultur": dict(
        label="Museum / Theater / Kulturbau / Rathaus",
        cues="repräsentativer Bau, Freitreppe, Portikus mit Säulen oder Glasfoyer, Sockel, Symmetrie, oft Kuppel oder Turm",
        typ="Grundriss 20-40 x 30-60 m, 2-3 Geschosse hoch (Geschosshöhe 4-5 m)",
        recipe="Hauptvolumen roof hip/flat; steps breit; column order plain davor + entablature; cornice, quoins, pilaster; tower dome optional; Fenster mit surround pediment",
        watch="Säulenanzahl und Lage genau übernehmen; Skulpturen/Reliefs nicht darstellbar (limitations)"),
    "bahnhof_halle": dict(
        label="Bahnhof / Verkehrsbau / Terminal",
        cues="lange Halle mit Bogen-/Tonnendach oder flachem Glasdach, großes Portal, Uhrenturm optional, Bahnsteigdächer",
        typ="Halle 25-40 x 60-150 m, Höhe 12-20 m; Empfangsgebäude 12-15 m tief, Uhrturm 25-40 m",
        recipe="Empfangsgebäude hip/flat mit Rundbogenfenstern (top round_arch); Halle als Volumen roof gable flach (15-20°) mit Glas; tower flat/cone als Uhrturm; arcade; canopy als Bahnsteigdach",
        watch="Tonnengewölbe nicht abbildbar: flaches Satteldach mit Oberlicht als Näherung in limitations nennen"),
    "windmuehle": dict(
        label="Windmühle / Wasserturm / Leuchtturm / Silo",
        cues="runder oder polygonaler schlanker Körper, konischer Helm, oft Flügel/Galerie, kaum Fenster",
        typ="Radius unten 3-6 m, Höhe 12-35 m, Verjüngung nach oben; Helm 3-6 m",
        recipe="tower mit sides 32 (rund) oder 8, radius, z1 = Höhe, roof cone/dome, band true, slits oder wenige kleine Fenster, finial; kleine Tür am Fuß; Sockel aus stone_*",
        watch="Windmühlenflügel, Laterne und Galerie sind nicht darstellbar (limitations)"),
    "burg_schloss": dict(
        label="Burg / Schloss / Festung",
        cues="massive Mauern, Zinnen, runde oder eckige Türme mit Kegeldach, hoher Torbau, Hof, Steinfassade",
        typ="Mauern 8-12 m hoch, 1,5-2,5 m dick; Türme Radius 3-5 m, Höhe 18-30 m; Gebäudeflügel 12-14 m tief",
        recipe="U- oder Rechteck-Volumen roof hip/gable steil (50°); tower an jeder Ecke (cone, band true); buttress/pilaster; Rundbogen-/Spitzbogenfenster klein; rustication; steps; Material stone_* oder plaster_*",
        watch="Zinnen und Wehrgang fehlen; Hof als Aussparung der Volumen (U-Form) abbilden"),
    "gewaechshaus_pavillon": dict(
        label="Gewächshaus / Wintergarten / Pavillon",
        cues="Glas auf allen Seiten, dünne Rahmen, Satteldach aus Glas, Sockel niedrig",
        typ="4-6 x 8-20 m, Traufe 2-3 m, First 4-5 m; Dach 25-30°",
        recipe="Volumen roof gable, Fassade glass (Material glass_*), Fensterreihen über die ganze Wand mit kleinem pitch, Rahmen alu_*/steel_*; Tür full_glass; Sockel 0,5 m",
        watch="Sprossenraster über viele schmale Fenster (repeat) nachbilden"),
    "parkhaus": dict(
        label="Parkhaus / Garage / Tankstelle",
        cues="offene Geschosse, Betonbrüstungen, Rampenturm, wenige geschlossene Flächen",
        typ="Grundriss 20-30 x 40-80 m, Geschosshöhe 2,8-3,0 m, 3-8 Ebenen, Flachdach",
        recipe="Volumen roof flat, Fassade concrete_exposed mit Fensterbändern repeat (offen) ; ramp außen; stair_ext; pylon für Zufahrtsschild; parking auf Erdgeschoss",
        watch="Offene Geschossseiten als lange Fensterbänder darstellen"),
    "feuerwache_depot": dict(
        label="Feuerwache / Depot / Remise",
        cues="große Tore (3-5 m breit) in Reihe, 1-2 Geschosse, Turm für Schlauchtrocknung, Ziegel oder Putz",
        typ="Halle 14-18 x 25-40 m, Tore 4 x 4,5 m, Turm 4 x 4 m, Höhe 12-18 m",
        recipe="Volumen roof gable/hip; Tore als Öffnungen door_type sectional mit repeat; Anbau; tower oder Kamin-/Turmvolumen; Fenster klein darüber; parking davor",
        watch=""),
    "moschee_pagode": dict(
        label="Moschee / Pagode / Tempel (Orient und Asien)",
        cues="Kuppel(n), Minarette, Rundbogenfenster, Portal; oder gestufte geschwungene Dächer mit weiter Auskragung",
        typ="Moschee: Hauptraum 25 x 25 m mit Kuppel Radius 8-12 m, Minarette Radius 1,5, Höhe 30-50 m. Pagode: 3-7 Stufen, je 3 m, Grundriss verjüngt",
        recipe="Moschee: Volumen flat, tower dome groß (sides 32) auf der Mitte, 2-4 Minarette (tower radius 1,5, roof cone, finial), arcade, Rundbogenfenster, Material plaster_white/stone_*. Pagode: gestapelte Volumen mit abnehmender Fläche, je roof hip flach (15-20°) mit großem Überstand, Material wood_*/roof_tile_*",
        watch="Kalligraphie, Ornamente und geschwungene Traufen nicht darstellbar (limitations)"),
    "industriehalle_fabrik": dict(
        label="Fabrik / Industriebau / Kraftwerk",
        cues="Sheddach (Sägezahn), Schornstein, Silos, Rohrbrücken, Trapezblech- oder Ziegelwand",
        typ="Hallen 30-60 x 60-150 m, Traufe 8-12 m, Schornstein Radius 1,5-3 m, Höhe 40-100 m",
        recipe="Volumen roof sawtooth oder flat; metal_corrugated oder brick; tower flat als Schornstein (z1 hoch, roof flat), Silo als tower; technical_box; ramp/Tore sectional; fence",
        watch="Rohrleitungen und Kräne nicht darstellbar"),
    "mehrgenerationen_hofhaus": dict(
        label="Hofhaus / Atriumhaus / Vierseithof",
        cues="Gebäude um einen Innenhof, oft Torbogen, ein- bis zweigeschossig",
        typ="Flügel 8-10 m tief, Hof 10-20 m, Außenmaß 25-40 m",
        recipe="U- oder O-förmig aus 3-4 Volumen (Stoß an Stoß), roof gable/hip einheitlich; Torbogen als Öffnung top round_arch breit; Fenster nach innen und außen; fence/hedge",
        watch="Keine Überlappung der Flügel; Innenhof frei lassen"),
}
from .typologies_wohnhaus import T_WOHN  # noqa: E402
T.update({k: v for k, v in T_WOHN.items() if k not in T})
KEYS = list(T)


def prompt_table(compact: bool = False) -> str:
    out = ["# Gebäudetypologien (building_type wählen; Rezept als Ausgangspunkt, dann Foto/Text anpassen)"]
    if compact:  # one line per type for small-context models
        for k, d in T.items():
            out.append(f"- {k}: {d['label']}; {d['cues'][:80]}; {d['typ'][:70]}")
        out.append("\nVorgehen: Typologie als building_type setzen, Maße aus Bild/Text, Fensterachsen mit storeys/repeat, Katalogbauteile nutzen, Unmögliches in limitations.")
        return "\n".join(out)
    for k, d in T.items():
        out.append(f"- {k}: {d['label']}\n  Merkmale: {d['cues']}\n  Typisch: {d['typ']}\n  Rezept: {d['recipe']}"
                   + (f"\n  Achtung: {d['watch']}" if d["watch"] else ""))
    out.append(
        "\n# Vorgehen (Checkliste)\n"
        "1. Typologie bestimmen und als building_type setzen; mehrere Volumen nur bei echter Gliederung.\n"
        "2. Maße aus Bild/Text; fehlen sie, Typwerte oben nehmen und in assumptions nennen.\n"
        "3. Regelmäßige Fensterachsen immer mit storeys/repeat statt Einzeleinträgen.\n"
        "4. Katalogbauteile bevorzugen (Gesims, Vordach, Fallrohr, Erker ...) statt Dinge wegzulassen.\n"
        "5. Logik prüft das System selbst: Balkon, Terrasse, Außentreppe, Eingangstreppe und Rampe bekommen automatisch eine passende Tür (Fenster wird zur Tür umgewandelt oder Tür ergänzt), Vordächer werden über die Tür gehoben; trotzdem Türen selbst setzen, wenn Lage und Typ bekannt sind.\n"
        "6. Was nicht darstellbar ist, kommt in limitations; nichts erfinden.\n"
        "# Kompaktnotation: Öffnung mit \"storeys\":[0,1,2] (statt storey) und/oder \"repeat\":{\"count\":n,\"pitch\":m} (Versatz entlang der Fassade)\n")
    return "\n".join(out)
