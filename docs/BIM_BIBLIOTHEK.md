# Bauteil- und Materialbibliothek

Automatisch erzeugt mit `python tools/catalog_doc.py`. Quellen: `materials/library.json` (Materialien), `bimrender/catalog.py` (Bauteile).

**124 Materialien, 41 parametrische Komponenten, Öffnungs-Typfamilien, 6 Dachformen, 5 Fachwerkmuster.**

## Materialien

### Anstrich (13)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `paint_white` | Lack weiß | painted | weiße Fenster, weißer Rahmen, RAL 9016 |
| `paint_cream` | Lack cremeweiß | painted | cremefarbene Fenster |
| `paint_grey_light` | Lack hellgrau | painted | RAL 7035 |
| `paint_anthracite` | Lack anthrazit | painted | RAL 7016, anthrazit |
| `paint_black` | Lack schwarz | painted | RAL 9005 |
| `paint_green_dark` | Lack Tannengrün | painted | Fensterladen grün, RAL 6009, dunkelgrün |
| `paint_green_sage` | Lack Salbeigrün | painted | salbei, hellgrün |
| `paint_blue_dark` | Lack Dunkelblau | painted | blaue Tür, RAL 5011 |
| `paint_blue_light` | Lack Taubenblau | painted | hellblau, RAL 5014 |
| `paint_red_sweden` | Lack Schwedenrot | painted | Falunrot, Schwedenrot |
| `paint_red_bright` | Lack Rot (Tür) | painted | rote Fensterläden, RAL 3000 |
| `paint_brown` | Lack Braun | painted | braune Fenster, RAL 8014 |
| `paint_yellow` | Lack Gelb | painted | gelbe Tür |

### Außen (13)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `paving_concrete` | Betonplatten | paving | Terrassenplatten, Platten, Pflaster |
| `gravel` | Kies | gravel | Splitt, Kiesbett |
| `water` | Wasser | water | Pool, Teich |
| `boxwood` | Buchs/Hecke | foliage | Hecke, Buchshecke |
| `cobblestone` | Kopfsteinpflaster | paving | Pflaster, Granitpflaster, Kopfstein |
| `terrace_decking` | Terrassendielen Holz | wood | Terrassenboden, Dielen außen |
| `paving_granite` | Granitpflaster | paving | Kopfsteinpflaster Granit |
| `paving_flagstone` | Natursteinplatten | stone | Sandsteinplatten, Terrasse Naturstein, Gehwegplatten |
| `paving_clinker` | Klinkerpflaster | brick | Ziegelpflaster, Klinkerweg |
| `asphalt` | Asphalt | concrete | Straße, Asphaltdecke |
| `concrete_light` | Beton hell geschliffen | concrete | heller Beton, Sichtbeton hell |
| `gravel_light` | Kies hell | gravel | Kiesbett, Splitt |
| `soil_dark` | Erde dunkel (Beet) | concrete | Mutterboden, Beeterde |

### Dach (14)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `roof_tile_brown` | Dachziegel braun | tile | brauner Ziegel, Dachpfanne braun |
| `roof_tile_anthracite` | Dachziegel anthrazit | tile | anthrazite Dachpfanne, Betondachstein anthrazit |
| `roof_tile_black_glazed` | Dachziegel schwarz glasiert | tile | glasierte Pfanne |
| `roof_slate` | Naturschiefer | slate | Schieferdach, Schiefer, Schieferdeckung |
| `roof_slate_scallop` | Schiefer Schuppendeckung | slate | Schuppenschiefer |
| `roof_wood_shingle` | Holzschindel | slate | Schindeldach, Holzschindeln |
| `roof_thatch` | Reet-/Strohdach | thatch | Reetdach, Strohdach |
| `roof_zinc_standing` | Stehfalz Zink | metal | Zinkdach, Stehfalzdach |
| `roof_copper` | Kupfer (neu) | metal | Kupferdach |
| `roof_copper_patina` | Kupfer patiniert (grün) | painted | Patina, grünes Kupferdach, Kuppel grün |
| `roof_bitumen` | Bitumen/Flachdachbahn | concrete | Dachpappe, Flachdach schwarz |
| `roof_gravel_flat` | Kiesschüttung Flachdach | gravel | Kiesdach |
| `solar_panel` | Solarmodul (PV) | metal | Photovoltaik, PV-Modul, Solarpaneel |
| `roof_sedum` | Gründach (Sedum) | grass_hair | Gründach, extensive Dachbegrünung |

### Dach/Blech (2)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `zinc` | Zink | metal | Titanzink, Zinkblech, Blech |
| `roof_tile_red` | Dachziegel rot | tile | Ziegeldach, Biberschwanz, rote Dachziegel, Dachpfannen |

### Fassade (9)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `plaster_white` | Putz weiß | plaster | weißer Putz, Putz, Kalkputz weiß |
| `plaster_beige` | Putz beige | plaster | beiger Putz, sandfarbener Putz |
| `plaster_anthracite` | Putz anthrazit | plaster | dunkler Putz, anthrazitfarbener Putz |
| `concrete_exposed` | Sichtbeton | concrete | Beton, Betonfassade, Sichtbetonfassade |
| `brick_red` | Klinker rot | brick | Ziegel, Backstein, roter Klinker, Klinker |
| `brick_buff` | Klinker hell | brick | heller Klinker, gelber Klinker, Sandklinker |
| `wood_larch` | Holz Lärche | wood | Holzfassade, Holzverkleidung, Lärche |
| `timber_dark` | Fachwerkholz dunkel | wood | Fachwerk, dunkles Fachwerk, Eichenfachwerk, Balken |
| `stone_plinth` | Natursteinsockel | concrete | Sockel, Bruchstein, Sandstein, Steinsockel |

### Fassade/Naturstein (8)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `stone_sandstone_yellow` | Sandstein gelb | stone | Sandstein |
| `stone_sandstone_red` | Sandstein rot | stone | Buntsandstein, roter Sandstein |
| `stone_limestone` | Kalkstein hell | stone | Kalkstein, Jurakalk |
| `stone_granite_grey` | Granit grau | stone | Granit |
| `stone_basalt_dark` | Basalt/Schiefer dunkel | stone | Basalt, Lavastein |
| `stone_field` | Feldstein/Bruchstein | stone | Bruchstein, Naturstein-Mauerwerk, Feldsteinmauer |
| `stone_ashlar_light` | Quader hell (Werkstein) | stone | Werkstein, Quaderstein, Gewändestein |
| `stone_marble_white` | Marmor weiß | stone | Marmor |

### Fassade/Putz (13)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `plaster_cream` | Putz cremeweiß | plaster | Cremeputz, Elfenbein |
| `plaster_yellow` | Putz gelb/ocker | plaster | gelber Putz, Ockerputz, Schlossgelb |
| `plaster_grey_light` | Putz hellgrau | plaster | grauer Putz |
| `plaster_grey_mid` | Putz mittelgrau | plaster | Betongrau Putz |
| `plaster_terracotta` | Putz terrakotta | plaster | roter Putz, Terrakottaputz |
| `plaster_salmon` | Putz lachs/rosa | plaster | rosa Putz |
| `plaster_green_pale` | Putz mintgrün | plaster | grüner Putz |
| `plaster_blue_grey` | Putz graublau | plaster | blauer Putz |
| `plaster_rough_white` | Kratz-/Rauputz weiß | plaster | Rauputz, Kratzputz, Spritzputz |
| `plaster_lime_old` | Kalkputz gealtert | plaster | Kalkputz, verwitterter Putz |
| `plaster_timber_infill` | Gefach weiß (Fachwerk) | plaster | Gefache, Lehmputz weiß |
| `fibre_cement_grey` | Faserzementplatte grau | concrete | Eternit, Faserzement |
| `fibre_cement_anthracite` | Faserzementplatte anthrazit | concrete | Faserzement dunkel |

### Fassade/Ziegel (6)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `brick_brown` | Ziegel braun | brick | brauner Backstein |
| `brick_dark` | Klinker dunkel/blau-braun | brick | Klinker, dunkler Backstein |
| `brick_yellow` | Ziegel gelb (Hamburger) | brick | gelber Backstein, Handstrichziegel gelb |
| `brick_orange` | Ziegel orange | brick | oranger Backstein |
| `brick_white` | Ziegel weiß geschlämmt | brick | geschlämmter Backstein, weißer Backstein |
| `brick_red_large` | Ziegel rot Großformat | brick | Klosterformat |

### Glas (6)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `glass_clear` | Glas klar | glass | Glas, Verglasung |
| `glass_tinted_grey` | Glas getönt grau | glass | Sonnenschutzglas, graues Glas |
| `glass_tinted_green` | Glas grünlich | glass | grünes Glas, Antikglas |
| `glass_frosted` | Glas satiniert | glass | Milchglas, satiniertes Glas |
| `glass_curtain_blue` | Glas Vorhangfassade blau | glass | Bürohausglas, Curtain Wall |
| `glass_curtain_dark` | Glas Vorhangfassade dunkel | glass | Spiegelglas dunkel, Glasfassade dunkel |

### Holz (5)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `wood_oak` | Eiche natur | wood | Eichenholz |
| `wood_pine` | Kiefer/Fichte hell | wood | Fichte, Kiefer, Nadelholz |
| `wood_cedar` | Zeder/Lärche rötlich | wood | Zeder |
| `wood_thermo` | Thermoholz dunkelbraun | wood | Thermoesche |
| `wood_weathered` | Holz vergraut | wood | vergrautes Holz, Silbergrau |

### Holz/Fachwerk (4)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `timber_oak_aged` | Eichenfachwerk gealtert | wood | Fachwerkbalken, Eichenbalken, Balken |
| `timber_black` | Fachwerk schwarz gestrichen | wood | schwarze Balken |
| `timber_brown_dark` | Fachwerk dunkelbraun gestrichen | wood | braune Balken, Fachwerk braun |
| `timber_oxblood` | Fachwerk ochsenblutrot | wood | rote Balken, Ochsenblut |

### Innen (14)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `floor_oak` | Eiche | wood | Parkett, Eichenboden, Holzboden |
| `walnut` | Nussbaum | wood | Nussbaumtür, Walnuss, dunkles Holz |
| `interior_white` | Innenputz weiß | plaster | Innenwand, weiße Wand innen |
| `fabric_grey` | Stoff grau | fabric | graues Sofa, grauer Stoff |
| `fabric_sand` | Stoff sand | fabric | Teppich sand, sandfarbener Stoff |
| `floor_parquet_light` | Parkett hell (Ahorn/Esche) | wood | Parkett, heller Boden |
| `floor_parquet_dark` | Parkett dunkel (Räuchereiche) | wood | dunkles Parkett, Räuchereiche |
| `floor_tile_grey` | Fliese grau | stone | Feinsteinzeug grau, Fliesen |
| `floor_tile_white` | Fliese weiß | stone | weiße Fliesen, Badfliesen |
| `plaster_interior_cream` | Wand innen creme | plaster | Wandfarbe creme |
| `plaster_interior_grey` | Wand innen grau | plaster | Wandfarbe grau |
| `fabric_blue` | Stoff blau | fabric | blaues Sofa |
| `fabric_green` | Stoff grün | fabric | grünes Polster |
| `leather_brown` | Leder braun | painted | Leder, Ledersofa |

### Metall (17)

| Schlüssel | Bezeichnung | Shader | auch gemeint |
|---|---|---|---|
| `steel_black` | Stahl schwarz | painted | schwarzer Stahl, Stahlprofil, schwarze Rahmen |
| `alu_anthracite` | Aluminium anthrazit | painted | anthrazitfarbene Fenster, Fensterrahmen anthrazit, RAL 7016 |
| `aluminium` | Aluminium natur | metal | Aluminium, Alu |
| `chrome` | Chrom | metal | verchromt, Edelstahl poliert |
| `red_door` | Rot lackiert | painted | rote Tür, rot |
| `copper` | Kupfer blank | metal | Kupfer |
| `copper_patina` | Kupfer grün patiniert | painted | Grünspan |
| `brass` | Messing | metal | Messing, Gold |
| `cast_iron_black` | Gusseisen schwarz | painted | Gusseisen, Schmiedeeisen, Geländer schwarz |
| `steel_galvanized` | Stahl verzinkt | metal | feuerverzinkt, Zinkstahl |
| `steel_corten` | Cortenstahl | painted | Corten, Rost |
| `alu_white` | Aluminium weiß | painted | Alu weiß |
| `alu_bronze` | Aluminium bronze | metal | Alu bronze, Bronze eloxiert |
| `lead_grey` | Blei/Blech grau | metal | Bleiblech, Verwahrung |
| `metal_corrugated` | Trapezblech | metal | Wellblech, Profilblech, Trapezblech grau |
| `metal_panel_anthracite` | Metallpaneel anthrazit | metal | Alu-Verbundplatte, Metallfassade dunkel |
| `metal_panel_silver` | Metallpaneel silber | metal | Aluminiumfassade, Alupaneel |

## Gebäudetypologien und ehrliche Abdeckung

Keine gemessene Prozentzahl: die Tabelle sagt, was gerendert und geprüft wurde und wo der Katalog Lücken hat.

| Typologie | Status | Hinweis |
|---|---|---|
| `efh_satteldach` – Einfamilienhaus mit Satteldach | abgenommen | Spec 2 (Landhaus) und Spec 3 (Solarhaus) |
| `doppel_reihenhaus` – Doppel-/Reihenhaus | Katalog deckt ab | mehrere Volumen Stoß an Stoß, nicht gerendert |
| `stadtvilla_walmdach` – Stadtvilla / Walmdachhaus | abgenommen | Spec 2 (Turmvilla) |
| `bungalow_flach` – Bungalow / Flachdachhaus | Katalog deckt ab | nicht gerendert |
| `fachwerkhaus` – Fachwerkhaus | abgenommen | Referenzfall des Projekts |
| `bauernhaus_scheune` – Bauernhaus / Scheune / Landwirtschaft | abgenommen | Spec 2 (Scheune); Giebelfenster bei gambrel fehlen |
| `reetdachhaus` – Reetdach-/Landhaus | Katalog deckt ab | Material thatch vorhanden, Gaube nur Standardform |
| `villa_historisch` – Historische Villa / Gründerzeit / Herrenhaus | abgenommen | Spec 1 und 2 |
| `mehrfamilienhaus` – Mehrfamilienhaus / Wohnblock (Putz) | abgenommen | Spec 3 (Wohnblock mit Balkonen, Solar, Außentreppe) |
| `blockrand_gruenderzeit` – Blockrand / Altbau-Stadthaus | teilweise | Mansard, Erker, Gesimse ok; Stuckornament fehlt |
| `plattenbau` – Plattenbau / Zeilenbau | teilweise | Loggia nur vorgesetzt (nicht eingerückt); Balkone mit Tür-Logik ok |
| `buero_glas` – Bürogebäude mit Glasfassade / Vorhangfassade | abgenommen | Spec 3 (Bürohaus mit Glasraster) |
| `buero_beton` – Bürogebäude / Verwaltung mit Putz- oder Betonfassade | Katalog deckt ab | wie Bürohaus mit Faserzement/Beton |
| `gewerbehalle` – Halle / Gewerbe / Industrie | abgenommen | Spec 3 (Halle mit Sheddach, Sektionaltoren, Rampe) |
| `supermarkt_handel` – Supermarkt / Handelsbau | abgenommen | Spec 3 (Supermarkt mit Pylon, Stellplätzen, Rampe) |
| `schule_kita` – Schule / Kita / öffentliches Gebäude | abgenommen | Spec 3 (Schulpavillon mit Terrasse, Carport) |
| `kirche` – Kirche / Kapelle | teilweise | Kapelle mit Spitzbogen und Strebepfeilern abgenommen; Turmkirche nur per tower-Bauteil, Gewölbe nicht |
| `moderner_kubus` – Moderner Kubus / Architektenhaus | abgenommen | Villa Kubus |
| `hochhaus_turm` – Hochhaus / Turm | teilweise | Raster per repeat ok; runde Baukörper und Kern nicht |

Bekannte Lücken: eingerückte Loggien (nur vorgesetzt), runde Baukörper (nur Türme), Gewölbe, Stuckornament, Gauben nur als Standardform, Fenster in Gambrel-/Mansardgiebeln, Gelände/Topografie, Vegetation nur einfach.

## Komponenten (`components[]`)

### `cornice` – Gesims / Traufgesims / Gurtband (umlaufend oder je Seite)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W|all | all | Seite oder all (alle vier, an den Ecken überlappend) |
| `z` | 0.0..60.0 |  | Höhe der Unterkante über Volumenbasis; Standard: Oberkante des Volumens (Traufe) |
| `height` | 0.04..1.2 | 0.28 | Bauhöhe des Gesimses |
| `projection` | 0.02..0.8 | 0.22 | Ausladung |
| `profile` | band|simple|stepped|cove | simple | band=glatter Streifen, simple=klassisch, stepped=Konsolreihen/Stufen, cove=Hohlkehle |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `quoins` – Ecksteine / Eckquaderung (wechselnd lang/kurz)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `width` | 0.15..1.2 | 0.5 | lange Läufer; die kurzen Binder sind 60 % |
| `course` | 0.12..0.7 | 0.3 | Schichthöhe |
| `z0` | 0.0..60.0 | 0.0 | Start über Volumenbasis |
| `z1` | 0.0..60.0 |  | Ende; Standard: Traufe |
| `proud` | 0.01..0.12 | 0.03 | Vorsprung vor der Wand |
| `material` | Materialschlüssel | stone_sandstone_yellow | Material |

### `pilaster` – Lisene / Pilaster (Wandvorlage, optional mit Basis und Kapitell)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte von der linken Ecke (von außen gesehen) |
| `count` | 1..12 | 1 | Anzahl |
| `spacing` | 0.5..20.0 | 3.0 | Abstand bei count>1 |
| `width` | 0.1..0.9 | 0.3 | Breite |
| `projection` | 0.02..0.4 | 0.08 | Vorsprung |
| `z0` | 0.0..60.0 | 0.0 | Unterkante |
| `z1` | 0.0..60.0 |  | Oberkante; Standard: Traufe |
| `capital` | bool | True | Kapitell/Kopf |
| `base` | bool | True | Fußplatte |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `column` – Säule (rund) vor der Fassade, z. B. Portikus

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte entlang der Fassade |
| `count` | 1..12 | 1 | Anzahl |
| `spacing` | 0.8..12.0 | 2.5 | Abstand |
| `distance` | 0.05..6.0 | 1.2 | Abstand der Säulenachse von der Wand |
| `radius` | 0.05..0.6 | 0.15 | Radius |
| `z0` | 0.0..30.0 | 0.0 | Unterkante (Basis) |
| `z1` | 0.5..60.0 | 3.0 | Oberkante (unter Gebälk) |
| `capital` | bool | True | Kapitell |
| `base` | bool | True | Basis |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `bracket` – Konsole / Knagge / Kragstein (Dreieckskonsole)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `z` | 0.0..60.0 |  | Oberkante der Konsole; Standard: Traufe |
| `count` | 1..40 | 1 | Anzahl |
| `spacing` | 0.2..10.0 | 0.9 | Abstand |
| `size` | 0.1..1.2 | 0.3 | Höhe der Konsole |
| `projection` | 0.05..1.0 | 0.28 | Ausladung |
| `thickness` | 0.04..0.4 | 0.12 | Breite entlang der Fassade |
| `material` | Materialschlüssel | timber_oak_aged | Material |

### `canopy` – Vordach über Eingang (flach, Pult oder Giebel; optional mit Stützen/Streben)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 0.8..14.0 | 2.2 | Breite |
| `projection` | 0.4..4.0 | 1.3 | Ausladung |
| `z` | 1.8..20.0 | 2.5 | Unterkante an der Wand |
| `kind` | flat|shed|gable | flat | flat=Flachdach, shed=Pultdach, gable=Giebeldach quer zur Wand |
| `support` | none|posts|brackets | brackets | Stützen |
| `thickness` | 0.05..0.5 | 0.14 | Dicke der Platte |
| `material` | Materialschlüssel | steel_black | Tragwerk/Platte |
| `roof_material` | Materialschlüssel |  | Deckung (nur shed/gable); Standard = material |

### `steps` – Eingangstreppe / Freitreppe (Blockstufen mit Podest)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 0.6..8.0 | 1.6 | Breite |
| `count` | 1..12 | 3 | Anzahl Stufen |
| `rise` | 0.12..0.22 | 0.17 | Steigung |
| `tread` | 0.22..0.5 | 0.32 | Auftritt |
| `z0` | 0.0..60.0 |  | Gelände unten (absolut); Standard: Basis des Volumens |
| `material` | Materialschlüssel | stone_granite_grey | Material |

### `chimney` – Schornstein (Backstein mit Kopfplatte und Aufsatz)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -50.0..200.0 |  | Mitte in x, gemessen ab Volumen-Ursprung |
| `y` | -50.0..200.0 |  | Mitte in y, gemessen ab Volumen-Ursprung |
| `width` | 0.3..2.0 | 0.65 | Breite (x) |
| `depth` | 0.3..2.0 | 0.65 | Tiefe (y) |
| `height` | 0.3..4.0 | 1.0 | Höhe über First (Satteldach) bzw. über Attika |
| `material` | Materialschlüssel | brick_red | Material |
| `cap_material` | Materialschlüssel | concrete_light | Kopfplatte |

### `downpipe` – Fallrohr (rund) mit Rohrschellen

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Position |
| `z0` | 0.0..30.0 | 0.1 | unten |
| `z1` | 0.0..60.0 |  | oben; Standard: Traufe |
| `radius` | 0.02..0.12 | 0.045 | Radius |
| `material` | Materialschlüssel | zinc | Material |

### `lamp` – Wandleuchte / Laterne an der Fassade

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Position |
| `z` | 1.0..20.0 | 2.2 | Höhe der Leuchtenmitte |
| `size` | 0.1..0.8 | 0.28 | Höhe der Leuchte |
| `material` | Materialschlüssel | cast_iron_black | Gestell |

### `sign` – Aushängeschild an Ausleger (Gasthaus, Laden)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Position |
| `z` | 1.8..20.0 | 2.8 | Oberkante des Auslegers |
| `width` | 0.2..2.0 | 0.6 | Schildbreite (weg von der Wand) |
| `height` | 0.2..1.5 | 0.5 | Schildhöhe |
| `arm` | 0.3..2.0 | 0.9 | Länge des Auslegers |
| `material` | Materialschlüssel | cast_iron_black | Ausleger |
| `plate_material` | Materialschlüssel | paint_red_sweden | Schild |

### `fence` – Zaun (Lattenzaun, Staketen, Pfosten-Riegel) entlang achsparalleler Linien im Grundstück

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `points` | Punktliste |  | Liste [[x,y],...] in Weltkoordinaten (m), nur achsparallele Segmente |
| `kind` | picket|post_rail|wall_cap | picket | picket=Lattenzaun, post_rail=Pfosten-Riegel, wall_cap=Mauer mit Abdeckplatte |
| `height` | 0.4..2.5 | 1.0 | Höhe |
| `material` | Materialschlüssel | paint_white | Material |

### `tower` – Turm / Rundturm / Erkerturm mit Kegel-, Kuppel-, Zwiebel- oder Flachdach (n Ecken: 6-8 = Polygonturm)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -50.0..200.0 |  | Mitte in x ab Volumen-Ursprung (Pflicht) |
| `y` | -50.0..200.0 |  | Mitte in y ab Volumen-Ursprung (Pflicht) |
| `radius` | 0.5..8.0 | 1.6 | Schaftradius |
| `z0` | 0.0..60.0 | 0.0 | Unterkante über Volumenbasis |
| `z1` | 2.0..80.0 | 9.0 | Traufhöhe über Volumenbasis |
| `sides` | 5..64 | 32 | Eckenzahl (32 = rund, 8 = Oktogon, 6 = Sechseck) |
| `roof` | cone|dome|onion|flat | cone | Helmform |
| `roof_height` | 0.2..15.0 | 3.0 | Helmhöhe |
| `roof_overhang` | 0.0..1.5 | 0.3 | Dachüberstand |
| `material` | Materialschlüssel | plaster_white | Schaft |
| `roof_material` | Materialschlüssel | roof_slate | Helm |
| `band` | bool | False | Gesimsring unter dem Helm |
| `band_material` | Materialschlüssel |  | Material des Rings (Standard = Schaft) |
| `finial` | bool | False | Spitze/Knauf aus Messing |
| `slits` | 0..16 | 0 | Anzahl Schlitzfenster rund um den Schaft |
| `slit_angle` | 0.0..360.0 | 0.0 | Startwinkel der Schlitze in Grad (0 = +x) |
| `slit_z` | 0.0..80.0 |  | Höhe der Schlitzmitte; Standard: Mitte des Schafts |
| `slit_width` | 0.1..1.2 | 0.3 | Schlitzbreite |
| `slit_height` | 0.3..3.0 | 1.0 | Schlitzhöhe |

### `bay` – Erker / Auslucht (box = eckig, canted = dreiseitig geknickt), auch auskragend ab z0 > 0

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 0.8..8.0 | 2.4 | Breite an der Wand |
| `projection` | 0.2..1.5 | 0.7 | Ausladung |
| `z0` | 0.0..60.0 | 0.0 | Unterkante über Volumenbasis |
| `z1` | 1.6..60.0 | 3.0 | Oberkante (Dachplatte liegt darauf) |
| `kind` | box|canted | box | Form |
| `sill` | 0.3..1.2 | 0.9 | Brüstungshöhe |
| `material` | Materialschlüssel |  | Wandmaterial; Standard = Fassade des Volumens |
| `frame` | Materialschlüssel | paint_white | Rahmen |
| `roof_material` | Materialschlüssel | zinc | Dachplatte |
| `support_material` | Materialschlüssel | stone_ashlar_light | Konsole unter schwebenden Erkern |

### `arcade` – Arkade / Bogenhalle / Laubengang vor der Fassade (Pfeiler + Bögen)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | linke Kante der Arkade; Standard: mittig |
| `count` | 1..20 | 3 | Anzahl Bögen |
| `span` | 1.0..6.0 | 2.6 | lichte Bogenweite |
| `pier` | 0.3..1.5 | 0.6 | Pfeilerbreite |
| `z0` | 0.0..30.0 | 0.0 | Unterkante |
| `spring_z` | 1.0..10.0 | 2.6 | Bogenansatz (Kämpfer) über Volumenbasis |
| `z1` | 2.0..20.0 | 4.6 | Oberkante der Arkadenwand |
| `kind` | round_arch|segment_arch|pointed_arch | round_arch | Bogenform |
| `arch_rise` | 0.05..3.0 |  | Pfeilhöhe nur bei segment_arch |
| `distance` | 0.0..6.0 | 0.0 | Abstand zur Wand (0 = vorgesetzt direkt an der Wand) |
| `depth` | 0.2..1.5 | 0.5 | Tiefe der Arkadenwand |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `awning` – Markise / Sonnenschutz (gestreift) über Schaufenster oder Eingang

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 0.6..10.0 | 2.5 | Breite |
| `projection` | 0.4..3.5 | 1.4 | Ausladung |
| `z` | 1.8..20.0 | 2.6 | Befestigungshöhe an der Wand |
| `drop` | 0.2..1.2 | 0.6 | Gefälle bis zur Vorderkante |
| `stripe` | 0.1..1.0 | 0.3 | Streifenbreite |
| `material` | Materialschlüssel | paint_red_bright | Streifenfarbe 1 |
| `material2` | Materialschlüssel | paint_white | Streifenfarbe 2 |

### `rustication` – Bossenwerk / Rustika (horizontale Quaderung, spart Öffnungen aus), meist am Erdgeschoss

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W|all | all | Seite oder all |
| `z0` | 0.0..60.0 | 0.0 | Start |
| `z1` | 0.0..60.0 |  | Ende; Standard: z0 + 3 m |
| `course` | 0.2..1.2 | 0.5 | Schichthöhe |
| `proud` | 0.01..0.1 | 0.02 | Vorsprung |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `dentil` – Zahnschnitt (Reihe kleiner Klötzchen unter dem Gesims)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W|all | all | Seite oder all |
| `z` | 0.0..60.0 |  | Unterkante; Standard: 0.4 m unter der Traufe |
| `width` | 0.04..0.25 | 0.09 | Klotzbreite |
| `height` | 0.04..0.3 | 0.1 | Klotzhöhe |
| `depth` | 0.03..0.3 | 0.08 | Vorsprung |
| `spacing` | 0.1..0.6 | 0.2 | Abstand (Mitte zu Mitte, ungefähr) |
| `material` | Materialschlüssel | stone_ashlar_light | Material |

### `gutter` – Dachrinne an den Traufen (Satteldach: nur Traufseiten)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W|all | all | Seite oder all |
| `material` | Materialschlüssel | zinc | Material |

### `bargeboard` – Ortgangbrett an den Giebelkanten eines Satteldachs

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `height` | 0.08..0.6 | 0.25 | Brettbreite (senkrecht gemessen) |
| `thickness` | 0.02..0.12 | 0.04 | Brettdicke |
| `material` | Materialschlüssel | paint_white | Material |

### `skylight` – Dachflächenfenster (nur Satteldach)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `slope` | S|N|E|W | S | Dachseite (bei ridge x: S/N, bei ridge y: W/E) |
| `u` | 0.0..100.0 | 2.0 | Abstand vom Dachanfang entlang des Firsts (linke Kante) |
| `up` | 0.3..8.0 | 1.0 | waagerechter Abstand der Unterkante von der Außenwand zum First |
| `width` | 0.4..2.0 | 0.78 | Breite |
| `height` | 0.5..2.5 | 1.18 | Länge entlang der Dachschräge |
| `frame` | Materialschlüssel | alu_anthracite | Rahmen |

### `solar` – Photovoltaik: aufgeständert auf Flachdach (mode flat) oder bündig auf Satteldach (mode pitched)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `mode` | flat|pitched | flat | flat=Flachdach aufgeständert, pitched=Satteldachfläche |
| `x` | 0.0..200.0 |  | flat: linke Kante ab Volumen-Ursprung (Standard 0,8) |
| `y` | 0.0..200.0 |  | flat: untere Kante ab Volumen-Ursprung (Standard 0,8) |
| `cols` | 1..30 | 4 | Module nebeneinander |
| `rows` | 1..12 | 2 | Modulreihen |
| `panel_w` | 0.6..1.4 | 1.05 | Modulbreite |
| `panel_l` | 1.0..2.5 | 1.75 | Modullänge |
| `tilt` | 5.0..40.0 | 15.0 | flat: Neigung in Grad (Ausrichtung nach Süden) |
| `slope` | S|N|E|W | S | pitched: Dachseite |
| `u` | 0.3..100.0 | 2.0 | pitched: Abstand ab Dachanfang entlang des Firsts |
| `up` | 0.2..8.0 | 0.6 | pitched: Abstand der Unterkante von der Wand horizontal |
| `material` | Materialschlüssel | solar_panel | Modulfläche |

### `technical_box` – Technikaufbau auf dem Flachdach (Lüftung, Aufzugsüberfahrt, Treppenhauskopf)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | 0.0..200.0 |  | linke Kante ab Volumen-Ursprung (Standard mittig) |
| `y` | 0.0..200.0 |  | untere Kante ab Volumen-Ursprung (Standard mittig) |
| `width` | 0.5..15.0 | 2.2 | Breite (x) |
| `depth` | 0.5..15.0 | 1.6 | Tiefe (y) |
| `height` | 0.5..5.0 | 1.8 | Höhe |
| `material` | Materialschlüssel | metal_panel_silver | Hülle |
| `cap_material` | Materialschlüssel | steel_galvanized | Kappe/Lamellen |

### `ramp` – Rampe (barrierefrei oder Anlieferung), massiver Keil mit optionalem Geländer

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 0.9..8.0 | 1.5 | Breite |
| `length` | 0.5..30.0 | 6.0 | Länge (Neigung max 12 %, barrierefrei 6 %) |
| `height` | 0.05..1.5 | 0.3 | Höhenunterschied |
| `z0` | 0.0..60.0 |  | Gelände unten (absolut); Standard: Basis des Volumens |
| `railing` | none|steel | steel | Handlauf beidseitig |
| `railing_material` | Materialschlüssel | steel_galvanized | Handlauf |
| `material` | Materialschlüssel | concrete_light | Rampe |

### `terrace` – Terrasse / Austritt vor der Fassade, optional mit Geländer (Stäbe, Glas, Brüstung, Seile)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 1.0..16.0 | 4.0 | Breite |
| `depth` | 1.0..8.0 | 3.0 | Tiefe |
| `z` | 0.0..60.0 | 0.0 | Oberkante über Volumenbasis |
| `thickness` | 0.05..0.4 | 0.15 | Plattendicke |
| `material` | Materialschlüssel | terrace_decking | Belag |
| `railing` | none|bars|glass|solid|cable | none | Geländertyp |
| `railing_sides` |  | front,left,right | Seiten mit Geländer (Komma-Liste aus front,left,right) |
| `railing_height` | 0.8..1.3 | 1.0 | Geländerhöhe |
| `railing_material` | Materialschlüssel | steel_black | Geländer |

### `carport` – Carport an der Fassade (Flach- oder Pultdach, Stützen im Abstand von höchstens 3,5 m)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 2.5..12.0 | 3.2 | Breite (je Stellplatz 2,5-3 m) |
| `projection` | 2.5..7.0 | 5.5 | Tiefe |
| `height` | 2.0..3.5 | 2.4 | lichte Höhe an der Außenkante |
| `kind` | flat|shed | flat | Dachform |
| `material` | Materialschlüssel | steel_black | Stützen und Dach |
| `roof_material` | Materialschlüssel |  | Dachdeckung (nur shed); Standard = material |

### `retaining_wall` – Stützmauer / Gartenmauer freistehend (achsparallel, mit Abdeckplatte)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x0` | -200.0..400.0 |  | Start x (absolut) |
| `y0` | -200.0..400.0 |  | Start y (absolut) |
| `x1` | -200.0..400.0 |  | Ende x (absolut); x0==x1 für Mauer in y-Richtung |
| `y1` | -200.0..400.0 |  | Ende y (absolut); y0==y1 für Mauer in x-Richtung |
| `height` | 0.3..4.0 | 1.0 | Höhe über z0 |
| `thickness` | 0.15..0.8 | 0.3 | Dicke |
| `z0` | -2.0..60.0 | 0.0 | Unterkante absolut |
| `material` | Materialschlüssel | concrete_exposed | Mauer |
| `cap_material` | Materialschlüssel | stone_granite_grey | Abdeckplatte |

### `stair_ext` – Außentreppe / Fluchttreppe aus Stahl entlang der Fassade mit Podest und Handlauf

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Anfang des Laufs (unten), von links |
| `width` | 0.8..2.0 | 1.1 | Laufbreite |
| `z0` | 0.0..60.0 | 0.0 | unten, über Volumenbasis |
| `z1` | 0.5..12.0 | 3.0 | oben (Podestoberkante), über Volumenbasis |
| `tread` | 0.22..0.35 | 0.27 | Auftritt |
| `landing` | 0.9..2.5 | 1.2 | Podestlänge am oberen Ende |
| `material` | Materialschlüssel | steel_black | Wangen/Geländer |
| `tread_material` | Materialschlüssel | steel_galvanized | Stufen/Podest |

### `loggia` – Loggia (vorgesetzt, geschosshoch mit Seitenwänden, Decke und Brüstung); Tür dorthin wird automatisch ergänzt

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte |
| `width` | 1.6..8.0 | 3.0 | Breite |
| `depth` | 1.0..3.5 | 1.6 | Tiefe |
| `storey` | 0..40 | 1 | Geschoss (0 = Erdgeschoss) |
| `ceiling` | bool | True | Deckenplatte; false, wenn darüber eine weitere Loggia/ein Balkon die Decke bildet (sonst Z-Fighting) |
| `railing` | none|solid|glass|bars | solid | Brüstungstyp vorn |
| `railing_height` | 0.8..1.3 | 1.0 | Brüstungshöhe |
| `railing_material` | Materialschlüssel | concrete_light | Brüstung |
| `slab_material` | Materialschlüssel | concrete_exposed | Platten |
| `wall_material` | Materialschlüssel |  | Seitenwände; Standard = Fassade des Volumens |

### `buttress` – Strebepfeiler (abgetreppt, in Reihe) für Kirchen und Burgen

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `side` | S|N|E|W | S | Fassadenseite |
| `u` | 0.0..200.0 |  | Mitte des ersten Pfeilers |
| `count` | 1..20 | 4 | Anzahl |
| `pitch` | 1.0..20.0 | 4.0 | Abstand der Pfeiler (Mitte-Mitte) |
| `width` | 0.3..1.5 | 0.7 | Breite |
| `projection` | 0.3..2.0 | 0.9 | Ausladung unten |
| `z0` | 0.0..60.0 | 0.0 | unten, über Volumenbasis |
| `height` | 1.0..40.0 |  | Höhe; Standard bis knapp unter die Traufe |
| `material` | Materialschlüssel | stone_limestone | Material |

### `pylon` – Werbepylon / Einkaufsmarkt-Stele (freistehend, absolute Position)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -200.0..400.0 |  | Position x |
| `y` | -200.0..400.0 |  | Position y |
| `height` | 3.0..30.0 | 7.0 | Gesamthöhe |
| `width` | 0.8..5.0 | 2.2 | Breite der Werbetafel |
| `z0` | -2.0..60.0 | 0.0 | Fußpunkt absolut |
| `material` | Materialschlüssel | metal_panel_anthracite | Stele |
| `sign_material` | Materialschlüssel | paint_red_bright | Werbetafel |

### `parking` – Stellplatzfläche mit Markierungen (freistehend, absolute Position)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -200.0..400.0 |  | linke Kante x |
| `y` | -200.0..400.0 |  | untere Kante y |
| `width` | 2.5..100.0 | 15.0 | Länge der Reihe in x |
| `depth` | 4.0..20.0 | 5.0 | Tiefe eines Stellplatzes in y |
| `spaces` | 1..40 | 6 | Anzahl Stellplätze (mind. 2,2 m je Platz) |
| `z0` | -1.0..60.0 | 0.0 | Höhe absolut |
| `material` | Materialschlüssel | asphalt | Belag |
| `line_material` | Materialschlüssel | paint_white | Markierung |

### `tree` – Baum (Laubbaum mit detaillierter Krone im Render, oder Konifere); absolute Position

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | Position x |
| `y` | -300.0..500.0 |  | Position y |
| `height` | 2.0..35.0 | 9.0 | Gesamthöhe |
| `crown_radius` | 0.8..9.0 | 3.0 | Kronenradius |
| `kind` | deciduous|conifer | deciduous | Laubbaum oder Konifere |

### `hedge` – Hecke (geschnitten, achsparallel); absolute Koordinaten

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x0` | -300.0..500.0 |  | Start x |
| `y0` | -300.0..500.0 |  | Start y |
| `x1` | -300.0..500.0 |  | Ende x |
| `y1` | -300.0..500.0 |  | Ende y |
| `height` | 0.3..4.0 | 1.4 | Höhe |
| `thickness` | 0.3..2.0 | 0.7 | Dicke |

### `shrub` – Strauch / Zierbusch, optional im Pflanzkübel

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | Position x |
| `y` | -300.0..500.0 |  | Position y |
| `radius` | 0.2..2.0 | 0.7 | Radius |
| `height` | 0.2..3.0 | 1.0 | Höhe |
| `pot` | bool | False | im Kübel (0,4 m erhöht) |

### `flowerbed` – Blumenbeet mit Steineinfassung, Erde und Blumen

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | linke Kante x |
| `y` | -300.0..500.0 |  | untere Kante y |
| `width` | 0.6..20.0 | 3.0 | Breite (x) |
| `depth` | 0.6..10.0 | 1.2 | Tiefe (y) |
| `density` | 1.0..12.0 | 5.0 | Blumen je m² |
| `flowers` |  | paint_red_bright,paint_yellow,paint_white | Blütenfarben als Materialschlüssel, Komma-getrennt |
| `border_material` | Materialschlüssel | stone_granite_grey | Einfassung |

### `path` – Gartenweg / Zufahrt aus Platten, Pflaster oder Kies (achsparallele Knicke)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `points` | Punktliste |  | Punkte [[x,y],...]; Richtung muss bei jedem Punkt wechseln |
| `width` | 0.5..6.0 | 1.2 | Breite |
| `material` | Materialschlüssel | paving_flagstone | Belag (paving_*, cobblestone, gravel_light) |

### `pool` – Schwimmbecken oder Teich mit Rand (rechteckig)

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | linke Kante x |
| `y` | -300.0..500.0 |  | untere Kante y |
| `width` | 2.0..30.0 | 8.0 | Breite |
| `depth` | 1.5..15.0 | 4.0 | Tiefe |
| `deep` | 0.4..3.0 | 1.4 | Beckentiefe |
| `coping` | 0.15..1.0 | 0.35 | Randbreite |
| `coping_material` | Materialschlüssel | stone_limestone | Randmaterial |

### `bench` – Gartenbank mit Lehne

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | linke untere Ecke x |
| `y` | -300.0..500.0 |  | linke untere Ecke y |
| `length` | 0.9..3.0 | 1.6 | Länge |
| `orientation` | x|y | x | Länge in x- oder y-Richtung |
| `flip` | bool | False | Lehne auf der anderen Seite |
| `material` | Materialschlüssel | wood_oak | Sitz/Lehne |
| `frame_material` | Materialschlüssel | steel_black | Gestell |

### `garden_set` – Gartenmöbel-Set: Tisch, vier Stühle, optional Sonnenschirm

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | Tischmitte x |
| `y` | -300.0..500.0 |  | Tischmitte y |
| `parasol` | bool | True | Sonnenschirm |
| `parasol_material` | Materialschlüssel | plaster_cream | Schirmbespannung |
| `material` | Materialschlüssel | wood_oak | Tisch/Stühle |
| `frame_material` | Materialschlüssel | steel_black | Gestell |

### `garden_light` – Gartenleuchten (Poller oder Mast), einzeln oder in Reihe

| Parameter | Typ/Bereich | Standard | Bedeutung |
|---|---|---|---|
| `x` | -300.0..500.0 |  | erste Leuchte x |
| `y` | -300.0..500.0 |  | erste Leuchte y |
| `count` | 1..30 | 1 | Anzahl in Reihe |
| `pitch` | 1.0..20.0 | 3.0 | Abstand |
| `axis` | x|y | x | Reihenrichtung |
| `kind` | bollard|post | bollard | Poller 0,8 m oder Mast |
| `height` | 1.5..6.0 | 3.0 | Masthöhe (nur post) |
| `material` | Materialschlüssel | steel_black | Gestell |

## Öffnungen, Dächer, Fachwerk

```
(openings[])
- window_type: casement (Standard, Flügel/Setzhölzer) | fixed (Festverglasung) | oculus (rundes Ochsenauge, Öffnung quadratisch)
- top: flat | round_arch (Rundbogen, Bogenhöhe=Breite/2 ist Teil von height) | segment_arch (Segmentbogen, arch_rise m) | pointed_arch (Spitzbogen)
- sashes: 1-6 Flügel; bars: {cols, rows, width} Sprossen; transom: 0-1 Kämpferhöhe (Anteil der Höhe)
- door_type: panel (Füllungstür) | double (zweiflügelig) | glazed (Glasfüllung) | plank (Brettertür) | sectional (Garagen-/Sektionaltor, bis 5 m breit) | full_glass (Ladentür/Schaufenstertür) | french (zweiflügelige Terrassen-/Balkontür, fast ganz verglast); top/transom wie bei Fenstern; handle: Materialschlüssel
- surround: {material, width 0.1-0.4, depth, lintel: flat|keystone|pediment|segment_pediment|hood, keystone: bool, sill: bool} – Gewände/Einfassung aus Stein
- shutters: {material, state: open|closed, style: louvre|panel|plank} – Fensterläden
- balconies[].railing.type: rails (Standard, Rohr) | bars (Stäbe) | glass (Glasbrüstung) | solid (Vollbrüstung) | cable (Seile); material Materialschlüssel; height, sides
- flower_box: true | {material} – Blumenkasten unter dem Fenster
- sill_material: Materialschlüssel oder none (Fensterbank)

# Dachtypen (volumes[].roof.type): flat | gable | hip (Walmdach) | shed (Pultdach, fall_to: S|N|E|W) | sawtooth (Sheddach-Reihe für Hallen: teeth 2-16, pitch_deg 8-25, Verglasung zur Nordseite) | mansard (Mansarddach: pitch_deg oben, lower_pitch_deg 30-85, lower_height m) | gambrel (Bohlendach/Scheune: ridge, pitch_deg oben, lower_pitch_deg, lower_run Anteil 0.15-0.7)
# Fachwerk-Muster (facade_detail.timber_frame.pattern): st_andrew (Andreaskreuz) | k_brace (Streben je Gefach schräg, Standard) | man (Mann-Figur) | foot_head (Fuß-/Kopfbänder) | diamond (Raute) | none
```

## Ausbaustufen (Pareto)

| Stufe | Inhalt | Status |
|---|---|---|
| 1 | Putzfarben, Ziegel/Klinker, Naturstein, Dachdeckungen, Hölzer, Lacke, Metalle, Glas, Beläge; Fenster-/Türtypen, Bögen, Sprossen, Gewände, Läden, Gesimse, Ecksteine, Lisenen, Säulen, Konsolen, Vordach, Treppe, Schornstein, Fallrohr, Leuchte, Schild, Zaun; Walm-/Pultdach; fünf Fachwerkmuster | fertig |
| 2 | Mansard- und Bohlendach, Türme/Kuppeln/Zwiebelhelme (auch Polygonturm), Erker (eckig/geknickt), Arkade, Markise, Bossenwerk, Zahnschnitt, Dachrinne, Ortgangbrett, Dachfenster, Garagen- und Ladentür | fertig |
| 2b | Gaubenformen (Schleppgaube, Giebelgaube, Fledermaus), Loggia/Balkontypen mit Geländerarten, Rollladenkasten, Sprossenteilung nach Stilepochen, Fenster in Gambrel-/Mansard-Giebeln, Dachaufbauten auf Mansard | geplant |
| 3 | Moderne Bauweisen: Solar (Flachdach/Satteldach), Technikaufbau, Rampe, Terrasse, Carport, Stützmauer, Außentreppe, Sheddach, Geländertypen (Stäbe/Glas/Vollbrüstung/Seile), französische Tür, Glas je Öffnung, Fassadenplatten und Vorhangfassadenglas; Kompaktnotation `storeys`/`repeat` | fertig |
| 3b | Logikschicht (`logic.py`): Balkon/Terrasse/Loggia/Außentreppe/Eingangstreppe/Rampe erhalten automatisch passende Tür, Vordach über Tür, Überlappungs- und Carport-Prüfung; Loggia (vorgesetzt), Strebepfeiler, Pylon, Stellplätze | fertig |
| 3c | Konfliktlöser (`logic.resolve`): Fenster werden an Türen/Erkern/Balkonplatten/Gesims beschnitten oder entfernt, Fallrohr/Lampe/Schild/Pilaster/Säule rücken auf freie Stelle, Vordach wird neben Fenstern gekürzt; alles als Warnung „Automatisch ergänzt“ | fertig |
| 5 | Gartenobjekte: Baum, Hecke, Strauch, Beet, Weg, Pool, Bank, Gartenset, Gartenleuchte (Gras wächst nicht durch Weg/Pool/Beet) | fertig |
| 4 | Ornament: Zahnschnitt, Konsolfries, Pilasterkapitelle (ionisch, korinthisch), Giebelfelder mit Relief, Schnitzwerk an Fachwerkbalken, Balkonkonsolen, Türmchen/Dachreiter, Zwiebel- und Kegelhelm, Fialen, Maßwerkfenster, Rosette; Natursteinmauern mit unregelmäßigem Verband; Pflanzen (Rankgerüst, Spalierobst) | geplant |
| 5 | Innenausbau-Katalog (Küchen, Bäder, Treppentypen, Türzargen, Fußleisten), Möbelfamilien nach Stil | geplant |

