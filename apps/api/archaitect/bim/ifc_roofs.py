"""Hip (Walmdach) and shed (Pultdach) roofs as IFC extrusions; mixin for ifcgen.Builder.

Every roof plane is a slab: a planar polygon in 3D extruded downwards (into the building) by its thickness.
"""
from __future__ import annotations

import math


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return tuple(c / n for c in a)


class RoofsMixin:
    def _slope_slab(self, pts3, th, style):
        """Planar polygon (3D points, counter-clockwise seen from above) -> slab of thickness th below it."""
        P = []
        for p in pts3:  # drop consecutive duplicates (pyramid roofs)
            if not P or max(abs(p[i] - P[-1][i]) for i in range(3)) > 1e-6:
                P.append(p)
        if len(P) > 2 and max(abs(P[0][i] - P[-1][i]) for i in range(3)) < 1e-6:
            P.pop()
        n = _unit(_cross(_sub(P[1], P[0]), _sub(P[2], P[0])))
        if n[2] < 0:
            n = tuple(-c for c in n)
        ref = _unit(_sub(P[1], P[0]))
        y = _cross(tuple(-c for c in n), ref)  # placement: Z = -n, X = ref, Y = Z x X
        pts2 = [(_dot(_sub(p, P[0]), ref), _dot(_sub(p, P[0]), y)) for p in P]
        return self._prism(pts2, P[0], tuple(-c for c in n), ref, th, style)

    def _hip(self, v, ox, oy, W, D, t, top, fac, roof):
        tn = math.tan(math.radians(float(roof.get("pitch_deg", 35))))
        cs = math.cos(math.radians(float(roof.get("pitch_deg", 35))))
        ov = float(roof.get("overhang", 0.4))
        mat = roof.get("material", "roof_tile_red")
        th = 0.18 / cs
        x0, x1, y0, y1 = ox - ov, ox + W + ov, oy - ov, oy + D + ov
        ze = top - ov * tn
        if W >= D:
            half = (y1 - y0) / 2
            ym = (y0 + y1) / 2
            xr0, xr1 = x0 + half, x1 - half
            zr = ze + half * tn
            R0, R1 = (xr0, ym, zr), (xr1, ym, zr)
            faces = [[(x0, y0, ze), (x1, y0, ze), R1, R0], [(x1, y1, ze), (x0, y1, ze), R0, R1],
                     [(x0, y1, ze), (x0, y0, ze), R0], [(x1, y0, ze), (x1, y1, ze), R1]]
        else:
            half = (x1 - x0) / 2
            xm = (x0 + x1) / 2
            yr0, yr1 = y0 + half, y1 - half
            zr = ze + half * tn
            R0, R1 = (xm, yr0, zr), (xm, yr1, zr)
            faces = [[(x1, y0, ze), (x1, y1, ze), R1, R0], [(x0, y1, ze), (x0, y0, ze), R0, R1],
                     [(x0, y0, ze), (x1, y0, ze), R0], [(x1, y1, ze), (x0, y1, ze), R1]]
        items = [self._slope_slab(f, th, mat) for f in faces]
        self.element("IfcRoof", f"Dach {v['id']} Walmdach", items, z_ref=top, predefined="HIP_ROOF", material="Dachziegel")
        return {"rise": zr - top}

    def _shed(self, v, ox, oy, W, D, t, top, fac, roof):
        tn = math.tan(math.radians(float(roof.get("pitch_deg", 15))))
        cs = math.cos(math.radians(float(roof.get("pitch_deg", 15))))
        ov = float(roof.get("overhang", 0.3))
        mat = roof.get("material", "roof_zinc_standing")
        fall = roof.get("fall_to", "S")
        th = 0.16 / cs
        if fall in ("S", "N"):
            span = D
            along0, along1 = ox - ov, ox + W + ov
            lo, hi = (oy, oy + D) if fall == "S" else (oy + D, oy)  # lo = low edge coordinate
            sgn = 1 if fall == "S" else -1
        else:
            span = W
            along0, along1 = oy - ov, oy + D + ov
            lo, hi = (ox, ox + W) if fall == "W" else (ox + W, ox)
            sgn = 1 if fall == "W" else -1
        rise = span * tn
        b_lo, b_hi = -ov, span + 0.05
        zf = lambda b: top + b * tn
        pos = lambda b: lo + sgn * b
        if fall in ("S", "N"):
            pts = [(along0, pos(b_lo), zf(b_lo)), (along1, pos(b_lo), zf(b_lo)), (along1, pos(b_hi), zf(b_hi)), (along0, pos(b_hi), zf(b_hi))]
        else:
            pts = [(pos(b_lo), along0, zf(b_lo)), (pos(b_lo), along1, zf(b_lo)), (pos(b_hi), along1, zf(b_hi)), (pos(b_hi), along0, zf(b_hi))]
        self.element("IfcRoof", f"Dach {v['id']} Pultdach", [self._slope_slab(pts, th, mat)], z_ref=top, predefined="SHED_ROOF", material="Dach")
        # raised wall on the high side and triangular infill on the two lateral sides
        if fall in ("S", "N"):
            hy = oy + D - t if fall == "S" else oy
            w = self.element("IfcWall", f"Wand {v['id']} Pultdach hoch", [self.box(ox, hy, top, W, t, rise, fac)], z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
            ya, yb = (oy, oy + D) if fall == "S" else (oy + D, oy)
            for xa in (ox, ox + W - t):
                tri = [(xa, ya, top), (xa, yb, top), (xa, yb, top + rise)]
                self.element("IfcWall", f"Giebel {v['id']} Pultdach", [self._hprism(tri, (1, 0, 0), (xa, 0.0, 0.0), t, fac)],
                             z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
        else:
            hx = ox + W - t if fall == "W" else ox
            w = self.element("IfcWall", f"Wand {v['id']} Pultdach hoch", [self.box(hx, oy, top, t, D, rise, fac)], z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
            xa_, xb_ = (ox, ox + W) if fall == "W" else (ox + W, ox)
            for ya in (oy, oy + D - t):
                tri = [(xa_, ya, top), (xb_, ya, top), (xb_, ya, top + rise)]
                self.element("IfcWall", f"Giebel {v['id']} Pultdach", [self._hprism(tri, (0, 1, 0), (0.0, ya, 0.0), t, fac)],
                             z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
        self.pset(w, "Pset_WallCommon", {"IsExternal": True, "LoadBearing": True})
        return {"rise": rise}

    def _hip_faces(self, x0, x1, y0, y1, ze, tn):
        """Faces of a hip roof over the rectangle at eaves height ze; returns (faces, ridge height)."""
        if x1 - x0 >= y1 - y0:
            half, ym = (y1 - y0) / 2, (y0 + y1) / 2
            zr = ze + half * tn
            R0, R1 = (x0 + half, ym, zr), (x1 - half, ym, zr)
            return [[(x0, y0, ze), (x1, y0, ze), R1, R0], [(x1, y1, ze), (x0, y1, ze), R0, R1],
                    [(x0, y1, ze), (x0, y0, ze), R0], [(x1, y0, ze), (x1, y1, ze), R1]], zr
        half, xm = (x1 - x0) / 2, (x0 + x1) / 2
        zr = ze + half * tn
        R0, R1 = (xm, y0 + half, zr), (xm, y1 - half, zr)
        return [[(x1, y0, ze), (x1, y1, ze), R1, R0], [(x0, y1, ze), (x0, y0, ze), R0, R1],
                [(x0, y0, ze), (x1, y0, ze), R0], [(x1, y1, ze), (x0, y1, ze), R1]], zr

    def _mansard(self, v, ox, oy, W, D, t, top, fac, roof):
        up = math.tan(math.radians(float(roof.get("pitch_deg", 20))))
        lo_deg = float(roof.get("lower_pitch_deg", 70))
        lo = math.tan(math.radians(lo_deg))
        lh = float(roof.get("lower_height", 2.2))
        ov = float(roof.get("overhang", 0.3))
        mat = roof.get("material", "roof_slate")
        th = 0.18
        inset = lh / lo
        if inset * 2 > min(W, D) - 0.5:
            raise ValueError(f"Mansarddach {v['id']}: lower_height {lh} m bei {lo_deg} Grad ist für die Grundfläche zu hoch (Einzug {inset:.2f} m je Seite)")
        ze = top - ov * lo
        X0, X1, Y0, Y1 = ox - ov, ox + W + ov, oy - ov, oy + D + ov
        x0, x1, y0, y1 = ox + inset, ox + W - inset, oy + inset, oy + D - inset
        z1 = top + lh
        R0 = [(X0, Y0, ze), (X1, Y0, ze), (X1, Y1, ze), (X0, Y1, ze)]
        R1 = [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        faces = [[R0[k], R0[(k + 1) % 4], R1[(k + 1) % 4], R1[k]] for k in range(4)]
        upper, zr = self._hip_faces(x0, x1, y0, y1, z1, up)
        items = [self._slope_slab(f, th, mat) for f in faces + upper]
        self.element("IfcRoof", f"Dach {v['id']} Mansarddach", items, z_ref=top, predefined="USERDEFINED", material="Dach")
        return {"rise": zr - top}

    def _gambrel(self, v, ox, oy, W, D, t, top, fac, roof):
        ridge = roof.get("ridge", "x")
        up = math.tan(math.radians(float(roof.get("pitch_deg", 20))))
        lo = math.tan(math.radians(float(roof.get("lower_pitch_deg", 65))))
        frac = float(roof.get("lower_run", 0.4))
        ov = float(roof.get("overhang", 0.3))
        mat = roof.get("material", "roof_wood_shingle")
        th = 0.16
        if ridge == "x":
            a0, a1, b0, b1 = ox, ox + W, oy, oy + D
            mk, loc, axis, ref, sides = (lambda b, z: (b, z)), (lambda a: (a, 0, 0)), (1, 0, 0), (0, 1, 0), ("W", "E")
        else:
            a0, a1, b0, b1 = oy, oy + D, ox, ox + W
            mk, loc, axis, ref, sides = (lambda b, z: (-b, z)), (lambda a: (0, a, 0)), (0, 1, 0), (-1, 0, 0), ("S", "N")
        bm = (b0 + b1) / 2
        half = bm - b0
        r1 = frac * half
        zk = top + r1 * lo
        zr = zk + (half - r1) * up
        pts_l = [(b0 - ov, top - ov * lo), (b0 + r1, zk), (bm, zr)]
        pts_r = [(b1 + ov, top - ov * lo), (b1 - r1, zk), (bm, zr)]
        length = a1 - a0 + 2 * ov
        items = []
        for pts in (pts_l, pts_r):
            for p, q in zip(pts, pts[1:]):
                poly = [mk(*p), mk(*q), mk(q[0], q[1] - th), mk(p[0], p[1] - th)]
                items.append(self._prism(poly, loc(a0 - ov), axis, ref, length, mat))
        self.element("IfcRoof", f"Dach {v['id']} Mansarddach (Gambrel)", items, z_ref=top, predefined="USERDEFINED", material="Dach")
        outline = [mk(b0, top), mk(b1, top), mk(b1 - r1, zk - th), mk(bm, zr - th), mk(b0 + r1, zk - th)]
        for k, side in enumerate(sides):
            a_start = a0 if k == 0 else a1 - t
            w = self.element("IfcWall", f"Giebel {v['id']}-{side}", [self._prism(outline, loc(a_start), axis, ref, t, fac)], z_ref=top,
                             predefined="SOLIDWALL", material="Mauerwerk verputzt")
            self.pset(w, "Pset_WallCommon", {"IsExternal": True, "LoadBearing": True})
        return {"rise": zr - top}

    def _sawtooth(self, v, ox, oy, W, D, t, top, fac, roof):
        """Sheddach-Reihe (Sägezahn): teeth wedges along y, vertical glazing on the north side of each tooth."""
        n = int(roof.get("teeth", 4))
        pitch = math.radians(float(roof.get("pitch_deg", 15)))
        mat = roof.get("material", "roof_zinc_standing")
        pw = D / n
        H = pw * math.tan(pitch)
        if H > 3.5:
            raise ValueError(f"Sheddach: Zahnhöhe {H:.1f} m zu groß; weniger Neigung oder mehr teeth")
        items, glass = [], []
        for k in range(n):
            ys, ye = oy + k * pw, oy + (k + 1) * pw
            tri = [(ox + t, ys, top), (ox + t, ye, top), (ox + t, ye, top + H)]
            items.append(self._hprism(tri, (1, 0, 0), (ox + t, 0.0, 0.0), W - 2 * t, mat))
            glass.append(self.box(ox + t, ye - 0.04, top, W - 2 * t, 0.06, H, "glass_curtain_blue"))
        self.element("IfcRoof", f"Dach {v['id']} Sheddach", items, z_ref=top, predefined="SHED_ROOF", material="Dach")
        self.element("IfcWindow", f"Oberlicht {v['id']} Shed", glass, z_ref=top, predefined="SKYLIGHT", material="Glas")
        for xa in (ox, ox + W - t):
            tris = []
            for k in range(n):
                ys, ye = oy + k * pw, oy + (k + 1) * pw
                tris.append(self._hprism([(xa, ys, top), (xa, ye, top), (xa, ye, top + H)], (1, 0, 0), (xa, 0.0, 0.0), t, fac))
            self.element("IfcWall", f"Giebel {v['id']} Shed", tris, z_ref=top, predefined="SOLIDWALL", material="Mauerwerk verputzt")
        return {"rise": H}
