"""Texture tiles for the GLB viewer.

The procedural Cycles materials cannot be exported to glTF. Instead each textured material is rendered ONCE
into a small tile image (flat, unlit: only its base colour), cached on disk, and applied to the meshes through
box-projected UVs measured in metres. Later exports only assign UVs, so a new 3D view costs seconds.
Tiles are not perfectly seamless for noise-based materials (brick bonds tile exactly); sizes are chosen large
so repeats are rare.
"""
import hashlib
import json
import math
from pathlib import Path

import bmesh
import bpy

TILE_VER = 1          # bump to invalidate cached tiles
TILE_PX = 1024
SIZES = {"brick": (1.92, 2.0), "wood": (2.0, 2.0), "lawn_soil": (6.0, 6.0)}  # tile size in metres per shader kind
DEFAULT = (4.0, 4.0)
Z0 = 10.0             # tile plane floats above the ground so height-based grime shaders stay neutral
SKIP = {"grass_hair", "leaf"}


def _source_socket(mat):
    """Socket feeding the Principled Base Color, or None (flat colours need no tile)."""
    nt = mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if not out or not out.inputs["Surface"].links:
        return None
    bsdf = out.inputs["Surface"].links[0].from_node
    if bsdf.type != "BSDF_PRINCIPLED":
        return None
    links = bsdf.inputs["Base Color"].links
    return links[0].from_socket if links else None


def bake_tile(mat, w, h, png):
    """Render the base colour of `mat` on a w x h metre plane (orthographic, unlit). True if a tile was written."""
    m = mat.copy()
    nt = m.node_tree
    src = _source_socket(m)
    if src is None:
        bpy.data.materials.remove(m)
        return False
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(src, em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    sc = bpy.data.scenes.new("tile")
    me = bpy.data.meshes.new("tile")
    me.from_pydata([(0, 0, Z0), (w, 0, Z0), (w, 0, Z0 + h), (0, 0, Z0 + h)], [], [(0, 1, 2, 3)])
    me.materials.append(m)
    ob = bpy.data.objects.new("tile", me)
    sc.collection.objects.link(ob)
    cd = bpy.data.cameras.new("tile")
    cd.type = "ORTHO"
    cd.ortho_scale = w
    cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("tile", cd)
    cam.location = (w / 2, -5.0, Z0 + h / 2)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    sc.cycles.use_denoising = False
    sc.render.resolution_x = TILE_PX
    sc.render.resolution_y = max(16, round(TILE_PX * h / w))
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(png)
    Path(png).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True, scene=sc.name)
    for blk, coll in ((ob, bpy.data.objects), (cam, bpy.data.objects), (me, bpy.data.meshes), (cd, bpy.data.cameras),
                      (m, bpy.data.materials), (sc, bpy.data.scenes)):
        coll.remove(blk)
    return True


def bake_all(libj, cache_dir, log=print):
    """Returns {material name: (png path, (w, h))} for every material that has a texture tile."""
    tiles = {}
    for name, entry in libj.items():
        mat = bpy.data.materials.get(name)
        if mat is None or name in SKIP or not mat.node_tree:
            continue
        w, h = SIZES.get(entry["shader"]["kind"], DEFAULT)
        key = hashlib.sha1(json.dumps([entry["shader"], w, h, TILE_PX, TILE_VER], sort_keys=True).encode()).hexdigest()[:8]
        png = Path(cache_dir) / f"{name}_{key}.png"
        if png.exists() or (_source_socket(mat) is not None and bake_tile(mat, w, h, png) and (log(f"tile {name}") or True)):
            tiles[name] = (png, (w, h))
    return tiles


def box_uvs(ob, sizes):
    """Metre-based box projection UVs. `sizes` maps material name -> (w, h) of its tile."""
    me = ob.data
    if ob.type != "MESH" or not me.polygons:
        return
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    mw, nm = ob.matrix_world, ob.matrix_world.to_3x3()
    slots = [s.material.name if s.material else None for s in ob.material_slots]
    for f in bm.faces:
        mat = slots[f.material_index] if f.material_index < len(slots) else None
        w, h = sizes.get(mat, DEFAULT)
        n = nm @ f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for lp in f.loops:
            p = mw @ lp.vert.co
            if az >= ax and az >= ay:
                a, b = p.x, p.y
            elif ax >= ay:
                a, b = p.y, p.z
            else:
                a, b = p.x, p.z
            lp[uv].uv = (a / w, b / h)
    bm.to_mesh(me)
    bm.free()


def add_tile_to_material(mat, png):
    """Principled node tree whose base colour is the tile image (repeating)."""
    nt = mat.node_tree
    bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(png), check_existing=True)
    tex.extension = "REPEAT"
    nt.links.new(tex.outputs["Color"], bs.inputs["Base Color"])
