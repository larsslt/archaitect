"""Zusatz-Typologien Wohnhäuser. Einfügen in apps/api/archaitect/bim/typologies.py vor der schließenden Klammer von T
(oder: from .typologies_wohnhaus_add import T_WOHN; T.update(T_WOHN) vor KEYS = list(T))."""
T_WOHN: dict[str, dict] = {
    "bauhaus_haus": dict(
        label="Bauhaus-/Neue-Sachlichkeit-Haus (1920er-30er)",
        cues="weiße Kuben, Flachdach, waagerechte Fensterbänder, Eckfenster, Rundbalkon/Dachterrasse, schmales Vordach, Treppenhaus-Glasband",
        typ="9-12 x 8-11 m, 2 Geschosse + Staffelgeschoss, Geschosshöhe 2,9-3,2 m",
        recipe="1-2 versetzte Volumen, roof flat mit Attika; plaster_white; Fensterbänder (repeat, kleiner pitch), Eckfenster; terrace/loggia auf dem Staffelgeschoss; canopy dünn; Treppenhaus als vertikales Fensterband",
        watch="Keine Dachüberstände, keine Gesimse; Rundungen nur als Näherung (limitations)"),
    "moderner_flachdach_architektenhaus": dict(
        label="Modernes Architektenhaus (Flachdach, Glas, Holz)",
        cues="Flachdach mit Überstand, raumhohe Verglasung, Holz- oder Putzflächen, Carport, Terrasse, Staffel- oder Obergeschoss kragt aus",
        typ="10-14 x 9-12 m, 2 Geschosse, Geschosshöhe 2,8-3,0 m",
        recipe="2 Volumen versetzt (EG breiter, OG kragt aus), roof flat; full_glass zur Terrasse; cladding wood_larch + plaster_anthracite; carport; terrace; kein Gesims",
        watch="Auskragung nicht zu groß wählen (max. 2 m ohne Stütze)"),
    "backsteinhaus_nord": dict(
        label="Backsteinhaus (Norddeutschland, Klinker)",
        cues="rote oder braune Klinkerfassade, Satteldach mit roten/anthrazit Pfannen, weiße Sprossenfenster, Klinkerverband, Backsteingiebel",
        typ="9-11 x 10-13 m, 1,5-2 Geschosse, Dach 40-50°, Traufüberstand 0,3 m",
        recipe="1 Volumen roof gable; facade brick_red (oder brick_buff/brick_brown); Fenster mit bars und weißem surround (lintel segment_arch oder flat), Sockel stone_plinth; Haustür mit canopy, steps; chimney; gutter+downpipe",
        watch="Klinkerton immer aus Materialtabelle Gruppe Ziegel wählen"),
    "altbau_backstein_1900": dict(
        label="Älteres Backsteinhaus um 1900 (Gründerzeit-/Kaiserzeit-Wohnhaus)",
        cues="Ziegelfassade mit Gesimsbändern, Segmentbogen-Fenster, Zierverband, hohes Sockelgeschoss, Satteldach mit Zwerchgiebel",
        typ="9-12 x 10-14 m, 2-3 Geschosse, Geschosshöhe 3,0-3,4 m, Dach 40-50°",
        recipe="roof gable; brick_red mit cornice und dentil; Fenster top segment_arch, surround lintel keystone; quoins aus brick_buff oder stone; steps hoch; bay als Erker; chimney",
        watch="Sockel absetzen (stone_plinth), Gesimse zwischen den Geschossen"),
    "reetdach_friesenhaus": dict(
        label="Reetdachhaus / Friesenhaus / Landhaus im Norden",
        cues="Reetdach mit tiefer Traufe und Aufschieblingen, Backsteinwände, weiße Sprossenfenster, Eulenloch im Giebel, oft Krüppelwalm",
        typ="12-20 x 8-11 m, 1 Geschoss + Dach 45-55°, Traufe 1,8-2,2 m hoch",
        recipe="1 Volumen roof gable (steil) oder hip, material thatch_*; brick_red-Wände; Fenster mit bars (weiß), Haustür mittig mit steps; dormer/Gauben; chimney; hedge",
        watch="Krüppelwalm und geschwungene Dachkanten nicht darstellbar (limitations)"),
    "siedlerhaus_50er": dict(
        label="Siedlerhaus / Nachkriegshaus (1950er-60er)",
        cues="einfacher Putzbau, Satteldach 35°, kleine Sprossen- oder Lochfenster, Kniestock, kleiner Eingangsvorbau, Gartenanteil",
        typ="8-10 x 8-9 m, 1,5 Geschosse, Kniestock 0,5-1 m, Dach 35-40°",
        recipe="1 Volumen roof gable; plaster_cream/plaster_grey_light; Fenster einzeln gereiht mit shutters; canopy klein; chimney; fence/hedge; Garage separat",
        watch="Keine Gesimse, schlichte Details"),
    "haus_70er_pultdach": dict(
        label="Haus der 1970er-80er (Pultdach, Winkelbungalow, Klinker-Beton)",
        cues="flach geneigtes Pult- oder Satteldach, Sichtbetonbrüstung, braune Klinker, Dachgauben, Garage im Hang",
        typ="10-14 x 9-12 m, 1-2 Geschosse, Dach 10-25°",
        recipe="roof shed oder flache gable (15-25°); brick_buff/brick_brown plus concrete_exposed; Fenster breit gereiht; carport/garage; terrace",
        watch=""),
    "kniestock_haus_zwerchgiebel": dict(
        label="Haus mit Zwerchgiebel / Kniestock (Neubau-Standard 2000er)",
        cues="Satteldach, Zwerchgiebel an der Straße, Erker, Putz in Weiß/Beige, Doppelgarage seitlich",
        typ="10-13 x 10-12 m, 2 Vollgeschosse, Dach 30-38°",
        recipe="1 Volumen roof gable + ein querstehendes Volumen (Zwerchgiebel) bündig an der Straßenseite; bay am Eingang; canopy; Garage als zweites Volumen door_type sectional; gutter+downpipe",
        watch="Giebelfenster im Zwerchgiebel nicht vergessen"),
    "schwedenhaus_holz": dict(
        label="Schwedenhaus / Holzfertighaus (skandinavisch)",
        cues="Holzverschalung (Falu-Rot, Weiß, Grau), Satteldach mit schlankem Überstand, weiße Fensterrahmen, Veranda",
        typ="9-12 x 7-9 m, 1,5 Geschosse, Dach 30-40°",
        recipe="roof gable; cladding wood_* in Rot/Weiß/Grau (Material aus Gruppe Holz); Fenster mit weißem surround; terrace als Veranda mit Vordach; bargeboard; chimney",
        watch="Farbe aus Material-Tabelle wählen, nicht erfinden"),
    "alpenhaus_chalet": dict(
        label="Alpenhaus / Chalet",
        cues="flach geneigtes weit auskragendes Satteldach (20-25°), Holzbalkone mit Brüstung, Sockel aus Stein/Putz, Holzschalung, Schindeln",
        typ="10-14 x 9-11 m, 2-3 Geschosse, Dachüberstand 1,2-1,8 m, Dach 18-25°",
        recipe="roof gable flach mit großem overhang; Sockel stone_plinth/plaster_white; Obergeschoss wood_*; balcony über loggia/terrace mit Holzbrüstung; bargeboard; shutters; steps",
        watch="Schnitzereien nicht darstellbar"),
    "blockhaus_holz": dict(
        label="Blockhaus / Holzhaus (Rundbohlen)",
        cues="liegende Rundstämme mit überstehenden Eckverbindungen, Satteldach, Veranda",
        typ="8-12 x 7-10 m, 1-1,5 Geschosse, Dach 30°",
        recipe="roof gable; Fassade wood_* (Rundholz-Look); kleine Fenster mit Fensterläden; terrace/Veranda; chimney aus Stein",
        watch="Eckverkämmung nicht darstellbar (limitations)"),
    "toskana_mediterran": dict(
        label="Mediterranes Haus / Toskana-Villa / Landhausvilla",
        cues="ockerfarbener Putz, flach geneigtes Ziegeldach (Mönch-Nonne), Rundbogenfenster, Holzläden, Pergola/Loggia, Zypressen",
        typ="12-16 x 9-12 m, 2 Geschosse, Dach 18-24° hip oder gable, Traufe weit vorstehend",
        recipe="roof hip oder gable flach; plaster_yellow/plaster_terracotta; Fenster top round_arch mit shutters; loggia oder arcade; terrace; steps; chimney",
        watch="Pergola nur als arcade/loggia annähern"),
    "stadthaus_reihe_gruenderzeit": dict(
        label="Schmales Stadthaus / Townhouse (Reihe, Giebelständig)",
        cues="schmale Front (5-6 m), 3-4 Geschosse, Stufengiebel oder Traufständig, Hochparterre, Stufen zur Tür",
        typ="5,5-7 x 10-14 m, Geschosshöhe 3,0-3,3 m",
        recipe="1 Volumen roof gable/mansard; hohes Sockelgeschoss; steps mit Geländer; bay am 1. OG; cornice; Fenster storeys [1,2,3] mit surround",
        watch="Seitenwände sind Brandwände: keine Fenster auf den Stoßseiten"),
    "jugendstilvilla": dict(
        label="Jugendstil-/Gründerzeitvilla",
        cues="Putz mit Stuck, Turm- oder Erkerbetonung, Walm-/Mansarddach, verzierte Eingangstür, Zaun mit Pfosten",
        typ="12-16 x 11-14 m, 2-3 Geschosse, Dach 40-50°",
        recipe="roof hip/mansard; cornice, quoins, pilaster; bay + tower mit onion/cone; Fenster mit surround pediment; steps; fence mit Steinpfeilern",
        watch="Stuckornamente nicht darstellbar (limitations)"),
    "pyramiden_zeltdach_haus": dict(
        label="Haus mit Zeltdach / Pyramidendach (quadratisch)",
        cues="quadratischer Grundriss, allseitig geneigtes Dach zu einer Spitze, oft Bungalow oder Stadtvilla",
        typ="10 x 10 m bis 12 x 12 m, 1-2 Geschosse, Dach 25-35°",
        recipe="1 quadratisches Volumen roof hip (gleiche Neigung); Fenster symmetrisch; canopy; chimney mittig versetzt",
        watch="Nur bei quadratischem Grundriss Spitze, sonst kurzer First"),
    "mansarddach_haus": dict(
        label="Haus mit Mansarddach",
        cues="geknicktes Dach, steile untere Dachflächen mit Gauben, ausgebautes Dachgeschoss",
        typ="9-12 x 10-13 m, 2 Geschosse + Mansarde",
        recipe="roof mansard; Gauben je Achse (dormer); cornice an der Traufe; Fenster storeys; steps",
        watch=""),
    "hanghaus_splitlevel": dict(
        label="Hanghaus / Split-Level",
        cues="versetzte Ebenen, Stützmauer, Terrassen talseitig, Garage im Sockel, Pultdach",
        typ="10-14 x 9-12 m, 2-3 versetzte Ebenen (je 1,4-1,5 m Versatz)",
        recipe="2-3 Volumen auf versetztem base_z; roof shed oder flat; retaining_wall; terrace talseitig; ramp/Garage im Sockel; stair_ext",
        watch="Gelände aus DGM beachten, base_z nicht frei erfinden"),
    "doppelhaus_haelfte": dict(
        label="Doppelhaushälfte / Kettenhaus",
        cues="zwei spiegelbildliche Haushälften, gemeinsamer First, getrennte Eingänge, eine Garage je Seite",
        typ="je Hälfte 6-7 x 9-11 m, 2 Geschosse",
        recipe="zwei Volumen Stoß an Stoß, roof gable durchgehend; Eingänge gespiegelt; Fenster symmetrisch; je eine canopy",
        watch="Grundstücksgrenze mittig: Hälften nicht überlappen"),
    "tiny_house": dict(
        label="Tiny House / Ferienhäuschen / Gartenhaus",
        cues="sehr klein, Satteldach oder Pultdach, Holzverschalung, große Glastür, oft auf Rädern oder Punktfundament",
        typ="3 x 6 bis 3 x 8 m, Höhe 3,5-4 m",
        recipe="1 Volumen roof gable/shed; Fassade wood_*; Tür full_glass; terrace klein; chimney (Ofenrohr)",
        watch="Mindestmaße der Bauordnung beachten (Hinweis in assumptions)"),
    "kolonial_veranda_haus": dict(
        label="Haus mit Veranda / Kolonialstil / Farmhouse",
        cues="umlaufende oder frontale Veranda, Satteldach, Holzverschalung, Säulen, Fensterläden",
        typ="10-14 x 8-10 m, 2 Geschosse, Veranda 2-2,5 m tief",
        recipe="roof gable; Fassade wood_*; terrace + column (order plain) + canopy als Veranda; Fenster mit shutters; steps breit",
        watch="Säulenzahl wie angefragt"),
}
