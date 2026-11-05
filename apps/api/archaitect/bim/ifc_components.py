"""Generators for the parametric component catalog (see catalog.py). Mixin for ifcgen.Builder."""
from __future__ import annotations

import math

from . import catalog
from .geom import facade_xy, side_length, SIDES

PROFILES = {  # (projection fraction, height fraction) polygons, wall side at 0
    "band": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "simple": [(0, 0), (0.6, 0), (0.6, 0.3), (1, 0.35), (1, 0.55), (0.7, 0.65), (0.7, 1), (0, 1)],
    "stepped": [(0, 0), (0.4, 0), (0.4, 0.25), (0.7, 0.25), (0.7, 0.5), (1, 0.5), (1, 1), (0, 1)],
}
PROFILES["cove"] = [(0, 0)] + [(math.sin(a * math.pi / 2 / 8), 0.85 * (1 - math.cos(a * math.pi / 2 / 8))) for a in range(1, 9)] + [(1, 1), (0, 1)]


from .ifc_garden2 import TYPES as G2_TYPES


class ComponentsMixin:
    def _vtop(self, v):
        return float(v["base_z"]) + int(v["storeys"]) * float(v.get("storey_height", self.storey_h))

    def _comp_prox(self, name, items, z_ref, material="Naturstein", cls="IfcBuildingElementProxy", predefined="USERDEFINED"):
        return self.element(cls, name, items, z_ref=z_ref, predefined=predefined, material=material)

    def _us(self, c, L):
        u = c.get("u")
        if u is None:
            u = L / 2
        n, sp = int(c.get("count", 1)), float(c.get("spacing", 1.0))
        return [u + (i - (n - 1) / 2) * sp for i in range(n)]

    def components(self):
        for i, raw in enumerate(self.spec.get("components", [])):
            try:
                c = catalog.resolve(raw)
            except ValueError as e:
                raise ValueError(f"components[{i}]: {e}")
            t = c["type"]
            self.cur_obj = (f"comp.{i}" if t in ("pool", "pond", "sauna_hut", "flowerbed", "parking", "terrace", "carport", "ramp", "garden_set", "bench", "tree", "shrub", "garden_light") + tuple(G2_TYPES)
                            and c.get("x") is not None else self.vobj.get(c.get("volume")))
            if t == "fence":
                self._fence(c)
                continue
            if t in ("pylon", "parking"):
                getattr(self, f"_c_{t}")(c, None, i)
                continue
            if t in ("tree", "hedge", "shrub", "flowerbed", "path", "pool", "pond", "lake", "sauna_hut", "bench", "garden_set", "garden_light") or t in G2_TYPES:
                getattr(self, f"_c_{t}")(c, i)
                continue
            if t == "retaining_wall":
                if any(c[k] is None for k in ("x0", "y0", "x1", "y1")):
                    raise ValueError(f"components[{i}] (retaining_wall): x0, y0, x1, y1 sind Pflicht")
                self._c_retaining_wall(c, None, i)
                continue
            if c["volume"] not in self.vol:
                raise ValueError(f"components[{i}] ({t}): Volumen {c['volume']!r} existiert nicht")
            v = self.vol[c["volume"]]
            getattr(self, f"_c_{t}")(c, v, i)

    # ------------------------------------------------------------------ cornice
    def _c_cornice(self, c, v, i):
        base, top = float(v["base_z"]), self._vtop(v)
        h, p = c["height"], c["projection"]
        z = base + c["z"] if c["z"] is not None else top - h  # crown sits just below the eaves/parapet by default
        ox, oy = v["origin"]
        W, D = v["size"]
        pts = [(-(a * p), z + b * h) for a, b in PROFILES[c["profile"]]]  # d negative = outwards
        sides = SIDES if c["side"] == "all" else (c["side"],)
        items = []
        for side in sides:
            L = side_length(side, W, D)
            # S/N run over the corners, E/W only between them: butt joint instead of overlapping (coplanar) volumes
            ext = p if (c["side"] == "all" and side in ("S", "N")) or c["side"] != "all" else 0.0
            items.append(self._sprism_at(v, side, pts, -ext, L + 2 * ext, c["material"]))
        self._comp_prox(f"Gesims {v['id']} {c['side']}", items, z)

    # ------------------------------------------------------------------ quoins
    def _c_quoins(self, c, v, i):
        base, top = float(v["base_z"]), self._vtop(v)
        z0, z1 = base + c["z0"], (base + c["z1"]) if c["z1"] is not None else top
        W, D = v["size"]
        w_long, w_short, ch, pr = c["width"], c["width"] * 0.6, c["course"], c["proud"]
        n = max(1, int((z1 - z0) / ch))
        ch = (z1 - z0) / n
        items = []
        for side in SIDES:
            L = side_length(side, W, D)
            for end in ("l", "r"):
                par = 0 if (side, end) in {("S", "l"), ("S", "r"), ("E", "r"), ("N", "r")} else 1
                for k in range(n):
                    w = w_long if (k + par) % 2 == 0 else w_short
                    ua, ub = (-pr, w) if end == "l" else (L - w, L + pr)
                    items.append(self._fbx(v, side, ua, ub, -pr, 0.0, z0 + k * ch + 0.004, z0 + (k + 1) * ch - 0.004, c["material"]))
        self._comp_prox(f"Ecksteine {v['id']}", items, z0)

    # ------------------------------------------------------------------ pilaster
    def _c_pilaster(self, c, v, i):
        base, top = float(v["base_z"]), self._vtop(v)
        z0, z1 = base + c["z0"], (base + c["z1"]) if c["z1"] is not None else top
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        w, pr = c["width"], c["projection"]
        items = []
        for u in self._us(c, L):
            items.append(self._fbx(v, c["side"], u - w / 2, u + w / 2, -pr, 0.0, z0, z1, c["material"]))
            if c["base"]:
                items.append(self._fbx(v, c["side"], u - w / 2 - 0.04, u + w / 2 + 0.04, -pr - 0.03, 0.0, z0, z0 + 0.22, c["material"]))
            if c["capital"]:
                items.append(self._fbx(v, c["side"], u - w / 2 - 0.05, u + w / 2 + 0.05, -pr - 0.04, 0.0, z1 - 0.28, z1, c["material"]))
        self._comp_prox(f"Pilaster {v['id']}-{c['side']}", items, z0)

    # ------------------------------------------------------------------ column
    def _c_column(self, c, v, i):
        base = float(v["base_z"])
        z0, z1 = base + c["z0"], base + c["z1"]
        if z1 - z0 < 0.5:
            raise ValueError(f"components[{i}] (column): z1 muss mindestens 0.5 m über z0 liegen")
        ox, oy = v["origin"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        r = c["radius"]
        items = []
        for u in self._us(c, L):
            x, y = facade_xy(c["side"], ox, oy, W, D, u, -c["distance"])
            if c.get("order") == "doric":
                # Doric order: tapered, entasis-swelled, faceted (fluted) shaft without base; echinus + square abacus on top
                H = z1 - z0
                ch = min(0.45, H * 0.1)
                zs = z1 - ch
                prof = [(0.0, z0), (r, z0), (r * 1.035, z0 + (zs - z0) * 0.32), (r * 0.9, z0 + (zs - z0) * 0.75), (r * 0.78, zs), (r * 0.95, zs + ch * 0.18), (r * 1.2, zs + ch * 0.55), (r * 1.2, z1 - ch * 0.25), (0.0, z1 - ch * 0.25)]
                items.append(self._revolve(prof, x, y, c["material"], 20))
                items.append(self.box(x - r * 1.3, y - r * 1.3, z1 - ch * 0.25, r * 2.6, r * 2.6, ch * 0.25, c["material"]))
                continue
            h0 = z0 + (0.2 if c["base"] else 0.0)
            h1 = z1 - (0.25 if c["capital"] else 0.0)
            items.append(self.cylinder((x, y, h0), (x, y, h1), r, c["material"]))
            if c["base"]:
                items.append(self.box(x - r * 1.35, y - r * 1.35, z0, r * 2.7, r * 2.7, 0.2, c["material"]))
            if c["capital"]:
                items.append(self.box(x - r * 1.5, y - r * 1.5, z1 - 0.25, r * 3.0, r * 3.0, 0.25, c["material"]))
        self._comp_prox(f"Saeule {v['id']}-{c['side']}", items, z0, cls="IfcColumn", predefined="COLUMN")

    # ------------------------------------------------------------------ entablature (architrave, frieze with triglyphs, cornice, soffit)
    def _c_entablature(self, c, v, i):
        base = float(v["base_z"])
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b = u - c["span"] / 2, u + c["span"] / 2
        z0, h, dist, hb, m, side = base + c["z"], c["height"], c["distance"], c["beam_depth"] / 2, c["material"], c["side"]
        ha, hf = h * 0.4, h * 0.42
        hc = h - ha - hf
        items = [self._fbx(v, side, a, b, -(dist + hb), -(dist - hb), z0, z0 + ha, m),                                   # architrave
                 self._fbx(v, side, a, b, -(dist + hb - 0.04), -(dist - hb + 0.04), z0 + ha, z0 + ha + hf, m),             # frieze
                 self._fbx(v, side, a - 0.15, b + 0.15, -(dist + hb + 0.3), -(dist - hb), z0 + ha + hf, z0 + h, m),         # cornice (geison), projecting
                 self._fbx(v, side, a, b, -(dist - hb), 0.0, z0 + ha - 0.2, z0 + ha, m)]                                     # soffit slab back to the wall
        if c["triglyphs"]:
            uu = a + 0.45
            while uu < b - 0.3:
                items.append(self._fbx(v, side, uu - 0.13, uu + 0.13, -(dist + hb - 0.04) - 0.05, -(dist + hb - 0.04), z0 + ha + 0.05, z0 + ha + hf - 0.05, "stone_granite_grey"))
                uu += 0.95
        self._comp_prox(f"Gebaelk {v['id']}-{side}", items, z0, material="Marmor")

    # ------------------------------------------------------------------ bracket
    def _c_bracket(self, c, v, i):
        top = self._vtop(v)
        z = float(v["base_z"]) + c["z"] if c["z"] is not None else top
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        s, p, th = c["size"], c["projection"], c["thickness"]
        items = [self._sprism_at(v, c["side"], [(0.0, z), (-p, z), (-p, z - 0.06), (0.0, z - s)], u - th / 2, th, c["material"])
                 for u in self._us(c, L)]
        self._comp_prox(f"Konsolen {v['id']}-{c['side']}", items, z, material="Holz")

    # ------------------------------------------------------------------ canopy
    def _c_canopy(self, c, v, i):
        base = float(v["base_z"])
        z = base + c["z"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b, p, th = u - c["width"] / 2, u + c["width"] / 2, c["projection"], c["thickness"]
        mat = c["material"]
        rmat = c["roof_material"] or mat
        items = []
        if c["kind"] == "flat":
            items.append(self._fbx(v, c["side"], a, b, -p, 0.0, z, z + th, mat))
        elif c["kind"] == "shed":
            items.append(self._sprism_at(v, c["side"], [(0.0, z + 0.3), (-p, z), (-p, z + th), (0.0, z + 0.3 + th)], a, b - a, rmat))
        else:
            items.append(self._fp(v, c["side"], [(a - 0.1, z), (b + 0.1, z), (u, z + (b - a) * 0.3)], -p, 0.0, rmat))
            items.append(self._fbx(v, c["side"], a, b, -p + 0.02, 0.0, z - 0.1, z, mat))
        if c["support"] == "posts":
            for uu in (a + 0.06, b - 0.06):
                items.append(self._fbx(v, c["side"], uu - 0.06, uu + 0.06, -p + 0.06, -p + 0.18, base, z, mat))
        elif c["support"] == "brackets":
            drop = min(0.9, p * 0.8)
            for uu in (a + 0.12, b - 0.12):
                items.append(self._sprism_at(v, c["side"], [(0.0, z - drop), (0.0, z - drop + 0.1), (-p * 0.85, z), (-p * 0.85, z - 0.1)], uu - 0.035, 0.07, mat))
        self._comp_prox(f"Vordach {v['id']}-{c['side']}", items, z, material="Stahl")

    # ------------------------------------------------------------------ steps
    def _c_steps(self, c, v, i):
        n, rs, tr = c["count"], c["rise"], c["tread"]
        # the top step ends flush with the threshold (= base of the volume); the steps descend from there
        z0 = c["z0"] if c["z0"] is not None else max(0.0, float(v["base_z"]) - n * rs)
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b = u - c["width"] / 2, u + c["width"] / 2
        items = [self._fbx(v, c["side"], a, b, -(n - k) * tr - 0.0, 0.0, z0, z0 + (k + 1) * rs, c["material"]) for k in range(n)]
        # k = 0 is the lowest and widest-reaching step, the top step ends flush with the threshold level
        self._comp_prox(f"Treppe {v['id']}-{c['side']}", items, z0, cls="IfcStair", predefined=None)

    # ------------------------------------------------------------------ chimney
    def _c_chimney(self, c, v, i):
        ox, oy = v["origin"]
        W, D = v["size"]
        roof = v.get("roof") or {}
        top = self._vtop(v)
        x = ox + (c["x"] if c["x"] is not None else W / 2)
        y = oy + (c["y"] if c["y"] is not None else D / 2)
        zt = top + c["height"]
        zt = top + self.roof_rise.get(v["id"], 0.0) + c["height"]
        w, d = c["width"], c["depth"]
        items = [self.box(x - w / 2, y - d / 2, top - 0.2, w, d, zt - top + 0.2, c["material"]),
                 self.box(x - w / 2 - 0.05, y - d / 2 - 0.05, zt, w + 0.1, d + 0.1, 0.1, c["cap_material"]),
                 self.box(x - w * 0.18, y - d * 0.18, zt + 0.1, w * 0.36, d * 0.36, 0.3, "cast_iron_black")]
        self._comp_prox(f"Schornstein {v['id']}", items, top, material="Mauerwerk", cls="IfcChimney", predefined=None)

    # ------------------------------------------------------------------ downpipe
    def _c_downpipe(self, c, v, i):
        base, top = float(v["base_z"]), self._vtop(v)
        z0 = base + c["z0"]
        ox, oy = v["origin"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L - 0.3
        r = c["radius"]
        roof = v.get("roof") or {}
        rt = roof.get("type")
        side = c["side"]
        gut = any(g.get("type") == "gutter" and g.get("volume") == v["id"] and g.get("side", "all") in ("all", side) for g in self.spec.get("components", []))
        eaves = {"gable": ("S", "N") if roof.get("ridge", "x") == "x" else ("W", "E"), "shed": (roof.get("fall_to", "S"),)}.get(rt, ("S", "E", "N", "W") if rt in ("hip", "mansard", "gambrel") else ()) 
        items = []
        dw = -(r + 0.03)
        if gut and side in eaves:
            # gutter outlet -> 45 degree elbow -> wall pipe: the water really runs from the eaves gutter down to the ground
            ov = float(roof.get("overhang", 0.0)) if rt in ("gable", "hip", "shed", "mansard", "gambrel") else 0.0
            low = float(roof.get("lower_pitch_deg", roof.get("pitch_deg", 30))) if rt in ("mansard", "gambrel") else float(roof.get("pitch_deg", 30))
            ze = top - ov * math.tan(math.radians(low)) - 0.02 if ov else top - 0.12
            do = -((ov if ov else 0.03) + 0.065)
            za = ze - 0.1
            run = abs(do - dw)
            zb = za - run
            x0, y0 = facade_xy(side, ox, oy, W, D, u, do)
            x1, y1 = facade_xy(side, ox, oy, W, D, u, dw)
            if run > 0.04:
                items.append(self.cylinder((x0, y0, za + 0.03), (x0, y0, za - 0.06), r * 1.25, c["material"]))      # outlet collar in the gutter bottom
                items.append(self.cylinder((x0, y0, za - 0.06), (x1, y1, zb), r, c["material"]))                    # elbow
                items.append(self.cylinder((x1, y1, zb + 0.05), (x1, y1, zb - 0.02), r * 1.2, c["material"]))
                z1 = zb if c["z1"] is None else min(base + c["z1"], zb)
            else:
                z1 = za - 0.05 if c["z1"] is None else min(base + c["z1"], za - 0.05)
        else:
            z1 = base + c["z1"] if c["z1"] is not None else top - 0.1
        x, y = facade_xy(side, ox, oy, W, D, u, dw)
        items.append(self.cylinder((x, y, z0), (x, y, z1), r, c["material"]))
        for zc in (z0 + 0.3, (z0 + z1) / 2, z1 - 0.3):                  # pipe clips to the wall
            if z0 < zc < z1:
                items.append(self.cylinder((x, y, zc - 0.02), (x, y, zc + 0.02), r * 1.3, c["material"]))
        self._comp_prox(f"Fallrohr {v['id']}-{c['side']}", items, z0, material="Zink")

    # ------------------------------------------------------------------ lamp
    def _c_lamp(self, c, v, i):
        z = float(v["base_z"]) + c["z"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        s = c["size"]
        m = c["material"]
        items = [self._fbx(v, c["side"], u - 0.04, u + 0.04, -0.02, 0.0, z - s / 2 - 0.05, z + s / 2 + 0.05, m),
                 self._fbx(v, c["side"], u - 0.02, u + 0.02, -0.14, -0.02, z + s / 2 - 0.03, z + s / 2 + 0.01, m),
                 self._fbx(v, c["side"], u - s * 0.28, u + s * 0.28, -0.14 - s * 0.45, -0.14, z - s / 2, z + s / 2, "glass_frosted"),
                 self._fbx(v, c["side"], u - s * 0.34, u + s * 0.34, -0.14 - s * 0.52, -0.14 + 0.03, z + s / 2, z + s / 2 + 0.04, m),
                 self._fbx(v, c["side"], u - s * 0.34, u + s * 0.34, -0.14 - s * 0.52, -0.14 + 0.03, z - s / 2 - 0.04, z - s / 2, m)]
        self._comp_prox(f"Leuchte {v['id']}-{c['side']}", items, z, material="Metall")

    # ------------------------------------------------------------------ sign
    def _c_sign(self, c, v, i):
        z = float(v["base_z"]) + c["z"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        arm, pw, ph = c["arm"], c["width"], c["height"]
        m = c["material"]
        items = [self._fbx(v, c["side"], u - 0.025, u + 0.025, -arm, 0.0, z - 0.05, z, m),
                 self._sprism_at(v, c["side"], [(0.0, z - 0.45), (0.0, z - 0.38), (-arm * 0.75, z - 0.05), (-arm * 0.75, z - 0.12)], u - 0.02, 0.04, m)]
        d1 = min(arm - 0.05, 0.08 + pw)
        items.append(self._fbx(v, c["side"], u - 0.02, u + 0.02, -d1, -0.08, z - 0.1 - ph, z - 0.1, c["plate_material"]))
        for dd in (d1 - 0.02, 0.1):
            items.append(self._fbx(v, c["side"], u - 0.012, u + 0.012, -dd - 0.01, -dd + 0.01, z - 0.1, z, m))
        self._comp_prox(f"Ausleger {v['id']}-{c['side']}", items, z, material="Metall")

    # ------------------------------------------------------------------ fence
    def _fence(self, c):
        pts = c["points"]
        H = c["height"]
        m = c["material"]
        kind = c["kind"]
        items = []
        posts = set()
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(x1 - x2) > 1e-6 and abs(y1 - y2) > 1e-6:
                raise ValueError("fence: nur achsparallele Segmente erlaubt")
            L = abs(x2 - x1) + abs(y2 - y1)
            if L < 0.3:
                continue
            ex, ey = (1, 0) if abs(x2 - x1) > 1e-6 else (0, 1)
            sx = 1 if (x2 - x1 + y2 - y1) > 0 else -1
            ex, ey = ex * sx, ey * sx
            P = lambda t, w, d, z0, z1: self._seg_box(x1, y1, ex, ey, t, w, d, z0, z1, m)
            if kind == "wall_cap":
                items.append(P(0, L, 0.3, 0.0, H))
                items.append(P(-0.03, L + 0.06, 0.38, H, H + 0.06))
                continue
            n = max(1, round(L / 2.0))
            for k in range(n + 1):
                t = L * k / n
                key = (round(x1 + ex * t, 3), round(y1 + ey * t, 3))
                if key in posts:  # shared corner post of two segments: one solid only (coplanar duplicates render black)
                    continue
                posts.add(key)
                items.append(P(t - 0.05, 0.1, 0.1, 0.0, H + 0.05))
            for zr in (H * 0.25, H * 0.7):
                items.append(P(0.0, L, 0.04, zr, zr + 0.06))
            if kind == "picket":
                m_n = max(2, int(L / 0.11))
                for k in range(m_n):
                    t = 0.05 + k * (L - 0.1) / m_n
                    items.append(P(t, 0.06, 0.025, 0.08, H - 0.05 + (0.03 if k % 2 else 0.0)))
        if items:
            self._comp_prox("Zaun", items, 0.0, material="Holz")

    def _seg_box(self, x1, y1, ex, ey, t, w, d, z0, z1, style):
        """Box along a fence segment: from distance t, length w, thickness d centred on the line."""
        xa, ya = x1 + ex * t, y1 + ey * t
        xb, yb = x1 + ex * (t + w), y1 + ey * (t + w)
        if ex != 0:
            return self.box(min(xa, xb), y1 - d / 2, z0, abs(xb - xa), d, z1 - z0, style)
        return self.box(x1 - d / 2, min(ya, yb), z0, d, abs(yb - ya), z1 - z0, style)
