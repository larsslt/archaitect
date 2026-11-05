"""Kontaktbogen der Materialbibliothek: pro Gruppe ein Bild mit beschrifteten Mustern.

Aufruf: blender -b --factory-startup -P blender/gallery.py -- <ausgabeordner> [gruppen-praefix ...]
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(__file__))
import materials  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "out/gallery"
ONLY = argv[1:]
os.makedirs(OUT, exist_ok=True)

DATA = json.loads(materials.LIB_PATH.read_text(encoding="utf-8"))
DATA = {k: v for k, v in DATA.items() if not k.startswith("_")}
groups = {}
for k, v in DATA.items():
    groups.setdefault(v.get("group", "Render").split("/")[0], []).append(k)


def render_group(gname, keys):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    lib = {k: materials.BUILDERS[DATA[k]["shader"]["kind"]](k, DATA[k]["shader"]) for k in keys}
    cols = min(6, len(keys))
    rows = math.ceil(len(keys) / cols)
    pitch = 1.5
    for i, k in enumerate(keys):
        cx, cz = (i % cols) * pitch, -(i // cols) * pitch * 1.25
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, 0, cz))
        ob = bpy.context.object
        ob.scale = (1.2, 0.12, 1.0)
        ob.name = k
        ob.data.materials.append(lib[k])
        # Mauerwerks-/Fliesen-Verbaende projizieren ueber Objektkoordinaten: Skalierung in die Geometrie backen
        bpy.ops.object.transform_apply(scale=True)
        t = bpy.data.curves.new("t" + k, "FONT")
        t.body = k
        t.size = 0.1
        t.align_x = "CENTER"
        to = bpy.data.objects.new("t" + k, t)
        to.location = (cx, -0.08, cz - 0.62)
        to.rotation_euler = (math.radians(90), 0, 0)
        tm = bpy.data.materials.new("lbl")
        tm.use_nodes = True
        tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1)
        to.data.materials.append(tm)
        sc.collection.objects.link(to)
    # Licht: weicher Himmel + Sonne
    w = bpy.data.worlds.new("w")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.82, 0.92, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.45
    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 1.6
    so = bpy.data.objects.new("sun", sun)
    so.rotation_euler = (math.radians(55), 0, math.radians(-25))
    sc.collection.objects.link(so)
    cam = bpy.data.cameras.new("cam")
    cam.type = "ORTHO"
    W = cols * pitch
    H = rows * pitch * 1.25
    cam.ortho_scale = max(W, H * 16 / 9) + 0.6
    co = bpy.data.objects.new("cam", cam)
    co.location = ((cols - 1) * pitch / 2, -6, -(rows - 1) * pitch * 1.25 / 2 - 0.1)
    co.rotation_euler = (math.radians(90), 0, 0)
    sc.collection.objects.link(co)
    sc.camera = co
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 48
    sc.cycles.device = "CPU"
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 900
    sc.view_settings.view_transform = "Standard" if False else "Standard"  # if "Filmic" in [v.identifier for v in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Standard"
    sc.render.filepath = os.path.join(OUT, f"{gname}.png")
    bpy.ops.render.render(write_still=True)
    print("gallery", gname, len(keys), flush=True)


for g, keys in groups.items():
    if ONLY and not any(g.startswith(o) for o in ONLY):
        continue
    for n in range(0, len(keys), 24):
        render_group(g if n == 0 else f"{g}_{n // 24 + 1}", keys[n:n + 24])
