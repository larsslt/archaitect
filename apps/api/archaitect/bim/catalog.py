"""Component catalog: single source of truth for parametric building components.

The registry feeds (1) parameter validation with defaults/ranges, (2) the interpreter prompt (generated table),
(3) the gallery spec and the docs. Generators live in ifc_components.py / ifc_openings.py.
All lengths in metres; `z` values are heights above the base of the referenced volume.
"""
from __future__ import annotations

SIDE_ANY = ("S", "N", "E", "W", "all")

# param: (type, default, lo, hi, text)   type: n=number, i=integer, s=string, b=bool, st=style key, e=enum(list in lo), p=points
C = {
    "cornice": {
        "label": "Gesims / Traufgesims / Gurtband (umlaufend oder je Seite)",
        "tier": 1,
        "params": {
            "side": ("e", "all", SIDE_ANY, None, "Seite oder all (alle vier, an den Ecken überlappend)"),
            "z": ("n", None, 0.0, 60.0, "Höhe der Unterkante über Volumenbasis; Standard: Oberkante des Volumens (Traufe)"),
            "height": ("n", 0.28, 0.04, 1.2, "Bauhöhe des Gesimses"),
            "projection": ("n", 0.22, 0.02, 0.8, "Ausladung"),
            "profile": ("e", "simple", ("band", "simple", "stepped", "cove"), None, "band=glatter Streifen, simple=klassisch, stepped=Konsolreihen/Stufen, cove=Hohlkehle"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "quoins": {
        "label": "Ecksteine / Eckquaderung (wechselnd lang/kurz)",
        "tier": 1,
        "params": {
            "width": ("n", 0.5, 0.15, 1.2, "lange Läufer; die kurzen Binder sind 60 %"),
            "course": ("n", 0.3, 0.12, 0.7, "Schichthöhe"),
            "z0": ("n", 0.0, 0.0, 60.0, "Start über Volumenbasis"),
            "z1": ("n", None, 0.0, 60.0, "Ende; Standard: Traufe"),
            "proud": ("n", 0.03, 0.01, 0.12, "Vorsprung vor der Wand"),
            "material": ("st", "stone_sandstone_yellow", None, None, "Material"),
        },
    },
    "pilaster": {
        "label": "Lisene / Pilaster (Wandvorlage, optional mit Basis und Kapitell)",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte von der linken Ecke (von außen gesehen)"),
            "count": ("i", 1, 1, 12, "Anzahl"),
            "spacing": ("n", 3.0, 0.5, 20.0, "Abstand bei count>1"),
            "width": ("n", 0.3, 0.1, 0.9, "Breite"),
            "projection": ("n", 0.08, 0.02, 0.4, "Vorsprung"),
            "z0": ("n", 0.0, 0.0, 60.0, "Unterkante"),
            "z1": ("n", None, 0.0, 60.0, "Oberkante; Standard: Traufe"),
            "capital": ("b", True, None, None, "Kapitell/Kopf"),
            "base": ("b", True, None, None, "Fußplatte"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "column": {
        "label": "Säule (rund) vor der Fassade, z. B. Portikus",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte entlang der Fassade"),
            "count": ("i", 1, 1, 12, "Anzahl"),
            "spacing": ("n", 2.5, 0.8, 12.0, "Abstand"),
            "distance": ("n", 1.2, 0.05, 6.0, "Abstand der Säulenachse von der Wand"),
            "radius": ("n", 0.15, 0.05, 0.6, "Radius"),
            "z0": ("n", 0.0, 0.0, 30.0, "Unterkante (Basis)"),
            "z1": ("n", 3.0, 0.5, 60.0, "Oberkante (unter Gebälk)"),
            "capital": ("b", True, None, None, "Kapitell"),
            "base": ("b", True, None, None, "Basis"),
            "order": ("e", "plain", ("plain", "doric"), None, "plain = glatter Zylinder; doric = verjüngter, kannelierter Schaft mit Echinus-Kapitell und Abakus, ohne Basis (griechischer Tempel)"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "entablature": {
        "label": "Gebälk über einer Säulenreihe (Architrav, Fries mit Triglyphen, Geison) mit Decke bis zur Wand",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte entlang der Fassade"),
            "span": ("n", 10.0, 1.0, 100.0, "Länge entlang der Fassade (Säulenreihe + Überstand)"),
            "z": ("n", 5.0, 0.5, 60.0, "Unterkante Architrav (= Oberkante der Säulen)"),
            "height": ("n", 1.1, 0.4, 3.0, "Gesamthöhe Architrav + Fries + Geison"),
            "distance": ("n", 1.5, 0.05, 6.0, "Abstand der Säulenachse von der Wand"),
            "beam_depth": ("n", 1.1, 0.3, 3.0, "Tiefe des Gebälks"),
            "triglyphs": ("b", True, None, None, "Triglyphen im Fries"),
            "material": ("st", "stone_marble_white", None, None, "Material"),
        },
    },
    "bracket": {
        "label": "Konsole / Knagge / Kragstein (Dreieckskonsole)",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "z": ("n", None, 0.0, 60.0, "Oberkante der Konsole; Standard: Traufe"),
            "count": ("i", 1, 1, 40, "Anzahl"),
            "spacing": ("n", 0.9, 0.2, 10.0, "Abstand"),
            "size": ("n", 0.3, 0.1, 1.2, "Höhe der Konsole"),
            "projection": ("n", 0.28, 0.05, 1.0, "Ausladung"),
            "thickness": ("n", 0.12, 0.04, 0.4, "Breite entlang der Fassade"),
            "material": ("st", "timber_oak_aged", None, None, "Material"),
        },
    },
    "canopy": {
        "label": "Vordach über Eingang (flach, Pult oder Giebel; optional mit Stützen/Streben)",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 2.2, 0.8, 14.0, "Breite"),
            "projection": ("n", 1.3, 0.4, 4.0, "Ausladung"),
            "z": ("n", 2.5, 1.8, 20.0, "Unterkante an der Wand"),
            "kind": ("e", "flat", ("flat", "shed", "gable"), None, "flat=Flachdach, shed=Pultdach, gable=Giebeldach quer zur Wand"),
            "support": ("e", "brackets", ("none", "posts", "brackets"), None, "Stützen"),
            "thickness": ("n", 0.14, 0.05, 0.5, "Dicke der Platte"),
            "material": ("st", "steel_black", None, None, "Tragwerk/Platte"),
            "roof_material": ("st", None, None, None, "Deckung (nur shed/gable); Standard = material"),
        },
    },
    "steps": {
        "label": "Eingangstreppe / Freitreppe (Blockstufen mit Podest)",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 1.6, 0.6, 8.0, "Breite"),
            "count": ("i", 3, 1, 12, "Anzahl Stufen"),
            "rise": ("n", 0.17, 0.12, 0.22, "Steigung"),
            "tread": ("n", 0.32, 0.22, 0.5, "Auftritt"),
            "z0": ("n", None, 0.0, 60.0, "Gelände unten (absolut); Standard: Basis des Volumens"),
            "material": ("st", "stone_granite_grey", None, None, "Material"),
        },
    },
    "chimney": {
        "label": "Schornstein (Backstein mit Kopfplatte und Aufsatz)",
        "tier": 1,
        "params": {
            "x": ("n", None, -50.0, 200.0, "Mitte in x, gemessen ab Volumen-Ursprung"),
            "y": ("n", None, -50.0, 200.0, "Mitte in y, gemessen ab Volumen-Ursprung"),
            "width": ("n", 0.65, 0.3, 2.0, "Breite (x)"),
            "depth": ("n", 0.65, 0.3, 2.0, "Tiefe (y)"),
            "height": ("n", 1.0, 0.3, 4.0, "Höhe über First (Satteldach) bzw. über Attika"),
            "material": ("st", "brick_red", None, None, "Material"),
            "cap_material": ("st", "concrete_light", None, None, "Kopfplatte"),
        },
    },
    "downpipe": {
        "label": "Fallrohr (rund) mit Rohrschellen",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Position"),
            "z0": ("n", 0.1, 0.0, 30.0, "unten"),
            "z1": ("n", None, 0.0, 60.0, "oben; Standard: Traufe"),
            "radius": ("n", 0.045, 0.02, 0.12, "Radius"),
            "material": ("st", "zinc", None, None, "Material"),
        },
    },
    "lamp": {
        "label": "Wandleuchte / Laterne an der Fassade",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Position"),
            "z": ("n", 2.2, 1.0, 20.0, "Höhe der Leuchtenmitte"),
            "size": ("n", 0.28, 0.1, 0.8, "Höhe der Leuchte"),
            "material": ("st", "cast_iron_black", None, None, "Gestell"),
        },
    },
    "sign": {
        "label": "Aushängeschild an Ausleger (Gasthaus, Laden)",
        "tier": 1,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Position"),
            "z": ("n", 2.8, 1.8, 20.0, "Oberkante des Auslegers"),
            "width": ("n", 0.6, 0.2, 2.0, "Schildbreite (weg von der Wand)"),
            "height": ("n", 0.5, 0.2, 1.5, "Schildhöhe"),
            "arm": ("n", 0.9, 0.3, 2.0, "Länge des Auslegers"),
            "material": ("st", "cast_iron_black", None, None, "Ausleger"),
            "plate_material": ("st", "paint_red_sweden", None, None, "Schild"),
        },
    },
    "fence": {
        "label": "Zaun (Lattenzaun, Staketen, Pfosten-Riegel) entlang achsparalleler Linien im Grundstück",
        "tier": 1,
        "params": {
            "points": ("p", None, 2, 40, "Liste [[x,y],...] in Weltkoordinaten (m), nur achsparallele Segmente"),
            "kind": ("e", "picket", ("picket", "post_rail", "wall_cap"), None, "picket=Lattenzaun, post_rail=Pfosten-Riegel, wall_cap=Mauer mit Abdeckplatte"),
            "height": ("n", 1.0, 0.4, 2.5, "Höhe"),
            "material": ("st", "paint_white", None, None, "Material"),
        },
    },
    "tower": {
        "label": "Turm / Rundturm / Erkerturm mit Kegel-, Kuppel-, Zwiebel- oder Flachdach (n Ecken: 6-8 = Polygonturm)",
        "tier": 2,
        "params": {
            "x": ("n", None, -50.0, 200.0, "Mitte in x ab Volumen-Ursprung (Pflicht)"),
            "y": ("n", None, -50.0, 200.0, "Mitte in y ab Volumen-Ursprung (Pflicht)"),
            "radius": ("n", 1.6, 0.5, 8.0, "Schaftradius"),
            "z0": ("n", 0.0, 0.0, 60.0, "Unterkante über Volumenbasis"),
            "z1": ("n", 9.0, 2.0, 80.0, "Traufhöhe über Volumenbasis"),
            "sides": ("i", 32, 5, 64, "Eckenzahl (32 = rund, 8 = Oktogon, 6 = Sechseck)"),
            "roof": ("e", "cone", ("cone", "dome", "onion", "flat"), None, "Helmform"),
            "roof_height": ("n", 3.0, 0.2, 15.0, "Helmhöhe"),
            "roof_overhang": ("n", 0.3, 0.0, 1.5, "Dachüberstand"),
            "material": ("st", "plaster_white", None, None, "Schaft"),
            "roof_material": ("st", "roof_slate", None, None, "Helm"),
            "band": ("b", False, None, None, "Gesimsring unter dem Helm"),
            "band_material": ("st", None, None, None, "Material des Rings (Standard = Schaft)"),
            "finial": ("b", False, None, None, "Spitze/Knauf aus Messing"),
            "slits": ("i", 0, 0, 16, "Anzahl Schlitzfenster rund um den Schaft"),
            "slit_angle": ("n", 0.0, 0.0, 360.0, "Startwinkel der Schlitze in Grad (0 = +x)"),
            "slit_z": ("n", None, 0.0, 80.0, "Höhe der Schlitzmitte; Standard: Mitte des Schafts"),
            "slit_width": ("n", 0.3, 0.1, 1.2, "Schlitzbreite"),
            "slit_height": ("n", 1.0, 0.3, 3.0, "Schlitzhöhe"),
        },
    },
    "bay": {
        "label": "Erker / Auslucht (box = eckig, canted = dreiseitig geknickt), auch auskragend ab z0 > 0",
        "tier": 2,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 2.4, 0.8, 8.0, "Breite an der Wand"),
            "projection": ("n", 0.7, 0.2, 1.5, "Ausladung"),
            "z0": ("n", 0.0, 0.0, 60.0, "Unterkante über Volumenbasis"),
            "z1": ("n", 3.0, 1.6, 60.0, "Oberkante (Dachplatte liegt darauf)"),
            "kind": ("e", "box", ("box", "canted"), None, "Form"),
            "sill": ("n", 0.9, 0.3, 1.2, "Brüstungshöhe"),
            "material": ("st", None, None, None, "Wandmaterial; Standard = Fassade des Volumens"),
            "frame": ("st", "paint_white", None, None, "Rahmen"),
            "roof_material": ("st", "zinc", None, None, "Dachplatte"),
            "support_material": ("st", "stone_ashlar_light", None, None, "Konsole unter schwebenden Erkern"),
        },
    },
    "arcade": {
        "label": "Arkade / Bogenhalle / Laubengang vor der Fassade (Pfeiler + Bögen)",
        "tier": 2,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "linke Kante der Arkade; Standard: mittig"),
            "count": ("i", 3, 1, 20, "Anzahl Bögen"),
            "span": ("n", 2.6, 1.0, 6.0, "lichte Bogenweite"),
            "pier": ("n", 0.6, 0.3, 1.5, "Pfeilerbreite"),
            "z0": ("n", 0.0, 0.0, 30.0, "Unterkante"),
            "spring_z": ("n", 2.6, 1.0, 10.0, "Bogenansatz (Kämpfer) über Volumenbasis"),
            "z1": ("n", 4.6, 2.0, 20.0, "Oberkante der Arkadenwand"),
            "kind": ("e", "round_arch", ("round_arch", "segment_arch", "pointed_arch"), None, "Bogenform"),
            "arch_rise": ("n", None, 0.05, 3.0, "Pfeilhöhe nur bei segment_arch"),
            "distance": ("n", 0.0, 0.0, 6.0, "Abstand zur Wand (0 = vorgesetzt direkt an der Wand)"),
            "depth": ("n", 0.5, 0.2, 1.5, "Tiefe der Arkadenwand"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "awning": {
        "label": "Markise / Sonnenschutz (gestreift) über Schaufenster oder Eingang",
        "tier": 2,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 2.5, 0.6, 10.0, "Breite"),
            "projection": ("n", 1.4, 0.4, 3.5, "Ausladung"),
            "z": ("n", 2.6, 1.8, 20.0, "Befestigungshöhe an der Wand"),
            "drop": ("n", 0.6, 0.2, 1.2, "Gefälle bis zur Vorderkante"),
            "stripe": ("n", 0.3, 0.1, 1.0, "Streifenbreite"),
            "material": ("st", "paint_red_bright", None, None, "Streifenfarbe 1"),
            "material2": ("st", "paint_white", None, None, "Streifenfarbe 2"),
        },
    },
    "rustication": {
        "label": "Bossenwerk / Rustika (horizontale Quaderung, spart Öffnungen aus), meist am Erdgeschoss",
        "tier": 2,
        "params": {
            "side": ("e", "all", SIDE_ANY, None, "Seite oder all"),
            "z0": ("n", 0.0, 0.0, 60.0, "Start"),
            "z1": ("n", None, 0.0, 60.0, "Ende; Standard: z0 + 3 m"),
            "course": ("n", 0.5, 0.2, 1.2, "Schichthöhe"),
            "proud": ("n", 0.02, 0.01, 0.1, "Vorsprung"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "dentil": {
        "label": "Zahnschnitt (Reihe kleiner Klötzchen unter dem Gesims)",
        "tier": 2,
        "params": {
            "side": ("e", "all", SIDE_ANY, None, "Seite oder all"),
            "z": ("n", None, 0.0, 60.0, "Unterkante; Standard: 0.4 m unter der Traufe"),
            "width": ("n", 0.09, 0.04, 0.25, "Klotzbreite"),
            "height": ("n", 0.1, 0.04, 0.3, "Klotzhöhe"),
            "depth": ("n", 0.08, 0.03, 0.3, "Vorsprung"),
            "spacing": ("n", 0.2, 0.1, 0.6, "Abstand (Mitte zu Mitte, ungefähr)"),
            "material": ("st", "stone_ashlar_light", None, None, "Material"),
        },
    },
    "gutter": {
        "label": "Dachrinne an den Traufen (Satteldach: nur Traufseiten)",
        "tier": 2,
        "params": {
            "side": ("e", "all", SIDE_ANY, None, "Seite oder all"),
            "material": ("st", "zinc", None, None, "Material"),
        },
    },
    "bargeboard": {
        "label": "Ortgangbrett an den Giebelkanten eines Satteldachs",
        "tier": 2,
        "params": {
            "height": ("n", 0.25, 0.08, 0.6, "Brettbreite (senkrecht gemessen)"),
            "thickness": ("n", 0.04, 0.02, 0.12, "Brettdicke"),
            "material": ("st", "paint_white", None, None, "Material"),
        },
    },
    "skylight": {
        "label": "Dachflächenfenster (nur Satteldach)",
        "tier": 2,
        "params": {
            "slope": ("e", "S", ("S", "N", "E", "W"), None, "Dachseite (bei ridge x: S/N, bei ridge y: W/E)"),
            "u": ("n", 2.0, 0.0, 100.0, "Abstand vom Dachanfang entlang des Firsts (linke Kante)"),
            "up": ("n", 1.0, 0.3, 8.0, "waagerechter Abstand der Unterkante von der Außenwand zum First"),
            "width": ("n", 0.78, 0.4, 2.0, "Breite"),
            "height": ("n", 1.18, 0.5, 2.5, "Länge entlang der Dachschräge"),
            "frame": ("st", "alu_anthracite", None, None, "Rahmen"),
        },
    },
    "solar": {
        "label": "Photovoltaik: aufgeständert auf Flachdach (mode flat) oder bündig auf Satteldach (mode pitched)",
        "tier": 3,
        "params": {
            "mode": ("e", "flat", ("flat", "pitched"), None, "flat=Flachdach aufgeständert, pitched=Satteldachfläche"),
            "x": ("n", None, 0.0, 200.0, "flat: linke Kante ab Volumen-Ursprung (Standard 0,8)"),
            "y": ("n", None, 0.0, 200.0, "flat: untere Kante ab Volumen-Ursprung (Standard 0,8)"),
            "cols": ("i", 4, 1, 30, "Module nebeneinander"),
            "rows": ("i", 2, 1, 12, "Modulreihen"),
            "panel_w": ("n", 1.05, 0.6, 1.4, "Modulbreite"),
            "panel_l": ("n", 1.75, 1.0, 2.5, "Modullänge"),
            "tilt": ("n", 15.0, 5.0, 40.0, "flat: Neigung in Grad (Ausrichtung nach Süden)"),
            "slope": ("e", "S", ("S", "N", "E", "W"), None, "pitched: Dachseite"),
            "u": ("n", 2.0, 0.3, 100.0, "pitched: Abstand ab Dachanfang entlang des Firsts"),
            "up": ("n", 0.6, 0.2, 8.0, "pitched: Abstand der Unterkante von der Wand horizontal"),
            "material": ("st", "solar_panel", None, None, "Modulfläche"),
        },
    },
    "technical_box": {
        "label": "Technikaufbau auf dem Flachdach (Lüftung, Aufzugsüberfahrt, Treppenhauskopf)",
        "tier": 3,
        "params": {
            "x": ("n", None, 0.0, 200.0, "linke Kante ab Volumen-Ursprung (Standard mittig)"),
            "y": ("n", None, 0.0, 200.0, "untere Kante ab Volumen-Ursprung (Standard mittig)"),
            "width": ("n", 2.2, 0.5, 15.0, "Breite (x)"),
            "depth": ("n", 1.6, 0.5, 15.0, "Tiefe (y)"),
            "height": ("n", 1.8, 0.5, 5.0, "Höhe"),
            "material": ("st", "metal_panel_silver", None, None, "Hülle"),
            "cap_material": ("st", "steel_galvanized", None, None, "Kappe/Lamellen"),
        },
    },
    "ramp": {
        "label": "Rampe (barrierefrei oder Anlieferung), massiver Keil mit optionalem Geländer",
        "tier": 3,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 1.5, 0.9, 8.0, "Breite"),
            "length": ("n", 6.0, 0.5, 30.0, "Länge (Neigung max 12 %, barrierefrei 6 %)"),
            "height": ("n", 0.3, 0.05, 1.5, "Höhenunterschied"),
            "z0": ("n", None, 0.0, 60.0, "Gelände unten (absolut); Standard: Basis des Volumens"),
            "railing": ("e", "steel", ("none", "steel"), None, "Handlauf beidseitig"),
            "railing_material": ("st", "steel_galvanized", None, None, "Handlauf"),
            "material": ("st", "concrete_light", None, None, "Rampe"),
        },
    },
    "terrace": {
        "label": "Terrasse / Austritt vor der Fassade, optional mit Geländer (Stäbe, Glas, Brüstung, Seile)",
        "tier": 3,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 4.0, 1.0, 16.0, "Breite"),
            "depth": ("n", 3.0, 1.0, 8.0, "Tiefe"),
            "z": ("n", 0.0, 0.0, 60.0, "Oberkante über Volumenbasis"),
            "thickness": ("n", 0.15, 0.05, 0.4, "Plattendicke"),
            "material": ("st", "terrace_decking", None, None, "Belag"),
            "railing": ("e", "none", ("none", "bars", "glass", "solid", "cable"), None, "Geländertyp"),
            "railing_sides": ("s", "front,left,right", None, None, "Seiten mit Geländer (Komma-Liste aus front,left,right)"),
            "railing_height": ("n", 1.0, 0.8, 1.3, "Geländerhöhe"),
            "railing_material": ("st", "steel_black", None, None, "Geländer"),
        },
    },
    "carport": {
        "label": "Carport an der Fassade (Flach- oder Pultdach, Stützen im Abstand von höchstens 3,5 m)",
        "tier": 3,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 3.2, 2.5, 12.0, "Breite (je Stellplatz 2,5-3 m)"),
            "projection": ("n", 5.5, 2.5, 7.0, "Tiefe"),
            "height": ("n", 2.4, 2.0, 3.5, "lichte Höhe an der Außenkante"),
            "kind": ("e", "flat", ("flat", "shed"), None, "Dachform"),
            "material": ("st", "steel_black", None, None, "Stützen und Dach"),
            "roof_material": ("st", None, None, None, "Dachdeckung (nur shed); Standard = material"),
        },
    },
    "retaining_wall": {
        "label": "Stützmauer / Gartenmauer freistehend (achsparallel, mit Abdeckplatte)",
        "tier": 3,
        "params": {
            "x0": ("n", None, -200.0, 400.0, "Start x (absolut)"),
            "y0": ("n", None, -200.0, 400.0, "Start y (absolut)"),
            "x1": ("n", None, -200.0, 400.0, "Ende x (absolut); x0==x1 für Mauer in y-Richtung"),
            "y1": ("n", None, -200.0, 400.0, "Ende y (absolut); y0==y1 für Mauer in x-Richtung"),
            "height": ("n", 1.0, 0.3, 4.0, "Höhe über z0"),
            "thickness": ("n", 0.3, 0.15, 0.8, "Dicke"),
            "z0": ("n", 0.0, -2.0, 60.0, "Unterkante absolut"),
            "material": ("st", "concrete_exposed", None, None, "Mauer"),
            "cap_material": ("st", "stone_granite_grey", None, None, "Abdeckplatte"),
        },
    },
    "stair_ext": {
        "label": "Außentreppe / Fluchttreppe aus Stahl entlang der Fassade mit Podest und Handlauf",
        "tier": 3,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Anfang des Laufs (unten), von links"),
            "width": ("n", 1.1, 0.8, 2.0, "Laufbreite"),
            "z0": ("n", 0.0, 0.0, 60.0, "unten, über Volumenbasis"),
            "z1": ("n", 3.0, 0.5, 12.0, "oben (Podestoberkante), über Volumenbasis"),
            "tread": ("n", 0.27, 0.22, 0.35, "Auftritt"),
            "landing": ("n", 1.2, 0.9, 2.5, "Podestlänge am oberen Ende"),
            "material": ("st", "steel_black", None, None, "Wangen/Geländer"),
            "tread_material": ("st", "steel_galvanized", None, None, "Stufen/Podest"),
        },
    },
    "loggia": {
        "label": "Loggia (vorgesetzt, geschosshoch mit Seitenwänden, Decke und Brüstung); Tür dorthin wird automatisch ergänzt",
        "tier": 4,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte"),
            "width": ("n", 3.0, 1.6, 8.0, "Breite"),
            "depth": ("n", 1.6, 1.0, 3.5, "Tiefe"),
            "storey": ("i", 1, 0, 40, "Geschoss (0 = Erdgeschoss)"),
            "ceiling": ("b", True, None, None, "Deckenplatte; false, wenn darüber eine weitere Loggia/ein Balkon die Decke bildet (sonst Z-Fighting)"),
            "railing": ("e", "solid", ("none", "solid", "glass", "bars"), None, "Brüstungstyp vorn"),
            "railing_height": ("n", 1.0, 0.8, 1.3, "Brüstungshöhe"),
            "railing_material": ("st", "concrete_light", None, None, "Brüstung"),
            "slab_material": ("st", "concrete_exposed", None, None, "Platten"),
            "wall_material": ("st", None, None, None, "Seitenwände; Standard = Fassade des Volumens"),
        },
    },
    "buttress": {
        "label": "Strebepfeiler (abgetreppt, in Reihe) für Kirchen und Burgen",
        "tier": 4,
        "params": {
            "side": ("e", "S", ("S", "N", "E", "W"), None, "Fassadenseite"),
            "u": ("n", None, 0.0, 200.0, "Mitte des ersten Pfeilers"),
            "count": ("i", 4, 1, 20, "Anzahl"),
            "pitch": ("n", 4.0, 1.0, 20.0, "Abstand der Pfeiler (Mitte-Mitte)"),
            "width": ("n", 0.7, 0.3, 1.5, "Breite"),
            "projection": ("n", 0.9, 0.3, 2.0, "Ausladung unten"),
            "z0": ("n", 0.0, 0.0, 60.0, "unten, über Volumenbasis"),
            "height": ("n", None, 1.0, 40.0, "Höhe; Standard bis knapp unter die Traufe"),
            "material": ("st", "stone_limestone", None, None, "Material"),
        },
    },
    "pylon": {
        "label": "Werbepylon / Einkaufsmarkt-Stele (freistehend, absolute Position)",
        "tier": 4,
        "params": {
            "x": ("n", None, -200.0, 400.0, "Position x"),
            "y": ("n", None, -200.0, 400.0, "Position y"),
            "height": ("n", 7.0, 3.0, 30.0, "Gesamthöhe"),
            "width": ("n", 2.2, 0.8, 5.0, "Breite der Werbetafel"),
            "z0": ("n", 0.0, -2.0, 60.0, "Fußpunkt absolut"),
            "material": ("st", "metal_panel_anthracite", None, None, "Stele"),
            "sign_material": ("st", "paint_red_bright", None, None, "Werbetafel"),
        },
    },
    "parking": {
        "label": "Stellplatzfläche mit Markierungen (freistehend, absolute Position)",
        "tier": 4,
        "params": {
            "x": ("n", None, -200.0, 400.0, "linke Kante x"),
            "y": ("n", None, -200.0, 400.0, "untere Kante y"),
            "width": ("n", 15.0, 2.5, 100.0, "Länge der Reihe in x"),
            "depth": ("n", 5.0, 4.0, 20.0, "Tiefe eines Stellplatzes in y"),
            "spaces": ("i", 6, 1, 40, "Anzahl Stellplätze (mind. 2,2 m je Platz)"),
            "z0": ("n", 0.0, -1.0, 60.0, "Höhe absolut"),
            "material": ("st", "asphalt", None, None, "Belag"),
            "line_material": ("st", "paint_white", None, None, "Markierung"),
        },
    },
    "tree": {
        "label": "Baum (Laubbaum mit detaillierter Krone im Render, oder Konifere); absolute Position",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "Position x"),
            "y": ("n", None, -300.0, 500.0, "Position y"),
            "height": ("n", 9.0, 2.0, 35.0, "Gesamthöhe"),
            "crown_radius": ("n", 3.0, 0.8, 9.0, "Kronenradius"),
            "kind": ("e", "deciduous", ("deciduous", "conifer"), None, "Laubbaum oder Konifere"),
        },
    },
    "hedge": {
        "label": "Hecke (geschnitten, achsparallel); absolute Koordinaten",
        "tier": 5,
        "params": {
            "x0": ("n", None, -300.0, 500.0, "Start x"), "y0": ("n", None, -300.0, 500.0, "Start y"),
            "x1": ("n", None, -300.0, 500.0, "Ende x"), "y1": ("n", None, -300.0, 500.0, "Ende y"),
            "height": ("n", 1.4, 0.3, 4.0, "Höhe"),
            "thickness": ("n", 0.7, 0.3, 2.0, "Dicke"),
        },
    },
    "shrub": {
        "label": "Strauch / Zierbusch, optional im Pflanzkübel",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "Position x"), "y": ("n", None, -300.0, 500.0, "Position y"),
            "radius": ("n", 0.7, 0.2, 2.0, "Radius"), "height": ("n", 1.0, 0.2, 3.0, "Höhe"),
            "pot": ("b", False, None, None, "im Kübel (0,4 m erhöht)"),
        },
    },
    "flowerbed": {
        "label": "Blumenbeet mit Steineinfassung, Erde und Blumen",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "linke Kante x"), "y": ("n", None, -300.0, 500.0, "untere Kante y"),
            "width": ("n", 3.0, 0.6, 20.0, "Breite (x)"), "depth": ("n", 1.2, 0.6, 10.0, "Tiefe (y)"),
            "density": ("n", 5.0, 1.0, 12.0, "Blumen je m²"),
            "flowers": ("s", "paint_red_bright,paint_yellow,paint_white", None, None, "Blütenfarben als Materialschlüssel, Komma-getrennt"),
            "border_material": ("st", "stone_granite_grey", None, None, "Einfassung"),
        },
    },
    "path": {
        "label": "Gartenweg / Zufahrt aus Platten, Pflaster oder Kies (achsparallele Knicke)",
        "tier": 5,
        "params": {
            "points": ("p", None, 2, 12, "Punkte [[x,y],...]; Richtung muss bei jedem Punkt wechseln"),
            "width": ("n", 1.2, 0.5, 6.0, "Breite"),
            "material": ("st", "paving_flagstone", None, None, "Belag (paving_*, cobblestone, gravel_light)"),
        },
    },
    "pool": {
        "label": "Schwimmbecken (rechteckig, Randplatten) - ein Teich ist KEIN pool, dafür pond",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "linke Kante x"), "y": ("n", None, -300.0, 500.0, "untere Kante y"),
            "width": ("n", 8.0, 2.0, 30.0, "Breite"), "depth": ("n", 4.0, 1.5, 15.0, "Tiefe"),
            "deep": ("n", 1.4, 0.4, 3.0, "Beckentiefe"), "coping": ("n", 0.35, 0.15, 1.0, "Randbreite"),
            "coping_material": ("st", "stone_limestone", None, None, "Randmaterial"),
        },
    },
    "pond": {
        "label": "Gartenteich mit natürlicher Uferlinie, ins Gelände eingesenkt, Steine am Rand (kein Becken)",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "linke Kante x der Umrissbox"), "y": ("n", None, -300.0, 500.0, "untere Kante y der Umrissbox"),
            "width": ("n", 8.0, 3.0, 40.0, "Breite"), "depth": ("n", 5.5, 2.5, 30.0, "Tiefe"),
            "deep": ("n", 0.8, 0.3, 2.0, "Wassertiefe"),
            "rim_material": ("st", "stone_granite_grey", None, None, "Randsteine"),
        },
    },
    "lake": {
        "label": "See: füllt die gemessene Geländesenke bis zu einem Wasserspiegel (Umriss kommt aus dem Gelände, nicht aus Maßen), mit Schilf, Seerosen, Findlingen, Sträuchern und Uferbäumen",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "Punkt in der Senke (tiefster Punkt aus dem Geländehinweis)"),
            "y": ("n", None, -300.0, 500.0, "Punkt in der Senke (tiefster Punkt aus dem Geländehinweis)"),
            "fill": ("n", 0.55, 0.15, 0.95, "Füllgrad der Senke (Anteil bis zur Überlaufhöhe)"),
            "life": ("b", True, None, None, "Uferbepflanzung und Tiere/Habitat: Schilf, Seerosen, Findlinge, Sträucher, Bäume"),
        },
    },
    "sauna_hut": {
        "label": "Saunahütte aus Holz mit Satteldach, Ofenrohr, Vorbau mit Bank, auf Punktfundamenten (steht auch am Hang oder am See)",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "linke untere Ecke x"), "y": ("n", None, -300.0, 500.0, "linke untere Ecke y"),
            "width": ("n", 3.8, 2.4, 8.0, "Breite (Firstrichtung)"), "depth": ("n", 3.0, 2.2, 6.0, "Tiefe ohne Vorbau"),
            "facing": ("e", "S", ("S", "N", "E", "W"), None, "Seite mit Tür und Vorbau (z. B. zum See)"),
            "wall_material": ("st", "wood_cedar", None, None, "Wand"), "roof_material": ("st", "roof_wood_shingle", None, None, "Dach"),
        },
    },
    "bench": {
        "label": "Gartenbank mit Lehne",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "linke untere Ecke x"), "y": ("n", None, -300.0, 500.0, "linke untere Ecke y"),
            "length": ("n", 1.6, 0.9, 3.0, "Länge"),
            "orientation": ("e", "x", ("x", "y"), None, "Länge in x- oder y-Richtung"),
            "flip": ("b", False, None, None, "Lehne auf der anderen Seite"),
            "material": ("st", "wood_oak", None, None, "Sitz/Lehne"), "frame_material": ("st", "steel_black", None, None, "Gestell"),
        },
    },
    "garden_set": {
        "label": "Gartenmöbel-Set: Tisch, vier Stühle, optional Sonnenschirm",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "Tischmitte x"), "y": ("n", None, -300.0, 500.0, "Tischmitte y"),
            "parasol": ("b", True, None, None, "Sonnenschirm"),
            "parasol_material": ("st", "plaster_cream", None, None, "Schirmbespannung"),
            "material": ("st", "wood_oak", None, None, "Tisch/Stühle"), "frame_material": ("st", "steel_black", None, None, "Gestell"),
        },
    },
    "garden_light": {
        "label": "Gartenleuchten (Poller oder Mast), einzeln oder in Reihe",
        "tier": 5,
        "params": {
            "x": ("n", None, -300.0, 500.0, "erste Leuchte x"), "y": ("n", None, -300.0, 500.0, "erste Leuchte y"),
            "count": ("i", 1, 1, 30, "Anzahl in Reihe"), "pitch": ("n", 3.0, 1.0, 20.0, "Abstand"),
            "axis": ("e", "x", ("x", "y"), None, "Reihenrichtung"),
            "kind": ("e", "bollard", ("bollard", "post"), None, "Poller 0,8 m oder Mast"),
            "height": ("n", 3.0, 1.5, 6.0, "Masthöhe (nur post)"),
            "material": ("st", "steel_black", None, None, "Gestell"),
        },
    },
}

from .ifc_garden2 import CATALOG as _G2, TYPES as G2_TYPES
C.update(_G2)

# components that are not volume-bound (absolute coordinates)
NO_VOLUME = set(G2_TYPES) | {"fence", "retaining_wall", "pylon", "parking", "tree", "hedge", "shrub", "flowerbed", "path", "pool", "pond", "lake", "sauna_hut", "bench", "garden_set", "garden_light"}


def types() -> list[str]:
    return list(C)


def resolve(comp: dict) -> dict:
    """Validate one component and return all params with defaults filled in. Raises ValueError with a repair hint."""
    t = comp.get("type")
    if t not in C:
        raise ValueError(f"unbekannter Bauteiltyp {t!r}; erlaubt: {', '.join(C)}")
    spec = C[t]["params"]
    out = {}
    unknown = [k for k in comp if k not in spec and k not in ("type", "volume", "note", "id")]
    if unknown:
        raise ValueError(f"Bauteil {t}: unbekannte Parameter {unknown}; erlaubt: {', '.join(spec)}")
    if t not in NO_VOLUME and not comp.get("volume"):
        raise ValueError(f"Bauteil {t}: 'volume' fehlt")
    for k, (ty, default, lo, hi, _txt) in spec.items():
        val = comp.get(k, default)
        if val is None:
            out[k] = None
            continue
        if ty in ("n", "i"):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError(f"Bauteil {t}.{k}: Zahl erwartet, bekommen {val!r}")
            if ty == "i":
                val = int(val)
            if (lo is not None and val < lo - 1e-9) or (hi is not None and val > hi + 1e-9):
                raise ValueError(f"Bauteil {t}.{k}={val} außerhalb {lo}..{hi}")
        elif ty == "e":
            if val not in lo:
                raise ValueError(f"Bauteil {t}.{k}={val!r}; erlaubt: {', '.join(map(str, lo))}")
        elif ty == "b":
            val = bool(val)
        elif ty == "p":
            if not isinstance(val, list) or not (lo <= len(val) <= hi) or any(len(p) != 2 for p in val):
                raise ValueError(f"Bauteil {t}.{k}: Liste von {lo}..{hi} Punkten [x,y] erwartet")
        out[k] = val
    out["type"], out["volume"], out["note"] = t, comp.get("volume"), comp.get("note", "")
    return out


def prompt_table() -> str:
    lines = ["# Bauteilkatalog (`components` im Spec; z immer in Metern über der Volumenbasis, u von der linken Ecke von außen gesehen)"]
    for t, d in C.items():
        ps = []
        for k, (ty, default, lo, hi, txt) in d["params"].items():
            rng = (f"{lo}..{hi}" if ty in ("n", "i") else "|".join(map(str, lo)) if ty == "e" else
                   {"st": "Materialschlüssel", "b": "bool", "p": "Punktliste"}.get(ty, ""))
            ps.append(f"{k} [{rng}{'; Standard ' + str(default) if default is not None else ''}] {txt}")
        lines.append(f"- {t}: {d['label']}\n  Parameter: " + "; ".join(ps))
    lines.append(
        "\n# Typen an Öffnungen (openings[])\n"
        "- window_type: casement (Standard, Flügel/Setzhölzer) | fixed (Festverglasung) | oculus (rundes Ochsenauge, Öffnung quadratisch)\n"
        "- top: flat | round_arch (Rundbogen, Bogenhöhe=Breite/2 ist Teil von height) | segment_arch (Segmentbogen, arch_rise m) | pointed_arch (Spitzbogen)\n"
        "- sashes: 1-6 Flügel; bars: {cols, rows, width} Sprossen; transom: 0-1 Kämpferhöhe (Anteil der Höhe)\n"
        "- door_type: panel (Füllungstür) | double (zweiflügelig) | glazed (Glasfüllung) | plank (Brettertür) | sectional (Garagen-/Sektionaltor, bis 5 m breit) | full_glass (Ladentür/Schaufenstertür) | french (zweiflügelige Terrassen-/Balkontür, fast ganz verglast); top/transom wie bei Fenstern; handle: Materialschlüssel\n"
        "- surround: {material, width 0.1-0.4, depth, lintel: flat|keystone|pediment|segment_pediment|hood, keystone: bool, sill: bool} – Gewände/Einfassung aus Stein\n"
        "- shutters: {material, state: open|closed, style: louvre|panel|plank} – Fensterläden\n"
        "- balconies[].railing.type: rails (Standard, Rohr) | bars (Stäbe) | glass (Glasbrüstung) | solid (Vollbrüstung) | cable (Seile); material Materialschlüssel; height, sides\n"
        "- flower_box: true | {material} – Blumenkasten unter dem Fenster\n"
        "- sill_material: Materialschlüssel oder none (Fensterbank)\n"
        "\n# Dachtypen (volumes[].roof.type): flat | gable | hip (Walmdach) | shed (Pultdach, fall_to: S|N|E|W) | sawtooth (Sheddach-Reihe für Hallen: teeth 2-16, pitch_deg 8-25, Verglasung zur Nordseite) | mansard (Mansarddach: pitch_deg oben, lower_pitch_deg 30-85, lower_height m) | gambrel (Bohlendach/Scheune: ridge, pitch_deg oben, lower_pitch_deg, lower_run Anteil 0.15-0.7)\n"
        "# Fachwerk-Muster (facade_detail.timber_frame.pattern): st_andrew (Andreaskreuz) | k_brace (Streben je Gefach schräg, Standard) | man (Mann-Figur) | foot_head (Fuß-/Kopfbänder) | diamond (Raute) | none\n")
    return "\n".join(lines)
