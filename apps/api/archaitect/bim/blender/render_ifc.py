"""Render an IFC model produced by bimrender with Blender Cycles.

Run via:  python -m bimrender render out/model.ifc --spec specs/x.json --camera hero_sw
Env: BIM_SP (site-packages with ifcopenshell), BIM_IFC, BIM_SPEC, BIM_CAMERA, BIM_QUALITY, BIM_OUT.
The IFC is the only source of building geometry. Site dressing (lawn, grass, tree crowns,
hedge shape) is render-only and driven by the spec's site section.
"""
import json
import math
import os
import random
import sys
import time

import bpy
import bmesh
from mathutils import Vector

sys.path.append(os.environ["BIM_SP"])
sys.path.append(os.path.dirname(__file__))
import ifcopenshell  # noqa: E402
import ifcopenshell.geom  # noqa: E402
import materials  # noqa: E402

T0 = time.time()
IFC = os.environ["BIM_IFC"]
SPEC = json.load(open(os.environ["BIM_SPEC"], encoding="utf-8"))
CAMERA = os.environ.get("BIM_CAMERA", "hero_sw")
QUALITY = os.environ.get("BIM_QUALITY", "preview")
OUT = os.environ["BIM_OUT"]


def log(*a):
    print(f"[bimrender {time.time() - T0:6.1f}s]", *a, flush=True)


# ------------------------------------------------------------------ scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
LIB = materials.build_library()

# ------------------------------------------------------------------ IFC import
f = ifcopenshell.open(IFC)
shading_to_style = {}
for st in f.by_type("IfcSurfaceStyle"):
    for s in st.Styles:
        shading_to_style[s.id()] = st.Name

FALLBACK = {"IfcWall": "plaster_white", "IfcSlab": "concrete_exposed", "IfcStairFlight": "concrete_exposed",
            "IfcBuildingElementProxy": "concrete_exposed", "IfcGeographicElement": "foliage"}


def style_name(mat, ifc_class):
    name = mat.name
    if "-" in name:
        try:
            sid = int(name.rsplit("-", 1)[1])
            if sid in shading_to_style:
                return shading_to_style[sid]
        except ValueError:
            pass
    return FALLBACK.get(ifc_class, "plaster_white")


settings = ifcopenshell.geom.settings()
settings.set("use-world-coords", True)
it = ifcopenshell.geom.iterator(settings, f, os.cpu_count() or 4)
coll = bpy.data.collections.new("IFC")
scene.collection.children.link(coll)
objects = {}
n_tris = 0
if it.initialize():
    while True:
        sh = it.get()
        el = f.by_id(sh.id)
        if el.is_a("IfcOpeningElement") or el.is_a("IfcSpace"):
            if not it.next():
                break
            continue
        g = sh.geometry
        v = g.verts
        fc = g.faces
        verts = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
        faces = [(fc[i], fc[i + 1], fc[i + 2]) for i in range(0, len(fc), 3)]
        n_tris += len(faces)
        me = bpy.data.meshes.new(el.Name or el.is_a())
        me.from_pydata(verts, [], faces)
        slot_names = [style_name(m, el.is_a()) for m in g.materials] or [FALLBACK.get(el.is_a(), "plaster_white")]
        uniq = []
        for nme in slot_names:
            if nme not in uniq:
                uniq.append(nme)
        for nme in uniq:
            me.materials.append(LIB.get(nme, LIB["plaster_white"]))
        mids = g.material_ids
        if len(mids) == len(faces):
            for p, mid in zip(me.polygons, mids):
                p.material_index = uniq.index(slot_names[mid]) if mid >= 0 else 0
        me.validate()
        me.update()
        ob = bpy.data.objects.new(f"{el.is_a()}:{el.Name}", me)
        ob["ifc_class"] = el.is_a()
        ob["ifc_guid"] = el.GlobalId
        coll.objects.link(ob)
        objects[el.GlobalId] = ob
        if not it.next():
            break
log(f"IFC import: {len(objects)} elements, {n_tris} triangles")

# ------------------------------------------------------------------ site dressing (render-only)
site = SPEC.get("site", {})

# ground relief: site.terrain = graded DGM1 ground in the spec frame, heights relative to the building pad (z = 0), see archaitect.bim.terrain
_TER = site.get("terrain") or {}
_TER_OK = _TER.get("status") == "OK"


def zf(x, y):
    """Ground height at (x, y); 0 without terrain. Outside the terrain grid the edge value continues."""
    if not _TER_OK:
        return 0.0
    st = _TER["step_m"]
    fx = min(max((x - _TER["x0"]) / st, 0.0), _TER["nx"] - 1.0)
    fy = min(max((y - _TER["y0"]) / st, 0.0), _TER["ny"] - 1.0)
    i, j = min(int(fx), _TER["nx"] - 2), min(int(fy), _TER["ny"] - 2)
    tx, ty = fx - i, fy - j
    z, nx = _TER["z"], _TER["nx"]
    return (z[j * nx + i] * (1 - tx) * (1 - ty) + z[j * nx + i + 1] * tx * (1 - ty)
            + z[(j + 1) * nx + i] * (1 - tx) * ty + z[(j + 1) * nx + i + 1] * tx * ty)


def rects_from(key, pad=0.0, extra=0.0):
    out = []
    for r in site.get(key, []):
        ox, oy = r["origin"]
        W, D = r["size"]
        e = extra if key != "pools" else float(r.get("coping", 0.0))
        out.append((ox - e - pad, oy - e - pad, ox + W + e + pad, oy + D + e + pad))
    return out


def comp_rects():
    """footprints of garden components (path, pool, flowerbed, hedge, parking) so no lawn grows through them"""
    out = []
    for c in SPEC.get("components", []):
        t = c.get("type")
        if t == "pool" and c.get("x") is not None:
            cp = float(c.get("coping", 0.35))
            out.append((c["x"] - cp, c["y"] - cp, c["x"] + float(c.get("width", 8.0)) + cp, c["y"] + float(c.get("depth", 4.0)) + cp))
        elif t == "flowerbed" and c.get("x") is not None:
            out.append((c["x"] - 0.15, c["y"] - 0.15, c["x"] + float(c.get("width", 3.0)) + 0.15, c["y"] + float(c.get("depth", 1.2)) + 0.15))
        elif t == "parking" and c.get("x") is not None:
            out.append((c["x"], c["y"], c["x"] + float(c.get("width", 15.0)), c["y"] + float(c.get("depth", 5.0))))
        elif t == "hedge" and c.get("x0") is not None:
            th = float(c.get("thickness", 0.7)) / 2 + 0.05
            out.append((min(c["x0"], c["x1"]) - th, min(c["y0"], c["y1"]) - th, max(c["x0"], c["x1"]) + th, max(c["y0"], c["y1"]) + th))
        elif t == "path" and c.get("points"):
            hw = float(c.get("width", 1.2)) / 2
            for a, b in zip(c["points"], c["points"][1:]):
                out.append((min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw))
    return out


hard = comp_rects() + rects_from("paving", 0.02) + rects_from("pools", 0.02) + rects_from("paths", 0.0) + rects_from("hedges", 0.05)
for vdef in SPEC.get("volumes", []):
    if float(vdef["base_z"]) <= 0.01:
        ox, oy = vdef["origin"]
        W, D = vdef["size"]
        hard.append((ox, oy, ox + W, oy + D))
for cw in SPEC.get("curtain_walls", []):
    ox, oy = cw["origin"]
    W, D = cw["size"]
    hard.append((ox, oy, ox + W, oy + D))


def inside(x, y, rects):
    return any(a <= x <= c and b <= y <= d for a, b, c, d in rects)


def grid_mesh(name, x0, y0, x1, y1, step, z, holes, mat):
    bm = bmesh.new()
    nx, ny = int((x1 - x0) / step), int((y1 - y0) / step)
    vs = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            vs[i, j] = bm.verts.new((x0 + i * step, y0 + j * step, z(x0 + i * step, y0 + j * step) if callable(z) else z))
    for i in range(nx):
        for j in range(ny):
            cx, cy = x0 + (i + 0.5) * step, y0 + (j + 0.5) * step
            if not inside(cx, cy, holes):
                bm.faces.new((vs[i, j], vs[i + 1, j], vs[i + 1, j + 1], vs[i, j + 1]))
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


pool_inner = [(r["origin"][0], r["origin"][1], r["origin"][0] + r["size"][0], r["origin"][1] + r["size"][1])
              for r in site.get("pools", [])]
gx0, gy0, gx1, gy1 = site.get("ground_extent", [-60, -60, 90, 70])
grid_mesh("Untergrund", gx0, gy0, gx1, gy1, 1.0 if not _TER_OK else 0.5, (lambda x, y: zf(x, y) - 0.03), pool_inner, LIB["lawn_soil"])
lx0, ly0, lx1, ly1 = -22.0, -32.0, 48.0, 22.0
near = SPEC.get("render", {}).get("grass_region", [-14.0, -29.0, 36.0, -1.0])
if _TER_OK:  # ground and lawn follow the plot's terrain, not the fixed villa frame
    gx0, gy0 = _TER["x0"], _TER["y0"]
    gx1, gy1 = gx0 + (_TER["nx"] - 1) * _TER["step_m"], gy0 + (_TER["ny"] - 1) * _TER["step_m"]
    _pr = _TER.get("pad_ring") or [[-10, -10], [10, 10]]
    _px0, _py0 = min(p[0] for p in _pr), min(p[1] for p in _pr)
    _px1, _py1 = max(p[0] for p in _pr), max(p[1] for p in _pr)
    lx0, ly0, lx1, ly1 = _px0 - 18.0, _py0 - 18.0, _px1 + 18.0, _py1 + 18.0
    if "grass_region" not in SPEC.get("render", {}):
        near = [_px0 - 8.0, _py0 - 8.0, _px1 + 8.0, _py1 + 8.0]
far_holes = hard + [tuple(near)]
grid_mesh("Rasen fern", lx0, ly0, lx1, ly1, 0.5, zf, far_holes, LIB["lawn_soil"])
if _TER_OK:  # beyond the terrain data: a large plane at the lowest edge height instead of empty sky (far cameras, tall buildings)
    try:
        _zs = [zf(gx0 + (gx1 - gx0) * i / 24.0, gy0 + (gy1 - gy0) * j / 24.0) for i in range(25) for j in range(25)]
        bpy.ops.mesh.primitive_plane_add(size=3000.0, location=((gx0 + gx1) / 2, (gy0 + gy1) / 2, min(_zs) - 0.6))
        _hz = bpy.context.active_object
        _hz.name = "Horizont"
        _hz.data.materials.append(LIB["lawn_soil"])
    except Exception as e:  # noqa: BLE001
        log("horizon plane skipped:", e)
lawn = grid_mesh("Rasen", near[0], near[1], near[2], near[3], 0.25, zf, hard, LIB["lawn_soil"])
log("lawn faces", len(lawn.data.polygons))

grass_count = {"sketch": 0, "draft": 20000, "preview": 60000}.get(QUALITY, 100000)
try:
    if not grass_count:
        raise RuntimeError("sketch: no grass hairs")
    ps_mod = lawn.modifiers.new("Gras", "PARTICLE_SYSTEM")
    ps = ps_mod.particle_system.settings
    ps.type = "HAIR"
    ps.count = grass_count
    ps.hair_length = 0.085
    ps.render_step = 3
    ps.root_radius = 1.0
    ps.radius_scale = 0.003
    ps.child_type = "INTERPOLATED"
    ps.child_percent = 1
    ps.rendered_child_count = {"draft": 6, "preview": 12}.get(QUALITY, 20)
    ps.child_radius = 0.25
    ps.child_roundness = 1.0
    ps.child_length = 1.0
    ps.child_length_threshold = 0.3
    lawn.data.materials.append(LIB["grass_hair"])
    ps.material_slot = "grass_hair"
    ps.length_random = 0.6
    ps.use_hair_bspline = False
    log("grass hairs", grass_count)
except Exception as e:  # legacy hair may disappear in future Blender versions
    log("grass skipped:", e)

for ob in list(coll.objects):
    nm = ob.name
    if ob["ifc_class"] == "IfcGeographicElement" and "Buchs" not in nm and not nm.startswith(("Konifere", "Blumen")):
        bpy.data.objects.remove(ob)  # IFC tree placeholders are replaced by render trees
    elif ob["ifc_class"] == "IfcGeographicElement":
        if "Buchs" in nm:
            rm = ob.modifiers.new("remesh", "REMESH")
            rm.mode = "VOXEL"
            rm.voxel_size = 0.035
            rm.use_smooth_shade = True
            tex = bpy.data.textures.new("hedge_clouds", "CLOUDS")
            tex.noise_scale = 0.12
            dp = ob.modifiers.new("displace", "DISPLACE")
            dp.texture = tex
            dp.strength = 0.07
            dp.mid_level = 0.5
            for p in ob.data.polygons:
                p.use_smooth = True
            ob.data.materials.clear()
            ob.data.materials.append(LIB["boxwood"])

rng = random.Random(7)
leaf_me = bpy.data.meshes.new("Blatt")
leaf_me.from_pydata([(0, -0.035, 0), (0.06, 0, 0.008), (0, 0.035, 0), (-0.06, 0, 0.008)], [], [(0, 1, 2, 3)])
leaf_me.materials.append(LIB["leaf"])
leaf_ob = bpy.data.objects.new("Blatt", leaf_me)
scene.collection.objects.link(leaf_ob)
leaf_ob.location = (0, 0, -50)  # template below ground; instances carry the look


def _make_tree(name, x, y, H, R, leaves):
    import bpy as _b
    cyl = _b.ops.mesh.primitive_cylinder_add
    cyl(vertices=12, radius=max(0.12, R * 0.06), depth=H - R * 0.6, location=(x, y, (H - R * 0.6) / 2))
    trunk = _b.context.active_object
    trunk.data.materials.append(LIB["bark"])
    for k in range(5):  # main branches
        a = k * 2.0 * math.pi / 5 + rng.uniform(-0.3, 0.3)
        L = R * rng.uniform(0.6, 0.9)
        cyl(vertices=8, radius=max(0.05, R * 0.025), depth=L,
            location=(x + math.cos(a) * L * 0.35, y + math.sin(a) * L * 0.35, H - R * 1.1 + L * 0.4))
        br = _b.context.active_object
        br.rotation_euler = (0.0, math.radians(50), a)
        br.data.materials.append(LIB["bark"])
    parts = []
    for k in range(9):
        r = R * rng.uniform(0.45, 0.7)
        c = Vector((x + rng.uniform(-0.55, 0.55) * R, y + rng.uniform(-0.55, 0.55) * R, H - R + rng.uniform(-0.35, 0.45) * R))
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=r, location=c)
        parts.append(bpy.context.active_object)
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    crown = bpy.context.active_object
    crown.name = name + " Krone (Render)"
    rm = crown.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = 0.12
    rm.use_smooth_shade = True
    tex = bpy.data.textures.new("crown_clouds", "CLOUDS")
    tex.noise_scale = 0.9
    tex.noise_depth = 3
    dp = crown.modifiers.new("displace", "DISPLACE")
    dp.texture = tex
    dp.strength = 0.9
    tex2 = bpy.data.textures.new("crown_fine", "CLOUDS")
    tex2.noise_scale = 0.18
    dp2 = crown.modifiers.new("displace2", "DISPLACE")
    dp2.texture = tex2
    dp2.strength = 0.25
    for p in crown.data.polygons:
        p.use_smooth = True
    crown.data.materials.append(LIB["foliage"])
    if leaves:
        # particles need a stable topology: bake remesh/displace into the mesh first
        for mname in ("remesh", "displace", "displace2"):
            bpy.ops.object.modifier_apply(modifier=mname)
        pm = crown.modifiers.new("Laub", "PARTICLE_SYSTEM")
        ls = pm.particle_system.settings
        ls.type = "HAIR"
        ls.count = leaves
        ls.hair_length = 0.05
        ls.emit_from = "FACE"
        ls.use_emit_random = True
        ls.render_type = "OBJECT"
        ls.instance_object = leaf_ob
        ls.particle_size = 1.6
        ls.size_random = 0.6
        ls.use_rotations = True
        ls.rotation_mode = "NOR"
        ls.phase_factor_random = 2.0
        ls.rotation_factor_random = 0.8
        ls.use_rotation_instance = True
        crown.show_instancer_for_render = True


def make_tree(name, x, y, H, R, leaves):
    """Tree standing on the (possibly sloped) ground: everything the builder created is lifted to the local ground height."""
    before = set(bpy.data.objects)
    _make_tree(name, x, y, H, R, leaves)
    dz = zf(x, y)
    if dz:
        for ob in set(bpy.data.objects) - before:
            ob.location.z += dz


for tr in site.get("trees", []):
    x, y = tr["position"]
    make_tree(tr["name"], x, y, float(tr["height"]), float(tr["crown_radius"]),
              {"sketch": 0, "draft": 8000, "preview": 30000}.get(QUALITY, 60000))
for k, tr in enumerate(c for c in SPEC.get("components", []) if c.get("type") == "tree" and c.get("kind", "deciduous") == "deciduous" and c.get("x") is not None):
    make_tree(f"Baum {k}", tr["x"], tr["y"], float(tr.get("height", 9.0)), float(tr.get("crown_radius", 3.0)),
              {"sketch": 0, "draft": 8000, "preview": 30000}.get(QUALITY, 60000))
ctx = SPEC.get("render", {}).get("context", {})
for i, tr in enumerate(ctx.get("trees", [])):
    x, y = tr["position"]
    make_tree(f"Umgebung {i}", x, y, float(tr["height"]), float(tr["crown_radius"]), 0)
for i, b in enumerate(ctx.get("buildings", [])):
    (bx, by), (bw, bd) = b["origin"], b["size"]
    bpy.ops.mesh.primitive_cube_add(size=1, location=(bx + bw / 2, by + bd / 2, b["height"] / 2))
    nb = bpy.context.active_object
    nb.scale = (bw, bd, b["height"])
    nb.name = f"Nachbar {i}"
    nb.data.materials.append(LIB.get(b.get("material", "plaster_white")))
if ctx.get("hedge_boundary"):
    x0, y0, x1, y1 = ctx["hedge_boundary"]["rect"]
    hh = float(ctx["hedge_boundary"]["height"])
    for nm, cx, cy, sx, sy in (("S", (x0 + x1) / 2, y0, x1 - x0, 0.8), ("N", (x0 + x1) / 2, y1, x1 - x0, 0.8),
                               ("W", x0, (y0 + y1) / 2, 0.8, y1 - y0), ("E", x1, (y0 + y1) / 2, 0.8, y1 - y0)):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, hh / 2))
        hg = bpy.context.active_object
        hg.scale = (sx, sy, hh)
        hg.name = f"Grenzhecke {nm}"
        bpy.ops.object.transform_apply(scale=True)
        rm = hg.modifiers.new("remesh", "REMESH")
        rm.mode = "VOXEL"
        rm.voxel_size = 0.07
        rm.use_smooth_shade = True
        tex = bpy.data.textures.new("bh_clouds", "CLOUDS")
        tex.noise_scale = 0.2
        dp = hg.modifiers.new("displace", "DISPLACE")
        dp.texture = tex
        dp.strength = 0.12
        hg.data.materials.append(LIB["boxwood"])

# ------------------------------------------------------------------ light
sun_spec = SPEC.get("render", {}).get("sun", {"azimuth_deg": 225, "elevation_deg": 35})
az, el = math.radians(sun_spec["azimuth_deg"]), math.radians(sun_spec["elevation_deg"])
to_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
sun_data = bpy.data.lights.new("Sonne", "SUN")
sun_data.energy = 4.2
sun_data.angle = math.radians(0.6)
sun_data.color = (1.0, 0.95, 0.88)
sun = bpy.data.objects.new("Sonne", sun_data)
sun.rotation_mode = "QUATERNION"
sun.rotation_quaternion = to_sun.to_track_quat("Z", "Y")
scene.collection.objects.link(sun)

world = bpy.data.worlds.new("Himmel")
scene.world = world
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()
wout = wn.nodes.new("ShaderNodeOutputWorld")
bg = wn.nodes.new("ShaderNodeBackground")
sky = wn.nodes.new("ShaderNodeTexSky")
for t in ("MULTIPLE_SCATTERING", "SINGLE_SCATTERING", "NISHITA", "HOSEK_WILKIE"):
    try:
        sky.sky_type = t
        break
    except Exception:
        pass
for attr, val in (("sun_disc", False), ("sun_elevation", el), ("sun_rotation", math.atan2(to_sun.x, to_sun.y) + math.pi / 2),
                  ("air_density", 1.0), ("altitude", 100.0)):
    try:
        setattr(sky, attr, val)
    except Exception:
        pass
bg.inputs["Strength"].default_value = 0.22
wn.links.new(sky.outputs["Color"], bg.inputs["Color"])
wn.links.new(bg.outputs["Background"], wout.inputs["Surface"])

# ------------------------------------------------------------------ fog bank along the parcel boundary (BIM_FOG=1, photo shots)
if os.environ.get("BIM_FOG") == "1" and _TER_OK and (_TER.get("parcel_ring") or []):
    try:
        ring = [tuple(p) for p in _TER["parcel_ring"][:-1]]
        ccx, ccy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)

        def fog_mat(name, strength):
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            mix = nt.nodes.new("ShaderNodeMixShader")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = (0.86, 0.89, 0.92, 1.0)
            em.inputs["Strength"].default_value = 1.0
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            mr = nt.nodes.new("ShaderNodeMapRange")
            mr.inputs["From Min"].default_value = _FOG_Z0
            mr.inputs["From Max"].default_value = _FOG_Z0 + 38.0
            mr.inputs["To Min"].default_value = strength
            mr.inputs["To Max"].default_value = 0.0
            mr.clamp = True
            nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
            nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
            nt.links.new(mr.outputs["Result"], mix.inputs["Fac"])
            nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
            nt.links.new(em.outputs["Emission"], mix.inputs[2])
            nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
            return m
        _FOG_Z0 = min(zf(p[0], p[1]) for p in ring) - 1.0
        for k, (off, st) in enumerate(((0.0, 0.50), (9.0, 0.72), (18.0, 0.9), (30.0, 1.0))):
            bm = bmesh.new()
            vs = []
            for (px, py) in ring:
                dx, dy = px - ccx, py - ccy
                ln = math.hypot(dx, dy) or 1.0
                qx, qy = px + dx / ln * off, py + dy / ln * off
                g = zf(qx, qy)
                vs.append((bm.verts.new((qx, qy, g - 4.0)), bm.verts.new((qx, qy, _FOG_Z0 + 45.0))))
            for i in range(len(vs)):
                a, b = vs[i], vs[(i + 1) % len(vs)]
                bm.faces.new((a[0], b[0], b[1], a[1]))
            me = bpy.data.meshes.new(f"Nebel{k}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(fog_mat(f"Nebel{k}", st))
            ob = bpy.data.objects.new(f"Nebel{k}", me)
            ob.visible_shadow = False
            scene.collection.objects.link(ob)
        log("fog bank built")
    except Exception as e:  # noqa: BLE001
        log("fog skipped:", e)

# ------------------------------------------------------------------ camera (two-point perspective)
cams = {c["name"]: c for c in SPEC.get("render", {}).get("cameras", [])}
cs = cams.get(CAMERA) or next(iter(cams.values()))
pos, tgt = Vector(cs["position"]), Vector(cs["target"])
if _TER_OK:  # the camera stands on the graded ground at eye height, never in a hollow below or inside a slope
    try:
        _g = zf(pos.x, pos.y)
        if pos.z < _g + 1.6:
            pos.z = _g + 1.6
    except Exception as e:  # noqa: BLE001
        log("camera ground check skipped:", e)
cam_data = bpy.data.cameras.new(cs["name"])
cam_data.lens = float(cs.get("lens_mm", 24))
cam_data.sensor_width = 36.0
cam_data.sensor_fit = "HORIZONTAL"
cam_data.clip_end = 1000.0
cam = bpy.data.objects.new(cs["name"], cam_data)
cam.location = pos
d = tgt - pos
two_point = cs.get("two_point", pos.z < 6.0)
if two_point:
    horiz = Vector((d.x, d.y, 0.0))
    pitch = math.atan2(d.z, horiz.length)
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (-horiz.normalized()).to_track_quat("Z", "Y")
    cam_data.shift_y = math.tan(pitch) * cam_data.lens / cam_data.sensor_width
else:
    cam.rotation_mode = "QUATERNION"
    cam.rotation_quaternion = (-d.normalized()).to_track_quat("Z", "Y")
scene.collection.objects.link(cam)
scene.camera = cam


# ------------------------------------------------------------------ optional: GLB for the 3D viewer (no render)
GLB = os.environ.get("BIM_GLB")
if GLB:
    # keep the viewer focused on the house and its garden: drop far ground, neighbours and boundary hedge
    xs = [c[0] for o in coll.objects for c in (o.matrix_world @ __import__("mathutils").Vector(v) for v in o.bound_box)]
    ys = [c[1] for o in coll.objects for c in (o.matrix_world @ __import__("mathutils").Vector(v) for v in o.bound_box)]
    x0, x1, y0, y1 = min(xs) - 14, max(xs) + 14, min(ys) - 14, max(ys) + 14
    for ob in list(bpy.data.objects):
        far = ob.type == "MESH" and ob.name not in coll.objects and not (x0 <= ob.location.x <= x1 and y0 <= ob.location.y <= y1)
        if far or ob.name.startswith(("Untergrund", "Rasen fern", "Nachbar", "Umgebung", "Grenzhecke", "Blatt")):
            bpy.data.objects.remove(ob)
    libj = json.load(open(materials.LIB_PATH, encoding="utf-8"))
    import glb_textures
    tiles = glb_textures.bake_all(libj, materials.LIB_PATH.parent.parent / "out" / "_tiles", log)
    sizes = {n: wh for n, (_png, wh) in tiles.items()}
    for ob in bpy.data.objects:
        glb_textures.box_uvs(ob, sizes)
    for m in bpy.data.materials:
        e = libj.get(m.name)
        if not e or m.name in ("grass_hair", "leaf"):
            continue
        r, g, b = e["rgb"]
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bs.outputs["BSDF"], o.inputs["Surface"])
        bs.inputs["Base Color"].default_value = (r, g, b, 1)
        clear = m.name in ("glass_clear", "water")
        bs.inputs["Roughness"].default_value = 0.15 if clear else 0.8
        bs.inputs["Metallic"].default_value = 0.8 if e["shader"]["kind"] == "metal" else 0.0
        if clear:
            bs.inputs["Alpha"].default_value = 0.3
        if m.name in tiles:
            glb_textures.add_tile_to_material(m, tiles[m.name][0])
            if e["shader"]["kind"] == "wood":
                bs.inputs["Roughness"].default_value = 0.55
    os.makedirs(os.path.dirname(GLB), exist_ok=True)
    try:
        bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", export_apply=True, export_cameras=False,
                                  export_lights=False, use_selection=False, export_image_format="JPEG",
                                  export_jpeg_quality=88)
    except TypeError:  # option names differ between Blender versions
        bpy.ops.export_scene.gltf(filepath=GLB, export_format="GLB", export_apply=True, export_cameras=False,
                                  export_lights=False, use_selection=False)
    log("GLB", GLB)
    sys.exit(0)

# ------------------------------------------------------------------ render settings
scene.render.engine = "CYCLES"
cy = scene.cycles
try:
    if os.environ.get("BIM_DEVICE", "CPU") == "CPU":
        raise RuntimeError("CPU requested")
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = True
    cy.device = "GPU"
except Exception as e:
    log("GPU unavailable:", e)
if QUALITY == "sketch":
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    cy.samples = 16
elif QUALITY == "draft":
    scene.render.resolution_x, scene.render.resolution_y = 960, 540
    cy.samples = 32
elif QUALITY == "preview":
    scene.render.resolution_x, scene.render.resolution_y = 1600, 900
    cy.samples = 96
else:
    scene.render.resolution_x, scene.render.resolution_y = 3200, 1800
    cy.samples = 384
cy.use_adaptive_sampling = True
cy.adaptive_threshold = 0.01
cy.use_denoising = True
cy.max_bounces = 12
cy.diffuse_bounces = 4
cy.glossy_bounces = 6
cy.transmission_bounces = 12
cy.transparent_max_bounces = 16
cy.sample_clamp_indirect = 8.0
cy.caustics_reflective = False
cy.caustics_refractive = False
cy.blur_glossy = 1.0
if QUALITY == "sketch":  # fast look: fewer light bounces, same geometry and materials
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 6, 2, 3
    cy.transmission_bounces, cy.transparent_max_bounces = 6, 8
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
scene.view_settings.exposure = float(SPEC.get("render", {}).get("exposure", 0.0))
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = OUT
os.makedirs(os.path.dirname(OUT), exist_ok=True)
blend_path = os.path.splitext(OUT)[0] + ".blend"
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
log("rendering", CAMERA, QUALITY, f"{scene.render.resolution_x}x{scene.render.resolution_y}", cy.samples, "spp")
bpy.ops.render.render(write_still=True)
log("FERTIG", OUT)
