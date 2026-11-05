"""Procedural PBR material library for bimrender (Blender 5.x, Cycles).

No external textures: everything is procedural so the pipeline runs offline.
Names match the IFC surface-style names written by bimrender.ifcgen.
"""
import json
from pathlib import Path

import bpy

LIB_PATH = Path(__file__).resolve().parent.parent / "materials" / "library.json"


def _base(name):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf, out


def _set(bsdf, key, val):
    if key in bsdf.inputs:
        bsdf.inputs[key].default_value = val


def _texcoord(nt):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    return tc.outputs["Object"]


def _noise(nt, scale, detail=6.0, rough=0.6, vec=None):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    if vec is not None:
        nt.links.new(vec, n.inputs["Vector"])
    return n


def _ramp(nt, fac, c0, c1):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].color = (*c0, 1)
    r.color_ramp.elements[1].color = (*c1, 1)
    nt.links.new(fac, r.inputs["Fac"])
    return r


def _bevel_bump(nt, bsdf, radius, height_socket=None, strength=0.1, distance=0.01):
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = radius
    bev.samples = 6
    if height_socket is None:
        nt.links.new(bev.outputs["Normal"], bsdf.inputs["Normal"])
        return
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    nt.links.new(height_socket, bump.inputs["Height"])
    nt.links.new(bev.outputs["Normal"], bump.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _ground_grime(nt, color_socket, height=0.45, amount=0.82):
    """Darken the bottom of facades (splash zone) - a cheap but strong realism cue."""
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.0
    mr.inputs["From Max"].default_value = height
    mr.inputs["To Min"].default_value = amount
    mr.inputs["To Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(color_socket, mix.inputs["A"])
    nt.links.new(mr.outputs["Result"], mix.inputs["B"])
    return mix.outputs["Result"]


def plaster(name, col=(0.80, 0.79, 0.75), rough=0.92, grain_scale=220.0, grain=0.12, blot=0.35):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    big = _noise(nt, blot, 4, 0.5, v)
    tint = _ramp(nt, big.outputs["Fac"], tuple(c * 0.94 for c in col), col)
    nt.links.new(_ground_grime(nt, tint.outputs["Color"]), bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", rough)
    grain_n = _noise(nt, grain_scale, 8, 0.75, v)
    _bevel_bump(nt, bsdf, 0.012, grain_n.outputs["Fac"], grain, 0.004)
    return m


def concrete(name, col=(0.46, 0.46, 0.44)):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    blot = _noise(nt, 1.6, 10, 0.7, v)
    tint = _ramp(nt, blot.outputs["Fac"], tuple(c * 0.8 for c in col), tuple(min(1, c * 1.12) for c in col))
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.78)
    pores = _noise(nt, 120.0, 10, 0.8, v)
    _bevel_bump(nt, bsdf, 0.008, pores.outputs["Fac"], 0.25, 0.006)
    return m


def paving(name, col=(0.56, 0.55, 0.52), scale=1.0, rough=0.82):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = scale
    nt.links.new(v, vor.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vor.outputs["Color"], sep.inputs["Color"])
    tint = _ramp(nt, sep.outputs["Red"], tuple(c * 0.9 for c in col), tuple(min(1, c * 1.06) for c in col))
    dirt = _noise(nt, 3.0, 8, 0.7, v)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.25
    nt.links.new(tint.outputs["Color"], mix.inputs["A"])
    nt.links.new(dirt.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", rough)
    pores = _noise(nt, 90.0, 8, 0.8, v)
    _bevel_bump(nt, bsdf, 0.006, pores.outputs["Fac"], 0.2, 0.004)
    return m


def metal(name, col, rough, metallic=1.0, bevel=0.004):
    m, nt, bsdf, _ = _base(name)
    _set(bsdf, "Base Color", (*col, 1))
    _set(bsdf, "Roughness", rough)
    _set(bsdf, "Metallic", metallic)
    _bevel_bump(nt, bsdf, bevel)
    return m


def painted(name, col, rough):
    m, nt, bsdf, _ = _base(name)
    _set(bsdf, "Base Color", (*col, 1))
    _set(bsdf, "Roughness", rough)
    _set(bsdf, "Coat Weight", 0.3)
    _bevel_bump(nt, bsdf, 0.004)
    return m


def glass(name, tint=(0.93, 0.98, 0.96), rough=0.0):
    m, nt, bsdf, _ = _base(name)
    _set(bsdf, "Base Color", (*tint, 1))
    _set(bsdf, "Transmission Weight", 1.0)
    _set(bsdf, "IOR", 1.52)
    _set(bsdf, "Roughness", rough)
    return m


def water(name):
    m, nt, bsdf, out = _base(name)
    _set(bsdf, "Base Color", (0.85, 0.95, 0.95, 1))
    _set(bsdf, "Transmission Weight", 1.0)
    _set(bsdf, "IOR", 1.333)
    _set(bsdf, "Roughness", 0.02)
    v = _texcoord(nt)
    waves = _noise(nt, 1.2, 4, 0.5, v)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(waves.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    vol = nt.nodes.new("ShaderNodeVolumeAbsorption")
    vol.inputs["Color"].default_value = (0.35, 0.72, 0.75, 1)
    vol.inputs["Density"].default_value = 1.2
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return m


def foliage(name, c0=(0.035, 0.07, 0.02), c1=(0.12, 0.2, 0.05), scale=9.0):
    m, nt, bsdf, out = _base(name)
    v = _texcoord(nt)
    n = _noise(nt, scale, 6, 0.65, v)
    tint = _ramp(nt, n.outputs["Fac"], c0, c1)
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.6)
    _set(bsdf, "Subsurface Weight", 0.15)
    leaves = nt.nodes.new("ShaderNodeTexVoronoi")
    leaves.inputs["Scale"].default_value = 40.0
    nt.links.new(v, leaves.inputs["Vector"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.8
    nt.links.new(leaves.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def gravel(name):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 60.0
    nt.links.new(v, vor.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vor.outputs["Color"], sep.inputs["Color"])
    tint = _ramp(nt, sep.outputs["Green"], (0.36, 0.33, 0.29), (0.7, 0.67, 0.6))
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.9)
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.9
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def wood(name, c0=(0.25, 0.14, 0.07), c1=(0.45, 0.29, 0.15), scale=3.0, distortion=6.0, rough=0.45):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = distortion
    wave.inputs["Detail"].default_value = 4.0
    nt.links.new(v, wave.inputs["Vector"])
    grain_n = _noise(nt, 55.0, 8, 0.7, v)
    fine = nt.nodes.new("ShaderNodeMath")
    fine.operation = "MULTIPLY_ADD"
    nt.links.new(wave.outputs["Fac"], fine.inputs[0])
    fine.inputs[1].default_value = 0.55
    nt.links.new(grain_n.outputs["Fac"], fine.inputs[2])
    fine.inputs[2].default_value = 0.0
    tint = _ramp(nt, fine.outputs[0], c0, c1)
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", rough)
    _bevel_bump(nt, bsdf, 0.004, grain_n.outputs["Fac"], 0.15, 0.002)
    return m


def lawn_soil(name):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    n = _noise(nt, 4.0, 8, 0.7, v)
    tint = _ramp(nt, n.outputs["Fac"], (0.05, 0.085, 0.022), (0.13, 0.16, 0.05))
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 1.0)
    return m


def grass_hair(name):
    m, nt, bsdf, _ = _base(name)
    info = nt.nodes.new("ShaderNodeHairInfo")
    tint = _ramp(nt, info.outputs["Random"], (0.04, 0.085, 0.015), (0.2, 0.24, 0.06))
    grad = nt.nodes.new("ShaderNodeMix")
    grad.data_type = "RGBA"
    grad.blend_type = "MULTIPLY"
    nt.links.new(info.outputs["Intercept"], grad.inputs["Factor"])
    grad.inputs["A"].default_value = (0.45, 0.45, 0.45, 1)
    grad.inputs["B"].default_value = (1, 1, 1, 1)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tint.outputs["Color"], mul.inputs["A"])
    nt.links.new(grad.outputs["Result"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.55)
    _set(bsdf, "Subsurface Weight", 0.2)
    return m


def fabric(name, col):
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    n = _noise(nt, 300.0, 4, 0.6, v)
    tint = _ramp(nt, n.outputs["Fac"], tuple(c * 0.85 for c in col), col)
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.95)
    _set(bsdf, "Sheen Weight", 0.5)
    _bevel_bump(nt, bsdf, 0.03)
    return m


def leaf(name):
    m, nt, bsdf, out = _base(name)
    obj = nt.nodes.new("ShaderNodeObjectInfo")
    tint = _ramp(nt, obj.outputs["Random"], (0.03, 0.07, 0.012), (0.16, 0.24, 0.05))
    nt.links.new(tint.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.5)
    trans = nt.nodes.new("ShaderNodeBsdfTranslucent")
    trans.inputs["Color"].default_value = (0.25, 0.4, 0.06, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.3
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def _math(nt, op, a=None, b=None, a_link=None, b_link=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, (val, link) in enumerate(((a, a_link), (b, b_link))):
        if link is not None:
            nt.links.new(link, n.inputs[i])
        elif val is not None:
            n.inputs[i].default_value = val
    return n.outputs[0]


def brick(name, col1, col2, mortar, brick_w=0.24, row_h=0.0625, mortar_size=0.01, rough=0.85, bump=0.5, bump_dist=0.006, offset=0.5):
    """Brick bond projected per face direction (walls facing X, Y or up all get an undistorted bond)."""
    m, nt, bsdf, _ = _base(name)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    pos = nt.nodes.new("ShaderNodeSeparateXYZ")
    nrm = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], pos.inputs["Vector"])
    nt.links.new(tc.outputs["Normal"], nrm.inputs["Vector"])
    ax = _math(nt, "ABSOLUTE", a_link=nrm.outputs["X"])
    ay = _math(nt, "ABSOLUTE", a_link=nrm.outputs["Y"])
    wx = _math(nt, "GREATER_THAN", a_link=ax, b=0.5)
    wy = _math(nt, "GREATER_THAN", a_link=ay, b=0.5)
    wxy = _math(nt, "MAXIMUM", a_link=wx, b_link=wy)

    def pick(fac, a, b):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "FLOAT"
        nt.links.new(fac, mx.inputs[0]); nt.links.new(a, mx.inputs[2]); nt.links.new(b, mx.inputs[3])
        return mx.outputs[0]

    u = pick(wx, pos.outputs["X"], pos.outputs["Y"])
    v = pick(wxy, pos.outputs["Y"], pos.outputs["Z"])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u, comb.inputs["X"]); nt.links.new(v, comb.inputs["Y"])
    bk = nt.nodes.new("ShaderNodeTexBrick")
    nt.links.new(comb.outputs["Vector"], bk.inputs["Vector"])
    bk.inputs["Color1"].default_value = (*col1, 1)
    bk.inputs["Color2"].default_value = (*col2, 1)
    bk.inputs["Mortar"].default_value = (*mortar, 1)
    bk.inputs["Scale"].default_value = 1.0
    bk.inputs["Mortar Size"].default_value = mortar_size
    bk.inputs["Bias"].default_value = 0.0
    bk.offset = offset
    bk.inputs["Brick Width"].default_value = brick_w
    bk.inputs["Row Height"].default_value = row_h
    nt.links.new(bk.outputs["Color"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", rough)
    bn = nt.nodes.new("ShaderNodeBump")
    bn.inputs["Strength"].default_value = bump
    bn.inputs["Distance"].default_value = bump_dist
    nt.links.new(bk.outputs["Fac"], bn.inputs["Height"])
    nt.links.new(bn.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def thatch(name, c0=(0.30, 0.22, 0.10), c1=(0.55, 0.43, 0.22)):
    """Reed / straw: noise stretched along the fall line, rough, strong fibre bump."""
    m, nt, bsdf, _ = _base(name)
    v = _texcoord(nt)
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.05)
    nt.links.new(v, mp.inputs["Vector"])
    fib = _noise(nt, 90.0, 6, 0.7, mp.outputs["Vector"])
    big = _noise(nt, 1.2, 4, 0.5, v)
    tint = _ramp(nt, fib.outputs["Fac"], c0, c1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 0.5
    nt.links.new(tint.outputs["Color"], mix.inputs["A"])
    nt.links.new(big.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    _set(bsdf, "Roughness", 0.95)
    bn = nt.nodes.new("ShaderNodeBump")
    bn.inputs["Strength"].default_value = 0.8
    bn.inputs["Distance"].default_value = 0.02
    nt.links.new(fib.outputs["Fac"], bn.inputs["Height"])
    nt.links.new(bn.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def _c(s, key, default=None):
    v = s.get(key, default)
    return tuple(v) if isinstance(v, list) else v


def _brickish(defaults):
    def f(n, s):
        d = {**defaults, **{k: v for k, v in s.items() if k != "kind"}}
        return brick(n, _c(d, "col1"), _c(d, "col2"), _c(d, "mortar"), d.get("brick_w", 0.24), d.get("row_h", 0.0625),
                     d.get("mortar_size", 0.01), d.get("rough", 0.85), d.get("bump", 0.5), d.get("bump_dist", 0.006),
                     d.get("offset", 0.5))
    return f


BUILDERS = {
    "plaster": lambda n, s: plaster(n, _c(s, "col", (0.80, 0.79, 0.75)), s.get("rough", 0.92), s.get("grain_scale", 220.0), s.get("grain", 0.12), s.get("blot", 0.35)),
    "concrete": lambda n, s: concrete(n, _c(s, "col", (0.46, 0.46, 0.44))),
    "paving": lambda n, s: paving(n, _c(s, "col", (0.56, 0.55, 0.52)), s.get("scale", 1.0), s.get("rough", 0.82)),
    "painted": lambda n, s: painted(n, _c(s, "col"), s.get("rough", 0.4)),
    "metal": lambda n, s: metal(n, _c(s, "col"), s.get("rough", 0.3), s.get("metallic", 1.0)),
    "glass": lambda n, s: glass(n, _c(s, "tint", (0.93, 0.98, 0.96)), s.get("rough", 0.0)),
    "water": lambda n, s: water(n),
    "foliage": lambda n, s: foliage(n, _c(s, "c0", (0.035, 0.07, 0.02)), _c(s, "c1", (0.12, 0.2, 0.05)), s.get("scale", 9.0)),
    "gravel": lambda n, s: gravel(n),
    "wood": lambda n, s: wood(n, _c(s, "c0", (0.25, 0.14, 0.07)), _c(s, "c1", (0.45, 0.29, 0.15)), s.get("scale", 3.0), s.get("distortion", 6.0), s.get("rough", 0.45)),
    "fabric": lambda n, s: fabric(n, _c(s, "col")),
    "brick": _brickish({}),
    # Bausteine mit grossem Format / anderem Verband: gleicher Verband-Shader, andere Masse
    "stone": _brickish({"brick_w": 0.55, "row_h": 0.28, "mortar_size": 0.025, "rough": 0.95, "bump": 0.9, "bump_dist": 0.012, "offset": 0.4}),
    "tile": _brickish({"brick_w": 0.20, "row_h": 0.38, "mortar_size": 0.012, "rough": 0.7, "bump": 0.7, "bump_dist": 0.01, "offset": 0.5}),
    "slate": _brickish({"brick_w": 0.30, "row_h": 0.20, "mortar_size": 0.006, "rough": 0.55, "bump": 0.6, "bump_dist": 0.008, "offset": 0.5}),
    "thatch": lambda n, s: thatch(n, _c(s, "c0", (0.30, 0.22, 0.10)), _c(s, "c1", (0.55, 0.43, 0.22))),
    "lawn_soil": lambda n, s: lawn_soil(n),
    "grass_hair": lambda n, s: grass_hair(n),
    "leaf": lambda n, s: leaf(n),
}


def build_library():
    """Every entry of materials/library.json becomes one Blender material of the same name."""
    data = json.loads(LIB_PATH.read_text(encoding="utf-8"))
    return {k: BUILDERS[v["shader"]["kind"]](k, v["shader"]) for k, v in data.items() if not k.startswith("_")}
