"""Catalog stage 2: towers/domes (lathe solids), bay windows, arcades, awnings, rustication, dentils, gutters,
bargeboards and roof windows. Mixin for ifcgen.Builder; registry entries live in catalog.py."""
from __future__ import annotations

import math

from .geom import facade_xy, side_length, subtract_intervals, SIDES
from .ifc_openings import ARCH_KINDS, arch_rise

ONION = [(1.0, 0.0), (1.25, 0.12), (1.3, 0.28), (1.15, 0.45), (0.8, 0.62), (0.45, 0.78), (0.2, 0.9), (0.07, 0.96), (0.0, 1.0)]


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or max(abs(p[k] - out[-1][k]) for k in range(3)) > 1e-9:
            out.append(p)
    if len(out) > 1 and max(abs(out[0][k] - out[-1][k]) for k in range(3)) < 1e-9:
        out.pop()
    return out


class Components2Mixin:
    # ------------------------------------------------------------------ lathe solid (tower shafts, cones, domes, onions)
    def _revolve(self, prof, cx, cy, style, n=32):
        """Closed faceted solid from a profile [(radius, z), ...] with rising z, revolved around a vertical axis."""
        f = self.f
        rings = [[(cx + r * math.cos(2 * math.pi * j / n), cy + r * math.sin(2 * math.pi * j / n), z) for j in range(n)] for r, z in prof]
        faces = []
        for i in range(len(prof) - 1):
            for j in range(n):
                q = _dedupe([rings[i][j], rings[i][(j + 1) % n], rings[i + 1][(j + 1) % n], rings[i + 1][j]])
                if len(q) >= 3:
                    faces.append(q)
        if prof[0][0] > 1e-9:
            faces.append(list(reversed(rings[0])))
        if prof[-1][0] > 1e-9:
            faces.append(rings[-1])
        pt = lambda p: f.createIfcCartesianPoint(tuple(float(c) for c in p))
        fs = [f.createIfcFace([f.createIfcFaceOuterBound(f.createIfcPolyLoop([pt(p) for p in fc]), True)]) for fc in faces]
        solid = f.createIfcFacetedBrep(f.createIfcClosedShell(fs))
        if style:
            import ifcopenshell.api.style
            ifcopenshell.api.style.assign_item_style(f, item=solid, style=self.style(style))
        return solid

    def _c_tower(self, c, v, i):
        ox, oy = v["origin"]
        base = float(v["base_z"])
        z0 = base + c["z0"]
        z1 = base + c["z1"]
        if c["x"] is None or c["y"] is None:
            raise ValueError(f"components[{i}] (tower): x und y (Mitte ab Volumen-Ursprung) sind Pflicht")
        if z1 - z0 < 1.0:
            raise ValueError(f"components[{i}] (tower): z1 muss mindestens 1 m über z0 liegen")
        cx, cy, R, n = ox + c["x"], oy + c["y"], c["radius"], c["sides"]
        ov, rh, kind = c["roof_overhang"], c["roof_height"], c["roof"]
        items = [self._revolve([(R, z0), (R, z1)], cx, cy, c["material"], n)]
        if c["band"]:
            items.append(self._revolve([(R + 0.07, z1 - 0.3), (R + 0.07, z1 - 0.1), (R + 0.02, z1 - 0.1)], cx, cy, c["band_material"] or c["material"], n))
        rmat = c["roof_material"]
        if kind == "cone":
            prof = [(R + ov, z1), (0.0, z1 + rh)]
        elif kind == "dome":
            prof = [((R + ov) * math.cos(math.pi / 2 * k / 8), z1 + rh * math.sin(math.pi / 2 * k / 8)) for k in range(9)]
        elif kind == "onion":
            prof = [((R + ov) * a, z1 + rh * b) for a, b in ONION]
        else:  # flat with a small parapet look
            prof = [(R + ov, z1), (R + ov, z1 + 0.25), (0.0, z1 + 0.25)]
        items.append(self._revolve(prof, cx, cy, rmat, n))
        ztop = z1 + (rh if kind != "flat" else 0.25)
        if c["finial"] and kind != "flat":
            items.append(self._revolve([(0.04, ztop - 0.05), (0.04, ztop + 0.5), (0.0, ztop + 0.62)], cx, cy, "brass", 12))
        for k in range(c["slits"]):
            th = 2 * math.pi * k / c["slits"] + math.radians(c["slit_angle"])
            zc = base + (c["slit_z"] if c["slit_z"] is not None else (c["z0"] + c["z1"]) / 2)
            ux, uy = math.cos(th), math.sin(th)
            tx, ty = -uy, ux
            hw = c["slit_width"] / 2
            quad = [(cx + ux * (R - 0.02) + tx * s * hw, cy + uy * (R - 0.02) + ty * s * hw) for s in (-1, 1)] + \
                   [(cx + ux * (R + 0.03) + tx * s * hw, cy + uy * (R + 0.03) + ty * s * hw) for s in (1, -1)]
            items.append(self._prism(quad, (0.0, 0.0, zc - c["slit_height"] / 2), (0, 0, 1), (1, 0, 0), c["slit_height"], "glass_tinted_grey"))
        self._comp_prox(f"Turm {v['id']}", items, z0, material="Mauerwerk")

    # ------------------------------------------------------------------ bay window / oriel
    def _pface(self, v, side, A, B, off0, off1, za, zb, style, s0=0.0, s1=None):
        """Vertical prism over part s0..s1 (metres from A) of the plan edge A->B (given in facade (u, d)), spanning offsets off0..off1 outwards."""
        ox, oy = v["origin"]
        W, D = v["size"]
        du, dd = B[0] - A[0], B[1] - A[1]
        L = math.hypot(du, dd)
        eu, ed = du / L, dd / L
        nu, nd = ed, -eu
        s1 = L if s1 is None else s1
        P = lambda s, o: facade_xy(side, ox, oy, W, D, A[0] + eu * s + nu * o, A[1] + ed * s + nd * o)
        quad = [P(s0, off0), P(s1, off0), P(s1, off1), P(s0, off1)]
        return self._prism(quad, (0.0, 0.0, za), (0, 0, 1), (1, 0, 0), zb - za, style)

    def _c_bay(self, c, v, i):
        base = float(v["base_z"])
        z0, z1 = base + c["z0"], base + c["z1"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b, p = u - c["width"] / 2, u + c["width"] / 2, c["projection"]
        if a < 0 or b > L:
            raise ValueError(f"components[{i}] (bay): Erker ragt über die Fassade (u {a:.2f}..{b:.2f}, Länge {L:.2f})")
        if z1 - z0 < 1.6:
            raise ValueError(f"components[{i}] (bay): z1-z0 muss mindestens 1.6 m sein")
        fac = c["material"] or v.get("facade", "plaster_white")
        fr, glass = c["frame"], self.win["glass"]
        sill, top = c["sill"], 0.45
        zw0, zw1 = z0 + sill, z1 - top
        side = c["side"]
        items = []
        if c["kind"] == "canted":
            pl = [(a, 0.0), (a + p, -p), (b - p, -p), (b, 0.0)]
            poly = [facade_xy(side, *v["origin"], *v["size"], uu, dd) for uu, dd in pl]
            items.append(self._prism(poly, (0.0, 0.0, z0), (0, 0, 1), (1, 0, 0), sill, fac))
            items.append(self._prism(poly, (0.0, 0.0, zw1), (0, 0, 1), (1, 0, 0), top, fac))
            edges = [(pl[0], pl[1]), (pl[1], pl[2]), (pl[2], pl[3])]
            for A, B in edges:
                Ln = math.hypot(B[0] - A[0], B[1] - A[1])
                items.append(self._pface(v, side, A, B, 0.0, 0.05, zw0, zw1, fr, 0.0, 0.08))
                items.append(self._pface(v, side, A, B, 0.0, 0.05, zw0, zw1, fr, Ln - 0.08, Ln))
                items.append(self._pface(v, side, A, B, 0.0, 0.05, zw0, zw0 + 0.06, fr))
                items.append(self._pface(v, side, A, B, 0.0, 0.05, zw1 - 0.06, zw1, fr))
                items.append(self._pface(v, side, A, B, 0.01, 0.03, zw0, zw1, glass, 0.08, Ln - 0.08))
            roof_poly = [facade_xy(side, *v["origin"], *v["size"], uu, dd) for uu, dd in [(a - 0.1, 0.0), (a + p - 0.1 + 0.0, -p - 0.12), (b - p + 0.1, -p - 0.12), (b + 0.1, 0.0)]]
        else:
            items.append(self._fbx(v, side, a, b, -p, 0.0, z0, z0 + sill, fac))
            items.append(self._fbx(v, side, a, b, -p, 0.0, zw1, z1, fac))
            for uu0, uu1 in ((a, a + 0.12), (b - 0.12, b)):
                items.append(self._fbx(v, side, uu0, uu1, -p, 0.0, zw0, zw1, fac))
            n = max(1, round((b - a) / 0.9))
            for k in range(n + 1):
                uu = a + 0.12 + k * (b - a - 0.24) / n
                items.append(self._fbx(v, side, uu - 0.03, uu + 0.03, -p, -p + 0.07, zw0, zw1, fr))
            items.append(self._fbx(v, side, a + 0.12, b - 0.12, -p + 0.02, -p + 0.05, zw0, zw1, glass))
            items.append(self._fbx(v, side, a + 0.12, b - 0.12, -p, -p + 0.07, zw0, zw0 + 0.06, fr))
            items.append(self._fbx(v, side, a + 0.12, b - 0.12, -p, -p + 0.07, zw1 - 0.06, zw1, fr))
            roof_poly = None
        if z0 > base + 0.3:  # oriel hangs in the air: closed underside with a small corbel
            items.append(self._fbx(v, side, a - 0.04, b + 0.04, -p - 0.05, 0.0, z0 - 0.16, z0, c["support_material"]))
        rm = c["roof_material"]
        if roof_poly:
            items.append(self._prism(roof_poly, (0.0, 0.0, z1), (0, 0, 1), (1, 0, 0), 0.14, rm))
        else:
            items.append(self._fbx(v, side, a - 0.1, b + 0.1, -p - 0.12, 0.0, z1, z1 + 0.14, rm))
        self._comp_prox(f"Erker {v['id']}-{side}", items, z0, material="Mauerwerk")

    # ------------------------------------------------------------------ arcade
    def _c_arcade(self, c, v, i):
        base = float(v["base_z"])
        z0, zs, zt = base + c["z0"], base + c["spring_z"], base + c["z1"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        span, pier, n, kind = c["span"], c["pier"], c["count"], c["kind"]
        rise = arch_rise(kind, span, c["arch_rise"])
        if zt < zs + rise + 0.35:
            raise ValueError(f"components[{i}] (arcade): z1 muss mindestens {zs + rise + 0.35 - base:.2f} m sein (Anlauf {c['spring_z']} + Bogen {rise:.2f} + 0.35)")
        total = n * span + (n + 1) * pier
        u = c["u"] if c["u"] is not None else (L - total) / 2
        if u < -0.01 or u + total > L + 0.01:
            raise ValueError(f"components[{i}] (arcade): Arkade ({total:.2f} m) passt nicht in die Fassade ({L:.2f} m)")
        dist, dep, mat = c["distance"], c["depth"], c["material"]
        d_out, d_in = -(dist + dep), -dist
        items = []
        for k in range(n + 1):
            ua = u + k * (span + pier)
            items.append(self._fbx(v, c["side"], ua, ua + pier, d_out, d_in, z0, zt, mat))
        for k in range(n):
            ua = u + pier + k * (span + pier)
            items += self._spandrels(v, c["side"], ua, ua + span, zs, zt, kind, c["arch_rise"], d_out, d_in, mat)
        items.append(self._fbx(v, c["side"], u - 0.08, u + total + 0.08, d_out - 0.1, d_in, zt, zt + 0.22, mat))
        self._comp_prox(f"Arkade {v['id']}-{c['side']}", items, z0)

    # ------------------------------------------------------------------ awning
    def _c_awning(self, c, v, i):
        z = float(v["base_z"]) + c["z"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b, p, dr = u - c["width"] / 2, u + c["width"] / 2, c["projection"], c["drop"]
        n = max(1, round(c["width"] / c["stripe"]))
        w = (b - a) / n
        items = []
        for k in range(n):
            m = c["material"] if k % 2 == 0 else c["material2"]
            items.append(self._sprism_at(v, c["side"], [(0.0, z), (-p, z - dr), (-p, z - dr - 0.025), (0.0, z - 0.025)], a + k * w, w, m))
            items.append(self._fbx(v, c["side"], a + k * w, a + (k + 1) * w, -p - 0.01, -p + 0.01, z - dr - 0.18, z - dr, m))
        for uu in (a + 0.02, b - 0.02):
            items.append(self._fbx(v, c["side"], uu - 0.012, uu + 0.012, -p, -0.0, z - dr - 0.2 - 0.0, z - dr - 0.18 + 0.0, "cast_iron_black"))
        self._comp_prox(f"Markise {v['id']}-{c['side']}", items, z, material="Stoff")

    # ------------------------------------------------------------------ rustication, dentils
    def _c_rustication(self, c, v, i):
        base = float(v["base_z"])
        z0, z1 = base + c["z0"], (base + c["z1"]) if c["z1"] is not None else base + c["z0"] + 3.0
        W, D = v["size"]
        sides = SIDES if c["side"] == "all" else (c["side"],)
        ch, pr = c["course"], c["proud"]
        n = max(1, int((z1 - z0) / ch))
        ch = (z1 - z0) / n
        items = []
        for side in sides:
            L = side_length(side, W, D)
            ops = [(float(o["offset"]) - 0.02, float(o["offset"]) + float(o["width"]) + 0.02, int(o["storey"]), float(o.get("sill", 0.0)), float(o["height"]))
                   for o in self.spec.get("openings", []) if o["volume"] == v["id"] and o["side"] == side]
            h = float(v.get("storey_height", self.storey_h))
            for k in range(n):
                za, zb = z0 + k * ch + 0.012, z0 + (k + 1) * ch - 0.012
                cuts = [(u0, u1) for u0, u1, st, sl, hh in ops if base + st * h + sl < zb + 0.05 and base + st * h + sl + hh > za - 0.05]
                for ua, ub in subtract_intervals((0.0, L), cuts):
                    if ub - ua > 0.05:
                        items.append(self._fbx(v, side, ua, ub, -pr, 0.0, za, zb, c["material"]))
        if items:
            self._comp_prox(f"Bossenwerk {v['id']}", items, z0)

    def _c_dentil(self, c, v, i):
        base, top = float(v["base_z"]), float(v["base_z"]) + int(v["storeys"]) * float(v.get("storey_height", self.storey_h))
        z = base + c["z"] if c["z"] is not None else top - 0.4
        W, D = v["size"]
        sides = SIDES if c["side"] == "all" else (c["side"],)
        s, h, dp, sp = c["width"], c["height"], c["depth"], c["spacing"]
        items = []
        for side in sides:
            L = side_length(side, W, D)
            k = max(1, int((L - 0.4) / sp))
            for j in range(k + 1):
                uu = 0.2 + j * (L - 0.4 - s) / k
                items.append(self._fbx(v, side, uu, uu + s, -dp, 0.0, z, z + h, c["material"]))
        self._comp_prox(f"Zahnschnitt {v['id']}", items, z)

    # ------------------------------------------------------------------ gutter, bargeboard
    def _c_gutter(self, c, v, i):
        top = float(v["base_z"]) + int(v["storeys"]) * float(v.get("storey_height", self.storey_h))
        roof = v.get("roof") or {}
        W, D = v["size"]
        sides = SIDES if c["side"] == "all" else (c["side"],)
        ov = float(roof.get("overhang", 0.0)) if roof.get("type") in ("gable", "hip", "shed", "mansard", "gambrel") else 0.0
        pitch = float(roof.get("pitch_deg", 30))
        low = float(roof.get("lower_pitch_deg", pitch)) if roof.get("type") in ("mansard", "gambrel") else pitch
        ze = top - ov * math.tan(math.radians(low)) - 0.02 if ov else top - 0.12
        items = []
        for side in sides:
            if roof.get("type") == "gable":
                eaves = ("S", "N") if roof.get("ridge", "x") == "x" else ("W", "E")
                if side not in eaves:
                    continue
            if roof.get("type") == "shed" and side != roof.get("fall_to", "S"):
                continue
            L = side_length(side, W, D)
            e = ov if ov else 0.03
            ext = ov if roof.get("type") in ("hip", "mansard", "gable", "shed", "gambrel") else 0.0
            d_out, d_in = -(e + 0.13), -e
            items.append(self._fbx(v, side, -ext, L + ext, d_out, d_in, ze - 0.1, ze - 0.07, c["material"]))
            items.append(self._fbx(v, side, -ext, L + ext, d_out, d_out + 0.03, ze - 0.07, ze + 0.02, c["material"]))
            items.append(self._fbx(v, side, -ext, L + ext, d_in - 0.03, d_in, ze - 0.07, ze + 0.04, c["material"]))
        if not items:
            raise ValueError(f"components[{i}] (gutter): keine Traufseite für side={c['side']} bei diesem Dach")
        self._comp_prox(f"Dachrinne {v['id']}", items, ze, material="Zink")

    def _c_bargeboard(self, c, v, i):
        g = self.gables.get(v["id"])
        if not g:
            raise ValueError(f"components[{i}] (bargeboard): nur bei Volumen mit roof.type gable")
        top = float(v["base_z"]) + int(v["storeys"]) * float(v.get("storey_height", self.storey_h))
        tn, cs = math.tan(g["pitch"]), math.cos(g["pitch"])
        b0, b1, a0, a1, ov = g["b0"], g["b1"], g["a0"], g["a1"], g["ov"]
        bm = (b0 + b1) / 2
        h, th = c["height"], c["thickness"]
        ridge = g["ridge"]
        if ridge == "x":
            mk, loc, axis, ref = (lambda b, z: (b, z)), (lambda a: (a, 0, 0)), (1, 0, 0), (0, 1, 0)
        else:
            mk, loc, axis, ref = (lambda b, z: (-b, z)), (lambda a: (0, a, 0)), (0, 1, 0), (-1, 0, 0)
        zl = lambda b: top + (b - b0) * tn
        zr = lambda b: top + (b1 - b) * tn
        rise = (bm - b0) * tn
        lh = h / cs
        left = [mk(b0 - ov, zl(b0 - ov)), mk(bm, top + rise), mk(bm, top + rise - lh), mk(b0 - ov, zl(b0 - ov) - lh)]
        right = [mk(b1 + ov, zr(b1 + ov)), mk(bm, top + rise), mk(bm, top + rise - lh), mk(b1 + ov, zr(b1 + ov) - lh)]
        items = []
        for a in (a0 - ov - th, a1 + ov):
            items.append(self._prism(left, loc(a), axis, ref, th, c["material"]))
            items.append(self._prism(right, loc(a), axis, ref, th, c["material"]))
        self._comp_prox(f"Ortgangbrett {v['id']}", items, top, material="Holz")

    # ------------------------------------------------------------------ roof window
    def _c_skylight(self, c, v, i):
        g = self.gables.get(v["id"])
        if not g:
            raise ValueError(f"components[{i}] (skylight): nur bei Volumen mit roof.type gable")
        top = float(v["base_z"]) + int(v["storeys"]) * float(v.get("storey_height", self.storey_h))
        ridge, tn, cs = g["ridge"], math.tan(g["pitch"]), math.cos(g["pitch"])
        slope = c["slope"]
        if slope not in {"y": ("W", "E"), "x": ("S", "N")}[ridge]:
            raise ValueError(f"components[{i}] (skylight): Seite {slope} gibt es bei ridge={ridge} nicht (Dachseiten: {'W/E' if ridge == 'y' else 'S/N'})")
        low = slope in ("S", "W")
        w, hs = c["width"], c["height"]
        run = hs * cs
        half = (g["b1"] - g["b0"]) / 2
        if c["up"] + run > half - 0.2:
            raise ValueError(f"components[{i}] (skylight): 'up'+Fensterhöhe reicht über den First (max {half - 0.2 - run:.2f} m ab Wandkante)")
        a_s = g["a0"] + c["u"]
        if c["u"] < 0.3 or a_s + w > g["a1"] - 0.3:
            raise ValueError(f"components[{i}] (skylight): u außerhalb der Dachlänge")
        b_e = g["b0"] + c["up"] if low else g["b1"] - c["up"]
        sg = 1 if low else -1
        zf = lambda b: top + (b - g["b0"]) * tn if low else top + (g["b1"] - b) * tn

        def corner(a, b, lift):
            pt = (a, b) if ridge == "x" else (b, a)
            return (pt[0], pt[1], zf(b) + lift)

        def quad(inset, lift):
            ba, bb = b_e + sg * (inset * cs), b_e + sg * (run - inset * cs)
            aa, ab = a_s + inset, a_s + w - inset
            return [corner(aa, ba, lift), corner(ab, ba, lift), corner(ab, bb, lift), corner(aa, bb, lift)]

        items = [self._slope_slab(quad(0.0, 0.10), 0.14, c["frame"]), self._slope_slab(quad(0.07, 0.115), 0.04, "glass_clear")]
        self._comp_prox(f"Dachfenster {v['id']}-{slope}", items, top, material="Holz/Glas")
