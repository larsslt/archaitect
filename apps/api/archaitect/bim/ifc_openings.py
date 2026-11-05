"""Catalog of window/door types, stone surrounds, shutters and flower boxes (mixin for ifcgen.Builder).

Everything works in facade coordinates: u along the side (from the left end seen from outside), d depth into the
wall (negative = in front of the wall), z absolute height. Arches are approximated by polylines; the rectangular
wall opening stays rectangular and the spandrels above an arch are filled with wall material.
"""
from __future__ import annotations

import math

from .geom import facade_box, side_length

ARCH_KINDS = ("round_arch", "segment_arch", "pointed_arch")
WINDOW_KEYS = {"window_type", "top", "bars", "sashes", "transom", "arch_rise", "glass"}


def arch_rise(kind: str, c: float, rise=None) -> float:
    if kind == "round_arch":
        return c / 2
    if kind == "pointed_arch":
        return c * math.sin(math.pi / 3)
    return float(rise) if rise else 0.18 * c


def arch_curve(u0, u1, zs, kind, rise=None, inset=0.0, n=16):
    """Points of the arch curve from the left to the right spring. inset > 0 moves it inwards (concentric)."""
    c = u1 - u0
    um = (u0 + u1) / 2
    if kind == "pointed_arch":
        R = c - inset
        left = [(u1 + R * math.cos(t), zs + R * math.sin(t)) for t in
                [math.pi - (math.pi / 3) * i / n for i in range(n)]]
        right = [(u0 + R * math.cos(t), zs + R * math.sin(t)) for t in
                 [(math.pi / 3) * (1 - i / n) for i in range(n + 1)]]
        return left + right
    r = arch_rise(kind, c, rise)
    R0 = (c * c / 4 + r * r) / (2 * r)
    cz = zs + r - R0
    tl = math.atan2(R0 - r, -c / 2)
    tr = math.atan2(R0 - r, c / 2)
    R = R0 - inset
    return [(um + R * math.cos(tl + (tr - tl) * i / n), cz + R * math.sin(tl + (tr - tl) * i / n)) for i in range(n + 1)]


class OpeningsMixin:
    # ------------------------------------------------------------ helpers
    def _fp(self, v, side, pts, d_out, d_in, style):
        ox, oy = v["origin"]
        W, D = v["size"]
        return self._fprism(side, ox, oy, W, D, pts, d_in - d_out, style, d0=d_in)

    def _fbx(self, v, side, u0, u1, d0, d1, z0, z1, style):
        ox, oy = v["origin"]
        W, D = v["size"]
        return self.box(*facade_box(side, ox, oy, W, D, u0, u1, d0, d1, z0, z1), style)

    def _ring(self, v, side, outer, inner, d0, d1, style):
        """Strip between two polylines with the same number of points."""
        return [self._fp(v, side, [outer[i], outer[i + 1], inner[i + 1], inner[i]], d0, d1, style)
                for i in range(len(outer) - 1)]

    def _spandrels(self, v, side, u0, u1, zs, zt, kind, rise, d0, d1, style):
        arc = arch_curve(u0, u1, zs, kind, rise)
        mid = len(arc) // 2
        if kind == "pointed_arch":
            mid = 16
        um = (u0 + u1) / 2
        left = arc[: mid + 1] + [(um, zt), (u0, zt)]
        right = arc[mid:] + [(u1, zt), (um, zt)]
        out = []
        for pg in (left, right):
            try:
                out.append(self._fp(v, side, pg, d0, d1, style))
            except Exception:  # degenerate polygon: skip, the arch simply sits flush
                pass
        return out

    # ------------------------------------------------------------ windows
    def _window_ext(self, o, v, side, u0, u1, zb, zt, sill):
        fw, fd = self.win["frame_width"], self.win["frame_depth"]
        rd = float(o.get("reveal_depth", self.win["reveal_depth"]))
        fr = o.get("frame", self.win["frame"])
        glass = o.get("glass", self.win["glass"])
        d0, d1 = rd, rd + fd
        dm = (d0 + d1) / 2
        c = u1 - u0
        um = (u0 + u1) / 2
        wt = float(v.get("wall_thickness", self.wall_t))
        fac = v.get("facade", "plaster_white")
        kind = o.get("kind", "window")
        top = o.get("top", "flat")
        wtype = o.get("window_type", "casement")
        fb = lambda a, b, d_a, d_b, za, zb_, st: self._fbx(v, side, a, b, d_a, d_b, za, zb_, st)
        items = []
        if wtype == "oculus" and kind == "window":
            return self._oculus(o, v, side, u0, u1, zb, zt, fr, glass, d0, d1, dm, fac, wt, sill)
        rise = arch_rise(top, c, o.get("arch_rise")) if top in ARCH_KINDS else 0.0
        zs = zt - rise
        if top in ARCH_KINDS and zs - zb < max(0.5, 3 * fw):
            raise ValueError(f"Fenster {o.get('note', '')}: {top} braucht Hoehe >= {rise + max(0.5, 3 * fw):.2f} m bei Breite {c:.2f} m "
                             f"(Bogen allein {rise:.2f} m); Hoehe erhoehen, Breite verringern oder arch_rise/segment_arch waehlen")
        arched = top in ARCH_KINDS
        # ---- frame
        items += [fb(u0, u0 + fw, d0, d1, zb, zs, fr), fb(u1 - fw, u1, d0, d1, zb, zs, fr),
                  fb(u0 + fw, u1 - fw, d0, d1, zb, zb + fw, fr)]
        if arched:
            outer = arch_curve(u0, u1, zs, top, o.get("arch_rise"))
            inner = arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=fw)
            items += self._ring(v, side, outer, inner, d0, d1, fr)
            items += self._spandrels(v, side, u0, u1, zs, zt, top, o.get("arch_rise"), 0.0, wt, fac)
        else:
            items.append(fb(u0 + fw, u1 - fw, d0, d1, zt - fw, zt, fr))
        ztop_in = zs if arched else zt - fw
        # ---- sashes / mullions
        if wtype == "fixed":
            ns = 1
        elif o.get("sashes"):
            ns = int(o["sashes"])
        elif o.get("mullion_spacing"):
            ns = max(1, round(c / float(o["mullion_spacing"])))
        else:
            ns = max(1, round(c / 0.9)) if c > 1.2 else 1
        ns = max(1, min(ns, 6))
        mw = fw * (1.3 if wtype == "casement" else 0.8)
        for k in range(1, ns):
            um_k = u0 + k * c / ns
            items.append(fb(um_k - mw / 2, um_k + mw / 2, d0, d1, zb + fw, ztop_in, fr))
        # ---- transom (Kaempfer)
        if o.get("transom"):
            zk = zb + float(o["transom"]) * (ztop_in - zb)
            items.append(fb(u0 + fw, u1 - fw, d0, d1, zk - fw / 2, zk + fw / 2, fr))
        # ---- glass
        items.append(fb(u0 + fw, u1 - fw, dm - 0.012, dm + 0.012, zb + fw, ztop_in, glass))
        if arched:
            ring_in = arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=fw)
            items.append(self._fp(v, side, ring_in, dm - 0.012, dm + 0.012, glass))
        # ---- Sprossen
        bars = o.get("bars")
        if bars:
            cols, rows = int(bars.get("cols", 2)), int(bars.get("rows", 2))
            bw = float(bars.get("width", 0.028))
            zlo, zhi = zb + fw, ztop_in
            for k in range(1, cols):
                ub = u0 + fw + k * (c - 2 * fw) / cols
                items.append(fb(ub - bw / 2, ub + bw / 2, d0 + 0.01, d1 - 0.01, zlo, zhi, fr))
            for k in range(1, rows):
                zbk = zlo + k * (zhi - zlo) / rows
                items.append(fb(u0 + fw, u1 - fw, d0 + 0.01, d1 - 0.01, zbk - bw / 2, zbk + bw / 2, fr))
        sm = o.get("sill_material", "aluminium")
        if sill > 0 and self.win.get("sill_board", True) and sm != "none":
            items.append(fb(u0 - 0.03, u1 + 0.03, -0.05, d0, zb - 0.03, zb, sm))
        el = self.element("IfcWindow", o.get("note", "Fenster"), items, z_ref=zb, predefined="WINDOW",
                          material="Holz/Glas" if "paint" in str(fr) or "wood" in str(fr) else "Stahl/Glas")
        el.OverallWidth, el.OverallHeight = c, zt - zb
        return el

    def _oculus(self, o, v, side, u0, u1, zb, zt, fr, glass, d0, d1, dm, fac, wt, sill):
        fw = self.win["frame_width"]
        c = min(u1 - u0, zt - zb)
        cu, cz = (u0 + u1) / 2, (zb + zt) / 2
        R = c / 2
        n = 28
        circ = lambda r: [(cu + r * math.cos(2 * math.pi * i / n), cz + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]
        items = self._ring(v, side, circ(R), circ(R - fw), d0, d1, fr)
        items.append(self._fp(v, side, circ(R - fw)[:-1], dm - 0.012, dm + 0.012, glass))
        for k in (1, 2, 3, 4):  # corner fillers between the square opening and the circle
            sx, sz = (1, 1) if k == 1 else (-1, 1) if k == 2 else (-1, -1) if k == 3 else (1, -1)
            a0 = (k - 1) * math.pi / 2
            arc = [(cu + R * math.cos(a0 + math.pi / 2 * i / 7), cz + R * math.sin(a0 + math.pi / 2 * i / 7)) for i in range(8)]
            corner = (cu + sx * (u1 - u0) / 2, cz + sz * (zt - zb) / 2)
            try:
                items.append(self._fp(v, side, [corner] + arc, 0.0, wt, fac))
            except Exception:
                pass
        el = self.element("IfcWindow", o.get("note", "Ochsenauge"), items, z_ref=zb, predefined="WINDOW", material="Holz/Glas")
        el.OverallWidth, el.OverallHeight = u1 - u0, zt - zb
        return el

    # ------------------------------------------------------------ doors
    def _door_ext(self, o, v, side, u0, u1, zb, zt):
        fw, fd = self.win["frame_width"], self.win["frame_depth"]
        rd = float(o.get("reveal_depth", self.win["reveal_depth"]))
        fr = o.get("frame", self.win["frame"])
        panel = o.get("panel", "walnut")
        d0, d1 = rd, rd + fd
        dm = (d0 + d1) / 2
        c = u1 - u0
        wt = float(v.get("wall_thickness", self.wall_t))
        fac = v.get("facade", "plaster_white")
        top = o.get("top", "flat")
        dtype = o.get("door_type", "panel")
        glass = o.get("glass", self.win["glass"])
        fb = lambda a, b, d_a, d_b, za, zb_, st: self._fbx(v, side, a, b, d_a, d_b, za, zb_, st)
        rise = arch_rise(top, c, o.get("arch_rise")) if top in ARCH_KINDS else 0.0
        zs = zt - rise
        if top in ARCH_KINDS and zs - zb < 1.6:
            raise ValueError(f"Tuer {o.get('note', '')}: {top} braucht Hoehe >= {rise + 1.6:.2f} m bei Breite {c:.2f} m (Bogen allein {rise:.2f} m)")
        arched = top in ARCH_KINDS
        items = [fb(u0, u0 + fw, d0, d1, zb, zs, fr), fb(u1 - fw, u1, d0, d1, zb, zs, fr)]
        if arched:
            outer = arch_curve(u0, u1, zs, top, o.get("arch_rise"))
            inner = arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=fw)
            items += self._ring(v, side, outer, inner, d0, d1, fr)
            items += self._spandrels(v, side, u0, u1, zs, zt, top, o.get("arch_rise"), 0.0, wt, fac)
        else:
            items.append(fb(u0 + fw, u1 - fw, d0, d1, zt - fw, zt, fr))
        ztop = zs if arched else zt - fw
        zl0 = zb + 0.02
        # fixed light above a transom (Oberlicht)
        zleaf = ztop
        if o.get("transom"):
            zleaf = zb + float(o["transom"]) * (ztop - zb)
            items.append(fb(u0 + fw, u1 - fw, d0, d1, zleaf - fw / 2, zleaf + fw / 2, fr))
            items.append(fb(u0 + fw, u1 - fw, dm - 0.012, dm + 0.012, zleaf + fw / 2, ztop, glass))
            if arched:
                items.append(self._fp(v, side, arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=fw), dm - 0.012, dm + 0.012, glass))
            zleaf -= fw / 2
        leaves = [(u0 + fw, u1 - fw)] if dtype not in ("double", "french") else [(u0 + fw, (u0 + u1) / 2 - 0.006), ((u0 + u1) / 2 + 0.006, u1 - fw)]
        for li, (a, b) in enumerate(leaves):
            if arched and not o.get("transom"):
                inner = arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=fw)
                pts = [q for q in inner if a - 1e-6 <= q[0] <= b + 1e-6]
                if not pts:
                    pts = [(a, zs), (b, zs)]
                if abs(pts[0][0] - a) > 1e-3:
                    pts = [(a, pts[0][1])] + pts
                if abs(pts[-1][0] - b) > 1e-3:
                    pts = pts + [(b, pts[-1][1])]
                items.append(self._fp(v, side, [(a, zl0)] + pts + [(b, zl0)], dm - 0.03, dm + 0.03, panel))
                zpan_top = zs - 0.15
            else:
                items.append(fb(a, b, dm - 0.03, dm + 0.03, zl0, zleaf, panel))
                zpan_top = zleaf - 0.12
            lw = b - a
            if dtype in ("panel", "double"):
                m = 0.12
                rows = [(zl0 + m, zl0 + (zpan_top - zl0) * 0.58), (zl0 + (zpan_top - zl0) * 0.58 + m, zpan_top)]
                for (pa, pb) in rows:
                    if pb - pa > 0.15 and lw > 2 * m + 0.1:
                        items.append(fb(a + m, b - m, dm - 0.045, dm - 0.03, pa, pb, panel))
            elif dtype == "plank":
                n = max(3, round(lw / 0.14))
                for k in range(1, n):
                    uj = a + k * lw / n
                    items.append(fb(uj - 0.004, uj + 0.004, dm - 0.034, dm - 0.03, zl0 + 0.05, zpan_top + 0.05 if not arched else zpan_top, "timber_black"))
                for zk in (zl0 + 0.35, zpan_top - 0.3):  # Zierbaender / Querleisten
                    items.append(fb(a + 0.03, b - 0.03, dm - 0.04, dm - 0.03, zk, zk + 0.12, "timber_black"))
            elif dtype == "sectional":
                zk = zl0 + 0.5
                while zk < zpan_top + 0.1:
                    items.append(fb(a, b, dm - 0.036, dm - 0.03, zk - 0.008, zk + 0.008, "steel_black"))
                    zk += 0.5
            elif dtype == "full_glass":
                items.append(fb(a + 0.06, b - 0.06, dm - 0.04, dm + 0.04, zl0 + 0.1, zpan_top + 0.05, glass))
                items.append(fb(a, b, dm - 0.035, dm + 0.035, zl0, zl0 + 0.1, panel))
            elif dtype in ("glazed", "french"):
                zg0 = zl0 + (zleaf - zl0) * (0.38 if dtype == "glazed" else 0.1)
                bw = 0.1 if dtype == "glazed" else 0.06
                gi = fb(a + bw, b - bw, dm - 0.04, dm + 0.04, zg0, zpan_top, glass)
                items.append(gi)
                for (ua, ub, za, zb2) in ((a, a + bw, zg0, zleaf), (b - bw, b, zg0, zleaf), (a + bw, b - bw, zpan_top, zleaf)):
                    if ub > ua and zb2 > za:
                        items.append(fb(ua, ub, dm - 0.035, dm + 0.035, za, zb2, panel))
        hz = zb + 1.05
        hand = o.get("handle", "chrome")
        if dtype in ("double", "french"):
            um = (u0 + u1) / 2
            for uh in (um - 0.09, um + 0.09):
                items.append(fb(uh - 0.02, uh + 0.02, d0 - 0.07, d0 - 0.03, hz - 0.35, hz + 0.35, hand))
        else:
            items.append(fb(u1 - fw - 0.16, u1 - fw - 0.12, d0 - 0.06, d0, hz - 0.5, hz + 0.5, hand))
        el = self.element("IfcDoor", o.get("note", "Tuer"), items, z_ref=zb, predefined="DOOR", material="Holz")
        el.OverallWidth, el.OverallHeight = c, zt - zb
        return el

    # ------------------------------------------------------------ surround, shutters, flower box
    def _opening_extras(self, o, v, side, u0, u1, zb, zt, sill):
        if o.get("surround"):
            self._surround(o, v, side, u0, u1, zb, zt, sill)
        if o.get("shutters"):
            self._shutters(o, v, side, u0, u1, zb, zt)
        if o.get("flower_box") and o.get("kind", "window") == "window":
            self._flower_box(o, v, side, u0, u1, zb)

    def _surround(self, o, v, side, u0, u1, zb, zt, sill):
        sd = o["surround"]
        mat = sd.get("material", "stone_ashlar_light")
        w = float(sd.get("width", 0.16))
        dep = float(sd.get("depth", 0.05))
        lintel = sd.get("lintel", "flat")
        top = o.get("top", "flat")
        c = u1 - u0
        um = (u0 + u1) / 2
        fbx = lambda a, b, d_a, d_b, za, zb_, st=mat: self._fbx(v, side, a, b, d_a, d_b, za, zb_, st)
        fpo = lambda pts, d_a, d_b, st=mat: self._fp(v, side, pts, d_a, d_b, st)
        items = []
        arched = top in ARCH_KINDS
        rise = arch_rise(top, c, o.get("arch_rise")) if arched else 0.0
        zs = zt - rise
        if arched and zs - zb < 0.5:
            arched, zs = False, zt
        z_low = zb - (0.06 if (sill > 0 and sd.get("sill", True)) else 0.0)
        items.append(fbx(u0 - w, u0, -dep, 0.0, z_low if sill > 0 else zb, zs if arched else zt))
        items.append(fbx(u1, u1 + w, -dep, 0.0, z_low if sill > 0 else zb, zs if arched else zt))
        zr = zt
        if arched:
            outer = arch_curve(u0, u1, zs, top, o.get("arch_rise"), inset=-w)
            inner = arch_curve(u0, u1, zs, top, o.get("arch_rise"))
            items += self._ring(v, side, outer, inner, -dep, 0.0, mat)
            if sd.get("keystone", True):
                ia = len(outer) // 2
                ap = outer[ia]
                items.append(fpo([(um - 0.09, ap[1] - 0.2 - 0.0), (um + 0.09, ap[1] - 0.2), (um + 0.13, ap[1] + 0.06), (um - 0.13, ap[1] + 0.06)], -dep - 0.03, 0.0))
            zr = max(p[1] for p in outer)
        else:
            lh = float(sd.get("lintel_height", w * 1.2))
            items.append(fbx(u0 - w, u1 + w, -dep, 0.0, zt, zt + lh))
            zr = zt + lh
            if lintel == "keystone":
                items.append(fpo([(um - 0.1, zt - 0.1), (um + 0.1, zt - 0.1), (um + 0.14, zt + lh + 0.04), (um - 0.14, zt + lh + 0.04)], -dep - 0.03, 0.0))
            elif lintel == "pediment":
                span = c + 2 * w + 0.12
                items.append(fpo([(u0 - w - 0.06, zr), (u1 + w + 0.06, zr), (um, zr + span * 0.22)], -dep - 0.04, 0.0))
            elif lintel == "segment_pediment":
                span = c + 2 * w + 0.12
                arc = arch_curve(u0 - w - 0.06, u1 + w + 0.06, zr, "segment_arch", span * 0.12)
                items.append(fpo(arc, -dep - 0.04, 0.0))
            elif lintel == "hood":
                items.append(fbx(u0 - w - 0.1, u1 + w + 0.1, -0.25, 0.0, zr, zr + 0.07))
                for ub in (u0 - w / 2, u1 + w / 2):
                    items.append(self._sprism_at(v, side, [(0.0, zr), (-0.22, zr), (0.0, zr - 0.3)], ub - 0.05, 0.1, mat))
        if sill > 0 and sd.get("sill", True):
            items.append(fbx(u0 - w - 0.04, u1 + w + 0.04, -dep - 0.05, 0.0, zb - 0.07, zb))
        self.element("IfcBuildingElementProxy", f"Gewaende {o.get('note', 'Oeffnung')}", items, z_ref=zb, predefined="USERDEFINED", material="Naturstein")

    def _sprism_at(self, v, side, pts_dz, u_pos, thick, style):
        ox, oy = v["origin"]
        W, D = v["size"]
        return self._sprism(side, ox, oy, W, D, pts_dz, u_pos, thick, style)

    def _shutters(self, o, v, side, u0, u1, zb, zt):
        sh = o["shutters"]
        mat = sh.get("material", "paint_green_dark")
        state = sh.get("state", "open")
        style = sh.get("style", "louvre")
        c = u1 - u0
        lw = c / 2 - 0.01 if state == "closed" else max(0.3, c / 2 - 0.02)
        leaves = [(u0 - lw - 0.03, u0 - 0.03), (u1 + 0.03, u1 + lw + 0.03)] if state == "open" else [(u0 + 0.0, u0 + c / 2 - 0.005), (u0 + c / 2 + 0.005, u1)]
        z0, z1 = zb - (0.0 if state == "closed" else 0.0), zt
        depth = (-0.05, -0.012)
        items = []
        for (a, b) in leaves:
            fw = 0.06
            items += [self._fbx(v, side, a, a + fw, depth[0], depth[1], z0, z1, mat), self._fbx(v, side, b - fw, b, depth[0], depth[1], z0, z1, mat),
                      self._fbx(v, side, a + fw, b - fw, depth[0], depth[1], z0, z0 + 0.08, mat),
                      self._fbx(v, side, a + fw, b - fw, depth[0], depth[1], z1 - 0.08, z1, mat)]
            if style == "louvre":
                zk = z0 + 0.1
                while zk + 0.03 < z1 - 0.1:
                    items.append(self._sprism_at(v, side, [(-0.05, zk), (-0.05, zk + 0.008), (-0.012, zk + 0.034), (-0.012, zk + 0.026)], a + fw, (b - a) - 2 * fw, mat))
                    zk += 0.06
            elif style == "panel":
                items.append(self._fbx(v, side, a + fw, b - fw, -0.04, -0.012, z0 + 0.08, z1 - 0.08, mat))
                zm = (z0 + z1) / 2
                items.append(self._fbx(v, side, a + fw, b - fw, -0.055, -0.04, zm - 0.04, zm + 0.04, mat))
            else:  # plank: Brettlaeden with Z-brace look
                n = max(3, round((b - a - 2 * fw) / 0.12))
                for k in range(n):
                    ua = a + fw + k * (b - a - 2 * fw) / n
                    items.append(self._fbx(v, side, ua + 0.003, ua + (b - a - 2 * fw) / n - 0.003, -0.04, -0.012, z0 + 0.08, z1 - 0.08, mat))
        self.element("IfcBuildingElementProxy", f"Fensterlaeden {o.get('note', '')}".strip(), items, z_ref=zb, predefined="USERDEFINED", material="Holz")

    def _flower_box(self, o, v, side, u0, u1, zb):
        fb = o["flower_box"]
        mat = fb.get("material", "paint_brown") if isinstance(fb, dict) else "paint_brown"
        z1 = zb - 0.03
        items = [self._fbx(v, side, u0 - 0.04, u1 + 0.04, -0.26, -0.04, z1 - 0.2, z1, mat)]
        n = max(2, round((u1 - u0) / 0.25))
        for k in range(n):
            ua = u0 - 0.02 + k * (u1 - u0 + 0.04) / n
            items.append(self._fbx(v, side, ua + 0.01, ua + (u1 - u0 + 0.04) / n - 0.01, -0.24, -0.06, z1, z1 + 0.16 + 0.04 * (k % 2), "boxwood"))
        self.element("IfcBuildingElementProxy", "Blumenkasten", items, z_ref=zb, predefined="USERDEFINED", material="Holz")
