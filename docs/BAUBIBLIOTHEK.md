# Baubibliothek: Bestand und Ausbauziel

Ziel ist eine breite Abdeckung typischer Wohnbauprojekte. „95 %“ ist ein Abnahmeziel, keine bereits gemessene Abdeckung. Dafür muss eine repräsentative Sammlung von Hausbau-Szenarien definiert und getestet werden.

## Tatsächlich vorhandener Bestand

Typologien sind Erkennungs- und Bauanleitungen für den Generator, nicht automatisch fertige platzierbare Hausmodelle. Bauteilgeneratoren benötigen teilweise einen Gebäudebezug. Materialien sind im Renderer vorhanden, aber noch nicht durchgehend im Editor auswählbar.

### Gebäudetypologien

- `efh_satteldach`: Einfamilienhaus mit Satteldach
- `doppel_reihenhaus`: Doppel-/Reihenhaus
- `stadtvilla_walmdach`: Stadtvilla / Walmdachhaus
- `bungalow_flach`: Bungalow / Flachdachhaus
- `antiker_tempel`: Antiker griechischer Tempel
- `fachwerkhaus`: Fachwerkhaus
- `bauernhaus_scheune`: Bauernhaus / Scheune / Landwirtschaft
- `reetdachhaus`: Reetdach-/Landhaus
- `villa_historisch`: Historische Villa / Gründerzeit / Herrenhaus
- `mehrfamilienhaus`: Mehrfamilienhaus / Wohnblock (Putz)
- `blockrand_gruenderzeit`: Blockrand / Altbau-Stadthaus
- `plattenbau`: Plattenbau / Zeilenbau
- `buero_glas`: Bürogebäude mit Glasfassade / Vorhangfassade
- `buero_beton`: Bürogebäude / Verwaltung mit Putz- oder Betonfassade
- `gewerbehalle`: Halle / Gewerbe / Industrie
- `supermarkt_handel`: Supermarkt / Handelsbau
- `schule_kita`: Schule / Kita / öffentliches Gebäude
- `kirche`: Kirche / Kapelle
- `moderner_kubus`: Moderner Kubus / Architektenhaus
- `hochhaus_turm`: Hochhaus / Turm
- `hotel`: Hotel / Pension
- `krankenhaus`: Krankenhaus / Klinik / Pflegeheim
- `sporthalle`: Sporthalle / Turnhalle / Schwimmhalle
- `museum_kultur`: Museum / Theater / Kulturbau / Rathaus
- `bahnhof_halle`: Bahnhof / Verkehrsbau / Terminal
- `windmuehle`: Windmühle / Wasserturm / Leuchtturm / Silo
- `burg_schloss`: Burg / Schloss / Festung
- `gewaechshaus_pavillon`: Gewächshaus / Wintergarten / Pavillon
- `parkhaus`: Parkhaus / Garage / Tankstelle
- `feuerwache_depot`: Feuerwache / Depot / Remise
- `moschee_pagode`: Moschee / Pagode / Tempel (Orient und Asien)
- `industriehalle_fabrik`: Fabrik / Industriebau / Kraftwerk
- `mehrgenerationen_hofhaus`: Hofhaus / Atriumhaus / Vierseithof
- `bauhaus_haus`: Bauhaus-/Neue-Sachlichkeit-Haus (1920er-30er)
- `moderner_flachdach_architektenhaus`: Modernes Architektenhaus (Flachdach, Glas, Holz)
- `backsteinhaus_nord`: Backsteinhaus (Norddeutschland, Klinker)
- `altbau_backstein_1900`: Älteres Backsteinhaus um 1900 (Gründerzeit-/Kaiserzeit-Wohnhaus)
- `reetdach_friesenhaus`: Reetdachhaus / Friesenhaus / Landhaus im Norden
- `siedlerhaus_50er`: Siedlerhaus / Nachkriegshaus (1950er-60er)
- `haus_70er_pultdach`: Haus der 1970er-80er (Pultdach, Winkelbungalow, Klinker-Beton)
- `kniestock_haus_zwerchgiebel`: Haus mit Zwerchgiebel / Kniestock (Neubau-Standard 2000er)
- `schwedenhaus_holz`: Schwedenhaus / Holzfertighaus (skandinavisch)
- `alpenhaus_chalet`: Alpenhaus / Chalet
- `blockhaus_holz`: Blockhaus / Holzhaus (Rundbohlen)
- `toskana_mediterran`: Mediterranes Haus / Toskana-Villa / Landhausvilla
- `stadthaus_reihe_gruenderzeit`: Schmales Stadthaus / Townhouse (Reihe, Giebelständig)
- `jugendstilvilla`: Jugendstil-/Gründerzeitvilla
- `pyramiden_zeltdach_haus`: Haus mit Zeltdach / Pyramidendach (quadratisch)
- `mansarddach_haus`: Haus mit Mansarddach
- `hanghaus_splitlevel`: Hanghaus / Split-Level
- `doppelhaus_haelfte`: Doppelhaushälfte / Kettenhaus
- `tiny_house`: Tiny House / Ferienhäuschen / Gartenhaus
- `kolonial_veranda_haus`: Haus mit Veranda / Kolonialstil / Farmhouse

### Bauteilgeneratoren

- `cornice`: Gesims / Traufgesims / Gurtband (umlaufend oder je Seite)
- `quoins`: Ecksteine / Eckquaderung (wechselnd lang/kurz)
- `pilaster`: Lisene / Pilaster (Wandvorlage, optional mit Basis und Kapitell)
- `column`: Säule (rund) vor der Fassade, z. B. Portikus
- `entablature`: Gebälk über einer Säulenreihe (Architrav, Fries mit Triglyphen, Geison) mit Decke bis zur Wand
- `bracket`: Konsole / Knagge / Kragstein (Dreieckskonsole)
- `canopy`: Vordach über Eingang (flach, Pult oder Giebel; optional mit Stützen/Streben)
- `steps`: Eingangstreppe / Freitreppe (Blockstufen mit Podest)
- `chimney`: Schornstein (Backstein mit Kopfplatte und Aufsatz)
- `downpipe`: Fallrohr (rund) mit Rohrschellen
- `lamp`: Wandleuchte / Laterne an der Fassade
- `sign`: Aushängeschild an Ausleger (Gasthaus, Laden)
- `fence`: Zaun (Lattenzaun, Staketen, Pfosten-Riegel) entlang achsparalleler Linien im Grundstück
- `tower`: Turm / Rundturm / Erkerturm mit Kegel-, Kuppel-, Zwiebel- oder Flachdach (n Ecken: 6-8 = Polygonturm)
- `bay`: Erker / Auslucht (box = eckig, canted = dreiseitig geknickt), auch auskragend ab z0 > 0
- `arcade`: Arkade / Bogenhalle / Laubengang vor der Fassade (Pfeiler + Bögen)
- `awning`: Markise / Sonnenschutz (gestreift) über Schaufenster oder Eingang
- `rustication`: Bossenwerk / Rustika (horizontale Quaderung, spart Öffnungen aus), meist am Erdgeschoss
- `dentil`: Zahnschnitt (Reihe kleiner Klötzchen unter dem Gesims)
- `gutter`: Dachrinne an den Traufen (Satteldach: nur Traufseiten)
- `bargeboard`: Ortgangbrett an den Giebelkanten eines Satteldachs
- `skylight`: Dachflächenfenster (nur Satteldach)
- `solar`: Photovoltaik: aufgeständert auf Flachdach (mode flat) oder bündig auf Satteldach (mode pitched)
- `technical_box`: Technikaufbau auf dem Flachdach (Lüftung, Aufzugsüberfahrt, Treppenhauskopf)
- `ramp`: Rampe (barrierefrei oder Anlieferung), massiver Keil mit optionalem Geländer
- `terrace`: Terrasse / Austritt vor der Fassade, optional mit Geländer (Stäbe, Glas, Brüstung, Seile)
- `carport`: Carport an der Fassade (Flach- oder Pultdach, Stützen im Abstand von höchstens 3,5 m)
- `retaining_wall`: Stützmauer / Gartenmauer freistehend (achsparallel, mit Abdeckplatte)
- `stair_ext`: Außentreppe / Fluchttreppe aus Stahl entlang der Fassade mit Podest und Handlauf
- `loggia`: Loggia (vorgesetzt, geschosshoch mit Seitenwänden, Decke und Brüstung); Tür dorthin wird automatisch ergänzt
- `buttress`: Strebepfeiler (abgetreppt, in Reihe) für Kirchen und Burgen
- `pylon`: Werbepylon / Einkaufsmarkt-Stele (freistehend, absolute Position)
- `parking`: Stellplatzfläche mit Markierungen (freistehend, absolute Position)
- `tree`: Baum (Laubbaum mit detaillierter Krone im Render, oder Konifere); absolute Position
- `hedge`: Hecke (geschnitten, achsparallel); absolute Koordinaten
- `shrub`: Strauch / Zierbusch, optional im Pflanzkübel
- `flowerbed`: Blumenbeet mit Steineinfassung, Erde und Blumen
- `path`: Gartenweg / Zufahrt aus Platten, Pflaster oder Kies (achsparallele Knicke)
- `pool`: Schwimmbecken (rechteckig, Randplatten) - ein Teich ist KEIN pool, dafür pond
- `pond`: Gartenteich mit natürlicher Uferlinie, ins Gelände eingesenkt, Steine am Rand (kein Becken)
- `lake`: See: füllt die gemessene Geländesenke bis zu einem Wasserspiegel (Umriss kommt aus dem Gelände, nicht aus Maßen), mit Schilf, Seerosen, Findlingen, Sträuchern und Uferbäumen
- `sauna_hut`: Saunahütte aus Holz mit Satteldach, Ofenrohr, Vorbau mit Bank, auf Punktfundamenten (steht auch am Hang oder am See)
- `bench`: Gartenbank mit Lehne
- `garden_set`: Gartenmöbel-Set: Tisch, vier Stühle, optional Sonnenschirm
- `garden_light`: Gartenleuchten (Poller oder Mast), einzeln oder in Reihe

### Materialien

#### Anstrich

- `paint_white`: Lack weiß
- `paint_cream`: Lack cremeweiß
- `paint_grey_light`: Lack hellgrau
- `paint_anthracite`: Lack anthrazit
- `paint_black`: Lack schwarz
- `paint_green_dark`: Lack Tannengrün
- `paint_green_sage`: Lack Salbeigrün
- `paint_blue_dark`: Lack Dunkelblau
- `paint_blue_light`: Lack Taubenblau
- `paint_red_sweden`: Lack Schwedenrot
- `paint_red_bright`: Lack Rot (Tür)
- `paint_brown`: Lack Braun
- `paint_yellow`: Lack Gelb

#### Außen

- `paving_concrete`: Betonplatten
- `gravel`: Kies
- `water`: Wasser
- `boxwood`: Buchs/Hecke
- `cobblestone`: Kopfsteinpflaster
- `terrace_decking`: Terrassendielen Holz
- `paving_granite`: Granitpflaster
- `paving_flagstone`: Natursteinplatten
- `paving_clinker`: Klinkerpflaster
- `asphalt`: Asphalt
- `concrete_light`: Beton hell geschliffen
- `gravel_light`: Kies hell
- `soil_dark`: Erde dunkel (Beet)

#### Dach

- `roof_tile_brown`: Dachziegel braun
- `roof_tile_anthracite`: Dachziegel anthrazit
- `roof_tile_black_glazed`: Dachziegel schwarz glasiert
- `roof_slate`: Naturschiefer
- `roof_slate_scallop`: Schiefer Schuppendeckung
- `roof_wood_shingle`: Holzschindel
- `roof_thatch`: Reet-/Strohdach
- `roof_zinc_standing`: Stehfalz Zink
- `roof_copper`: Kupfer (neu)
- `roof_copper_patina`: Kupfer patiniert (grün)
- `roof_bitumen`: Bitumen/Flachdachbahn
- `roof_gravel_flat`: Kiesschüttung Flachdach
- `solar_panel`: Solarmodul (PV)
- `roof_sedum`: Gründach (Sedum)

#### Dach/Blech

- `zinc`: Zink
- `roof_tile_red`: Dachziegel rot

#### Fassade

- `plaster_white`: Putz weiß
- `plaster_beige`: Putz beige
- `plaster_anthracite`: Putz anthrazit
- `concrete_exposed`: Sichtbeton
- `brick_red`: Klinker rot
- `brick_buff`: Klinker hell
- `wood_larch`: Holz Lärche
- `timber_dark`: Fachwerkholz dunkel
- `stone_plinth`: Natursteinsockel

#### Fassade/Naturstein

- `stone_sandstone_yellow`: Sandstein gelb
- `stone_sandstone_red`: Sandstein rot
- `stone_limestone`: Kalkstein hell
- `stone_granite_grey`: Granit grau
- `stone_basalt_dark`: Basalt/Schiefer dunkel
- `stone_field`: Feldstein/Bruchstein
- `stone_ashlar_light`: Quader hell (Werkstein)
- `stone_marble_white`: Marmor weiß

#### Fassade/Putz

- `plaster_cream`: Putz cremeweiß
- `plaster_yellow`: Putz gelb/ocker
- `plaster_grey_light`: Putz hellgrau
- `plaster_grey_mid`: Putz mittelgrau
- `plaster_terracotta`: Putz terrakotta
- `plaster_salmon`: Putz lachs/rosa
- `plaster_green_pale`: Putz mintgrün
- `plaster_blue_grey`: Putz graublau
- `plaster_rough_white`: Kratz-/Rauputz weiß
- `plaster_lime_old`: Kalkputz gealtert
- `plaster_timber_infill`: Gefach weiß (Fachwerk)
- `fibre_cement_grey`: Faserzementplatte grau
- `fibre_cement_anthracite`: Faserzementplatte anthrazit

#### Fassade/Ziegel

- `brick_brown`: Ziegel braun
- `brick_dark`: Klinker dunkel/blau-braun
- `brick_yellow`: Ziegel gelb (Hamburger)
- `brick_orange`: Ziegel orange
- `brick_white`: Ziegel weiß geschlämmt
- `brick_red_large`: Ziegel rot Großformat

#### Glas

- `glass_clear`: Glas klar
- `glass_tinted_grey`: Glas getönt grau
- `glass_tinted_green`: Glas grünlich
- `glass_frosted`: Glas satiniert
- `glass_curtain_blue`: Glas Vorhangfassade blau
- `glass_curtain_dark`: Glas Vorhangfassade dunkel

#### Holz

- `wood_oak`: Eiche natur
- `wood_pine`: Kiefer/Fichte hell
- `wood_cedar`: Zeder/Lärche rötlich
- `wood_thermo`: Thermoholz dunkelbraun
- `wood_weathered`: Holz vergraut

#### Holz/Fachwerk

- `timber_oak_aged`: Eichenfachwerk gealtert
- `timber_black`: Fachwerk schwarz gestrichen
- `timber_brown_dark`: Fachwerk dunkelbraun gestrichen
- `timber_oxblood`: Fachwerk ochsenblutrot

#### Innen

- `floor_oak`: Eiche
- `walnut`: Nussbaum
- `interior_white`: Innenputz weiß
- `fabric_grey`: Stoff grau
- `fabric_sand`: Stoff sand
- `floor_parquet_light`: Parkett hell (Ahorn/Esche)
- `floor_parquet_dark`: Parkett dunkel (Räuchereiche)
- `floor_tile_grey`: Fliese grau
- `floor_tile_white`: Fliese weiß
- `plaster_interior_cream`: Wand innen creme
- `plaster_interior_grey`: Wand innen grau
- `fabric_blue`: Stoff blau
- `fabric_green`: Stoff grün
- `leather_brown`: Leder braun

#### Metall

- `steel_black`: Stahl schwarz
- `alu_anthracite`: Aluminium anthrazit
- `aluminium`: Aluminium natur
- `chrome`: Chrom
- `red_door`: Rot lackiert
- `copper`: Kupfer blank
- `copper_patina`: Kupfer grün patiniert
- `brass`: Messing
- `cast_iron_black`: Gusseisen schwarz
- `steel_galvanized`: Stahl verzinkt
- `steel_corten`: Cortenstahl
- `alu_white`: Aluminium weiß
- `alu_bronze`: Aluminium bronze
- `lead_grey`: Blei/Blech grau
- `metal_corrugated`: Trapezblech
- `metal_panel_anthracite`: Metallpaneel anthrazit
- `metal_panel_silver`: Metallpaneel silber

#### Sonstige



## Zielstruktur des Seitenfensters

1. Gebäude: Einfamilienhaus, Bungalow, Stadtvilla, Doppelhaus, Reihenhaus, Mehrfamilienhaus, Hofhaus, L-/U-Haus, Hanghaus, Tiny House, Modulhaus, Garage, Carport, Gartenhaus, Werkstatt, Gewächshaus und Saunahaus.
2. Rohbau: Fundamente, Bodenplatten, Geschossdecken, Außen-/Innenwände, Stützen, Unterzüge, Holz-/Stahlträger, Bretter, Planken, Balken und Treppen.
3. Dächer: Flach-, Sattel-, Walm-, Pult-, Zelt- und Mansarddach, Dachflächen, Sparren, Pfetten, Gauben, Attika, Dachfenster, Rinnen und Fallrohre.
4. Öffnungen: Haustüren, Innentüren, Schiebetüren, Garagentore, Fenster, bodentiefe Fenster, Verglasungen, Rahmen und Sonnenschutz.
5. Ausbau: Böden, Beläge, Fassaden, Dämmung als sichtbare Schicht, Geländer, Balkone, Terrassen und Vordächer.
6. Grundstück: Wege, Einfahrten, Parkflächen, Zäune, Tore, Mauern, Stützwände, Stufen, Rampen, Pools und Teiche.
7. Pflanzen und Ausstattung: Bäume, Sträucher, Hecken, Beete, Rasen, Bänke, Sitzgruppen, Leuchten, Spielgeräte, Müll-/Fahrradboxen.
8. Haustechnik außen: PV, Solarthermie, Wärmepumpe, Lüftungsauslässe, Regenwassertank und Ladestation als Planungsobjekte.

## Materialsystem

Jedes Objekt erhält zulässige Materialplätze: Tragwerk, Oberfläche, Rahmen, Verglasung, Dach und Beschläge. Maße, Ausrichtung und Materialwahl bleiben nach Platzierung bearbeitbar. Ausgangsgruppen: Holz (Massivholz, Brettschichtholz, Planken), Stahl, Aluminium, Beton, Ziegel, Naturstein, Putz, Glas, Dachziegel, Schiefer, Metallbedachung, Asphalt, Pflaster, Kies, Wasser und Vegetation. Sichtmaterial ersetzt keine statische oder bauphysikalische Eigenschaft.

## Magnetmodus: verbindliches Verhalten für die Umsetzung

- Sichtbarer Schalter „Magnet“; ausgeschaltet sind Position und Drehung frei. Ein Raster ist separat einstellbar und kein Ersatz für Anschlusserkennung.
- Objekte besitzen lokale Anschlussanker: Eckpunkte, Kanten, Flächen, Mittellinien und Auflager; Anker werden mit der Objekttransformation in Weltkoordinaten überführt.
- Kandidaten werden innerhalb eines Bildschirmabstands gesucht, zusätzlich durch einen maximalen metrischen Abstand begrenzt. Priorität: passender Anschluss, Ecke, Kante, Fläche, Raster.
- Bodenplatte bietet Oberseite und Randkanten; Wandunterkante dockt an Oberseite; Balkenende an Stützenkopf oder Wandauflager; Bretter an Ebene und Nachbarkante. Richtung richtet sich nach Anschlussachsen aus, nicht pauschal nach Weltachsen.
- Vorschau zeigt Zielanker und Kontaktfläche. Hysterese verhindert Flackern zwischen benachbarten Zielen. Ohne passenden Anker bleibt freie Platzierung möglich.
- Server prüft dieselbe Endtransformation wie die Vorschau. Objektbezogene Regeln unterscheiden gewollten Kontakt von unerlaubter Durchdringung.
- Abnahme: gedrehte Bodenplatte, Balken an zwei Auflagern, mehrere Höhen, Hanggrundstück, deaktivierter Magnet, Abbruch mit Escape, Rückgängig/Wiederholen, Speichern/Neuladen ohne Lageänderung.

## Bauteile löschen und reparieren

Stabile IDs für jedes Öffnungs- und Bauteilobjekt; Auswahlmodus „Objekt / Bauteil“. Löschen verändert die Gebäudespezifikation und erzeugt eine Version, statt nur ein Dreieck im Viewer auszublenden. Tür entfernen muss auch den zugehörigen Wanddurchbruch schließen. Abhängigkeiten werden vorab angezeigt. Das letzte Gebäude muss löschbar werden; dafür müssen leerer Entwurf, erneutes Platzieren und Rückgängig durchgängig unterstützt sein.

## Aktueller Implementierungsstand

Neun Garten-/Nebenobjekte platzierbar. Ziehen zeigt eine halbtransparente schematische 3D-Vorschau; sie ist noch kein identisches gerendertes Objekt und keine Kollisionsfreigabe. Vollständiger Katalogzugriff, Hausvorlagen als zusätzliche Gebäude, Materialeditor, freier Rohbau, Anschlussmagnete und Bauteillöschen sind noch umzusetzen. Die oben aufgelisteten Ausbauziele sind nicht sämtlich bereits vorhanden.
