"""Erzeugt specs/gebaeudetypen.json: fuenf unterschiedliche Gebaeudetypen aus den Stufe-2-Bauteilen
(Turmvilla, Mansard-Stadthaus, Scheune, Laden mit Arkade, Landhaus). Aufruf: python tools/gen_catalog_spec2.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "specs" / "gebaeudetypen.json"


def win(vol, side, st, off, w, h, sill, **kw):
    return {"volume": vol, "side": side, "storey": st, "offset": off, "width": w, "height": h, "sill": sill, "kind": "window", **kw}


def door(vol, side, off, w, h, **kw):
    return {"volume": vol, "side": side, "storey": 0, "offset": off, "width": w, "height": h, "sill": 0.0, "kind": "door", **kw}


stone = {"material": "stone_ashlar_light", "width": 0.14}
vols = [
    {"id": "E", "name": "Turmvilla", "origin": [0.0, 0.0], "size": [12.0, 9.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.4,
     "facade": "plaster_yellow", "storey_height": 3.2, "roof": {"type": "hip", "pitch_deg": 30, "overhang": 0.5, "material": "roof_tile_anthracite"}},
    {"id": "F", "name": "Mansard-Stadthaus", "origin": [17.0, 0.0], "size": [10.0, 10.0], "base_z": 0.0, "storeys": 3, "wall_thickness": 0.4,
     "facade": "stone_limestone", "storey_height": 3.1,
     "roof": {"type": "mansard", "pitch_deg": 15, "lower_pitch_deg": 72, "lower_height": 2.4, "overhang": 0.25, "material": "roof_slate"}},
    {"id": "G", "name": "Scheune", "origin": [32.0, 0.0], "size": [12.0, 8.0], "base_z": 0.0, "storeys": 1, "wall_thickness": 0.3,
     "facade": "paint_red_sweden", "storey_height": 4.2,
     "roof": {"type": "gambrel", "ridge": "x", "pitch_deg": 22, "lower_pitch_deg": 65, "lower_run": 0.4, "overhang": 0.4, "material": "roof_wood_shingle"}},
    {"id": "H", "name": "Laden mit Arkade", "origin": [49.0, 0.0], "size": [9.0, 8.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.4,
     "facade": "brick_orange", "storey_height": 4.4},
    {"id": "I", "name": "Landhaus", "origin": [63.0, 0.0], "size": [10.0, 8.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.36,
     "facade": "brick_brown", "storey_height": 2.8,
     "roof": {"type": "gable", "ridge": "x", "pitch_deg": 40, "overhang": 0.6, "material": "roof_tile_red"}},
]
op = []
# E Turmvilla
op += [win("E", "S", 0, 3.2, 2.6, 1.9, 0.8, sashes=3, frame="paint_white"), win("E", "S", 1, 3.2, 2.6, 1.9, 0.6, sashes=3, frame="paint_white"),
       door("E", "S", 8.2, 1.5, 2.6, top="round_arch", door_type="glazed", panel="paint_green_dark", frame="paint_white", surround={**stone, "keystone": True}),
       win("E", "S", 1, 8.4, 1.1, 1.7, 0.7, top="segment_arch", bars={"cols": 2, "rows": 3}, frame="paint_white", surround={**stone, "keystone": True}),
       win("E", "S", 0, 10.4, 0.9, 1.7, 0.8, frame="paint_white", surround=stone), win("E", "S", 1, 10.4, 0.9, 1.7, 0.7, frame="paint_white", surround=stone),
       win("E", "E", 0, 3.0, 1.2, 1.7, 0.8, frame="paint_white"), win("E", "E", 1, 3.0, 1.2, 1.7, 0.7, frame="paint_white"),
       win("E", "N", 0, 4.0, 1.2, 1.7, 0.8, frame="paint_white"), win("E", "N", 1, 4.0, 1.2, 1.7, 0.7, frame="paint_white")]
# F Mansard-Stadthaus
for st in (0, 1, 2):
    for off in (1.0, 4.4, 7.8):
        if st == 0 and off == 4.4:
            op.append(door("F", "S", 4.2, 1.6, 2.6, top="round_arch", door_type="double", panel="paint_black", frame="paint_black", surround={**stone, "keystone": True}))
            continue
        kw = {"frame": "paint_white", "sashes": 2, "bars": {"cols": 2, "rows": 3}}
        if st == 0:
            op.append(win("F", "S", 0, off, 1.2, 2.2, 0.5, top="round_arch", surround={**stone, "keystone": True}, **kw))
        elif st == 1:
            op.append(win("F", "S", 1, off, 1.2, 2.3, 0.3, surround={**stone, "lintel": "segment_pediment" if off == 4.4 else "pediment", "sill": True}, **kw))
        else:
            op.append(win("F", "S", 2, off, 1.1, 1.9, 0.6, surround={**stone, "lintel": "flat"}, **kw))
op += [win("F", "E", 0, 4.0, 1.2, 2.0, 0.6, frame="paint_white"), win("F", "E", 1, 4.0, 1.2, 2.0, 0.6, frame="paint_white"), win("F", "E", 2, 4.0, 1.2, 1.8, 0.6, frame="paint_white")]
# G Scheune
op += [door("G", "S", 3.8, 4.0, 3.2, door_type="sectional", panel="paint_white", frame="paint_white"),
       door("G", "S", 9.2, 1.1, 2.1, door_type="plank", panel="paint_white", frame="paint_white"),
       win("G", "S", 0, 1.0, 1.0, 1.0, 1.4, window_type="fixed", bars={"cols": 2, "rows": 2}, frame="paint_white"),
       win("G", "N", 0, 3.0, 1.0, 1.0, 1.4, window_type="fixed", bars={"cols": 2, "rows": 2}, frame="paint_white"),
       win("G", "N", 0, 8.0, 1.0, 1.0, 1.4, window_type="fixed", bars={"cols": 2, "rows": 2}, frame="paint_white")]
# H Laden mit Arkade
op += [win("H", "S", 0, 1.2, 1.6, 2.6, 0.3, frame="paint_black", sashes=1), win("H", "S", 0, 3.7, 1.6, 2.6, 0.3, frame="paint_black"),
       door("H", "S", 6.2, 1.4, 2.6, door_type="full_glass", panel="paint_black", frame="paint_black")]
for off in (1.0, 3.6, 6.2):
    op.append(win("H", "S", 1, off, 1.4, 1.7, 0.8, frame="paint_white", bars={"cols": 2, "rows": 3}, shutters={"material": "paint_green_dark", "state": "open", "style": "louvre"}, flower_box=True))
op += [win("H", "E", 0, 2.5, 2.0, 2.2, 0.5, frame="paint_black"), win("H", "E", 1, 2.5, 1.2, 1.7, 0.8, frame="paint_white")]
# I Landhaus
op += [win("I", "S", 0, 1.2, 1.3, 1.5, 0.9, frame="paint_white", bars={"cols": 3, "rows": 2}, shutters={"material": "paint_blue_light", "state": "open", "style": "panel"}),
       door("I", "S", 4.2, 1.4, 2.3, door_type="panel", panel="paint_blue_dark", frame="paint_white", transom=0.75),
       win("I", "S", 0, 7.5, 1.3, 1.5, 0.9, frame="paint_white", bars={"cols": 3, "rows": 2}, shutters={"material": "paint_blue_light", "state": "open", "style": "panel"}),
       win("I", "S", 1, 1.2, 1.3, 1.4, 0.8, frame="paint_white", bars={"cols": 3, "rows": 2}), win("I", "S", 1, 4.35, 1.1, 1.4, 0.8, frame="paint_white", bars={"cols": 3, "rows": 2}),
       win("I", "S", 1, 7.5, 1.3, 1.4, 0.8, frame="paint_white", bars={"cols": 3, "rows": 2})]

comps = [
    {"type": "tower", "volume": "E", "x": 0.2, "y": 0.2, "radius": 2.0, "z1": 7.6, "roof": "onion", "roof_height": 4.2, "roof_overhang": 0.3,
     "material": "plaster_yellow", "roof_material": "copper_patina", "band": True, "band_material": "stone_ashlar_light", "finial": True, "slits": 3, "slit_angle": 250, "slit_z": 4.2},
    {"type": "bay", "volume": "E", "side": "S", "u": 4.5, "width": 3.4, "projection": 0.8, "z0": 0.0, "z1": 6.4, "kind": "canted", "frame": "paint_white", "roof_material": "copper_patina"},
    {"type": "rustication", "volume": "E", "side": "S", "z0": 0.0, "z1": 3.2, "course": 0.5},
    {"type": "dentil", "volume": "E", "side": "all"},
    {"type": "cornice", "volume": "E", "side": "all", "profile": "simple", "height": 0.4, "projection": 0.3},
    {"type": "gutter", "volume": "E"},
    {"type": "chimney", "volume": "E", "x": 9.0, "y": 4.5, "height": 1.0},
    {"type": "steps", "volume": "E", "side": "S", "u": 8.95, "width": 2.0, "count": 3},
    {"type": "cornice", "volume": "F", "side": "all", "profile": "stepped", "height": 0.5, "projection": 0.4},
    {"type": "rustication", "volume": "F", "side": "S", "z0": 0.0, "z1": 3.1, "course": 0.55},
    {"type": "cornice", "volume": "F", "side": "S", "z": 3.1, "height": 0.2, "projection": 0.07, "profile": "band"},
    {"type": "cornice", "volume": "F", "side": "S", "z": 6.2, "height": 0.2, "projection": 0.07, "profile": "band"},
    {"type": "dentil", "volume": "F", "side": "S", "z": 8.7},
    {"type": "gutter", "volume": "F"},
    {"type": "chimney", "volume": "F", "x": 2.0, "y": 5.0, "width": 0.9, "depth": 1.4, "height": 1.0},
    {"type": "chimney", "volume": "F", "x": 8.0, "y": 5.0, "width": 0.9, "depth": 1.4, "height": 1.0},
    {"type": "lamp", "volume": "F", "side": "S", "u": 3.0, "z": 2.4}, {"type": "lamp", "volume": "F", "side": "S", "u": 7.0, "z": 2.4},
    {"type": "steps", "volume": "F", "side": "S", "u": 5.0, "width": 2.4, "count": 3, "material": "stone_limestone"},
    {"type": "gutter", "volume": "G", "side": "S"},
    {"type": "downpipe", "volume": "G", "side": "S", "u": 0.3},
    {"type": "lamp", "volume": "G", "side": "S", "u": 8.4, "z": 2.5},
    {"type": "arcade", "volume": "H", "side": "S", "count": 3, "span": 2.0, "pier": 0.5, "spring_z": 2.9, "z1": 4.25, "material": "stone_limestone", "depth": 0.6},
    {"type": "awning", "volume": "H", "side": "E", "u": 3.5, "width": 2.6, "z": 2.9, "projection": 1.5, "material": "paint_green_dark", "material2": "paint_white"},
    {"type": "cornice", "volume": "H", "side": "all", "profile": "simple", "height": 0.45, "projection": 0.3, "material": "stone_limestone"},
    {"type": "sign", "volume": "H", "side": "E", "u": 7.0, "z": 3.9},
    {"type": "gutter", "volume": "I"}, {"type": "bargeboard", "volume": "I"},
    {"type": "skylight", "volume": "I", "slope": "S", "u": 2.0}, {"type": "skylight", "volume": "I", "slope": "S", "u": 6.0},
    {"type": "chimney", "volume": "I", "x": 5.0, "y": 4.0, "height": 0.9},
    {"type": "canopy", "volume": "I", "side": "S", "u": 4.9, "width": 2.4, "projection": 1.2, "z": 2.6, "kind": "gable", "support": "posts", "material": "wood_oak", "roof_material": "roof_tile_red"},
    {"type": "downpipe", "volume": "I", "side": "S", "u": 0.2},
    {"type": "fence", "points": [[61.0, -3.0], [61.0, -10.0], [75.0, -10.0], [75.0, -3.0]], "kind": "post_rail", "height": 1.1, "material": "wood_weathered"},
]
levels = [{"name": "EG", "elevation": 0.0}, {"name": "OG1", "elevation": 3.1}, {"name": "OG2", "elevation": 6.2}, {"name": "Dach", "elevation": 9.3}]
cams = [{"name": "front", "position": [37.0, -66.0, 1.7], "target": [37.0, 0.0, 4.5], "lens_mm": 20}]
for nm, cx, w in (("E", 6.0, 12), ("F", 22.0, 10), ("G", 38.0, 12), ("H", 53.5, 9), ("I", 68.0, 10)):
    cams.append({"name": f"cam_{nm}", "position": [cx + 8.0, -17.0, 1.7], "target": [cx, 0.0, 4.2], "lens_mm": 28})
spec = {
    "spec_version": 1, "name": "Gebaeudetypen Abnahme", "description": "Fuenf Gebaeudetypen mit Stufe-2-Bauteilen.", "assumptions": ["Reine Abnahmespec, keine reale Vorlage."],
    "levels": levels, "storey_height": 3.0, "slab_thickness": 0.25,
    "defaults": {"wall_thickness": 0.3, "parapet_height": 0.1,
                 "window": {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.14, "glass": "glass_clear", "frame": "paint_white", "sill_board": True}},
    "volumes": vols, "openings": op, "components": comps, "site": {"ground_extent": [-15, -40, 90, 25]},
    "render": {"sun": {"azimuth_deg": 215.0, "elevation_deg": 38.0}, "cameras": cams},
}
OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("geschrieben", OUT, len(op), "Oeffnungen", len(comps), "Bauteile")
