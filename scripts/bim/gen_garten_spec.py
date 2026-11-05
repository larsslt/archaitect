"""Erzeugt specs/garten.json: Stadtvilla mit Gartenausstattung (Weg, Hecken, Baeume, Beet, Pool, Bank, Gartenset, Leuchten).
Aufruf: python tools/gen_garten_spec.py"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "specs" / "garten.json"


def win(st, side, off, w=1.3, h=1.5, sill=0.9, **kw):
    return {"volume": "V", "side": side, "storey": st, "offset": off, "width": w, "height": h, "sill": sill, "kind": "window", "frame": "paint_white", **kw}


vol = {"id": "V", "name": "Stadtvilla", "origin": [0.0, 0.0], "size": [12.0, 9.0], "base_z": 0.0, "storeys": 2, "wall_thickness": 0.38,
       "facade": "plaster_cream", "storey_height": 2.9, "roof": {"type": "hip", "pitch_deg": 28, "overhang": 0.5, "material": "roof_tile_anthracite"}}
op = [{"volume": "V", "side": "S", "storey": 0, "offset": 5.4, "width": 1.4, "height": 2.2, "sill": 0.0, "kind": "door", "door_type": "panel", "panel": "paint_green_dark", "frame": "paint_white"},
      win(0, "S", 1.6), win(0, "S", 9.0), win(1, "S", 1.6), win(1, "S", 5.5), win(1, "S", 9.0),
      win(0, "E", 3.5), win(1, "E", 3.5), win(0, "W", 3.5), win(1, "W", 3.5), win(0, "N", 2.0), win(1, "N", 2.0), win(0, "N", 8.5), win(1, "N", 8.5)]
comps = [
    {"type": "steps", "volume": "V", "side": "S", "u": 6.1, "width": 1.8, "count": 2},
    {"type": "canopy", "volume": "V", "side": "S", "u": 6.1, "width": 2.4, "projection": 1.3, "z": 2.6, "kind": "gable", "support": "posts", "material": "wood_oak", "roof_material": "roof_tile_anthracite"},
    {"type": "terrace", "volume": "V", "side": "E", "u": 4.5, "width": 4.0, "depth": 3.0, "railing": "none"},
    {"type": "path", "points": [[6.1, -17.0], [6.1, -7.0], [14.5, -7.0]], "width": 1.4, "material": "paving_flagstone"},
    {"type": "path", "points": [[6.1, -7.0], [6.1, -1.3]], "width": 1.4, "material": "paving_flagstone"} if False else {"type": "path", "points": [[6.1, -2.5], [6.1, -5.6]], "width": 1.4, "material": "paving_flagstone"},
    {"type": "hedge", "x0": -8.0, "y0": -20.0, "x1": 4.0, "y1": -20.0, "height": 1.5, "thickness": 0.8},
    {"type": "hedge", "x0": 8.2, "y0": -20.0, "x1": 24.0, "y1": -20.0, "height": 1.5, "thickness": 0.8},
    {"type": "hedge", "x0": -8.0, "y0": -20.0, "x1": -8.0, "y1": 12.0, "height": 1.8, "thickness": 0.9},
    {"type": "hedge", "x0": 24.0, "y0": -20.0, "x1": 24.0, "y1": 12.0, "height": 1.8, "thickness": 0.9},
    {"type": "tree", "x": -4.0, "y": 6.5, "height": 10.0, "crown_radius": 3.6},
    {"type": "tree", "x": 19.0, "y": 8.0, "height": 8.5, "crown_radius": 3.0},
    {"type": "tree", "x": -5.0, "y": -14.0, "height": 6.0, "crown_radius": 1.4, "kind": "conifer"},
    {"type": "tree", "x": 21.5, "y": -16.0, "height": 7.0, "crown_radius": 1.6, "kind": "conifer"},
    {"type": "flowerbed", "x": -3.0, "y": -9.0, "width": 4.5, "depth": 1.4},
    {"type": "flowerbed", "x": 8.0, "y": -3.2, "width": 3.2, "depth": 1.2, "flowers": "paint_blue_light,paint_white"},
    {"type": "shrub", "x": 4.3, "y": -1.2, "radius": 0.45, "height": 1.0, "pot": True},
    {"type": "shrub", "x": 7.9, "y": -1.2, "radius": 0.45, "height": 1.0, "pot": True},
    {"type": "shrub", "x": -6.5, "y": -3.0, "radius": 1.0, "height": 1.3},
    {"type": "shrub", "x": 22.0, "y": -4.0, "radius": 1.0, "height": 1.3},
    {"type": "pool", "x": 14.0, "y": -17.0, "width": 7.0, "depth": 4.0},
    {"type": "bench", "x": 15.0, "y": -4.5, "length": 1.8},
    {"type": "garden_set", "x": 15.5, "y": 1.6},
    {"type": "garden_light", "x": 4.6, "y": -16.0, "count": 5, "pitch": 3.0, "axis": "y"},
    {"type": "garden_light", "x": 9.4, "y": -4.2, "kind": "post", "height": 2.6},
    {"type": "gutter", "volume": "V"},
    {"type": "downpipe", "volume": "V", "side": "S", "u": 0.3},
]
spec = {
    "spec_version": 1, "name": "Garten Abnahme", "description": "Stadtvilla mit Gartenausstattung.", "assumptions": ["Reine Abnahmespec."],
    "levels": [{"name": "EG", "elevation": 0.0}, {"name": "OG", "elevation": 2.9}, {"name": "Dach", "elevation": 5.8}],
    "storey_height": 2.9, "slab_thickness": 0.25,
    "defaults": {"wall_thickness": 0.3, "parapet_height": 0.1, "window": {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.14, "glass": "glass_clear", "frame": "paint_white", "sill_board": True}},
    "volumes": [vol], "openings": op, "components": comps, "site": {"ground_extent": [-12, -26, 30, 18]},
    "render": {"sun": {"azimuth_deg": 215.0, "elevation_deg": 40.0, "strength": 3.0} if False else {"azimuth_deg": 215.0, "elevation_deg": 40.0},
               "grass_region": [-12.0, -26.0, 30.0, 16.0],
               "cameras": [{"name": "front", "position": [3.0, -38.0, 4.5], "target": [8.0, -6.0, 1.5], "lens_mm": 30},
                           {"name": "luft", "position": [-22.0, -36.0, 20.0], "target": [8.0, -6.0, 1.0], "lens_mm": 28},
                           {"name": "pool", "position": [8.0, -9.0, 1.7], "target": [17.0, -15.0, 0.6], "lens_mm": 30}]},
}
OUT.write_text(json.dumps(spec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("geschrieben", OUT)
