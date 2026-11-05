"""Building spec (JSON) -> IFC4 BIM model.

Single source of truth for geometry. Every visible building part is a real IFC
element (walls with voided openings, windows/doors filling them, slabs,
parapets, curtain wall members/plates, stair flights, railings, pergolas).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.style
import ifcopenshell.api.unit

from . import fachwerk, library
from .geom import facade_box, facade_xy, side_length, subtract_intervals, SIDES
from .ifc_openings import OpeningsMixin, WINDOW_KEYS
from .ifc_components import ComponentsMixin
from .ifc_roofs import RoofsMixin
from .ifc_components2 import Components2Mixin
from .ifc_components3 import Components3Mixin
from .ifc_components4 import Components4Mixin
from .ifc_garden import GardenMixin
from .ifc_garden2 import Garden2Mixin

class Builder(OpeningsMixin, ComponentsMixin, Components2Mixin, Components3Mixin, Components4Mixin, GardenMixin, Garden2Mixin, RoofsMixin):
    def __init__(self, spec: dict):
        from .logic import normalize
        spec = normalize(spec)
        self.spec = spec
        from .terrain import SpecTerrain
        self.tz = SpecTerrain((spec.get("site") or {}).get("terrain") or {})   # derived ground, pad = 0 (optional)
        self.f = ifcopenshell.api.project.create_file(version="IFC4")
        f = self.f
        self.project = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name=spec["name"])
        units = [ifcopenshell.api.unit.add_si_unit(f, unit_type=t)
                 for t in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT")]
        units.append(ifcopenshell.api.unit.add_si_unit(f, unit_type="PLANEANGLEUNIT"))
        ifcopenshell.api.unit.assign_unit(f, units=units)  # metres, not the API default (mm)
        model = ifcopenshell.api.context.add_context(f, context_type="Model")
        self.body = ifcopenshell.api.context.add_context(
            f, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model)
        self.site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Grundstueck")
        self.building = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name=spec["name"])
        ifcopenshell.api.aggregate.assign_object(f, products=[self.site], relating_object=self.project)
        ifcopenshell.api.aggregate.assign_object(f, products=[self.building], relating_object=self.site)
        for p in (self.site, self.building):
            ifcopenshell.api.geometry.edit_object_placement(f, product=p)
        self.storeys = []
        for lv in spec["levels"]:
            st = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=lv["name"])
            st.Elevation = float(lv["elevation"])
            ifcopenshell.api.aggregate.assign_object(f, products=[st], relating_object=self.building)
            ifcopenshell.api.geometry.edit_object_placement(f, product=st)
            self.storeys.append((float(lv["elevation"]), st))
        self.styles = {}
        self.materials = {}
        self.z_dir = f.createIfcDirection((0.0, 0.0, 1.0))
        self.x_dir = f.createIfcDirection((1.0, 0.0, 0.0))
        d = spec.get("defaults", {})
        self.wall_t = float(d.get("wall_thickness", 0.36))
        self.parapet_h = float(d.get("parapet_height", 0.6))
        self.win = {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.12,
                    "glass": "glass_clear", "frame": "steel_black", "sill_board": True}
        self.win.update(d.get("window", {}))
        self.slab_t = float(spec.get("slab_thickness", 0.3))
        self.storey_h = float(spec.get("storey_height", 3.0))
        self.vol = {v["id"]: v for v in spec.get("volumes", [])}
        from . import objects as _objects
        self.cur_obj = None
        self.vobj = {vid: o["id"] for o in _objects.objects(spec) if o["kind"] == "house" for vid in o["volumes"]}
        self.walls = {}  # (volume, side, storey) -> IfcWall
        self.gables = {}  # volume id -> gable geometry
        self.roof_rise = {}  # volume id -> height of the roof above the eaves

    # ---------------------------------------------------------------- basics
    def style(self, name):
        if name not in self.styles:
            st = ifcopenshell.api.style.add_style(self.f, name=name)
            r, g, b = library.rgb(name)
            ifcopenshell.api.style.add_surface_style(
                self.f, style=st, ifc_class="IfcSurfaceStyleShading",
                attributes={"SurfaceColour": {"Name": None, "Red": r, "Green": g, "Blue": b},
                            "Transparency": 0.7 if name in ("glass_clear", "water") else 0.0})
            self.styles[name] = st
        return self.styles[name]

    def material(self, name):
        if name not in self.materials:
            self.materials[name] = ifcopenshell.api.material.add_material(self.f, name=name)
        return self.materials[name]

    def box(self, x, y, z, dx, dy, dz, style):
        f = self.f
        if dx <= 1e-4 or dy <= 1e-4 or dz <= 1e-4:
            raise ValueError(f"degenerate box {(x, y, z, dx, dy, dz)}")
        prof = f.createIfcRectangleProfileDef(
            "AREA", None, f.createIfcAxis2Placement2D(f.createIfcCartesianPoint((x + dx / 2, y + dy / 2))), dx, dy)
        solid = f.createIfcExtrudedAreaSolid(
            prof, f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, float(z)))), self.z_dir, dz)
        if style:
            ifcopenshell.api.style.assign_item_style(f, item=solid, style=self.style(style))
        return solid

    def cylinder(self, p0, p1, r, style):
        f = self.f
        v = [p1[i] - p0[i] for i in range(3)]
        L = math.sqrt(sum(c * c for c in v))
        axis = tuple(c / L for c in v)
        ref = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.9 else (0.0, 1.0, 0.0)
        pos = f.createIfcAxis2Placement3D(
            f.createIfcCartesianPoint(tuple(float(c) for c in p0)),
            f.createIfcDirection(axis), f.createIfcDirection(ref))
        prof = f.createIfcCircleProfileDef("AREA", None, None, r)
        solid = f.createIfcExtrudedAreaSolid(prof, pos, self.z_dir, L)
        if style:
            ifcopenshell.api.style.assign_item_style(f, item=solid, style=self.style(style))
        return solid

    def ground_z(self, *pts):
        """Lowest graded-ground height under the given (x, y) points (sink in rather than float); 0 without terrain."""
        return min((self.tz.at(x, y) for x, y in pts), default=0.0) if self.tz.ok else 0.0

    def element(self, ifc_class, name, items, z_ref=0.0, predefined=None, material=None, container=True, dz=0.0):
        f = self.f
        el = ifcopenshell.api.root.create_entity(f, ifc_class=ifc_class, name=name, predefined_type=predefined)
        if getattr(self, "cur_obj", None):
            el.Tag = self.cur_obj              # selectable object (bim/objects.py) for the 360° view
        if predefined == "USERDEFINED" and hasattr(el, "ObjectType"):
            el.ObjectType = name  # IFC rule: USERDEFINED requires ObjectType
        if dz:
            import numpy as np
            m = np.eye(4)
            m[2, 3] = dz
            ifcopenshell.api.geometry.edit_object_placement(f, product=el, matrix=m)
        else:
            ifcopenshell.api.geometry.edit_object_placement(f, product=el)
        rtype = "SolidModel" if any(i.is_a("IfcFacetedBrep") for i in items) else "SweptSolid"
        rep = f.createIfcShapeRepresentation(self.body, "Body", rtype, items)
        ifcopenshell.api.geometry.assign_representation(f, product=el, representation=rep)
        if container:
            ifcopenshell.api.spatial.assign_container(f, products=[el], relating_structure=self.storey_for(z_ref))
        if material:
            ifcopenshell.api.material.assign_material(f, products=[el], material=self.material(material))
        return el

    def storey_for(self, z):
        best = self.storeys[0][1]
        for elev, st in self.storeys:
            if elev <= z + 1e-6:
                best = st
        return best

    def pset(self, el, name, props):
        ps = ifcopenshell.api.pset.add_pset(self.f, product=el, name=name)
        ifcopenshell.api.pset.edit_pset(self.f, pset=ps, properties=props)

    # ---------------------------------------------------------------- volumes
    def volumes(self):
        for v in self.spec.get("volumes", []):
            self.cur_obj = self.vobj.get(v["id"])
            ox, oy = v["origin"]
            W, D = v["size"]
            t = float(v.get("wall_thickness", self.wall_t))
            base = float(v["base_z"])
            n = int(v["storeys"])
            h = float(v.get("storey_height", self.storey_h))
            top = base + n * h
            fac = v.get("facade", "plaster_white")
            for s in range(n):
                z0 = base + s * h
                for side in SIDES:
                    x, y, _, dx, dy, _ = self._wall_rect(side, ox, oy, W, D, t)
                    w = self.element("IfcWall", f"Wand {v['id']}-{side} G{s}",
                                     [self.box(x, y, z0, dx, dy, h, fac)], z_ref=z0,
                                     predefined="SOLIDWALL", material="Mauerwerk verputzt")
                    self.pset(w, "Pset_WallCommon", {"IsExternal": True, "LoadBearing": True})
                    self.walls[(v["id"], side, s)] = (w, z0, h, t)
                # floor slab of this storey (inside the walls)
                self.element("IfcSlab", f"Decke {v['id']} G{s}",
                             [self.box(ox + t, oy + t, z0 - self.slab_t, W - 2 * t, D - 2 * t, self.slab_t, "concrete_exposed"),
                              self.box(ox + t, oy + t, z0 - 0.02, W - 2 * t, D - 2 * t, 0.02, "floor_oak")],
                             z_ref=z0, predefined="FLOOR", material="Stahlbeton")
            if 0.05 < base <= 1.0:      # Hochparterre (Eingangstreppe): massiver Sockel unter dem Erdgeschoss, kein schwebendes Haus
                self.element("IfcFooting", f"Sockel {v['id']}",
                             [self.box(ox, oy, -0.4, W, D, base + 0.4, ((v.get("facade_detail") or {}).get("plinth") or {}).get("material", "stone_plinth"))],
                             z_ref=0.0, predefined="STRIP_FOOTING", material="Naturstein")
            # roof slab (with a pitched roof it is the ceiling of the top storey)
            self.element("IfcSlab", f"Dach {v['id']}",
                         [self.box(ox + t, oy + t, top - self.slab_t, W - 2 * t, D - 2 * t, self.slab_t, "concrete_exposed")],
                         z_ref=top, predefined="ROOF" if (v.get("roof") or {}).get("type") not in ("gable", "hip", "shed", "mansard", "gambrel", "sawtooth") else "FLOOR",
                         material="Stahlbeton")
            roof = v.get("roof") or {}
            if roof.get("type") == "gable":
                gable = self._gable(v, ox, oy, W, D, t, top, fac, roof)
                self.gables[v["id"]] = gable
                self.roof_rise[v["id"]] = gable["rise"]
            elif roof.get("type") in ("hip", "shed", "mansard", "gambrel", "sawtooth"):
                gable = None
                self.roof_rise[v["id"]] = getattr(self, "_" + roof["type"])(v, ox, oy, W, D, t, top, fac, roof)["rise"]
            else:
                gable = None
                self._parapets(v, ox, oy, W, D, t, top, fac)
            self._detail(v, ox, oy, W, D, base, n, h, top, gable)
            if gable:
                self._dormers(v, ox, oy, W, D, t, top, fac, roof, gable)

    # ---------------------------------------------------------------- pitched roof, timber frame, plinth
    def _prism(self, pts, loc, axis, ref, length, style):
        """Extrude a polygon (profile coordinates = local x/y of the placement) along `axis`."""
        f = self.f
        pos = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint(tuple(float(c) for c in loc)),
                                          f.createIfcDirection(tuple(float(c) for c in axis)),
                                          f.createIfcDirection(tuple(float(c) for c in ref)))
        poly = f.createIfcPolyline([f.createIfcCartesianPoint((float(a), float(b))) for a, b in list(pts) + [pts[0]]])
        solid = f.createIfcExtrudedAreaSolid(f.createIfcArbitraryClosedProfileDef("AREA", None, poly), pos, self.z_dir, float(length))
        if style:
            ifcopenshell.api.style.assign_item_style(f, item=solid, style=self.style(style))
        return solid

    FACE_DIR = {"S": ((0, -1, 0), (1, 0, 0)), "N": ((0, 1, 0), (-1, 0, 0)), "E": ((1, 0, 0), (0, 1, 0)), "W": ((-1, 0, 0), (0, -1, 0))}

    def _fprism(self, side, ox, oy, W, D, pts_uz, depth, style, d0=0.0):
        """Polygon in facade coordinates (u along the side, z up) standing `depth` metres proud of the plane at depth d0."""
        x, y = facade_xy(side, ox, oy, W, D, 0.0, d0)
        axis, ref = self.FACE_DIR[side]
        return self._prism(pts_uz, (x, y, 0.0), axis, ref, depth, style)

    def _sprism(self, side, ox, oy, W, D, pts_dz, u_pos, thick, style):
        """Polygon in the plane perpendicular to the facade (d = depth inwards, z up) at position u, `thick` metres along u."""
        x, y = facade_xy(side, ox, oy, W, D, u_pos, 0.0)
        out, uref = self.FACE_DIR[side]
        inward = (-out[0], -out[1], -out[2])
        return self._prism(pts_dz, (x, y, 0.0), uref, inward, thick, style)

    def _hprism(self, verts, axis, p0, length, style):
        """Polygon given by world points (x, y, z) in a vertical plane perpendicular to the horizontal `axis`."""
        xd = (-axis[1], axis[0], 0.0)
        pts = [((q[0] - p0[0]) * xd[0] + (q[1] - p0[1]) * xd[1], q[2]) for q in verts]
        return self._prism(pts, (p0[0], p0[1], 0.0), (axis[0], axis[1], 0.0), xd, length, style)

    @staticmethod
    def _seg_poly(p0, p1, w):
        """Thick line segment p0-p1 (2D) as a quadrilateral of width w."""
        dx, dz = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dz)
        if L < 1e-6:
            raise ValueError("brace with zero length")
        nx, nz = -dz / L * w / 2, dx / L * w / 2
        return [(p0[0] + nx, p0[1] + nz), (p1[0] + nx, p1[1] + nz), (p1[0] - nx, p1[1] - nz), (p0[0] - nx, p0[1] - nz)]

    def _gable(self, v, ox, oy, W, D, t, top, fac, roof):
        ridge = roof.get("ridge", "x")
        tn = math.tan(math.radians(float(roof.get("pitch_deg", 45))))
        cs = math.cos(math.radians(float(roof.get("pitch_deg", 45))))
        ov = float(roof.get("overhang", 0.4))
        mat = roof.get("material", "roof_tile_red")
        th = 0.2 / cs
        if ridge == "x":
            a0, a1, b0, b1 = ox, ox + W, oy, oy + D
            mk, loc, axis, ref, sides = (lambda b, z: (b, z)), (lambda a: (a, 0, 0)), (1, 0, 0), (0, 1, 0), ("W", "E")
        else:
            a0, a1, b0, b1 = oy, oy + D, ox, ox + W
            mk, loc, axis, ref, sides = (lambda b, z: (-b, z)), (lambda a: (0, a, 0)), (0, 1, 0), (-1, 0, 0), ("S", "N")
        bm = (b0 + b1) / 2
        rise = (bm - b0) * tn
        zl = lambda b: top + (b - b0) * tn
        zr = lambda b: top + (b1 - b) * tn
        left = [mk(b0 - ov, zl(b0 - ov)), mk(bm, top + rise), mk(bm, top + rise - th), mk(b0 - ov, zl(b0 - ov) - th)]
        right = [mk(b1 + ov, zr(b1 + ov)), mk(bm, top + rise), mk(bm, top + rise - th), mk(b1 + ov, zr(b1 + ov) - th)]
        length = a1 - a0 + 2 * ov
        items = [self._prism(left, loc(a0 - ov), axis, ref, length, mat), self._prism(right, loc(a0 - ov), axis, ref, length, mat)]
        self.element("IfcRoof", f"Dach {v['id']} Satteldach", items, z_ref=top, predefined="GABLE_ROOF", material="Dachziegel")
        tri = [mk(b0, top), mk(b1, top), mk(bm, top + rise - th)]
        for k, side in enumerate(sides):
            a_start = a0 if k == 0 else a1 - t
            w = self.element("IfcWall", f"Giebel {v['id']}-{side}", [self._prism(tri, loc(a_start), axis, ref, t, fac)],
                             z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
            self.pset(w, "Pset_WallCommon", {"IsExternal": True, "LoadBearing": True})
            self.walls[(v["id"], side, int(v["storeys"]))] = (w, top, rise - th, t)
        return {"sides": sides, "rise": rise, "ridge": ridge, "pitch": math.radians(float(roof.get("pitch_deg", 45))),
                "b0": b0, "b1": b1, "a0": a0, "a1": a1, "ov": ov, "mat": mat}

    def _dormers(self, v, ox, oy, W, D, t, top, fac, roof, g):
        ridge, tn = g["ridge"], math.tan(g["pitch"])
        for i, dm in enumerate(self.spec.get("dormers", [])):
            if dm["volume"] != v["id"]:
                continue
            slope = dm["slope"]
            if slope not in {"y": ("W", "E"), "x": ("S", "N")}[ridge]:
                raise ValueError(f"dormer {i}: slope {slope} does not exist on a roof with ridge {ridge} (slopes: "
                                 f"{'W/E' if ridge == 'y' else 'S/N'})")
            w, inset, wh = float(dm["width"]), float(dm.get("inset", 0.8)), float(dm.get("wall_height", 1.4))
            pd = math.radians(float(dm.get("pitch_deg", math.degrees(g["pitch"]))))
            ovd, thd, td = 0.25, 0.14 / math.cos(pd), 0.2
            fmat = dm.get("facade", fac)
            lo = g["a0"]
            a_s = lo + float(dm["offset"])
            if a_s < lo + t or a_s + w > g["a1"] - t + 1e-6:
                raise ValueError(f"dormer {i} exceeds the roof length ({a_s - lo + w:.2f} > {g['a1'] - lo:.2f} m)")
            low = slope in ("W", "S")
            b_edge = g["b0"] if low else g["b1"]
            sg = 1 if low else -1
            bm = (g["b0"] + g["b1"]) / 2
            b_f = b_edge + sg * inset
            zs = lambda b: top + abs(b - b_edge) * tn
            z_fb, z_ft = zs(b_f) - 0.2, zs(b_f) + wh
            a_c = a_s + w / 2
            z_rd = z_ft + (w / 2 + ovd) * math.tan(pd)
            b_r = b_edge + sg * (z_ft - top) / tn
            b_x = b_edge + sg * (z_rd - top) / tn
            if abs(b_x - b_edge) >= abs(bm - b_edge) - 0.05:
                raise ValueError(f"dormer {i} is too tall: its ridge ({z_rd:.2f} m) would reach the main ridge; lower wall_height or inset")
            mkw = (lambda b, a, z: (b, a, z)) if ridge == "y" else (lambda b, a, z: (a, b, z))
            ax_a = (0, 1, 0) if ridge == "y" else (1, 0, 0)
            ax_b = {"W": (1, 0, 0), "E": (-1, 0, 0), "S": (0, 1, 0), "N": (0, -1, 0)}[slope]
            cheek = [mkw(b_f, 0, z_fb), mkw(b_f, 0, z_ft), mkw(b_r, 0, z_ft), mkw(b_r, 0, zs(b_r) - 0.2)]
            for k, a_k in enumerate((a_s, a_s + w - td)):
                vt = [(q[0] if ridge == "y" else a_k, q[1] if ridge == "x" else a_k, q[2]) for q in cheek]
                self.element("IfcWall", f"Gaube {i + 1} Wange {k + 1}", [self._hprism(vt, ax_a, vt[0], td, fmat)], z_ref=top,
                             predefined="SOLIDWALL", material="Mauerwerk verputzt")
            # front wall with window (facade coordinates of a virtual volume whose side plane is the dormer front)
            M = 1000.0
            vv = {"S": ((0.0, b_f), "S"), "N": ((0.0, b_f - M), "N"), "E": ((b_f - M, 0.0), "E"), "W": ((b_f, 0.0), "W")}[slope]
            (vox, voy), side = vv
            c0, c1 = a_s, a_s + w
            u0, u1 = {"S": (c0, c1), "N": (M - c1, M - c0), "E": (c0, c1), "W": (M - c1, M - c0)}[slope]
            vd = {"origin": [vox, voy], "size": [M, M]}
            fw = self.element("IfcWall", f"Gaube {i + 1} Front", [self.box(*facade_box(side, vox, voy, M, M, u0, u1, 0.0, td, z_fb, z_ft), fmat)],
                              z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
            win = dm.get("window", {})
            ww = float(win.get("width", min(w - 0.5, 1.0)))
            wsill = float(win.get("sill", 0.2))
            wh_ = float(win.get("height", max(0.6, wh - 0.45)))
            zb = zs(b_f) + wsill
            zt = zb + wh_
            if zt > z_ft - 0.05 or ww > w - 0.2:
                raise ValueError(f"dormer {i}: window does not fit the dormer front (top {zt:.2f} > {z_ft - 0.05:.2f} m or width > {w - 0.2:.2f} m)")
            cu = (u0 + u1) / 2
            wu0, wu1 = cu - ww / 2, cu + ww / 2
            ob = facade_box(side, vox, voy, M, M, wu0, wu1, -0.05, td + 0.05, zb, zt)
            op = self.element("IfcOpeningElement", f"Oeffnung Gaube {i + 1}", [self.box(*ob, None)], z_ref=top, predefined="OPENING", container=False)
            ifcopenshell.api.feature.add_feature(self.f, feature=op, element=fw)
            wo = {"kind": "window", "note": f"Fenster Gaube {i + 1}", "mullion_spacing": float(win.get("mullion_spacing", 0))}
            ifcopenshell.api.feature.add_filling(self.f, opening=op, element=self._window(wo, vd, side, wu0, wu1, zb, zt, wsill))
            # front gable triangle + roof (ridge perpendicular to the main ridge)
            pf = mkw(b_f, 0, 0)
            def tri(a0_, a1_, ac_, zb_, zt_):
                return [(mkw(b_f, a0_, zb_)), (mkw(b_f, a1_, zb_)), (mkw(b_f, ac_, zt_))]
            self.element("IfcWall", f"Gaube {i + 1} Giebel", [self._hprism(tri(a_s, a_s + w, a_c, z_ft, z_ft + (w / 2) * math.tan(pd)),
                                                                         ax_b, mkw(b_f, a_s, 0), td, fmat)],
                         z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
            a_l, a_r = a_s - ovd, a_s + w + ovd
            pl = [mkw(b_f, a_l, z_ft), mkw(b_f, a_c, z_rd), mkw(b_f, a_c, z_rd - thd), mkw(b_f, a_l, z_ft - thd)]
            pr = [mkw(b_f, a_r, z_ft), mkw(b_f, a_c, z_rd), mkw(b_f, a_c, z_rd - thd), mkw(b_f, a_r, z_ft - thd)]
            start = tuple(c - sg * 0 for c in mkw(b_f - sg * ovd, a_s, 0))
            sh = lambda pts: [mkw(b_f - sg * ovd, q[1] if ridge == "y" else q[0], q[2]) for q in pts]
            roof_len = abs(b_x - b_f) + ovd + 0.05
            self.element("IfcRoof", f"Gaube {i + 1} Dach", [self._hprism(sh(pl), ax_b, start[:2], roof_len, g["mat"]),
                                                          self._hprism(sh(pr), ax_b, start[:2], roof_len, g["mat"])],
                         z_ref=top, predefined="GABLE_ROOF", material="Dachziegel")

    def _facade_elements(self):
        """Hand-placed facade members (timber frame, brackets, ornaments): polygons in (u, z) standing proud of the wall."""
        rect = lambda u0, u1, z0, z1: [(u0, z0), (u1, z0), (u1, z1), (u0, z1)]
        for k, fe in enumerate(self.spec.get("facade_elements", [])):
            v = self.vol[fe["volume"]]
            ox, oy = v["origin"]
            W, D = v["size"]
            side = fe["side"]
            L = side_length(side, W, D)
            base = float(v["base_z"])
            dep0, mat0 = float(fe.get("depth", 0.07)), fe.get("material", "timber_dark")
            solids = []
            for j, it in enumerate(fe["items"]):
                # members of different kinds stand a hair apart so overlapping faces never coincide (no z-fighting)
                kind_off = {"post": 0.0, "beam": 0.012, "brace": 0.024, "rect": 0.006, "poly": 0.036}
                dep = float(it.get("depth", dep0)) + next((o for kk, o in kind_off.items() if kk in it), 0.0)
                mat = it.get("material", mat0)
                try:
                    if "post" in it:
                        u, z0, z1 = [float(x) for x in it["post"]]
                        w = float(it.get("w", 0.14))
                        pts = rect(u - w / 2, u + w / 2, z0, z1)
                    elif "beam" in it:
                        u0, u1, z0 = [float(x) for x in it["beam"]]
                        pts = rect(u0, u1, z0, z0 + float(it.get("h", 0.16)))
                    elif "brace" in it:
                        u0, z0, u1, z1 = [float(x) for x in it["brace"]]
                        pts = self._seg_poly((u0, z0), (u1, z1), float(it.get("w", 0.12)))
                    elif "rect" in it:
                        u0, u1, z0, z1 = [float(x) for x in it["rect"]]
                        pts = rect(u0, u1, z0, z1)
                    elif "poly" in it:
                        pts = [(float(a), float(b)) for a, b in it["poly"]]
                    else:
                        raise ValueError("unknown item (use post, beam, brace, rect or poly)")
                except (TypeError, ValueError) as e:
                    raise ValueError(f"facade_elements[{k}] item {j}: {e}")
                if len(pts) < 3 or any(p[0] < -0.02 or p[0] > L + 0.02 for p in pts):
                    raise ValueError(f"facade_elements[{k}] item {j} lies outside the facade {fe['volume']}-{side} (u must be 0..{L:.2f})")
                if any(p[1] < -0.02 for p in pts):
                    raise ValueError(f"facade_elements[{k}] item {j}: z is height above the volume base and must be >= 0")
                solids.append(self._fprism(side, ox, oy, W, D, [(a, base + b) for a, b in pts], dep, mat))
            if solids:
                self.element("IfcMember", f"Fassadendetail {fe['volume']}-{side}", solids, z_ref=base, predefined="MEMBER", material="Holz")

    def _timber_balcony(self, b, side, ox, oy, W, D, u0, u1, dep, th, lvl):
        """Balcony in timber: deck, fascia, posts with caps, turned balusters, top rail, curved-looking diagonal brackets."""
        mat = b.get("material", "timber_dark")
        r = b.get("railing") or {}
        H = float(r.get("height", 1.0))
        sp = float(r.get("post_spacing", 0.12))
        rect = lambda a0, a1, z0, z1: [(a0, z0), (a1, z0), (a1, z1), (a0, z1)]
        items = [self.box(*facade_box(side, ox, oy, W, D, u0, u1, -dep, 0.0, lvl - th, lvl), mat),
                 self._fprism(side, ox, oy, W, D, rect(u0 - 0.03, u1 + 0.03, lvl - th - 0.12, lvl - th), 0.1, mat, d0=-dep + 0.08)]
        post = 0.1
        # silhouette of a turned baluster: (height fraction, half width)
        prof = [(0, 0.012), (0.08, 0.012), (0.12, 0.026), (0.2, 0.014), (0.3, 0.014), (0.38, 0.03), (0.5, 0.036), (0.62, 0.03),
                (0.7, 0.014), (0.8, 0.014), (0.88, 0.026), (0.92, 0.012), (1.0, 0.012)]
        hb = H - 0.2

        def baluster(c, z0):
            left = [(c - w_, z0 + f * hb) for f, w_ in prof]
            return left + [(c + w_, z0 + f * hb) for f, w_ in reversed(prof)]
        zb0 = lvl + 0.1
        front_d = -dep + 0.1
        sides = r.get("sides", ["front", "left", "right"])
        if "front" in sides:
            n = max(1, round((u1 - u0 - 2 * post) / sp))
            for k in range(n + 1):
                c = u0 + post + k * (u1 - u0 - 2 * post) / n
                items.append(self._fprism(side, ox, oy, W, D, baluster(c, zb0), 0.04, mat, d0=front_d - 0.02))
            for za in (lvl + H - 0.1, lvl + 0.04):
                items.append(self._fprism(side, ox, oy, W, D, rect(u0, u1, za, za + 0.1), 0.09, mat, d0=front_d + 0.02))
        for flag, upos in (("left", u0), ("right", u1 - 0.05)):
            if flag not in sides:
                continue
            n = max(1, round((dep - 0.2) / sp))
            for k in range(n + 1):
                d = -dep + post + k * (dep - post - 0.05) / n
                items.append(self._sprism(side, ox, oy, W, D, baluster(d, zb0), upos + 0.005, 0.04, mat))
            for za in (lvl + H - 0.1, lvl + 0.04):
                items.append(self._sprism(side, ox, oy, W, D, rect(-dep + 0.04, 0.0, za, za + 0.1), upos, 0.05, mat))
        for uc in (u0 + 0.04, u1 - 0.04 - post):
            if (uc == u0 + 0.04 and "left" in sides or "front" in sides) or True:
                items.append(self._fprism(side, ox, oy, W, D, rect(uc, uc + post, lvl - th, lvl + H + 0.06), post, mat, d0=-dep + 0.05 + post))
                items.append(self._fprism(side, ox, oy, W, D, rect(uc - 0.02, uc + post + 0.02, lvl + H + 0.06, lvl + H + 0.1), post + 0.04, mat, d0=-dep + 0.07 + post))
        # diagonal brackets under the deck, with a small curved-looking notch
        for upos in (u0 + 0.15, u1 - 0.25):
            bl = min(0.8, dep - 0.1)
            seg = self._seg_poly((-0.02, lvl - th - bl), (-dep + 0.1, lvl - th - 0.03), 0.14)
            items.append(self._sprism(side, ox, oy, W, D, seg, upos, 0.1, mat))
        self.element("IfcRailing", "Holzbalkon Bruestung", items, z_ref=lvl, predefined="GUARDRAIL", material="Holz")

    def _plinth(self, v, side, ox, oy, W, D, L, z0, ph, pl):
        """Natural-stone plinth: irregular courses of single stones (different sizes, depths and tones); doors break through it (no stone in the doorway)."""
        import random
        import zlib
        rnd = random.Random(zlib.crc32(f"{v['id']}{side}".encode()))
        doors = [(float(o["offset"]) - 0.02, float(o["offset"]) + float(o["width"]) + 0.02) for o in self.spec.get("openings", [])
                 if o["volume"] == v["id"] and o["side"] == side and int(o["storey"]) == 0 and o.get("kind") == "door"
                 and float(o.get("sill", 0.0)) < ph]
        spans = subtract_intervals((0.0, L), doors)
        mat = pl.get("material", "stone_plinth")
        tones = [mat, "stone_field", "stone_sandstone_yellow", "stone_sandstone_red", "stone_granite_grey", "stone_basalt_dark", "stone_limestone"]
        items = []
        for a, b in spans:
            if b - a < 0.1:
                continue
            items.append(self._fprism(side, ox, oy, W, D, [(a, z0), (b, z0), (b, z0 + ph), (a, z0 + ph)], 0.03, mat))      # mortar bed
            z = z0
            while z < z0 + ph - 0.05:
                hc = min(rnd.uniform(0.16, 0.27), z0 + ph - z)
                u = a + rnd.uniform(0.0, 0.25)
                u = a
                while u < b - 0.05:
                    ln = rnd.uniform(0.28, 0.78)
                    u1 = min(u + ln, b)
                    if b - u1 < 0.2:
                        u1 = b
                    gap = 0.012
                    pts = [(u + gap, z + gap), (u1 - gap, z + gap), (u1 - gap, z + hc - gap), (u + gap, z + hc - gap)]
                    items.append(self._fprism(side, ox, oy, W, D, pts, rnd.uniform(0.05, 0.09), rnd.choice(tones) if rnd.random() < 0.55 else mat))
                    u = u1
                z += hc
        if items:
            self.element("IfcBuildingElementProxy", f"Sockel {v['id']}-{side}", items, z_ref=z0, predefined="USERDEFINED", material="Naturstein")
        for d0, d1 in doors:        # carved wooden door frame (Türrahmen) with a heavy lintel, standing proud of the stone and timber
            hgt = max((float(o.get("sill", 0.0)) + float(o["height"]) for o in self.spec.get("openings", [])
                       if o["volume"] == v["id"] and o["side"] == side and int(o["storey"]) == 0 and o.get("kind") == "door"
                       and abs(float(o["offset"]) - 0.02 - d0) < 0.01), default=2.1)
            fw = 0.14
            frame = [[(d0 - fw, z0), (d0, z0), (d0, z0 + hgt + 0.18), (d0 - fw, z0 + hgt + 0.18)],
                     [(d1, z0), (d1 + fw, z0), (d1 + fw, z0 + hgt + 0.18), (d1, z0 + hgt + 0.18)],
                     [(d0 - fw, z0 + hgt), (d1 + fw, z0 + hgt), (d1 + fw, z0 + hgt + 0.18), (d0 - fw, z0 + hgt + 0.18)]]
            self.element("IfcBuildingElementProxy", f"Türrahmen {v['id']}-{side}", [self._fprism(side, ox, oy, W, D, p, 0.1, "timber_oak_aged") for p in frame],
                         z_ref=z0, predefined="USERDEFINED", material="Eichenholz")

    def _detail(self, v, ox, oy, W, D, base, n, h, top, gable):
        det = v.get("facade_detail") or {}
        tf, pl = det.get("timber_frame"), det.get("plinth")
        if not tf and not pl:
            return
        ph = float(pl.get("height", 0.7)) if pl else 0.0
        bw = float(tf.get("post_width", 0.14)) if tf else 0.14
        dep = float(tf.get("depth", 0.07)) if tf else 0.07
        sp = float(tf.get("spacing", 1.1)) if tf else 1.1
        tmat = tf.get("material", "timber_dark") if tf else None
        band, rect = 0.2, (lambda u0, u1, z0, z1: [(u0, z0), (u1, z0), (u1, z1), (u0, z1)])
        for side in SIDES:
            L = side_length(side, W, D)
            for s in range(n + (1 if gable and side in gable["sides"] else 0)):
                attic = s == n
                z0 = base + s * h
                hz = (lambda u: gable["rise"] * (1 - abs(2 * u / L - 1))) if attic else (lambda u: h)
                if s == 0 and pl:
                    self._plinth(v, side, ox, oy, W, D, L, z0, ph, pl)
                if not tf or (v["id"], side) in {(e["volume"], e["side"]) for e in self.spec.get("facade_elements", [])}:
                    continue
                ops = [(float(o["offset"]), float(o["offset"]) + float(o["width"]), z0 + float(o.get("sill", 0.0)),
                        z0 + float(o.get("sill", 0.0)) + float(o["height"]), o.get("kind", "window") == "door")
                       for o in self.spec.get("openings", [])
                       if o["volume"] == v["id"] and o["side"] == side and int(o["storey"]) == s]
                zlo = z0 + (ph + 0.16 if s == 0 else 0.0)
                # Traufseite des obersten Geschosses: die Dachhaut liegt dort knapp über der Wandkrone – das Rähmband liegt darunter, sonst sticht es als dunkler Strich durch die Ziegel
                bsh = 0.14 if (not attic and s == n - 1 and not (gable and side in gable["sides"]) and (v.get("roof") or {}).get("type") not in (None, "flat")) else 0.0
                zhi = z0 + h - band - bsh if not attic else z0 + gable["rise"]
                polys = []
                if not attic:
                    if s == 0:       # Schwelle: unterbrochen, wo eine Tür die Wand öffnet (kein Balken durch die Tür)
                        cuts = sorted((max(0.0, o[0] - bw), min(L, o[1] + bw)) for o in ops if o[4] and o[2] < z0 + ph + 0.16 and o[3] > z0 + ph)
                        xs = 0.0
                        for c0, c1 in cuts + [(L, L)]:
                            if c0 - xs > 0.05:
                                polys.append(rect(xs, c0, z0 + ph, z0 + ph + 0.16))
                            xs = max(xs, c1)
                    polys.append(rect(0.0, L, z0 + h - band - bsh, z0 + h - bsh))
                pattern = tf.get("pattern") or ("mixed" if tf.get("braces", True) else "none")
                hit = lambda a, b, ex=0.05: any(a < o[1] + ex and b > o[0] - ex for o in ops)
                if not attic:
                    frame_polys, _posts, _bays = fachwerk.plan_wall(L, zlo, zhi, ops, sp, bw, pattern)       # posts at every jamb, bracing per bay
                    polys += frame_polys
                else:
                    dz = 0.07 / math.cos(gable["pitch"]) + 0.08      # Ortgangbalken liegt ganz unter der Dachhaut (sonst sticht er als brauner Strich durch die Ziegel)
                    rise = float(gable["rise"])
                    for p0, p1 in (((0.0, z0 - dz), (L / 2, z0 + rise - dz)), ((L, z0 - dz), (L / 2, z0 + rise - dz))):
                        polys.append(self._seg_poly(p0, p1, 0.14))
                    polys += fachwerk.plan_gable(L, z0, rise, ops, sp, bw, pattern)
                if polys:
                    self.element("IfcMember", f"Fachwerk {v['id']}-{side} G{s}",
                                 [self._fprism(side, ox, oy, W, D, pg, dep, tmat) for pg in polys],
                                 z_ref=z0, predefined="MEMBER", material="Holz")

    @staticmethod
    def _wall_rect(side, ox, oy, W, D, t):
        if side == "S":
            return ox, oy, 0, W, t, 0
        if side == "N":
            return ox, oy + D - t, 0, W, t, 0
        if side == "W":
            return ox, oy + t, 0, t, D - 2 * t, 0
        return ox + W - t, oy + t, 0, t, D - 2 * t, 0

    def _parapets(self, v, ox, oy, W, D, t, top, fac):
        ph = float(v.get("parapet_height", self.parapet_h))
        for side in SIDES:
            L = side_length(side, W, D)
            cuts = []
            for u in self.spec.get("volumes", []):
                if u is v or abs(float(u["base_z"]) - top) > 1e-6:
                    continue
                uox, uoy = u["origin"]
                uW, uD = u["size"]
                if side == "S" and abs(uoy - oy) < 1e-6:
                    cuts.append((uox - ox, uox + uW - ox))
                elif side == "N" and abs(uoy + uD - (oy + D)) < 1e-6:
                    cuts.append((ox + W - (uox + uW), ox + W - uox))
                elif side == "E" and abs(uox + uW - (ox + W)) < 1e-6:
                    cuts.append((uoy - oy, uoy + uD - oy))
                elif side == "W" and abs(uox - ox) < 1e-6:
                    cuts.append((oy + D - (uoy + uD), oy + D - uoy))
            for a, b in subtract_intervals((0.0, L), cuts):
                # corner handling: S/N run full length, E/W between them
                if side in ("E", "W"):
                    a, b = max(a, t), min(b, L - t)
                    if b - a < 0.01:
                        continue
                x, y, z, dx, dy, dz = facade_box(side, ox, oy, W, D, a, b, 0.0, t, top, top + ph)
                cap = facade_box(side, ox, oy, W, D, a, b, -0.03, t + 0.03, top + ph, top + ph + 0.04)
                el = self.element("IfcWall", f"Attika {v['id']}-{side}",
                                  [self.box(x, y, z, dx, dy, dz, fac), self.box(*cap, "aluminium")],
                                  z_ref=top, predefined="PARAPET", material="Mauerwerk verputzt")
                self.pset(el, "Pset_WallCommon", {"IsExternal": True})

    # ---------------------------------------------------------------- openings
    def openings(self):
        for i, o in enumerate(self.spec.get("openings", [])):
            v = self.vol[o["volume"]]
            self.cur_obj = self.vobj.get(v["id"])
            ox, oy = v["origin"]
            W, D = v["size"]
            side, s = o["side"], int(o["storey"])
            if (v["id"], side, s) not in self.walls:
                have = sorted(k[1:] for k in self.walls if k[0] == v["id"])
                raise ValueError(f"opening {i}: volume {v['id']} has no wall on side {side} at storey {s} "
                                 f"(walls exist for storeys 0..{int(v['storeys']) - 1}, gable walls at storey {int(v['storeys'])} only on gable sides; existing (side, storey): {have})")
            wall, z0, h, t = self.walls[(v["id"], side, s)]
            u0 = float(o["offset"])
            u1 = u0 + float(o["width"])
            L = side_length(side, W, D)
            if u0 < -1e-6 or u1 > L + 1e-6:
                raise ValueError(f"opening {i} exceeds facade {v['id']}-{side} ({u1:.2f} > {L:.2f})")
            sill = float(o.get("sill", 0.0))
            hgt = float(o["height"])
            if sill + hgt > h + 1e-6:
                raise ValueError(f"opening {i} taller than storey")
            if s == int(v["storeys"]):  # opening in the gable triangle: it must fit inside the triangle
                rise = h  # h = rise of the gable for this wall
                for uu in (u0, u1):
                    allow = rise * (1 - abs(2 * uu / L - 1))
                    if sill + hgt > allow + 1e-6:
                        raise ValueError(f"opening {i} sticks out of the gable triangle {v['id']}-{side} (allowed height at "
                                         f"u={uu:.2f}: {allow:.2f} m, requested top {sill + hgt:.2f} m)")
            zb, zt = z0 + sill, z0 + sill + hgt
            ob = facade_box(side, ox, oy, W, D, u0, u1, -0.05, t + 0.05, zb, zt)
            op = self.element("IfcOpeningElement", f"Oeffnung {i}", [self.box(*ob, None)], z_ref=z0,
                              predefined="OPENING", container=False)
            ifcopenshell.api.feature.add_feature(self.f, feature=op, element=wall)
            # corner openings also cut the perpendicular wall's end
            for other in self._corner_walls(v, side, s, u0, u1, L, t):
                op2 = self.element("IfcOpeningElement", f"Oeffnung {i} Ecke", [self.box(*ob, None)], z_ref=z0,
                                   predefined="OPENING", container=False)
                ifcopenshell.api.feature.add_feature(self.f, feature=op2, element=other)
            fill = self._window(o, v, side, u0, u1, zb, zt, sill)
            ifcopenshell.api.feature.add_filling(self.f, opening=op, element=fill)
            self._opening_extras(o, v, side, u0, u1, zb, zt, sill)

    def _corner_walls(self, v, side, s, u0, u1, L, t):
        # S/N walls run full length, so an E/W opening touching the corner must cut S/N wall ends.
        res = []
        if side in ("E", "W"):
            if u0 <= t + 1e-6 and (v["id"], "S" if side == "E" else "N", s) in self.walls:
                res.append(self.walls[(v["id"], "S" if side == "E" else "N", s)][0])
            if u1 >= L - t - 1e-6 and (v["id"], "N" if side == "E" else "S", s) in self.walls:
                res.append(self.walls[(v["id"], "N" if side == "E" else "S", s)][0])
        return res

    def _window(self, o, v, side, u0, u1, zb, zt, sill):
        if o.get("kind", "window") == "door" and (o.get("door_type") or o.get("top") or o.get("transom")):
            return self._door_ext(o, v, side, u0, u1, zb, zt)
        if o.get("kind", "window") == "window" and (set(o) & WINDOW_KEYS):
            return self._window_ext(o, v, side, u0, u1, zb, zt, sill)
        ox, oy = v["origin"]
        W, D = v["size"]
        fw, fd = self.win["frame_width"], self.win["frame_depth"]
        rd = float(o.get("reveal_depth", self.win["reveal_depth"]))
        fr = o.get("frame", self.win["frame"])
        fb = lambda a, b, c, e, z0, z1, st: self.box(*facade_box(side, ox, oy, W, D, a, b, c, e, z0, z1), st)
        d0, d1 = rd, rd + fd
        items = [fb(u0, u0 + fw, d0, d1, zb, zt, fr), fb(u1 - fw, u1, d0, d1, zb, zt, fr),
                 fb(u0 + fw, u1 - fw, d0, d1, zb, zb + fw, fr), fb(u0 + fw, u1 - fw, d0, d1, zt - fw, zt, fr)]
        kind = o.get("kind", "window")
        dm = (d0 + d1) / 2
        if kind == "door":
            panel = o.get("panel", "walnut")
            items.append(fb(u0 + fw, u1 - fw, dm - 0.03, dm + 0.03, zb + fw, zt - fw, panel))
            hz = zb + 1.05
            items.append(fb(u1 - fw - 0.16, u1 - fw - 0.12, d0 - 0.06, d0, hz - 0.5, hz + 0.5, "chrome"))
            el = self.element("IfcDoor", o.get("note", "Tuer"), items, z_ref=zb, predefined="DOOR")
            el.OverallWidth, el.OverallHeight = u1 - u0, zt - zb
            return el
        sp = float(o.get("mullion_spacing", 0) or 0)
        width = u1 - u0
        n = max(1, round(width / sp)) if sp > 0 else 1
        mw = fw * 0.8
        for k in range(1, n):
            um = u0 + k * width / n
            items.append(fb(um - mw / 2, um + mw / 2, d0, d1, zb + fw, zt - fw, fr))
        items.append(fb(u0 + fw, u1 - fw, dm - 0.012, dm + 0.012, zb + fw, zt - fw, self.win["glass"]))
        if sill > 0 and self.win.get("sill_board", True):
            items.append(fb(u0 - 0.03, u1 + 0.03, -0.05, d0, zb - 0.03, zb, "aluminium"))
        el = self.element("IfcWindow", o.get("note", "Fenster"), items, z_ref=zb,
                          predefined="WINDOW", material="Stahl/Glas")
        el.OverallWidth, el.OverallHeight = width, zt - zb
        return el

    # ---------------------------------------------------------------- curtain wall + stair
    def curtain_walls(self):
        for cw in self.spec.get("curtain_walls", []):
            ox, oy = cw["origin"]
            W, D = cw["size"]
            gx, gz = cw["grid"]
            mw = float(cw.get("mullion", 0.06))
            md = float(cw.get("mullion_depth", 0.12))
            top = float(cw["top_z"])
            wall = ifcopenshell.api.root.create_entity(self.f, ifc_class="IfcCurtainWall", name=cw["name"])
            ifcopenshell.api.geometry.edit_object_placement(self.f, product=wall)
            ifcopenshell.api.spatial.assign_container(self.f, products=[wall], relating_structure=self.storeys[0][1])
            parts = []
            for face in cw["faces"]:
                side = face["side"]
                L = side_length(side, W, D)
                a, b = face.get("span", (0.0, L))
                z0, z1 = float(face["z0"]), float(face["z1"])
                fb = lambda u0, u1, d0, d1, za, zb_: facade_box(side, ox, oy, W, D, u0, u1, d0, d1, za, zb_)
                parts.append(self.element("IfcPlate", f"Glas {side}",
                                          [self.box(*fb(a, b, md / 2 - 0.01, md / 2 + 0.01, z0, z1), "glass_clear")],
                                          z_ref=z0, predefined="CURTAIN_PANEL", container=False))
                items = []
                nu = max(1, round((b - a) / gx))
                for k in range(nu + 1):
                    u = a + k * (b - a) / nu
                    uu0, uu1 = max(a, u - mw / 2), min(b, u + mw / 2)
                    items.append(self.box(*fb(uu0, uu1, 0.0, md, z0, z1), "steel_black"))
                nz = max(1, round((z1 - z0) / gz))
                for k in range(nz + 1):
                    z = z0 + k * (z1 - z0) / nz
                    za, zb_ = max(z0, z - mw / 2), min(z1, z + mw / 2)
                    items.append(self.box(*fb(a, b, -0.005, md + 0.005, za, zb_), "steel_black"))
                parts.append(self.element("IfcMember", f"Pfosten/Riegel {side}", items, z_ref=z0,
                                          predefined="MULLION", container=False))
            cap = self.element("IfcSlab", "Dach Glasturm",
                               [self.box(ox - 0.05, oy - 0.05, top - 0.25, W + 0.1, D + 0.1, 0.25, "steel_black")],
                               z_ref=top, predefined="ROOF", container=False)
            parts.append(cap)
            ifcopenshell.api.aggregate.assign_object(self.f, products=parts, relating_object=wall)
            if cw.get("stair"):
                self._stair(cw, ox, oy, W, D, top)

    def _stair(self, cw, ox, oy, W, D, top):
        st = cw["stair"]
        mat = st.get("material", "concrete_exposed")
        h = self.storey_h
        nr = int(st["riser_count"])
        half = nr // 2
        rise = h / nr
        going = float(st["tread_depth"])
        lw = float(st["width"])
        ld = float(st["landing_depth"])
        inner_x0, inner_x1 = ox + 0.15, ox + W - 0.15
        run = (half - 1) * going
        y_s0 = oy + (D - (2 * ld + run)) / 2
        y_s1 = y_s0 + ld
        y_n0 = y_s1 + run
        y_n1 = y_n0 + ld
        stair = ifcopenshell.api.root.create_entity(self.f, ifc_class="IfcStair", name="Treppe Glasturm")
        ifcopenshell.api.geometry.edit_object_placement(self.f, product=stair)
        ifcopenshell.api.spatial.assign_container(self.f, products=[stair], relating_structure=self.storeys[0][1])
        parts = []
        n_storeys = int(round((top - 0.6) // h))
        for k in range(n_storeys):
            z = k * h
            lanes = [(inner_x0, inner_x0 + lw, +1), (inner_x1 - lw, inner_x1, -1)]
            for j, (x0, x1, direction) in enumerate(lanes):
                zs = z + j * h / 2
                items = []
                for i in range(half - 1):
                    ztop = zs + (i + 1) * rise
                    if direction > 0:
                        y0 = y_s1 + i * going
                    else:
                        y0 = y_n0 - (i + 1) * going
                    items.append(self.box(x0, y0, ztop - 0.22, x1 - x0, going, 0.22, mat))
                parts.append(self.element("IfcStairFlight", f"Lauf G{k}-{j + 1}", items, z_ref=zs,
                                          predefined="STRAIGHT", container=False))
            parts.append(self.element("IfcSlab", f"Podest G{k} Mitte",
                                      [self.box(inner_x0, y_n0, z + h / 2 - 0.2, inner_x1 - inner_x0, ld, 0.2, mat)],
                                      z_ref=z, predefined="LANDING", container=False))
            parts.append(self.element("IfcSlab", f"Podest G{k + 1}",
                                      [self.box(inner_x0, y_s0, z + h - 0.2, inner_x1 - inner_x0, ld, 0.2, mat)],
                                      z_ref=z + h, predefined="LANDING", container=False))
        ifcopenshell.api.aggregate.assign_object(self.f, products=parts, relating_object=stair)

    # ---------------------------------------------------------------- balconies, pergolas, site
    def balconies(self):
        for b in self.spec.get("balconies", []):
            v = self.vol[b["volume"]]
            self.cur_obj = self.vobj.get(v["id"])
            ox, oy = v["origin"]
            W, D = v["size"]
            side = b["side"]
            u0 = float(b["offset"])
            u1 = u0 + float(b["width"])
            dep, th, lvl = float(b["depth"]), float(b["thickness"]), float(b["level"])
            if b.get("style") == "timber":
                self._timber_balcony(b, side, ox, oy, W, D, u0, u1, dep, th, lvl)
                continue
            self.element("IfcSlab", "Balkon", [self.box(*facade_box(side, ox, oy, W, D, u0, u1, -dep, 0.0, lvl - th, lvl),
                                                        "concrete_exposed")], z_ref=lvl, predefined="FLOOR",
                         material="Stahlbeton")
            r = b.get("railing")
            if not r:
                continue
            H = float(r["height"])
            if r.get("type", "rails") != "rails":
                items = self._railing_items(v, side, u0, u1, dep, lvl, r["type"], H, r.get("material", "steel_black"),
                                            tuple({"front": "front", "left": "left", "right": "right"}[x] for x in r["sides"]))
                self.element("IfcRailing", "Balkongelaender", items, z_ref=lvl, predefined="GUARDRAIL", material="Stahl")
                continue
            P = lambda u, d, z: (*facade_xy(side, ox, oy, W, D, u, d), z)
            st = r.get("material", "chrome")
            rh, rr = float(r.get("handrail_d", 0.04)) / 2, float(r.get("rail_d", 0.016)) / 2
            dF = -dep + 0.06
            lines = []
            if "front" in r["sides"]:
                lines.append(((u0 + 0.05, dF), (u1 - 0.05, dF)))
            if "left" in r["sides"]:
                lines.append(((u0 + 0.05, dF), (u0 + 0.05, -0.05)))
            if "right" in r["sides"]:
                lines.append(((u1 - 0.05, dF), (u1 - 0.05, -0.05)))
            items = []
            for (ua, da), (ub, db) in lines:
                items.append(self.cylinder(P(ua, da, lvl + H), P(ub, db, lvl + H), rh, st))
                for zr in r.get("rails_at", []):
                    items.append(self.cylinder(P(ua, da, lvl + zr), P(ub, db, lvl + zr), rr, st))
                L = math.hypot(ub - ua, db - da)
                n = max(1, math.ceil(L / float(r.get("post_spacing", 1.2))))
                for k in range(n + 1):
                    t = k / n
                    u, d = ua + t * (ub - ua), da + t * (db - da)
                    items.append(self.cylinder(P(u, d, lvl), P(u, d, lvl + H), 0.015, st))
            self.element("IfcRailing", "Balkongelaender", items, z_ref=lvl, predefined="GUARDRAIL",
                         material="Stahl verchromt")

    def pergolas(self):
        for p in self.spec.get("pergolas", []):
            ox, oy = p["origin"]
            W, D = p["size"]
            z0, H = float(p["base_z"]), float(p["height"])
            ps = float(p["post"])
            bw, bh = p["beam"]
            sw, sh = p["slat"]
            m = p.get("material", "steel_black")
            cols = [self.box(x, y, z0, ps, ps, H, m) for x in (ox, ox + W - ps) for y in (oy, oy + D - ps)]
            self.element("IfcColumn", f"{p['name']} Stuetzen", cols, z_ref=z0, predefined="COLUMN", material="Stahl")
            beams = [self.box(ox - 0.1, y, z0 + H, W + 0.2, bw, bh, m) for y in (oy, oy + D - bw)]
            self.element("IfcBeam", f"{p['name']} Traeger", beams, z_ref=z0, predefined="BEAM", material="Stahl")
            slats = []
            n = int(W // float(p["slat_spacing"]))
            for k in range(n + 1):
                x = ox + k * (W - sw) / n
                slats.append(self.box(x, oy - 0.15, z0 + H + bh, sw, D + 0.3, sh, m))
            self.element("IfcMember", f"{p['name']} Lamellen", slats, z_ref=z0, predefined="RAFTER", material="Stahl")

    @staticmethod
    def _corners(ox, oy, W, D):
        return [(ox, oy), (ox + W, oy), (ox, oy + D), (ox + W, oy + D), (ox + W / 2, oy + D / 2)]

    def site_elements(self):
        site = self.spec.get("site", {})
        self.cur_obj = None
        for _i, pv in enumerate(site.get("paving", [])):
            self.cur_obj = f"site.paving.{_i}"
            ox, oy = pv["origin"]
            W, D = pv["size"]
            tx, ty = pv["tile"]
            j, th = float(pv["joint"]), float(pv["thickness"])
            items = []
            for i in range(int(round(W / tx))):
                for k in range(int(round(D / ty))):
                    items.append(self.box(ox + i * tx + j / 2, oy + k * ty + j / 2, 0.0, tx - j, ty - j, th,
                                          pv.get("material", "paving_concrete")))
            self.element("IfcBuildingElementProxy", pv["name"], items, predefined="USERDEFINED", material="Betonplatten",
                         dz=self.ground_z(*self._corners(ox, oy, W, D)))
        for _i, pl in enumerate(site.get("pools", [])):
            self.cur_obj = f"site.pools.{_i}"
            ox, oy = pl["origin"]
            W, D = pl["size"]
            dep, c, ch = float(pl["depth"]), float(pl["coping"]), float(pl["coping_height"])
            cm = "concrete_exposed"
            items = [self.box(ox - c, oy - c, -0.2, W + 2 * c, c, ch + 0.2, cm),
                     self.box(ox - c, oy + D, -0.2, W + 2 * c, c, ch + 0.2, cm),
                     self.box(ox - c, oy, -0.2, c, D, ch + 0.2, cm),
                     self.box(ox + W, oy, -0.2, c, D, ch + 0.2, cm),
                     self.box(ox, oy, -dep - 0.2, W, D, 0.2, cm)]
            self.element("IfcBuildingElementProxy", pl["name"] + " Becken", items, predefined="USERDEFINED",
                         material="Sichtbeton")
            self.element("IfcBuildingElementProxy", pl["name"] + " Wasser",
                         [self.box(ox, oy, -dep, W, D, dep + ch - 0.06, "water")], predefined="USERDEFINED")
        for _i, pa in enumerate(site.get("paths", [])):
            self.cur_obj = f"site.paths.{_i}"
            ox, oy = pa["origin"]
            W, D = pa["size"]
            self.element("IfcBuildingElementProxy", pa["name"], [self.box(ox, oy, -0.02, W, D, 0.045, pa.get("material", "gravel"))],
                         predefined="USERDEFINED", material="Kies", dz=self.ground_z(*self._corners(ox, oy, W, D)))
        for _i, hd in enumerate(site.get("hedges", [])):
            self.cur_obj = f"site.hedges.{_i}"
            ox, oy = hd["origin"]
            W, D = hd["size"]
            self.element("IfcGeographicElement", hd["name"], [self.box(ox, oy, 0.0, W, D, float(hd["height"]), "boxwood")],
                         predefined="VEGETATION", dz=self.ground_z(*self._corners(ox, oy, W, D)))
        for _i, tr in enumerate(site.get("trees", [])):
            self.cur_obj = f"site.trees.{_i}"
            x, y = tr["position"]
            H, R = float(tr["height"]), float(tr["crown_radius"])
            trunk = self.cylinder((x, y, 0.0), (x, y, H - R), 0.22, "bark")
            sph = self.f.createIfcSphere(self.f.createIfcAxis2Placement3D(self.f.createIfcCartesianPoint((x, y, H - R))), R)
            ifcopenshell.api.style.assign_item_style(self.f, item=sph, style=self.style("foliage"))
            dz = self.ground_z((x, y))
            self.element("IfcGeographicElement", tr["name"], [trunk], predefined="VEGETATION", dz=dz)
            crown = self.element("IfcGeographicElement", tr["name"] + " Krone", [sph], predefined="VEGETATION", dz=dz)
            crown.Representation.Representations[0].RepresentationType = "CSG"

    def interiors(self):
        for pt in self.spec.get("partitions", []):
            (x0, y0), (x1, y1) = pt["start"], pt["end"]
            t = float(pt.get("thickness", 0.12))
            z0, h = float(pt["z"]), float(pt.get("height", self.storey_h))
            horiz = abs(y1 - y0) < 1e-6
            base = min(x0, x1) if horiz else min(y0, y1)
            L = abs(x1 - x0) if horiz else abs(y1 - y0)
            mat = pt.get("material", "interior_white")

            def seg(a, b, za, zb):  # wall piece from a to b along the axis, between heights za and zb
                if horiz:
                    return self.box(base + a, y0 - t / 2, za, b - a, t, zb - za, mat)
                return self.box(x0 - t / 2, base + a, za, t, b - a, zb - za, mat)

            # "doors": [{offset, width, height}] offset = distance from the lower-coordinate end of the wall
            doors = sorted(pt.get("doors", []), key=lambda d: float(d["offset"]))
            items, cur, leaves = [], 0.0, []
            for d in doors:
                a = max(0.0, float(d["offset"]))
                b = min(L, a + float(d["width"]))
                dh = min(float(d.get("height", 2.1)), h - 0.1)
                if b - a < 0.3:
                    continue
                if a - cur > 1e-3:
                    items.append(seg(cur, a, z0, z0 + h))
                items.append(seg(a, b, z0 + dh, z0 + h))
                cur = b
                if d.get("leaf", True):  # closed door leaf, 4 cm thick, centred in the wall
                    fw = 0.04
                    if horiz:
                        leaf = self.box(base + a + 0.04, y0 - fw / 2, z0 + 0.02, b - a - 0.08, fw, dh - 0.06, "walnut")
                    else:
                        leaf = self.box(x0 - fw / 2, base + a + 0.04, z0 + 0.02, fw, b - a - 0.08, dh - 0.06, "walnut")
                    door = self.element("IfcDoor", d.get("name", "Innentuer"), [leaf], z_ref=z0, predefined="DOOR")
                    door.OverallWidth, door.OverallHeight = b - a, dh
            if L - cur > 1e-3:
                items.append(seg(cur, L, z0, z0 + h))
            self.element("IfcWall", pt.get("name", "Innenwand"), items,
                         z_ref=z0, predefined="PARTITIONING", material="Trockenbau")
        for fu in self.spec.get("furniture", []):
            x, y, z = fu["origin"]
            w, d, h = fu["size"]
            self.element("IfcFurniture", fu["name"], [self.box(x, y, z, w, d, h, fu.get("material", "fabric_grey"))],
                         z_ref=z, predefined="USERDEFINED")

    def rooms(self):
        """IfcSpace per room with function and automatically detected window/door data."""
        from . import rooms as R
        info = {a["id"]: a for a in R.analyze(self.spec)}
        for r in self.spec.get("rooms", []):
            elev = R.level_elev(self.spec, r["level"])
            x0, y0, x1, y1 = r["rect"]
            h = R.level_height(self.spec, r["level"]) - self.slab_t
            sp = self.element("IfcSpace", r["name"], [self.box(x0, y0, elev, x1 - x0, y1 - y0, h, None)],
                              z_ref=elev, predefined="INTERNAL", container=False)
            sp.LongName = R.FUNCTIONS[r["function"]][0]
            ifcopenshell.api.aggregate.assign_object(self.f, products=[sp], relating_object=self.storey_for(elev))
            a = info[r["id"]]
            self.pset(sp, "Bimrender_Raum", {
                "Funktion": r["function"], "Flaeche_m2": float(a["area"]), "Fenster_Anzahl": len(a["windows"]),
                "Fensterflaeche_m2": float(a["glass_area"]), "Aussentueren": len(a["doors"]),
                "Treppe": bool(a["stair"])})

    # ---------------------------------------------------------------- run
    def build(self):
        self.volumes()
        self.cur_obj = None
        self._facade_elements()
        self.interiors()
        self.rooms()
        self.openings()
        self.curtain_walls()
        self.balconies()
        self.pergolas()
        self.components()
        self.site_elements()
        self.cur_obj = None
        return self.f


def build_ifc(spec_path: str | Path, out_path: str | Path, terrain: dict | None = None) -> Path:
    """``terrain``: derived graded ground (bim.terrain.build_terrain) — site trees, hedges and paths then stand on it instead of on floor level."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    if terrain:
        spec.setdefault("site", {})["terrain"] = terrain
    f = Builder(spec).build()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    f.write(str(out))
    return out
