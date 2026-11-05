"""Erweitert materials/library.json um die Pareto-Kern-Materialien (idempotent: bestehende Schluessel bleiben).
Aufruf: python tools/gen_materials.py"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "materials" / "library.json"


def lin(rgb, p=2.2, k=1.0):
    return [round(min(1.0, (c ** p) * k), 3) for c in rgb]


def dark(rgb, f):
    return [round(c * f, 3) for c in rgb]


NEW = {}


def add(key, label, group, aliases, rgb, kind, **shader):
    NEW[key] = {"label": label, "group": group, "aliases": aliases, "rgb": [round(c, 3) for c in rgb], "shader": {"kind": kind, **shader}}


def plaster(key, label, aliases, rgb, **kw):
    add(key, label, "Fassade/Putz", aliases, rgb, "plaster", col=lin(rgb, 1.8), **kw)


plaster("plaster_cream", "Putz cremeweiß", ["Cremeputz", "Elfenbein"], (0.93, 0.89, 0.76))
plaster("plaster_yellow", "Putz gelb/ocker", ["gelber Putz", "Ockerputz", "Schlossgelb"], (0.90, 0.76, 0.40))
plaster("plaster_grey_light", "Putz hellgrau", ["grauer Putz"], (0.76, 0.76, 0.74))
plaster("plaster_grey_mid", "Putz mittelgrau", ["Betongrau Putz"], (0.52, 0.52, 0.51))
plaster("plaster_terracotta", "Putz terrakotta", ["roter Putz", "Terrakottaputz"], (0.74, 0.40, 0.28))
plaster("plaster_salmon", "Putz lachs/rosa", ["rosa Putz"], (0.88, 0.63, 0.55))
plaster("plaster_green_pale", "Putz mintgrün", ["grüner Putz"], (0.73, 0.80, 0.68))
plaster("plaster_blue_grey", "Putz graublau", ["blauer Putz"], (0.62, 0.69, 0.74))
plaster("plaster_rough_white", "Kratz-/Rauputz weiß", ["Rauputz", "Kratzputz", "Spritzputz"], (0.92, 0.91, 0.87), grain_scale=60.0, grain=0.45, rough=0.97)
plaster("plaster_lime_old", "Kalkputz gealtert", ["Kalkputz", "verwitterter Putz"], (0.82, 0.78, 0.68), blot=1.2, grain=0.2)
plaster("plaster_timber_infill", "Gefach weiß (Fachwerk)", ["Gefache", "Lehmputz weiß"], (0.90, 0.88, 0.80), grain_scale=90.0, grain=0.3, blot=0.9)


def brk(key, label, aliases, rgb1, rgb2, mortar=(0.55, 0.53, 0.48), **kw):
    add(key, label, "Fassade/Ziegel", aliases, rgb1, "brick", col1=lin(rgb1, 2.4, 0.9), col2=lin(rgb2, 2.4, 0.9), mortar=list(mortar), **kw)


brk("brick_brown", "Ziegel braun", ["brauner Backstein"], (0.45, 0.28, 0.20), (0.36, 0.22, 0.16))
brk("brick_dark", "Klinker dunkel/blau-braun", ["Klinker", "dunkler Backstein"], (0.30, 0.21, 0.19), (0.22, 0.16, 0.15), mortar=(0.38, 0.37, 0.35))
brk("brick_yellow", "Ziegel gelb (Hamburger)", ["gelber Backstein", "Handstrichziegel gelb"], (0.80, 0.66, 0.40), (0.70, 0.57, 0.34))
brk("brick_orange", "Ziegel orange", ["oranger Backstein"], (0.72, 0.38, 0.22), (0.60, 0.30, 0.18))
brk("brick_white", "Ziegel weiß geschlämmt", ["geschlämmter Backstein", "weißer Backstein"], (0.88, 0.86, 0.82), (0.80, 0.77, 0.72), mortar=(0.8, 0.78, 0.74))
brk("brick_red_large", "Ziegel rot Großformat", ["Klosterformat"], (0.55, 0.22, 0.16), (0.42, 0.17, 0.12), brick_w=0.30, row_h=0.085)


def stn(key, label, aliases, rgb1, rgb2, mortar, **kw):
    add(key, label, "Fassade/Naturstein", aliases, rgb1, "stone", col1=lin(rgb1, 2.3, 0.95), col2=lin(rgb2, 2.3, 0.95), mortar=list(mortar), **kw)


stn("stone_sandstone_yellow", "Sandstein gelb", ["Sandstein"], (0.80, 0.68, 0.46), (0.70, 0.58, 0.40), (0.55, 0.50, 0.42))
stn("stone_sandstone_red", "Sandstein rot", ["Buntsandstein", "roter Sandstein"], (0.66, 0.38, 0.30), (0.56, 0.31, 0.25), (0.50, 0.40, 0.36))
stn("stone_limestone", "Kalkstein hell", ["Kalkstein", "Jurakalk"], (0.84, 0.80, 0.70), (0.76, 0.72, 0.62), (0.6, 0.58, 0.52))
stn("stone_granite_grey", "Granit grau", ["Granit"], (0.55, 0.55, 0.56), (0.45, 0.45, 0.47), (0.35, 0.35, 0.35))
stn("stone_basalt_dark", "Basalt/Schiefer dunkel", ["Basalt", "Lavastein"], (0.28, 0.28, 0.30), (0.20, 0.20, 0.22), (0.15, 0.15, 0.15))
stn("stone_field", "Feldstein/Bruchstein", ["Bruchstein", "Naturstein-Mauerwerk", "Feldsteinmauer"], (0.60, 0.56, 0.50), (0.46, 0.42, 0.38), (0.42, 0.40, 0.36), brick_w=0.38, row_h=0.22, mortar_size=0.04)
stn("stone_ashlar_light", "Quader hell (Werkstein)", ["Werkstein", "Quaderstein", "Gewändestein"], (0.82, 0.79, 0.72), (0.76, 0.73, 0.66), (0.62, 0.60, 0.55), brick_w=0.60, row_h=0.30, mortar_size=0.012)
stn("stone_marble_white", "Marmor weiß", ["Marmor"], (0.92, 0.91, 0.89), (0.88, 0.87, 0.85), (0.7, 0.7, 0.7), brick_w=0.8, row_h=0.4, mortar_size=0.004)


def roof(key, label, aliases, rgb1, rgb2, kind="tile", mortar=None, **kw):
    add(key, label, "Dach", aliases, rgb1, kind, col1=lin(rgb1, 2.3, 0.9), col2=lin(rgb2, 2.3, 0.9), mortar=mortar or dark(lin(rgb2, 2.3, 0.9), 0.4), **kw)


roof("roof_tile_brown", "Dachziegel braun", ["brauner Ziegel", "Dachpfanne braun"], (0.40, 0.22, 0.15), (0.32, 0.17, 0.12))
roof("roof_tile_anthracite", "Dachziegel anthrazit", ["anthrazite Dachpfanne", "Betondachstein anthrazit"], (0.20, 0.20, 0.22), (0.14, 0.14, 0.16))
roof("roof_tile_black_glazed", "Dachziegel schwarz glasiert", ["glasierte Pfanne"], (0.09, 0.09, 0.10), (0.05, 0.05, 0.06), rough=0.35)
roof("roof_slate", "Naturschiefer", ["Schieferdach", "Schiefer", "Schieferdeckung"], (0.24, 0.26, 0.29), (0.17, 0.19, 0.22), kind="slate")
roof("roof_slate_scallop", "Schiefer Schuppendeckung", ["Schuppenschiefer"], (0.22, 0.24, 0.27), (0.16, 0.17, 0.20), kind="slate", brick_w=0.22, row_h=0.22)
roof("roof_wood_shingle", "Holzschindel", ["Schindeldach", "Holzschindeln"], (0.42, 0.34, 0.26), (0.30, 0.25, 0.20), kind="slate", brick_w=0.12, row_h=0.18)
add("roof_thatch", "Reet-/Strohdach", "Dach", ["Reetdach", "Strohdach"], (0.50, 0.42, 0.28), "thatch", c0=[0.12, 0.08, 0.03], c1=[0.42, 0.32, 0.16])
add("roof_zinc_standing", "Stehfalz Zink", "Dach", ["Zinkdach", "Stehfalzdach"], (0.55, 0.57, 0.58), "metal", col=[0.40, 0.42, 0.44], rough=0.45)
add("roof_copper", "Kupfer (neu)", "Dach", ["Kupferdach"], (0.72, 0.42, 0.28), "metal", col=[0.70, 0.30, 0.17], rough=0.3)
add("roof_copper_patina", "Kupfer patiniert (grün)", "Dach", ["Patina", "grünes Kupferdach", "Kuppel grün"], (0.40, 0.62, 0.55), "painted", col=[0.10, 0.30, 0.24], rough=0.6)
add("roof_bitumen", "Bitumen/Flachdachbahn", "Dach", ["Dachpappe", "Flachdach schwarz"], (0.15, 0.15, 0.15), "concrete", col=[0.05, 0.05, 0.05])
add("roof_gravel_flat", "Kiesschüttung Flachdach", "Dach", ["Kiesdach"], (0.60, 0.58, 0.54), "gravel")


def wd(key, label, aliases, c0, c1, group="Holz", scale=3.0, distortion=6.0, rough=0.45):
    mid = [(a + b) / 2 for a, b in zip(c0, c1)]
    add(key, label, group, aliases, lin(mid, 1 / 2.2), "wood", c0=c0, c1=c1, scale=scale, distortion=distortion, rough=rough)


wd("wood_oak", "Eiche natur", ["Eichenholz"], [0.18, 0.10, 0.05], [0.42, 0.28, 0.15])
wd("wood_pine", "Kiefer/Fichte hell", ["Fichte", "Kiefer", "Nadelholz"], [0.40, 0.25, 0.12], [0.72, 0.55, 0.32], scale=2.2)
wd("wood_cedar", "Zeder/Lärche rötlich", ["Zeder"], [0.30, 0.13, 0.07], [0.55, 0.28, 0.14])
wd("wood_thermo", "Thermoholz dunkelbraun", ["Thermoesche"], [0.10, 0.06, 0.03], [0.22, 0.13, 0.07])
wd("wood_weathered", "Holz vergraut", ["vergrautes Holz", "Silbergrau"], [0.30, 0.28, 0.25], [0.52, 0.49, 0.45], rough=0.7)
wd("timber_oak_aged", "Eichenfachwerk gealtert", ["Fachwerkbalken", "Eichenbalken", "Balken"], [0.10, 0.07, 0.04], [0.26, 0.18, 0.11], group="Holz/Fachwerk", scale=1.4, distortion=9.0, rough=0.7)
wd("timber_black", "Fachwerk schwarz gestrichen", ["schwarze Balken"], [0.015, 0.012, 0.01], [0.05, 0.04, 0.035], group="Holz/Fachwerk", scale=1.4, rough=0.55)
wd("timber_brown_dark", "Fachwerk dunkelbraun gestrichen", ["braune Balken", "Fachwerk braun"], [0.06, 0.03, 0.015], [0.14, 0.075, 0.04], group="Holz/Fachwerk", scale=1.4, rough=0.55)
wd("timber_oxblood", "Fachwerk ochsenblutrot", ["rote Balken", "Ochsenblut"], [0.20, 0.03, 0.02], [0.34, 0.06, 0.04], group="Holz/Fachwerk", scale=1.4, rough=0.55)
wd("terrace_decking", "Terrassendielen Holz", ["Terrassenboden", "Dielen außen"], [0.20, 0.12, 0.06], [0.40, 0.24, 0.12], group="Außen", scale=2.0, rough=0.6)
wd("floor_parquet_light", "Parkett hell (Ahorn/Esche)", ["Parkett", "heller Boden"], [0.52, 0.38, 0.22], [0.78, 0.62, 0.40], group="Innen", scale=2.5)
wd("floor_parquet_dark", "Parkett dunkel (Räuchereiche)", ["dunkles Parkett", "Räuchereiche"], [0.10, 0.06, 0.03], [0.22, 0.14, 0.08], group="Innen", scale=2.5)


def paint(key, label, aliases, rgb, rough=0.42, group="Anstrich"):
    add(key, label, group, aliases, rgb, "painted", col=lin(rgb, 2.2), rough=rough)


paint("paint_white", "Lack weiß", ["weiße Fenster", "weißer Rahmen", "RAL 9016"], (0.95, 0.95, 0.93))
paint("paint_cream", "Lack cremeweiß", ["cremefarbene Fenster"], (0.90, 0.86, 0.72))
paint("paint_grey_light", "Lack hellgrau", ["RAL 7035"], (0.78, 0.79, 0.78))
paint("paint_anthracite", "Lack anthrazit", ["RAL 7016", "anthrazit"], (0.22, 0.24, 0.26))
paint("paint_black", "Lack schwarz", ["RAL 9005"], (0.05, 0.05, 0.05))
paint("paint_green_dark", "Lack Tannengrün", ["Fensterladen grün", "RAL 6009", "dunkelgrün"], (0.12, 0.25, 0.17))
paint("paint_green_sage", "Lack Salbeigrün", ["salbei", "hellgrün"], (0.55, 0.64, 0.50))
paint("paint_blue_dark", "Lack Dunkelblau", ["blaue Tür", "RAL 5011"], (0.10, 0.18, 0.33))
paint("paint_blue_light", "Lack Taubenblau", ["hellblau", "RAL 5014"], (0.50, 0.62, 0.73))
paint("paint_red_sweden", "Lack Schwedenrot", ["Falunrot", "Schwedenrot"], (0.50, 0.14, 0.10))
paint("paint_red_bright", "Lack Rot (Tür)", ["rote Fensterläden", "RAL 3000"], (0.60, 0.08, 0.07))
paint("paint_brown", "Lack Braun", ["braune Fenster", "RAL 8014"], (0.28, 0.17, 0.10))
paint("paint_yellow", "Lack Gelb", ["gelbe Tür"], (0.88, 0.70, 0.20))

add("copper", "Kupfer blank", "Metall", ["Kupfer"], (0.80, 0.48, 0.34), "metal", col=[0.85, 0.42, 0.27], rough=0.25)
add("copper_patina", "Kupfer grün patiniert", "Metall", ["Grünspan"], (0.40, 0.62, 0.55), "painted", col=[0.12, 0.33, 0.26], rough=0.6)
add("brass", "Messing", "Metall", ["Messing", "Gold"], (0.80, 0.65, 0.30), "metal", col=[0.85, 0.62, 0.20], rough=0.25)
add("cast_iron_black", "Gusseisen schwarz", "Metall", ["Gusseisen", "Schmiedeeisen", "Geländer schwarz"], (0.08, 0.08, 0.08), "painted", col=[0.007, 0.007, 0.008], rough=0.55)
add("steel_galvanized", "Stahl verzinkt", "Metall", ["feuerverzinkt", "Zinkstahl"], (0.62, 0.64, 0.65), "metal", col=[0.55, 0.57, 0.58], rough=0.5)
add("steel_corten", "Cortenstahl", "Metall", ["Corten", "Rost"], (0.45, 0.25, 0.15), "painted", col=[0.18, 0.07, 0.035], rough=0.75)
add("alu_white", "Aluminium weiß", "Metall", ["Alu weiß"], (0.93, 0.93, 0.92), "painted", col=[0.85, 0.85, 0.83], rough=0.38)
add("alu_bronze", "Aluminium bronze", "Metall", ["Alu bronze", "Bronze eloxiert"], (0.35, 0.28, 0.22), "metal", col=[0.15, 0.10, 0.07], rough=0.4)
add("lead_grey", "Blei/Blech grau", "Metall", ["Bleiblech", "Verwahrung"], (0.45, 0.46, 0.48), "metal", col=[0.18, 0.19, 0.20], rough=0.55)

add("glass_tinted_grey", "Glas getönt grau", "Glas", ["Sonnenschutzglas", "graues Glas"], (0.5, 0.55, 0.55), "glass", tint=[0.6, 0.65, 0.65])
add("glass_tinted_green", "Glas grünlich", "Glas", ["grünes Glas", "Antikglas"], (0.6, 0.75, 0.68), "glass", tint=[0.72, 0.9, 0.8])
add("glass_frosted", "Glas satiniert", "Glas", ["Milchglas", "satiniertes Glas"], (0.9, 0.93, 0.92), "glass", tint=[0.95, 0.97, 0.96], rough=0.35)

add("paving_granite", "Granitpflaster", "Außen", ["Kopfsteinpflaster Granit"], (0.52, 0.52, 0.53), "paving", col=[0.30, 0.30, 0.31], scale=14.0)
add("paving_flagstone", "Natursteinplatten", "Außen", ["Sandsteinplatten", "Terrasse Naturstein", "Gehwegplatten"], (0.66, 0.60, 0.50), "stone", col1=[0.40, 0.33, 0.24], col2=[0.32, 0.26, 0.19], mortar=[0.2, 0.18, 0.16], brick_w=0.6, row_h=0.4, mortar_size=0.02)
add("paving_clinker", "Klinkerpflaster", "Außen", ["Ziegelpflaster", "Klinkerweg"], (0.55, 0.30, 0.22), "brick", col1=[0.30, 0.10, 0.06], col2=[0.22, 0.07, 0.045], mortar=[0.3, 0.29, 0.27], brick_w=0.22, row_h=0.07)
add("asphalt", "Asphalt", "Außen", ["Straße", "Asphaltdecke"], (0.22, 0.22, 0.23), "concrete", col=[0.04, 0.04, 0.045])
add("concrete_light", "Beton hell geschliffen", "Außen", ["heller Beton", "Sichtbeton hell"], (0.72, 0.72, 0.70), "concrete", col=[0.48, 0.48, 0.46])
add("gravel_light", "Kies hell", "Außen", ["Kiesbett", "Splitt"], (0.78, 0.74, 0.65), "gravel")

add("floor_tile_grey", "Fliese grau", "Innen", ["Feinsteinzeug grau", "Fliesen"], (0.55, 0.55, 0.55), "stone", col1=[0.28, 0.28, 0.28], col2=[0.24, 0.24, 0.24], mortar=[0.12, 0.12, 0.12], brick_w=0.6, row_h=0.6, mortar_size=0.006, offset=0.0, rough=0.3)
add("floor_tile_white", "Fliese weiß", "Innen", ["weiße Fliesen", "Badfliesen"], (0.90, 0.90, 0.88), "stone", col1=[0.78, 0.78, 0.76], col2=[0.74, 0.74, 0.72], mortar=[0.5, 0.5, 0.5], brick_w=0.3, row_h=0.3, mortar_size=0.006, offset=0.0, rough=0.25)
add("plaster_interior_cream", "Wand innen creme", "Innen", ["Wandfarbe creme"], (0.90, 0.86, 0.74), "plaster", col=lin((0.90, 0.86, 0.74), 1.8), grain=0.04)
add("plaster_interior_grey", "Wand innen grau", "Innen", ["Wandfarbe grau"], (0.62, 0.62, 0.60), "plaster", col=lin((0.62, 0.62, 0.60), 1.8), grain=0.04)
add("fabric_blue", "Stoff blau", "Innen", ["blaues Sofa"], (0.20, 0.28, 0.42), "fabric", col=[0.03, 0.06, 0.14])
add("fabric_green", "Stoff grün", "Innen", ["grünes Polster"], (0.25, 0.38, 0.28), "fabric", col=[0.04, 0.12, 0.06])
add("leather_brown", "Leder braun", "Innen", ["Leder", "Ledersofa"], (0.35, 0.20, 0.12), "painted", col=[0.10, 0.04, 0.02], rough=0.5)


# --- Stufe 3: moderne Bauweisen
add("solar_panel", "Solarmodul (PV)", "Dach", ["Photovoltaik", "PV-Modul", "Solarpaneel"], (0.08, 0.11, 0.2), "metal", col=[0.015, 0.03, 0.09], rough=0.18)
add("metal_corrugated", "Trapezblech", "Metall", ["Wellblech", "Profilblech", "Trapezblech grau"], (0.5, 0.52, 0.54), "metal", col=[0.30, 0.32, 0.34], rough=0.6)
add("metal_panel_anthracite", "Metallpaneel anthrazit", "Metall", ["Alu-Verbundplatte", "Metallfassade dunkel"], (0.2, 0.21, 0.23), "metal", col=[0.07, 0.075, 0.085], rough=0.35)
add("metal_panel_silver", "Metallpaneel silber", "Metall", ["Aluminiumfassade", "Alupaneel"], (0.72, 0.74, 0.75), "metal", col=[0.7, 0.72, 0.73], rough=0.3)
add("fibre_cement_grey", "Faserzementplatte grau", "Fassade/Putz", ["Eternit", "Faserzement"], (0.55, 0.56, 0.55), "concrete", col=[0.28, 0.285, 0.28])
add("fibre_cement_anthracite", "Faserzementplatte anthrazit", "Fassade/Putz", ["Faserzement dunkel"], (0.24, 0.25, 0.26), "concrete", col=[0.05, 0.052, 0.056])
add("glass_curtain_blue", "Glas Vorhangfassade blau", "Glas", ["Bürohausglas", "Curtain Wall"], (0.45, 0.62, 0.72), "glass", tint=[0.55, 0.75, 0.9])
add("glass_curtain_dark", "Glas Vorhangfassade dunkel", "Glas", ["Spiegelglas dunkel", "Glasfassade dunkel"], (0.25, 0.32, 0.36), "glass", tint=[0.35, 0.45, 0.5])
add("roof_sedum", "Gründach (Sedum)", "Dach", ["Gründach", "extensive Dachbegrünung"], (0.38, 0.5, 0.28), "grass_hair", col=[0.18, 0.3, 0.1])

add("soil_dark", "Erde dunkel (Beet)", "Außen", ["Mutterboden", "Beeterde"], (0.17, 0.11, 0.07), "concrete", col=[0.03, 0.02, 0.012])


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    added = 0
    for k, v in NEW.items():
        if k not in data:
            data[k] = v
            added += 1
    data["_comment"] = ("Single source of truth for materials. rgb = display colour in IFC viewers; shader = procedural Blender material "
                        "(kinds: plaster, concrete, paving, painted, metal, glass, water, foliage, gravel, wood, fabric, brick, stone, tile, slate, thatch, "
                        "lawn_soil, grass_hair, leaf). render_only entries are not offered to the interpreter. aliases help the interpreter map everyday words to a key. "
                        "Erweiterung per tools/gen_materials.py.")
    PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("neu:", added, "gesamt:", len([k for k in data if not k.startswith('_')]))


if __name__ == "__main__":
    main()
