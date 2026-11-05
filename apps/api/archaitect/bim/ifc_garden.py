"""Garden / site objects (catalog stage 5): tree, hedge, shrub, flowerbed, path, pool, bench, garden_set, garden_light.
All are free standing (absolute x/y). Names containing 'Buchs' get the organic hedge look in the Blender render."""
from __future__ import annotations

import math


def _need(c, i, t, *keys):
    miss = [k for k in keys if c.get(k) is None]
    if miss:
        raise ValueError(f"components[{i}] ({t}): {', '.join(miss)} sind Pflicht")


def _lcg(seed):
    st = [seed % 2147483647 or 1]

    def nxt():
        st[0] = st[0] * 16807 % 2147483647
        return st[0] / 2147483647
    return nxt


def sauna_layout(w: float) -> dict:
    """Front-wall layout of the sauna hut (local x along the front): the door, real window holes and the porch bench - the bench never stands in front of the door."""
    door_x = w * 0.5 - 0.4
    ops = [(door_x, door_x + 0.8, 0.0, 1.95)]
    lx1 = door_x - 0.2
    if lx1 - 0.65 >= 0.15:
        ops.append((lx1 - 0.65, lx1, 1.0, 1.7))
    rx0 = door_x + 1.0
    if rx0 + 0.65 <= w - 0.15:
        ops.append((rx0, rx0 + 0.65, 1.0, 1.7))
    bx1 = door_x - 0.45
    bx0 = max(0.1, bx1 - 1.3)
    return {"wall": 0.14, "door_x": door_x, "openings": ops, "bench": (bx0, bx1), "door_clear": (door_x - 0.45, door_x + 1.25)}


class GardenMixin:
    def _veg(self, name, items, z=0.0, at=None):
        """``at``: (x, y) points the element stands on; with graded terrain it is lifted/sunk to the ground there."""
        return self.element("IfcGeographicElement", name, items, z_ref=z, predefined="VEGETATION", dz=self.ground_z(*at) if at else 0.0)

    # ------------------------------------------------------------------ vegetation
    def _c_tree(self, c, i, v=None):
        _need(c, i, "tree", "x", "y")
        x, y, H, R = c["x"], c["y"], c["height"], c["crown_radius"]
        if c["kind"] == "conifer":
            zb, n = max(0.6, H * 0.12), 14
            prof = [(R, zb)]
            tiers = 5
            for k in range(tiers):
                z = zb + (H - zb) * k / tiers
                r = R * (1 - k / tiers * 0.85)
                prof += [(r, z + 0.001), (r * 0.55, z + (H - zb) / tiers * 0.7)]
            prof += [(0.0, H)]
            self._veg("Konifere", [self._revolve(prof, x, y, "boxwood", n)], at=[(x, y)])
            self._veg("Konifere Stamm", [self.cylinder((x, y, 0.0), (x, y, zb + 0.3), 0.1, "bark")], at=[(x, y)])
            return
        if H - R < 0.8:
            raise ValueError(f"components[{i}] (tree): Stamm zu kurz: height {H} muss mindestens crown_radius {R} + 0,8 m sein")
        # trunk with root flare, fork and branches into a crown made of several overlapping foliage masses (never one ball)
        rr = max(0.12, R * 0.06)
        zt = H - R * 1.25                                   # fork height
        rng = _lcg(int(abs(x) * 100) * 7919 + int(abs(y) * 100) * 104729 + 13)
        items = [self.cylinder((x, y, 0.0), (x, y, 0.45), rr * 1.45, "bark"), self.cylinder((x, y, 0.4), (x, y, zt), rr, "bark")]
        blobs = [(0.0, 0.0, H - R * 0.95, R * 0.62)]        # top mass
        for k in range(6):
            ang = (k + rng() * 0.5) * math.pi / 3
            rad = R * (0.42 + 0.25 * rng())
            blobs.append((math.cos(ang) * rad, math.sin(ang) * rad, H - R * (0.85 + 0.55 * rng()), R * (0.38 + 0.2 * rng())))
        for bx, by, bz, br in blobs[1:5]:                     # branches from the fork to the foliage masses
            items.append(self.cylinder((x, y, zt), (x + bx * 0.8, y + by * 0.8, bz - br * 0.2), rr * 0.5, "bark"))
        self._veg(c.get("note") or "Baum", items, at=[(x, y)])
        crown = []
        for bx, by, bz, br in blobs:
            prof = [(0.0, bz - br * 0.78), (br * 0.62, bz - br * 0.62), (br * 0.97, bz - br * 0.2), (br, bz), (br * 0.9, bz + br * 0.4), (br * 0.55, bz + br * 0.8), (0.0, bz + br * 0.92)]
            crown.append(self._revolve(prof, x + bx, y + by, "foliage", 14))
        self._veg("Baum Krone", crown, at=[(x, y)])

    def _c_hedge(self, c, i, v=None):
        _need(c, i, "hedge", "x0", "y0", "x1", "y1")
        x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
        if abs(x1 - x0) > 1e-6 and abs(y1 - y0) > 1e-6:
            raise ValueError(f"components[{i}] (hedge): nur achsparallel; x0==x1 oder y0==y1 setzen")
        t = c["thickness"]
        if abs(x1 - x0) <= 1e-6:
            b = (x0 - t / 2, min(y0, y1) - t / 2, t, abs(y1 - y0) + t)
        else:
            b = (min(x0, x1) - t / 2, y0 - t / 2, abs(x1 - x0) + t, t)
        self._veg("Buchs Hecke", [self.box(*b[:2], 0.0, b[2], b[3], c["height"], "boxwood")], at=self._corners(b[0], b[1], b[2], b[3]))

    def _c_shrub(self, c, i, v=None):
        _need(c, i, "shrub", "x", "y")
        x, y, r, h = c["x"], c["y"], c["radius"], c["height"]
        z0 = 0.4 if c["pot"] else 0.0
        items = [self._revolve([(0.0, z0), (r * 0.8, z0 + h * 0.15), (r, z0 + h * 0.45), (r * 0.85, z0 + h * 0.8), (0.0, z0 + h)], x, y, "boxwood", 14)]
        self._veg("Buchs Strauch", items, at=[(x, y)])
        if c["pot"]:
            pr = min(r, 0.5)
            self.element("IfcBuildingElementProxy", "Pflanzkübel", [self._revolve([(pr * 0.7, 0.0), (pr, 0.4), (pr * 0.92, 0.42)], x, y, "plaster_terracotta", 16)],
                         predefined="USERDEFINED", material="Terrakotta", dz=self.ground_z((x, y)))

    def _c_flowerbed(self, c, i, v=None):
        _need(c, i, "flowerbed", "x", "y")
        x, y, w, d = c["x"], c["y"], c["width"], c["depth"]
        bt, bh = 0.12, 0.16
        items = [self.box(x - bt, y - bt, 0.0, w + 2 * bt, bt, bh, c["border_material"]), self.box(x - bt, y + d, 0.0, w + 2 * bt, bt, bh, c["border_material"]),
                 self.box(x - bt, y, 0.0, bt, d, bh, c["border_material"]), self.box(x + w, y, 0.0, bt, d, bh, c["border_material"])]
        self.element("IfcBuildingElementProxy", "Beeteinfassung", items, predefined="USERDEFINED", material="Naturstein",
                     dz=self.ground_z(*self._corners(x, y, w, d)))
        self.element("IfcBuildingElementProxy", "Beeterde", [self.box(x, y, 0.0, w, d, bh - 0.03, "soil_dark")], predefined="USERDEFINED", material="Erde")
        n = min(70, int(w * d * c["density"]))
        cols = [k.strip() for k in c["flowers"].split(",") if k.strip()]
        seed = 17
        fl, gr = [], []
        for k in range(n):
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            fx = x + 0.15 + (seed % 1000) / 1000 * max(0.01, w - 0.3)
            seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
            fy = y + 0.15 + (seed % 1000) / 1000 * max(0.01, d - 0.3)
            r = 0.09 + (seed % 7) * 0.01
            gr.append(self._revolve([(0.0, bh - 0.05), (0.13, bh + 0.05), (0.1, bh + 0.17), (0.0, bh + 0.22)], fx, fy, "boxwood", 8))
            fl.append(self._revolve([(0.0, bh + 0.14), (r, bh + 0.2), (0.0, bh + 0.3)], fx, fy, cols[k % len(cols)], 8))
        if gr:
            self._veg("Buchs Beetgrün", gr)
            self.element("IfcGeographicElement", "Blumen", fl, predefined="VEGETATION")

    # ------------------------------------------------------------------ ground
    def _pbox(self, x, y, dx, dy, style, piece=0.9):
        """Path slab that follows the graded ground: short pieces, each sunk 10 cm and standing 4 cm proud of the highest ground under it
        (a flat 5 cm slab disappears into the 2 m terrain mesh from a distance)."""
        n = max(1, math.ceil(max(dx, dy) / piece))
        out = []
        for k in range(n):
            if dx >= dy:
                px, py, pw, ph = x + dx * k / n, y, dx / n, dy
            else:
                px, py, pw, ph = x, y + dy * k / n, dx, dy / n
            gz = [self.ground_z((cx, cy)) for cx, cy in ((px, py), (px + pw, py), (px, py + ph), (px + pw, py + ph), (px + pw / 2, py + ph / 2))]
            zb, zt = min(gz) - 0.10, max(gz) + 0.06
            out.append(self.box(px, py, zb, pw, ph, zt - zb, style))
        return out

    def _c_path(self, c, i, v=None):
        pts = c["points"]
        if pts is None:
            raise ValueError(f"components[{i}] (path): points sind Pflicht (Liste von [x,y], achsparallele Abschnitte)")
        w, m = c["width"], c["material"]
        segs = []
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
                raise ValueError(f"components[{i}] (path): Abschnitt {a}->{b} nicht achsparallel")
            if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
                raise ValueError(f"components[{i}] (path): doppelter Punkt {a}")
            segs.append((a, b))
        horiz = [abs(a[1] - b[1]) < 1e-6 for a, b in segs]
        if any(h1 == h2 for h1, h2 in zip(horiz, horiz[1:])):
            raise ValueError(f"components[{i}] (path): aufeinanderfolgende Abschnitte müssen die Richtung wechseln (Knick); gerade Strecken als einen Abschnitt angeben")
        items = []
        hw = w / 2
        for k, ((a, b), h) in enumerate(zip(segs, horiz)):
            first, last = k == 0, k == len(segs) - 1
            if h:  # x-parallel pieces own the corner squares, y-parallel pieces stop at them
                lo, hi = min(a[0], b[0]) - hw, max(a[0], b[0]) + hw
                items.extend(self._pbox(lo, a[1] - hw, hi - lo, w, m))
            else:
                sg = 1 if b[1] > a[1] else -1
                e0 = a[1] + sg * hw if not first else a[1] - sg * hw
                e1 = b[1] - sg * hw if not last else b[1] + sg * hw
                lo, hi = min(e0, e1), max(e0, e1)
                items.extend(self._pbox(a[0] - hw, lo, w, hi - lo, m))
        self.element("IfcBuildingElementProxy", "Gartenweg", items, predefined="USERDEFINED", material="Belag")

    def _c_pool(self, c, i, v=None):
        _need(c, i, "pool", "x", "y")
        x, y, w, d, cp = c["x"], c["y"], c["width"], c["depth"], c["coping"]
        items = [self.box(x - cp, y - cp, 0.0, w + 2 * cp, cp, 0.1, c["coping_material"]), self.box(x - cp, y + d, 0.0, w + 2 * cp, cp, 0.1, c["coping_material"]),
                 self.box(x - cp, y, 0.0, cp, d, 0.1, c["coping_material"]), self.box(x + w, y, 0.0, cp, d, 0.1, c["coping_material"])]
        self.element("IfcBuildingElementProxy", "Beckenrand", items, predefined="USERDEFINED", material="Naturstein")
        self.element("IfcBuildingElementProxy", "Becken Wasser", [self.box(x, y, -c["deep"], w, d, c["deep"] + 0.04, "water")], predefined="USERDEFINED")

    # ------------------------------------------------------------------ sauna hut
    def _c_sauna_hut(self, c, i, v=None):
        """Log sauna: point foundations down to the ground (slope / shore), cedar body, gable roof with overhang, stove pipe, porch with bench."""
        _need(c, i, "sauna_hut", "x", "y")
        x, y, w, d, face = c["x"], c["y"], c["width"], c["depth"], c["facing"]
        porch = 1.5
        TD = d + porch                      # local depth incl. porch; ly = 0 is the porch front, the hut body starts at ly = porch
        Wd, Dd = (w, TD) if face in "SN" else (TD, w)

        def B(lx, ly, lz, dx, dy, dz, st):           # local box (lx along the front, ly away from the front) -> world box
            if face == "S":
                return self.box(x + lx, y + ly, lz, dx, dy, dz, st)
            if face == "N":
                return self.box(x + lx, y + TD - ly - dy, lz, dx, dy, dz, st)
            if face == "W":
                return self.box(x + ly, y + lx, lz, dy, dx, dz, st)
            return self.box(x + TD - ly - dy, y + lx, lz, dy, dx, dz, st)

        def world(lx, ly):
            return {"S": (x + lx, y + ly), "N": (x + lx, y + TD - ly), "W": (x + ly, y + lx), "E": (x + TD - ly, y + lx)}[face]
        pts = [world(a, b) for a, b in ((0, 0), (w, 0), (0, TD), (w, TD), (w / 2, TD / 2))]
        gz = [self.ground_z(p) for p in pts]
        base = max(gz) + 0.45                         # floor above the highest ground point; piers reach the lowest
        zt = base + 2.2
        wm, rm = c["wall_material"], c["roof_material"]
        piers = [B(lx, ly, min(gz) - 0.3, 0.3, 0.3, base - min(gz) + 0.3 - 0.12, "stone_granite_grey")
                 for lx in (0.1, w / 2 - 0.15, w - 0.4) for ly in (0.1, porch + d / 2 - 0.15, porch + d - 0.4)]
        self.element("IfcBuildingElementProxy", "Saunahütte Fundament", piers, z_ref=min(gz), predefined="USERDEFINED", material="Naturstein")
        lay = sauna_layout(w)
        t, door_x = lay["wall"], lay["door_x"]
        ops = lay["openings"]                          # (x0, x1, z0, z1) in the front wall; real holes, the panes sit in them
        H = 2.2
        body = [B(0.0, porch, base - 0.12, w, d, 0.12, "wood_pine")]
        xs = sorted({0.0, w, *[o[0] for o in ops], *[o[1] for o in ops]})
        for xa, xb in zip(xs, xs[1:]):                 # front wall in pieces around the openings
            hit = [o for o in ops if o[0] <= xa + 1e-6 and o[1] >= xb - 1e-6]
            if not hit:
                body.append(B(xa, porch, base, xb - xa, t, H, wm))
            else:
                o = hit[0]
                if o[2] > 0.01:
                    body.append(B(xa, porch, base, xb - xa, t, o[2], wm))
                if o[3] < H - 0.01:
                    body.append(B(xa, porch, base + o[3], xb - xa, t, H - o[3], wm))
        body += [B(0.0, porch + d - t, base, w, t, H, wm), B(0.0, porch + t, base, t, d - 2 * t, H, wm), B(w - t, porch + t, base, t, d - 2 * t, H, wm),
                 B(0.0, porch, base + H - 0.1, w, d, 0.1, "wood_pine")]
        for k in range(1, 8):                          # log courses: dark joint lines, interrupted by the openings
            z = base + k * 0.28
            if z > base + H - 0.1:
                break
            body += [B(0.0, porch + d - t - 0.012, z, w, 0.012, 0.025, "timber_brown_dark"), B(-0.012, porch + t, z, 0.012, d - 2 * t, 0.025, "timber_brown_dark"),
                     B(w, porch + t, z, 0.012, d - 2 * t, 0.025, "timber_brown_dark")]
            cuts = sorted([(o[0], o[1]) for o in ops if o[2] - 0.03 <= k * 0.28 <= o[3] + 0.03])
            x0 = 0.0
            for ca, cb in cuts + [(w, w)]:
                if ca - x0 > 0.02:
                    body.append(B(x0, porch - 0.012, z, ca - x0, 0.012, 0.025, "timber_brown_dark"))
                x0 = max(x0, cb)
        # door: leaf with a round porthole (glass disc in a timber ring), frame, handle
        body += [B(door_x, porch - 0.04, base, 0.8, 0.05, 1.95, "timber_brown_dark"), B(door_x - 0.08, porch - 0.05, base, 0.08, 0.06, 2.05, "wood_oak"),
                 B(door_x + 0.8, porch - 0.05, base, 0.08, 0.06, 2.05, "wood_oak"), B(door_x - 0.08, porch - 0.05, base + 1.95, 0.96, 0.06, 0.1, "wood_oak"),
                 B(door_x + 0.66, porch - 0.07, base + 0.95, 0.03, 0.03, 0.22, "steel_black")]
        pcx = door_x + 0.4
        pz = base + 1.45
        o0, o1 = world(pcx, porch - 0.045), world(pcx, porch - 0.075)
        body += [self.cylinder((*o0, pz), (*o1, pz), 0.24, "wood_oak"), self.cylinder((*world(pcx, porch - 0.07), pz), (*world(pcx, porch - 0.085), pz), 0.19, "glass_clear")]
        for (wx0, wx1, wz0, wz1) in ops:               # windows: clear glass in the hole, timber frame and a cross mullion
            if abs(wx0 - door_x) < 0.01:
                continue
            gw, gh = wx1 - wx0, wz1 - wz0
            body += [B(wx0 + 0.02, porch + t / 2, base + wz0 + 0.02, gw - 0.04, 0.02, gh - 0.04, "glass_clear"),
                     B(wx0 - 0.05, porch - 0.045, base + wz0 - 0.05, gw + 0.1, 0.05, 0.05, "wood_oak"), B(wx0 - 0.05, porch - 0.045, base + wz1, gw + 0.1, 0.05, 0.05, "wood_oak"),
                     B(wx0 - 0.05, porch - 0.045, base + wz0, 0.05, 0.05, gh, "wood_oak"), B(wx1, porch - 0.045, base + wz0, 0.05, 0.05, gh, "wood_oak"),
                     B(wx0 + gw / 2 - 0.015, porch - 0.03, base + wz0, 0.03, 0.04, gh, "wood_oak"), B(wx0, porch - 0.03, base + wz0 + gh / 2 - 0.015, gw, 0.04, 0.03, "wood_oak")]
        # inside (visible through the panes): two benches and the stove
        body += [B(t, porch + d - t - 0.6, base + 0.45, w - 2 * t, 0.6, 0.05, "wood_cedar"), B(t, porch + d - t - 0.55, base + 0.95, w - 2 * t, 0.5, 0.05, "wood_cedar"),
                 B(w - 1.0, porch + t + 0.15, base, 0.5, 0.5, 0.85, "steel_black")]
        self.element("IfcBuildingElementProxy", "Saunahütte Körper", body, z_ref=base, predefined="USERDEFINED", material="Holz")
        # gable: triangular prism under the roof, ridge parallel to the front
        rise = (d / 2 + 0.35) * math.tan(math.radians(28))
        ov = 0.4
        sl = rise * 0.82 / (d / 2)          # roof underside follows the gable slope: no gap between gable and roof
        if face in "SN":
            a0, a1 = (porch, porch + d) if face == "S" else (TD - porch - d, TD - porch)
            axis, ref, loc = (1, 0, 0), (0, 1, 0), (x, 0, 0)
            prof = lambda u: (y + u, 0)  # noqa: E731
            ya, yb, ym = y + a0 - ov, y + a1 + ov, y + (a0 + a1) / 2
            tri = [(y + a0, zt), (y + a1, zt), (ym, zt + rise * 0.82)]
            roof = [(ya, zt - sl * ov), (ym, zt + rise * 0.82), (yb, zt - sl * ov), (yb, zt - sl * ov + 0.13), (ym, zt + rise * 0.82 + 0.13), (ya, zt - sl * ov + 0.13)]
            ext0, ext1 = x - 0.35, x + w + 0.35
        else:
            a0, a1 = (porch, porch + d) if face == "W" else (TD - porch - d, TD - porch)
            axis, ref, loc = (0, 1, 0), (-1, 0, 0), (0, y, 0)
            xa, xb, xm = x + a0 - ov, x + a1 + ov, x + (a0 + a1) / 2
            tri = [(-(x + a0), zt), (-(x + a1), zt), (-xm, zt + rise * 0.82)]
            roof = [(-xa, zt - sl * ov), (-xm, zt + rise * 0.82), (-xb, zt - sl * ov), (-xb, zt - sl * ov + 0.13), (-xm, zt + rise * 0.82 + 0.13), (-xa, zt - sl * ov + 0.13)]
            ext0, ext1 = y - 0.35, y + w + 0.35
        if face in "SN":
            tri_p = tri
            roof_p = roof
            gloc, rloc = (x, 0.0, 0.0), (ext0, 0.0, 0.0)
        else:
            tri_p, roof_p = tri, roof
            gloc, rloc = (0.0, y, 0.0), (0.0, ext0, 0.0)
        gab = [self._prism(tri_p, gloc, axis, ref, w, wm)]
        self.element("IfcBuildingElementProxy", "Saunahütte Giebel", gab, z_ref=zt, predefined="USERDEFINED", material="Holz")
        self.element("IfcRoof", "Saunahütte Dach", [self._prism(roof_p, rloc, axis, ref, ext1 - ext0, rm)], z_ref=zt, predefined="GABLE_ROOF", material="Holzschindeln")
        # stove pipe, porch deck with bench, steps
        cx, cy = world(w * 0.78, porch + d * 0.35)
        self.element("IfcBuildingElementProxy", "Saunahütte Ofenrohr", [self.cylinder((cx, cy, zt - 0.3), (cx, cy, zt + rise + 0.75), 0.075, "steel_black"),
                                                                       self.cylinder((cx, cy, zt + rise + 0.75), (cx, cy, zt + rise + 0.85), 0.11, "steel_black")],
                     z_ref=zt, predefined="USERDEFINED", material="Stahl")
        bx0, bx1 = lay["bench"]
        deck = [B(-0.1, 0.0, base - 0.1, w + 0.2, porch, 0.1, "wood_weathered"), B(bx0, 0.12, base + 0.4, bx1 - bx0, 0.38, 0.05, "wood_cedar"),
                B(bx0 + 0.05, 0.2, base, 0.08, 0.22, 0.4, "wood_cedar"), B(bx1 - 0.13, 0.2, base, 0.08, 0.22, 0.4, "wood_cedar")]
        deck += [B(w * 0.5 - 0.5, -0.32, base - 0.3, 1.0, 0.32, 0.3, "wood_weathered"), B(w * 0.5 - 0.5, -0.64, base - 0.6, 1.0, 0.32, 0.3, "wood_weathered")] if base - min(gz) > 0.5 else []
        self.element("IfcBuildingElementProxy", "Saunahütte Vorbau", deck, z_ref=base, predefined="USERDEFINED", material="Holz")

    # ------------------------------------------------------------------ natural water
    def _rock(self, x, y, r, h, k, zbase, style, dz=0.0, name="Findling"):
        """Irregular boulder: faceted, flattened, tilted outline (never a cube)."""
        import math
        n = 7 + k % 3
        prof = [(0.0, zbase), (r * (0.85 + 0.1 * (k % 3)), zbase + h * 0.12), (r, zbase + h * 0.45), (r * 0.72, zbase + h * 0.85), (r * 0.3, zbase + h)]
        prof.append((0.0, zbase + h * 1.02))
        return self.element("IfcBuildingElementProxy", name, [self._revolve(prof, x, y, style, n)], z_ref=zbase, predefined="USERDEFINED",
                            material="Naturstein", dz=dz)

    def _shore(self, ring, level, c, i, seed, water_poly=None):
        """Biodiverse bank: boulder groups, reed beds, water lilies, shrubs and trees. Deterministic from ``seed`` so a rebuild looks the same."""
        import math
        import random
        from shapely.geometry import Point, Polygon
        rnd = random.Random(seed)
        pg = Polygon(ring)
        if not pg.is_valid or pg.area < 4:
            return
        cx, cy = pg.centroid.x, pg.centroid.y
        pts = list(pg.exterior.coords)[:-1]
        m = len(pts)

        def out(px, py, dist):          # point moved away from the lake centre
            dx, dy = px - cx, py - cy
            ln = math.hypot(dx, dy) or 1.0
            return px + dx / ln * dist, py + dy / ln * dist
        # boulder groups: 3-5 stones of different size, clustered, a few lying half in the water
        styles = ("stone_granite_grey", "stone_basalt_dark", "stone_limestone", "stone_field", "stone_sandstone_yellow")
        groups = max(2, min(9, int(m / 5)))
        for g in range(groups):
            px, py = pts[(g * m) // groups + rnd.randrange(0, max(1, m // groups))]
            for k in range(rnd.randint(3, 5)):
                ox, oy = out(px + rnd.uniform(-0.9, 0.9), py + rnd.uniform(-0.9, 0.9), rnd.uniform(-0.1, 0.5))
                r = rnd.uniform(0.18, 0.55) * (1.5 if k == 0 else 1.0)
                self._rock(ox, oy, r, r * rnd.uniform(0.6, 1.0), g * 5 + k, -0.12, styles[(g + k) % 5], dz=self.ground_z((ox, oy)))
        # reed beds (Schilf): bundles of slender slightly bent stems along ~half of the shore
        for k in range(m):
            if rnd.random() > 0.55:
                continue
            px, py = out(*pts[k], rnd.uniform(-0.15, 0.35))
            items = []
            for s in range(rnd.randint(6, 11)):
                sx, sy = px + rnd.uniform(-0.35, 0.35), py + rnd.uniform(-0.35, 0.35)
                hh = rnd.uniform(1.1, 2.0)
                lean = rnd.uniform(-0.18, 0.18)
                items.append(self.cylinder((sx, sy, -0.15), (sx + lean, sy + rnd.uniform(-0.18, 0.18), hh), 0.012, "grass_hair"))
                if rnd.random() < 0.5:
                    items.append(self.cylinder((sx + lean, sy, hh - 0.25), (sx + lean * 1.1, sy, hh + 0.1), 0.028, "bark"))      # Kolben / Rispe
            self._veg("Schilf", items, at=[(px, py)])
        # water lilies on the open water (not near the bank)
        inner = pg.buffer(-1.2)
        if not inner.is_empty:
            minx, miny, maxx, maxy = inner.bounds
            pads, blooms = [], []
            for _ in range(60):
                if len(pads) >= 14:
                    break
                px, py = rnd.uniform(minx, maxx), rnd.uniform(miny, maxy)
                if not inner.contains(Point(px, py)):
                    continue
                for _k in range(rnd.randint(2, 4)):
                    qx, qy = px + rnd.uniform(-0.7, 0.7), py + rnd.uniform(-0.7, 0.7)
                    if inner.contains(Point(qx, qy)):
                        rr = rnd.uniform(0.2, 0.42)
                        pads.append(self.cylinder((qx, qy, level - 0.0), (qx, qy, level + 0.018), rr, "leaf"))
                        if rnd.random() < 0.35:
                            blooms.append(self.cylinder((qx, qy, level + 0.018), (qx, qy, level + 0.09), 0.07, "plaster_white"))
            if pads:
                self.element("IfcGeographicElement", "Seerosen", pads + blooms, z_ref=level, predefined="VEGETATION")
        # shrubs and bank trees (alder / willow) a little away from the water
        for k in range(max(3, min(10, m // 3))):
            px, py = out(*pts[(k * 3 + rnd.randrange(0, 3)) % m], rnd.uniform(1.5, 3.5))
            if k % 3 == 0:
                H = rnd.uniform(6.0, 9.0)
                self._c_tree({"x": px, "y": py, "height": H, "crown_radius": rnd.uniform(2.2, 3.4), "kind": "deciduous", "note": "Uferbaum (Erle/Weide)"}, i)
            else:
                self._c_shrub({"x": px, "y": py, "radius": rnd.uniform(0.5, 1.0), "height": rnd.uniform(0.9, 1.6), "pot": False}, i)

    def _water_body(self, name, ring, level, depth_below, i):
        zb = level - depth_below
        self.element("IfcBuildingElementProxy", name, [self._prism(ring, (0.0, 0.0, zb), (0, 0, 1), (1, 0, 0), depth_below - 0.03, "water")],
                     z_ref=zb, predefined="USERDEFINED")

    def _c_pond(self, c, i, v=None):
        from . import pond as P
        _need(c, i, "pond", "x", "y")
        pts = P.outline(c)
        lvl = self.tz.pond_level(i) if getattr(self, "tz", None) is not None and self.tz.ok else 0.0
        zw = lvl - 0.15
        self._water_body("Teich Wasser", pts, zw, 0.5, i)
        self._shore(pts, zw, c, i, int(c["x"] * 31 + c["y"] * 17))

    def _c_lake(self, c, i, v=None):
        _need(c, i, "lake", "x", "y")
        lk = self.tz.lake(i) if getattr(self, "tz", None) is not None and self.tz.ok else None
        if not lk:      # no ground model (validation build) or no hollow there: nothing to fill; the 360° build with terrain draws the lake
            return
        ring = [tuple(p) for p in lk["ring"][:-1]]
        self._water_body("See Wasser", ring, lk["level"], 2.5, i)
        if c.get("life", True):
            self._shore(ring, lk["level"], c, i, int(c["x"] * 31 + c["y"] * 17))

    # ------------------------------------------------------------------ furniture and lights
    def _c_bench(self, c, i, v=None):
        _need(c, i, "bench", "x", "y")
        x, y, L, ax, flip = c["x"], c["y"], c["length"], c["orientation"], c["flip"]
        wd, mat, fr = 0.45, c["material"], c["frame_material"]

        def B(lx0, lx1, ly0, ly1, z0, z1, st):
            ly0, ly1 = (-ly1, -ly0) if flip else (ly0, ly1)
            if ax == "x":
                return self.box(x + lx0, y + ly0, z0, lx1 - lx0, ly1 - ly0, z1 - z0, st)
            return self.box(x + ly0, y + lx0, z0, ly1 - ly0, lx1 - lx0, z1 - z0, st)

        items = [B(0, L, 0, wd, 0.43, 0.47, mat), B(0, L, wd - 0.05, wd, 0.5, 0.85, mat)]
        for lx in (0.15, L - 0.2):
            items.append(B(lx, lx + 0.05, 0.05, wd - 0.05, 0.0, 0.44, fr))
        self.element("IfcFurniture", "Gartenbank", items, predefined="USERDEFINED", material="Holz")

    def _c_garden_set(self, c, i, v=None):
        _need(c, i, "garden_set", "x", "y")
        x, y = c["x"], c["y"]
        tl, tw = 1.6, 0.9
        m, fr = c["material"], c["frame_material"]
        items = [self.box(x - tl / 2, y - tw / 2, 0.72, tl, tw, 0.04, m)]
        for sx in (-1, 1):
            for sy in (-1, 1):
                items.append(self.box(x + sx * (tl / 2 - 0.1) - 0.03, y + sy * (tw / 2 - 0.1) - 0.03, 0.0, 0.06, 0.06, 0.73, fr))
        for sy in (-1, 1):
            for ox in (-0.4, 0.4):
                cx, cy = x + ox, y + sy * (tw / 2 + 0.3)
                items.append(self.box(cx - 0.22, cy - 0.22, 0.43, 0.44, 0.44, 0.04, m))
                items.append(self.box(cx - 0.22, cy + sy * 0.2 - 0.02, 0.45, 0.44, 0.04, 0.4, m))
                for lx in (-1, 1):
                    for ly in (-1, 1):
                        items.append(self.box(cx + lx * 0.18 - 0.02, cy + ly * 0.18 - 0.02, 0.0, 0.04, 0.04, 0.44, fr))
        self.element("IfcFurniture", "Gartenmöbel", items, predefined="USERDEFINED", material="Holz/Stahl")
        if c["parasol"]:
            pm = c["parasol_material"]
            r = 1.3
            self.element("IfcBuildingElementProxy", "Sonnenschirm",
                         [self.cylinder((x, y, 0.0), (x, y, 2.4), 0.025, fr),
                          self._revolve([(0.0, 2.55), (r * 0.5, 2.38), (r, 2.15), (r * 0.98, 2.1)], x, y, pm, 16)], predefined="USERDEFINED", material="Stoff")

    def _c_garden_light(self, c, i, v=None):
        _need(c, i, "garden_light", "x", "y")
        items = []
        for k in range(c["count"]):
            px = c["x"] + (k * c["pitch"] if c["axis"] == "x" else 0.0)
            py = c["y"] + (k * c["pitch"] if c["axis"] == "y" else 0.0)
            if c["kind"] == "bollard":
                items += [self.box(px - 0.06, py - 0.06, 0.0, 0.12, 0.12, 0.7, c["material"]), self.box(px - 0.07, py - 0.07, 0.7, 0.14, 0.14, 0.12, "glass_frosted"),
                          self.box(px - 0.09, py - 0.09, 0.82, 0.18, 0.18, 0.03, c["material"])]
            else:
                h = c["height"]
                items += [self.box(px - 0.04, py - 0.04, 0.0, 0.08, 0.08, h, c["material"]), self.box(px - 0.12, py - 0.12, h, 0.24, 0.24, 0.3, "glass_frosted"),
                          self.box(px - 0.16, py - 0.16, h + 0.28, 0.32, 0.32, 0.04, c["material"])]
        self.element("IfcLightFixture", "Gartenleuchte", items, predefined="USERDEFINED", material="Metall")
