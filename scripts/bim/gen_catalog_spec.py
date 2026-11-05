"""Erzeugt specs/bauteilkatalog.json: vier Beispielhaeuser, die moeglichst viele Katalogbauteile zeigen
(Abnahme-/Regressionsspec fuer die Bibliothek). Aufruf: python tools/gen_catalog_spec.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "specs" / "bauteilkatalog.json"


def win(vol, side, st, off, w, h, sill, **kw):
    return {"volume": vol, "side": side, "storey": st, "offset": off, "width": w, "height": h, "sill": sill, "kind": "window", **kw}


def door(vol, side, off, w, h, **kw):
    return {"volume": vol, "side": side, "storey": 0, "offset": off, "width": w, "height": h, "sill": 0.0, "kind": "door", **kw}


stone = {"material": "stone_ashlar_light", "width": 0.14}
vols = [
    {"id": "A", "name": "Stadtvilla Walmdach", "origin": [0.0, 0.0], "size": [9.0, 8.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.36,
     "facade": "plaster_cream", "storey_height": 3.0, "roof": {"type": "hip", "pitch_deg": 33, "overhang": 0.5, "material": "roof_tile_brown"}},
    {"id": "B", "name": "Fachwerkhaus Andreaskreuz", "origin": [12.0, 0.0], "size": [8.0, 9.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.3,
     "facade": "plaster_timber_infill", "storey_height": 2.9,
     "roof": {"type": "gable", "ridge": "y", "pitch_deg": 50, "overhang": 0.5, "material": "roof_slate"},
     "facade_detail": {"timber_frame": {"spacing": 1.3, "post_width": 0.15, "depth": 0.07, "pattern": "st_andrew", "material": "timber_oak_aged"},
                       "plinth": {"height": 0.6, "material": "stone_field"}}},
    {"id": "C", "name": "Klassizistisches Haus", "origin": [24.0, 0.0], "size": [10.0, 8.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.4,
     "facade": "plaster_yellow", "storey_height": 3.4},
    {"id": "D", "name": "Pultdach-Haeuschen", "origin": [38.0, 0.0], "size": [6.0, 6.0], "base_z": 0.0, "storeys": 1, "wall_thickness": 0.3,
     "facade": "plaster_white", "storey_height": 3.0,
     "roof": {"type": "shed", "pitch_deg": 12, "fall_to": "S", "overhang": 0.35, "material": "roof_zinc_standing"}},
]

op = []
# --- A
sh = {"material": "paint_green_dark", "state": "open", "style": "louvre"}
op += [win("A", "S", 0, 0.9, 1.2, 1.9, 0.7, top="segment_arch", bars={"cols": 2, "rows": 3}, surround={**stone, "keystone": True}, frame="paint_white", shutters=sh),
       door("A", "S", 3.6, 1.8, 2.6, top="round_arch", door_type="double", panel="paint_blue_dark", frame="paint_white", surround={**stone, "keystone": True}),
       win("A", "S", 0, 6.9, 1.2, 1.9, 0.7, top="segment_arch", bars={"cols": 2, "rows": 3}, surround={**stone, "keystone": True}, frame="paint_white", shutters=sh)]
for off in (0.9, 3.9, 6.9):
    op.append(win("A", "S", 1, off, 1.2, 1.5, 0.9, bars={"cols": 2, "rows": 3}, frame="paint_white", surround={"material": "stone_ashlar_light", "width": 0.12, "lintel": "keystone"}, shutters={**sh, "style": "panel"}, flower_box=True))
op += [win("A", "E", 0, 2.0, 1.2, 1.5, 0.9, frame="paint_white", sashes=2), win("A", "E", 1, 2.0, 1.2, 1.5, 0.9, frame="paint_white", sashes=2),
       win("A", "N", 0, 3.0, 1.2, 1.5, 0.9, frame="paint_white"), win("A", "N", 1, 3.0, 1.2, 1.5, 0.9, frame="paint_white")]
# --- B
shp = {"material": "paint_red_sweden", "state": "open", "style": "panel"}
op += [win("B", "S", 0, 0.9, 1.3, 1.3, 0.9, bars={"cols": 3, "rows": 2}, frame="paint_brown", shutters=shp, flower_box=True),
       door("B", "S", 3.2, 1.3, 2.2, door_type="plank", panel="paint_brown", frame="paint_brown", transom=0.78, surround={"material": "timber_oak_aged", "width": 0.12, "lintel": "flat"}),
       win("B", "S", 0, 5.8, 1.3, 1.3, 0.9, bars={"cols": 3, "rows": 2}, frame="paint_brown", shutters=shp, flower_box=True),
       win("B", "S", 1, 0.9, 1.3, 1.3, 0.9, bars={"cols": 3, "rows": 2}, frame="paint_brown", shutters=shp, flower_box=True),
       win("B", "S", 1, 3.35, 1.3, 1.3, 0.9, bars={"cols": 3, "rows": 2}, frame="paint_brown", shutters=shp, flower_box=True),
       win("B", "S", 1, 5.8, 1.3, 1.3, 0.9, bars={"cols": 3, "rows": 2}, frame="paint_brown", shutters=shp, flower_box=True),
       win("B", "E", 0, 2.0, 1.2, 1.3, 0.9, frame="paint_brown"), win("B", "E", 1, 2.0, 1.2, 1.3, 0.9, frame="paint_brown")]
# --- C
sp = {"material": "stone_ashlar_light", "width": 0.16}
op += [win("C", "S", 0, 1.0, 1.1, 2.4, 0.4, top="round_arch", sashes=2, bars={"cols": 2, "rows": 4}, frame="paint_white", surround={**sp, "keystone": True}),
       door("C", "S", 4.2, 1.6, 2.7, top="round_arch", door_type="glazed", panel="paint_green_dark", frame="paint_white", surround={**sp, "keystone": True}),
       win("C", "S", 0, 7.9, 1.1, 2.4, 0.4, top="round_arch", sashes=2, bars={"cols": 2, "rows": 4}, frame="paint_white", surround={**sp, "keystone": True})]
for off, lt in ((1.0, "pediment"), (4.4, "segment_pediment"), (7.9, "pediment")):
    op.append(win("C", "S", 1, off, 1.1, 1.9, 0.6, sashes=2, bars={"cols": 2, "rows": 3}, frame="paint_white", surround={**sp, "lintel": lt, "sill": True}))
op += [win("C", "E", 0, 2.0, 1.2, 2.0, 0.6, frame="paint_white"), win("C", "E", 1, 2.0, 1.2, 1.8, 0.6, frame="paint_white")]
# --- D
op += [door("D", "S", 0.9, 1.2, 2.4, top="round_arch", door_type="glazed", panel="paint_red_bright", frame="paint_white"),
       win("D", "S", 0, 3.3, 1.1, 2.3, 0.5, window_type="casement", top="pointed_arch", frame="paint_black", surround={"material": "stone_limestone", "width": 0.12}),
       win("D", "E", 0, 2.2, 1.0, 1.0, 1.5, window_type="oculus", frame="paint_black"),
       win("D", "W", 0, 2.2, 1.0, 1.0, 1.5, window_type="oculus", frame="paint_black")]

comps = [
    {"type": "cornice", "volume": "A", "side": "all", "profile": "stepped", "height": 0.4, "projection": 0.3},
    {"type": "quoins", "volume": "A", "material": "stone_ashlar_light", "width": 0.55, "course": 0.33},
    {"type": "cornice", "volume": "A", "side": "S", "z": 3.0, "height": 0.16, "projection": 0.06, "profile": "band"},
    {"type": "steps", "volume": "A", "side": "S", "u": 4.5, "width": 2.4, "count": 3},
    {"type": "lamp", "volume": "A", "side": "S", "u": 2.9, "z": 2.4},
    {"type": "lamp", "volume": "A", "side": "S", "u": 6.1, "z": 2.4},
    {"type": "chimney", "volume": "A", "x": 2.5, "y": 4.0, "width": 0.8, "depth": 0.8, "height": 0.9},
    {"type": "downpipe", "volume": "A", "side": "S", "u": 0.25},
    {"type": "downpipe", "volume": "A", "side": "S", "u": 8.75},
    {"type": "canopy", "volume": "B", "side": "S", "u": 3.85, "width": 2.4, "projection": 1.1, "z": 2.6, "kind": "gable", "support": "brackets", "material": "timber_oak_aged", "roof_material": "roof_slate"},
    {"type": "bracket", "volume": "B", "side": "S", "z": 2.9, "count": 6, "spacing": 1.3, "u": 4.0, "size": 0.4, "projection": 0.3, "material": "timber_oak_aged"},
    {"type": "sign", "volume": "B", "side": "S", "u": 7.6, "z": 3.4},
    {"type": "lamp", "volume": "B", "side": "S", "u": 2.2, "z": 2.5},
    {"type": "steps", "volume": "B", "side": "S", "u": 3.85, "width": 1.6, "count": 2, "material": "stone_field"},
    {"type": "chimney", "volume": "B", "x": 4.0, "y": 7.2, "height": 0.9, "material": "brick_red"},
    {"type": "cornice", "volume": "C", "side": "all", "profile": "simple", "height": 0.6, "projection": 0.45},
    {"type": "pilaster", "volume": "C", "side": "S", "u": 5.0, "count": 2, "spacing": 9.4, "width": 0.5, "z1": 6.4},
    {"type": "pilaster", "volume": "C", "side": "S", "u": 4.975, "count": 2, "spacing": 3.45, "width": 0.3, "z0": 3.4, "z1": 6.4, "capital": True},
    {"type": "cornice", "volume": "C", "side": "S", "z": 3.3, "height": 0.2, "projection": 0.08, "profile": "band"},
    {"type": "column", "volume": "C", "side": "S", "u": 5.0, "count": 4, "spacing": 2.0, "distance": 2.3, "radius": 0.2, "z1": 3.6},
    {"type": "canopy", "volume": "C", "side": "S", "u": 5.0, "width": 7.4, "projection": 2.6, "z": 3.6, "kind": "flat", "support": "none", "material": "stone_ashlar_light", "thickness": 0.3},
    {"type": "steps", "volume": "C", "side": "S", "u": 5.0, "width": 5.0, "count": 4, "tread": 0.4, "z0": 0.0, "material": "stone_ashlar_light"},
    {"type": "downpipe", "volume": "C", "side": "S", "u": 9.7, "z1": 6.6},
    {"type": "fence", "points": [[36.0, -3.0], [36.0, -9.0], [44.0, -9.0], [44.0, -3.0]], "kind": "picket", "height": 1.0, "material": "paint_white"},
    {"type": "fence", "points": [[-3.0, -3.0], [-3.0, -9.0], [11.0, -9.0]], "kind": "wall_cap", "height": 0.9, "material": "stone_field"},
    {"type": "bracket", "volume": "D", "side": "S", "z": 2.85, "count": 3, "spacing": 1.5, "u": 3.0, "material": "wood_cedar"},
]

levels = [{"name": "EG", "elevation": 0.0}, {"name": "OG1", "elevation": 3.0}, {"name": "Dach", "elevation": 6.0}]
cams = [{"name": "front", "position": [22.0, -36.0, 1.7], "target": [22.0, 0.0, 4.2], "lens_mm": 20}]
for nm, cx in (("A", 4.5), ("B", 16.0), ("C", 29.0), ("D", 41.0)):
    cams.append({"name": f"cam_{nm}", "position": [cx + 7.0, -15.0, 1.7], "target": [cx, 0.0, 3.6], "lens_mm": 28})
spec = {
    "spec_version": 1, "name": "Bauteilkatalog Abnahme", "description": "Vier Haeuser, die Katalogbauteile zeigen (Fenster-/Tuertypen, Gewaende, Laeden, Gesimse, Dachformen, Fachwerkmuster).",
    "assumptions": ["Reine Abnahmespec, keine reale Vorlage."], "levels": levels, "storey_height": 3.0, "slab_thickness": 0.25,
    "defaults": {"wall_thickness": 0.3, "parapet_height": 0.1,
                 "window": {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.14, "glass": "glass_clear", "frame": "paint_white", "sill_board": True}},
    "volumes": vols, "openings": op, "components": comps,
    "site": {"ground_extent": [-12, -30, 56, 24]},
    "render": {"sun": {"azimuth_deg": 215.0, "elevation_deg": 38.0}, "cameras": cams},
}
OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("geschrieben", OUT, len(op), "Oeffnungen", len(comps), "Bauteile")
