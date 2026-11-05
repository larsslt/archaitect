"""Erzeugt specs/moderne_typen.json: fuenf moderne Gebaeudetypen aus den Stufe-3-Bauteilen
(Buerohaus mit Glasfassade, Wohnblock, Halle mit Sheddach, Schulpavillon, Solarhaus). Aufruf: python tools/gen_catalog_spec3.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "specs" / "moderne_typen.json"


def win(vol, side, st, off, w, h, sill, **kw):
    return {"volume": vol, "side": side, "storey": st, "offset": off, "width": w, "height": h, "sill": sill, "kind": "window", **kw}


def door(vol, side, off, w, h, **kw):
    return {"volume": vol, "side": side, "storey": 0, "offset": off, "width": w, "height": h, "sill": 0.0, "kind": "door", **kw}


vols = [
    {"id": "J", "name": "Buerohaus", "origin": [0.0, 0.0], "size": [36.0, 14.0], "base_z": 0.0, "storeys": 4, "wall_thickness": 0.35,
     "facade": "plaster_grey_light", "storey_height": 3.6, "roof": {"type": "flat"}},
    {"id": "K", "name": "Wohnblock", "origin": [45.0, 0.0], "size": [30.0, 12.0], "base_z": 0.0, "storeys": 5, "wall_thickness": 0.35,
     "facade": "plaster_white", "storey_height": 2.9, "roof": {"type": "flat"}},
    {"id": "L", "name": "Halle", "origin": [84.0, 0.0], "size": [40.0, 20.0], "base_z": 0.0, "storeys": 1, "wall_thickness": 0.3,
     "facade": "metal_corrugated", "storey_height": 7.0, "roof": {"type": "sawtooth", "teeth": 4, "pitch_deg": 14, "material": "roof_zinc_standing"}},
    {"id": "M", "name": "Schulpavillon", "origin": [133.0, 0.0], "size": [24.0, 11.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.35,
     "facade": "fibre_cement_anthracite", "storey_height": 3.5, "roof": {"type": "flat"}},
    {"id": "N", "name": "Solarhaus", "origin": [166.0, 0.0], "size": [11.0, 9.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.36,
     "facade": "plaster_white", "storey_height": 2.8,
     "roof": {"type": "gable", "ridge": "x", "pitch_deg": 30, "overhang": 0.5, "material": "roof_tile_anthracite"}},
    {"id": "P", "name": "Supermarkt", "origin": [195.0, 0.0], "size": [36.0, 24.0], "base_z": 0.0, "storeys": 1, "wall_thickness": 0.3,
     "facade": "plaster_grey_light", "storey_height": 5.5, "roof": {"type": "flat"}},
    {"id": "Q", "name": "Kapelle", "origin": [245.0, 0.0], "size": [20.0, 10.0], "base_z": 0.0, "storeys": 1, "wall_thickness": 0.6,
     "facade": "stone_limestone", "storey_height": 7.0,
     "roof": {"type": "gable", "ridge": "x", "pitch_deg": 48, "overhang": 0.4, "material": "roof_slate"}},
]
op = []
# J Buero: Glasraster
g = dict(window_type="fixed", frame="alu_anthracite", glass="glass_curtain_blue")
op.append(win("J", "S", 0, 0.6, 1.25, 2.5, 0.8, storeys=[1, 2, 3], repeat={"count": 25, "pitch": 1.4}, **g))
op.append(win("J", "S", 0, 0.6, 1.25, 2.5, 0.8, repeat={"count": 11, "pitch": 1.4}, **g))
op.append(win("J", "S", 0, 21.0, 1.25, 2.5, 0.8, repeat={"count": 10, "pitch": 1.4}, **g))
op.append(door("J", "S", 16.9, 2.6, 2.8, door_type="full_glass", panel="alu_anthracite", frame="alu_anthracite"))
op.append(win("J", "E", 0, 3.0, 1.25, 2.5, 0.8, storeys=[0, 1, 2, 3], repeat={"count": 3, "pitch": 4.0}, **g))
op.append(win("J", "N", 0, 0.6, 1.25, 2.5, 0.8, storeys=[0, 1, 2, 3], repeat={"count": 25, "pitch": 1.4}, **g))
# K Wohnblock
w2 = dict(frame="paint_white", sashes=2)
op.append(win("K", "S", 0, 1.5, 1.4, 1.4, 0.9, storeys=[0, 1, 2, 3, 4], repeat={"count": 5, "pitch": 5.5}, **w2))
op.append(door("K", "S", 14.3, 1.6, 2.4, door_type="full_glass", panel="alu_anthracite", frame="alu_anthracite"))
op.append(win("K", "N", 0, 1.5, 1.2, 1.2, 1.0, storeys=[0, 1, 2, 3, 4], repeat={"count": 7, "pitch": 4.0}, **w2))
op.append(win("K", "E", 0, 5.0, 1.0, 1.4, 1.0, storeys=[0, 1, 2, 3, 4], **w2))
# L Halle
op.append(door("L", "S", 4.0, 4.0, 4.2, door_type="sectional", panel="paint_white", frame="paint_white", repeat={"count": 3, "pitch": 7.0}))
op.append(door("L", "E", 3.0, 1.1, 2.1, door_type="plank", panel="paint_grey", frame="paint_grey") if False else door("L", "E", 3.0, 1.1, 2.2, door_type="panel", panel="paint_black", frame="paint_black"))
op.append(win("L", "S", 0, 1.0, 1.5, 0.9, 5.0, window_type="fixed", frame="alu_anthracite", repeat={"count": 8, "pitch": 5.0}))
# M Schulpavillon: Fensterbaender
wb = dict(window_type="fixed", frame="alu_anthracite")
op.append(win("M", "S", 0, 1.0, 1.4, 2.2, 0.8, storeys=[0, 1], repeat={"count": 8, "pitch": 2.9}, **wb))
op.append(door("M", "S", 11.2, 1.3, 2.4, door_type="full_glass", panel="alu_anthracite", frame="alu_anthracite", storey=0) | {"storey": 0})
op.append(win("M", "N", 0, 1.0, 1.4, 2.2, 0.8, storeys=[0, 1], repeat={"count": 8, "pitch": 2.9}, **wb))
# N Solarhaus
op.append(win("N", "S", 0, 1.0, 1.2, 1.4, 0.9, frame="paint_white", sashes=2, storeys=[0, 1]))
op.append(door("N", "S", 3.4, 2.4, 2.3, door_type="french", panel="paint_white", frame="paint_white"))
op.append(win("N", "S", 0, 7.0, 1.2, 1.4, 0.9, frame="paint_white", sashes=2, storeys=[0, 1]))
op.append(door("N", "N", 4.5, 1.1, 2.2, door_type="panel", panel="paint_green_dark", frame="paint_white"))
op.append(win("N", "E", 0, 3.0, 1.0, 1.3, 0.9, frame="paint_white", storeys=[0, 1]))
op.append(door("P", "S", 14.0, 4.0, 3.0, door_type="full_glass", panel="alu_anthracite", frame="alu_anthracite"))
op.append(win("P", "S", 0, 2.0, 9.0, 3.0, 0.4, window_type="fixed", frame="alu_anthracite"))
op.append(win("P", "S", 0, 21.0, 9.0, 3.0, 0.4, window_type="fixed", frame="alu_anthracite"))
op.append(win("Q", "S", 0, 2.0, 1.2, 4.2, 1.5, top="pointed_arch", bars={"cols": 2, "rows": 3}, frame="paint_white", repeat={"count": 4, "pitch": 4.5}))
op.append(door("Q", "S", 9.4, 1.6, 3.2, top="pointed_arch", door_type="double", panel="timber_dark", frame="timber_dark"))
comps = [
    {"type": "canopy", "volume": "P", "side": "S", "u": 16.0, "width": 9.0, "projection": 3.5, "z": 3.6, "kind": "flat", "support": "posts", "material": "metal_panel_anthracite"},
    {"type": "pylon", "x": 192.0, "y": -12.0, "height": 9.0},
    {"type": "parking", "x": 198.0, "y": -12.0, "width": 30.0, "depth": 5.0, "spaces": 11},
    {"type": "ramp", "volume": "P", "side": "S", "u": 4.0, "width": 2.0, "length": 5.0, "height": 0.2},
    {"type": "buttress", "volume": "Q", "side": "S", "u": 4.5, "count": 4, "pitch": 4.5, "width": 0.8, "projection": 1.0},
    {"type": "tower", "volume": "Q", "x": 17.0, "y": 5.0, "radius": 2.0, "z0": 7.0, "height": 14.0, "kind": "cone", "sides": 8} if False else {"type": "steps", "volume": "Q", "side": "S", "u": 10.2, "width": 2.4, "count": 3},
    {"type": "chimney", "volume": "Q", "x": 3.0, "y": 5.0, "height": 1.0},
    {"type": "loggia", "volume": "K", "side": "S", "u": 24.0, "width": 3.0, "storey": 2, "railing": "glass", "ceiling": False},
    {"type": "loggia", "volume": "K", "side": "S", "u": 24.0, "width": 3.0, "storey": 3, "railing": "solid"},
    # J
    {"type": "canopy", "volume": "J", "side": "S", "u": 18.2, "width": 5.0, "projection": 2.2, "z": 3.1, "kind": "flat", "support": "posts", "material": "alu_anthracite"},
    {"type": "cornice", "volume": "J", "side": "all", "profile": "simple", "height": 0.3, "projection": 0.12, "material": "metal_panel_anthracite"},
    {"type": "technical_box", "volume": "J", "x": 6.0, "y": 4.0, "width": 5.0, "depth": 3.5, "height": 2.4},
    {"type": "technical_box", "volume": "J", "x": 26.0, "y": 5.0, "width": 2.4, "depth": 2.4, "height": 3.2, "material": "plaster_grey_light"},
    {"type": "solar", "volume": "J", "mode": "flat", "x": 13.0, "y": 2.0, "cols": 8, "rows": 3, "tilt": 12},
    {"type": "ramp", "volume": "J", "side": "S", "u": 12.0, "width": 1.6, "length": 6.0, "height": 0.35},
    {"type": "sign", "volume": "J", "side": "S", "u": 29.0, "z": 3.4},
    # K
    {"type": "steps", "volume": "K", "side": "S", "u": 15.1, "width": 2.4, "count": 2},
    {"type": "canopy", "volume": "K", "side": "S", "u": 15.1, "width": 3.0, "projection": 1.6, "z": 2.6, "kind": "flat", "support": "none", "material": "metal_panel_anthracite"},
    {"type": "cornice", "volume": "K", "side": "all", "profile": "simple", "height": 0.3, "projection": 0.1, "material": "plaster_white"},
    {"type": "solar", "volume": "K", "mode": "flat", "x": 2.0, "y": 2.0, "cols": 10, "rows": 2, "tilt": 12},
    {"type": "technical_box", "volume": "K", "x": 20.0, "y": 8.0, "width": 3.0, "depth": 2.2, "height": 2.4},
    {"type": "stair_ext", "volume": "K", "side": "E", "u": 1.0, "z0": 0.0, "z1": 5.8, "width": 1.1},
    # L
    {"type": "ramp", "volume": "L", "side": "S", "u": 10.0, "width": 4.0, "length": 8.0, "height": 0.9, "railing": "none"},
    {"type": "canopy", "volume": "L", "side": "E", "u": 3.6, "width": 2.4, "projection": 1.6, "z": 2.6, "kind": "shed", "support": "brackets", "material": "steel_black"},
    {"type": "downpipe", "volume": "L", "side": "S", "u": 0.2, "z1": 7.0},
    {"type": "downpipe", "volume": "L", "side": "S", "u": 39.8, "z1": 7.0},
    {"type": "carport", "volume": "L", "side": "W", "u": 10.0, "width": 6.0, "projection": 5.5, "kind": "shed", "material": "wood_larch"},
    # M
    {"type": "terrace", "volume": "M", "side": "S", "u": 12.0, "width": 8.0, "depth": 3.0, "railing": "glass", "railing_sides": "front,left,right"},
    {"type": "canopy", "volume": "M", "side": "S", "u": 11.85, "width": 2.4, "projection": 2.4, "z": 3.1, "kind": "flat", "support": "posts", "material": "steel_black"},
    {"type": "carport", "volume": "M", "side": "E", "u": 5.5, "width": 5.0, "projection": 5.5, "kind": "flat", "material": "steel_black"},
    {"type": "retaining_wall", "x0": 130.0, "y0": -14.0, "x1": 160.0, "y1": -14.0, "height": 0.9, "thickness": 0.3},
    {"type": "cornice", "volume": "M", "side": "all", "profile": "simple", "height": 0.3, "projection": 0.12, "material": "metal_panel_anthracite"},
    {"type": "lamp", "volume": "M", "side": "S", "u": 4.0, "z": 3.0} if False else {"type": "downpipe", "volume": "M", "side": "S", "u": 0.2, "z1": 7.0},
    # N
    {"type": "solar", "volume": "N", "mode": "pitched", "slope": "S", "u": 1.5, "up": 0.8, "cols": 6, "rows": 2},
    {"type": "terrace", "volume": "N", "side": "S", "u": 4.6, "width": 4.4, "depth": 3.2, "railing": "bars", "railing_height": 1.0, "railing_sides": "front,left,right"},
    {"type": "chimney", "volume": "N", "x": 8.5, "y": 4.5, "height": 0.8},
    {"type": "gutter", "volume": "N"}, {"type": "bargeboard", "volume": "N"},
    {"type": "downpipe", "volume": "N", "side": "S", "u": 0.15},
    {"type": "carport", "volume": "N", "side": "E", "u": 6.2, "width": 3.0, "projection": 5.5, "kind": "flat", "material": "wood_larch"},
    {"type": "retaining_wall", "x0": 166.0, "y0": -9.0, "x1": 177.0, "y1": -9.0, "height": 0.8, "thickness": 0.3},
    {"type": "fence", "points": [[164.0, -3.0], [164.0, -12.0], [180.0, -12.0], [180.0, -3.0]], "kind": "picket", "height": 1.0, "material": "wood_larch"},
]
balconies = [{"volume": "K", "side": "N", "level": 2.9 * s, "offset": off, "width": 2.8, "depth": 1.6, "thickness": 0.2,
              "railing": {"type": t, "height": 1.05, "sides": ["front", "left", "right"], "material": "steel_black"}}
             for s, t in ((1, "glass"), (2, "glass"), (3, "bars"), (4, "solid")) for off in (3.0, 13.0, 23.0)]
levels = [{"name": "EG", "elevation": 0.0}, {"name": "OG1", "elevation": 3.5}, {"name": "OG2", "elevation": 7.0}, {"name": "OG3", "elevation": 10.5}]
cams = [{"name": "front", "position": [90.0, -140.0, 1.7], "target": [90.0, 0.0, 5.0], "lens_mm": 24}]
for nm, cx, w in (("J", 18.0, 36), ("K", 60.0, 30), ("L", 104.0, 40), ("M", 145.0, 24), ("N", 171.0, 11), ("P", 213.0, 36), ("Q", 255.0, 20)):
    cams.append({"name": f"cam_{nm}", "position": [cx + w * 0.35, -w * 1.1 - 12.0, 1.7], "target": [cx, 0.0, 4.5], "lens_mm": 24})
cams.append({"name": "balkone_K", "position": [60.0, 30.0, 1.7], "target": [60.0, 12.0, 7.0], "lens_mm": 24})
spec = {
    "spec_version": 1, "name": "Moderne Typen Abnahme", "description": "Fuenf moderne Gebaeudetypen mit Stufe-3-Bauteilen.", "assumptions": ["Reine Abnahmespec, keine reale Vorlage."],
    "levels": levels, "storey_height": 3.0, "slab_thickness": 0.25,
    "defaults": {"wall_thickness": 0.3, "parapet_height": 0.1,
                 "window": {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.14, "glass": "glass_clear", "frame": "paint_white", "sill_board": True}},
    "volumes": vols, "openings": op, "components": comps, "balconies": balconies, "site": {"ground_extent": [-15, -60, 275, 40]},
    "render": {"sun": {"azimuth_deg": 215.0, "elevation_deg": 38.0}, "cameras": cams},
}
OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("geschrieben", OUT, len(op), "Oeffnungen", len(comps), "Bauteile")
