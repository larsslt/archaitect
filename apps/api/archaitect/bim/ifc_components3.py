"""Catalog components, stage 3: modern building types (solar, plant boxes, ramps, terraces, carports, retaining walls,
external stairs) and the shared railing builder (also used by balconies)."""
from __future__ import annotations

import math

from .geom import side_length


class Components3Mixin:
    # ------------------------------------------------------------------ railing (shared)
    def _railing_items(self, v, side, a, b, dep, z, kind, H, mat, sides=("front", "left", "right")):
        """Railing around the rectangle u in [a,b], d in [-dep,0] on a facade. kind: solid|glass|bars|cable.
        Butt joints only (no overlapping same-material volumes)."""
        t = {"solid": 0.12, "glass": 0.03, "bars": 0.05, "cable": 0.05}[kind]
        runs = []
        if "front" in sides:
            runs.append((a, b, -dep, -dep + t))
        d_lo = -dep + (t if "front" in sides else 0.0)
        if "left" in sides:
            runs.append((a, a + t, d_lo, -0.01))
        if "right" in sides:
            runs.append((b - t, b, d_lo, -0.01))
        items = []
        for (u0, u1, d0, d1) in runs:
            along_u = (u1 - u0) >= (d1 - d0)
            L = (u1 - u0) if along_u else (d1 - d0)
            s0 = u0 if along_u else d0

            def mem(z0, z1, w, p0, p1, m):
                """member of width w centred in the run, from p0 to p1 along it"""
                if along_u:
                    c = (d0 + d1) / 2
                    return self._fbx(v, side, s0 + p0, s0 + p1, c - w / 2, c + w / 2, z + z0, z + z1, m)
                c = (u0 + u1) / 2
                return self._fbx(v, side, c - w / 2, c + w / 2, s0 + p0, s0 + p1, z + z0, z + z1, m)

            if kind == "solid":
                items.append(mem(0.0, H, t, 0.0, L, mat))
                continue
            if kind == "glass":
                items.append(mem(0.06, H + 0.01, t, 0.0, L, "glass_clear"))
                items.append(mem(H, H + 0.05, 0.07, 0.0, L, mat))
                items.append(mem(0.0, 0.06, 0.05, 0.0, L, mat))
                continue
            sp = 0.12 if kind == "bars" else 1.2
            n = max(1, math.ceil(L / sp))
            pw = 0.025 if kind == "bars" else 0.045
            for k in range(n + 1):
                p = min(max(k * L / n, pw / 2), L - pw / 2)
                items.append(mem(0.05, H + 0.005, pw, p - pw / 2, p + pw / 2, mat))
            items.append(mem(H, H + 0.05, 0.07, 0.0, L, mat))
            if kind == "bars":
                items.append(mem(0.0, 0.05, 0.04, 0.0, L, mat))
            else:
                for zc in (0.25, 0.45, 0.65, 0.85):
                    if zc < H - 0.05:
                        items.append(mem(zc - 0.006, zc + 0.006, 0.012, 0.0, L, mat))
        return items

    # ------------------------------------------------------------------ solar
    def _c_solar(self, c, v, i):
        ox, oy = v["origin"]
        W, D = v["size"]
        cols, rows, pw, pl, th = c["cols"], c["rows"], c["panel_w"], c["panel_l"], 0.04
        gap = 0.02
        mat = c["material"]
        roof = v.get("roof") or {}
        top = self._vtop(v)
        items = []
        if c["mode"] == "flat":
            if roof.get("type", "flat") not in ("flat", None):
                raise ValueError(f"components[{i}] (solar): mode flat nur bei Flachdach; bei geneigtem Dach mode pitched benutzen")
            tilt = math.radians(c["tilt"])
            run = pl * math.cos(tilt)
            row_pitch = run + max(0.35, pl * math.sin(tilt) * 1.8)
            x0 = c["x"] if c["x"] is not None else 0.8
            y0 = c["y"] if c["y"] is not None else 0.8
            xe, ye = x0 + cols * (pw + gap) - gap, y0 + (rows - 1) * row_pitch + run
            if xe > W - 0.5 or ye > D - 0.5:
                raise ValueError(f"components[{i}] (solar): Feld {xe:.1f} x {ye:.1f} m passt nicht aufs Dach {W} x {D} m (Rand 0,5 m); weniger cols/rows")
            zb = top + 0.12
            for r in range(rows):
                ya = oy + y0 + r * row_pitch
                verts = [(0, ya, zb), (0, ya + run, zb + pl * math.sin(tilt)), (0, ya + run, zb + pl * math.sin(tilt) + th), (0, ya, zb + th)]
                for k in range(cols):
                    xk = ox + x0 + k * (pw + gap)
                    vv = [(xk, q[1], q[2]) for q in verts]
                    items.append(self._hprism(vv, (1, 0, 0), (xk, 0.0, 0.0), pw, mat))
            self._comp_prox(f"Solaranlage {v['id']}", items, top, material="Glas/Aluminium")
            return
        g = self.gables.get(v["id"])
        if not g:
            raise ValueError(f"components[{i}] (solar): mode pitched braucht roof.type gable; bei Flachdach mode flat")
        slope = c["slope"]
        if slope not in {"y": ("W", "E"), "x": ("S", "N")}[g["ridge"]]:
            raise ValueError(f"components[{i}] (solar): Dachseite {slope} gibt es bei ridge={g['ridge']} nicht (Seiten: {'W/E' if g['ridge'] == 'y' else 'S/N'})")
        low = slope in ("S", "W")
        cs, tn = math.cos(g["pitch"]), math.tan(g["pitch"])
        run = pl * cs
        half = (g["b1"] - g["b0"]) / 2
        up = c["up"]
        if up + rows * run + (rows - 1) * gap > half - 0.25:
            raise ValueError(f"components[{i}] (solar): Reihen reichen über den First (max {max(0.0, half - 0.25 - up):.2f} m Höhe in der Schräge); weniger rows oder kleineres up")
        a_s = g["a0"] + c["u"]
        if c["u"] < 0.3 or a_s + cols * (pw + gap) - gap > g["a1"] - 0.3:
            raise ValueError(f"components[{i}] (solar): Feld breiter als die Dachlänge; weniger cols oder kleineres u")
        sg = 1 if low else -1
        zf = lambda b: top + (b - g["b0"]) * tn if low else top + (g["b1"] - b) * tn

        def corner(a, b, lift):
            pt = (a, b) if g["ridge"] == "x" else (b, a)
            return (pt[0], pt[1], zf(b) + lift)

        for r in range(rows):
            for k in range(cols):
                ba = (g["b0"] + up if low else g["b1"] - up) + sg * r * (run + gap)
                bb = ba + sg * run
                aa = a_s + k * (pw + gap)
                ab = aa + pw
                pts = [corner(aa, ba, 0.12), corner(ab, ba, 0.12), corner(ab, bb, 0.12), corner(aa, bb, 0.12)]
                items.append(self._slope_slab(pts, th, mat))
        self._comp_prox(f"Solaranlage {v['id']}-{slope}", items, top, material="Glas/Aluminium")

    # ------------------------------------------------------------------ rooftop plant box
    def _c_technical_box(self, c, v, i):
        ox, oy = v["origin"]
        W, D = v["size"]
        w, d, h = c["width"], c["depth"], c["height"]
        x = c["x"] if c["x"] is not None else (W - w) / 2
        y = c["y"] if c["y"] is not None else (D - d) / 2
        if x < 0.3 or y < 0.3 or x + w > W - 0.3 or y + d > D - 0.3:
            raise ValueError(f"components[{i}] (technical_box): Aufbau {w} x {d} m an x={x}, y={y} liegt nicht innerhalb des Dachs {W} x {D} m")
        top = self._vtop(v)
        items = [self.box(ox + x, oy + y, top, w, d, h, c["material"]),
                 self.box(ox + x - 0.05, oy + y - 0.05, top + h - 0.02, w + 0.1, d + 0.1, 0.1, c["cap_material"])]
        # louvre strips on the front face
        for k in range(3):
            items.append(self.box(ox + x + 0.15, oy + y - 0.02, top + 0.35 + k * 0.22, min(w - 0.3, 1.2), 0.04, 0.05, c["cap_material"]))
        self._comp_prox(f"Technikaufbau {v['id']}", items, top, material="Metall")

    # ------------------------------------------------------------------ ramp
    def _c_ramp(self, c, v, i):
        z0 = c["z0"] if c["z0"] is not None else float(v["base_z"])
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b = u - c["width"] / 2, u + c["width"] / 2
        H, ln = c["height"], c["length"]
        if H / ln > 0.12 + 1e-9:
            raise ValueError(f"components[{i}] (ramp): Neigung {H / ln * 100:.0f} % zu steil (barrierefrei max 6 %, hier max 12 %); length >= {H / 0.12:.1f} m")
        items = [self._sprism_at(v, c["side"], [(0.0, z0), (0.0, z0 + H), (-ln, z0)], a, b - a, c["material"])]
        self._comp_prox(f"Rampe {v['id']}-{c['side']}", items, z0, material="Beton")
        if c["railing"] != "none":
            rm = c["railing_material"]
            for uu in (a, b - 0.05):
                it = [self._sprism_at(v, c["side"], [(0.0, z0 + H + 0.85), (-ln, z0 + 0.85), (-ln, z0 + 0.9), (0.0, z0 + H + 0.9)], uu, 0.05, rm),
                      self._sprism_at(v, c["side"], [(-0.1, z0 + H), (-0.1, z0 + H + 0.9), (-0.04, z0 + H + 0.9), (-0.04, z0 + H)], uu, 0.05, rm),
                      self._sprism_at(v, c["side"], [(-ln, z0), (-ln, z0 + 0.9), (-ln + 0.06, z0 + 0.9), (-ln + 0.06, z0)], uu, 0.05, rm)]
                self._comp_prox(f"Rampengeländer {v['id']}", it, z0, material="Stahl", cls="IfcRailing", predefined="HANDRAIL")

    # ------------------------------------------------------------------ terrace
    def _c_terrace(self, c, v, i):
        base = float(v["base_z"])
        z = base + c["z"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b = u - c["width"] / 2, u + c["width"] / 2
        dep, th = c["depth"], c["thickness"]
        items = [self._fbx(v, c["side"], a, b, -dep, 0.0, z - th, z, c["material"])]
        if z - th > 0.02:      # Unterbau: eine Terrasse schwebt nicht, sie steht auf einem Fundament bis unter das Gelände
            items.append(self._fbx(v, c["side"], a + 0.08, b - 0.08, -dep + 0.08, -0.05, -0.4, z - th, "stone_plinth"))
        self._comp_prox(f"Terrasse {v['id']}-{c['side']}", items, z, material="Belag")
        if c["railing"] != "none":
            sides = tuple(s for s in ("front", "left", "right") if s in c["railing_sides"].split(","))
            items = self._railing_items(v, c["side"], a, b, dep, z, c["railing"], c["railing_height"], c["railing_material"], sides)
            if items:
                self._comp_prox(f"Geländer Terrasse {v['id']}", items, z, material="Stahl", cls="IfcRailing", predefined="GUARDRAIL")

    # ------------------------------------------------------------------ carport
    def _c_carport(self, c, v, i):
        base = float(v["base_z"])
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b = u - c["width"] / 2, u + c["width"] / 2
        p, h, th, m = c["projection"], c["height"], 0.16, c["material"]
        items = []
        if c["kind"] == "flat":
            items.append(self._fbx(v, c["side"], a - 0.1, b + 0.1, -p - 0.1, 0.0, base + h, base + h + th, m))
        else:
            items.append(self._sprism_at(v, c["side"], [(0.0, base + h + 0.5), (-p - 0.1, base + h), (-p - 0.1, base + h + th), (0.0, base + h + 0.5 + th)], a - 0.1, b - a + 0.2, c["roof_material"] or m))
        n = max(1, math.ceil((b - a) / 3.5))
        for k in range(n + 1):
            uu = a + 0.1 + k * (b - a - 0.2) / n
            items.append(self._fbx(v, c["side"], uu - 0.07, uu + 0.07, -p + 0.0, -p + 0.14, base, base + h, m))
        self._comp_prox(f"Carport {v['id']}-{c['side']}", items, base, material="Holz/Stahl")

    # ------------------------------------------------------------------ retaining wall (free standing)
    def _c_retaining_wall(self, c, v, i):
        x0, y0, x1, y1 = c["x0"], c["y0"], c["x1"], c["y1"]
        if abs(x1 - x0) > 1e-6 and abs(y1 - y0) > 1e-6:
            raise ValueError(f"components[{i}] (retaining_wall): nur achsparallel; x0==x1 oder y0==y1 setzen")
        t, h, z0 = c["thickness"], c["height"], c["z0"]
        if abs(x1 - x0) <= 1e-6:
            bx, by, dx, dy = x0 - t / 2, min(y0, y1), t, abs(y1 - y0)
        else:
            bx, by, dx, dy = min(x0, x1), y0 - t / 2, abs(x1 - x0), t
        if max(dx, dy) < 0.5:
            raise ValueError(f"components[{i}] (retaining_wall): Länge zu kurz")
        items = [self.box(bx, by, z0, dx, dy, h, c["material"]), self.box(bx - 0.04, by - 0.04, z0 + h - 0.03, dx + 0.08, dy + 0.08, 0.09, c["cap_material"])]
        self.element("IfcWall", "Stützmauer", items, z_ref=z0, predefined="RETAININGWALL", material="Beton/Naturstein")

    # ------------------------------------------------------------------ external stair
    def _c_stair_ext(self, c, v, i):
        base = float(v["base_z"])
        z0 = base + c["z0"]
        z1 = base + c["z1"]
        H = z1 - z0
        if H < 0.5:
            raise ValueError(f"components[{i}] (stair_ext): z1 muss mindestens 0,5 m über z0 liegen")
        n = max(3, math.ceil(H / 0.18))
        rise, tr = H / n, c["tread"]
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u0 = c["u"] if c["u"] is not None else min(1.0, L / 4)
        run = n * tr
        w = c["width"]
        if u0 + run + c["landing"] > L - 0.2:
            raise ValueError(f"components[{i}] (stair_ext): Lauf {run + c['landing']:.1f} m ab u={u0} länger als die Fassade ({L} m); u verkleinern oder tread kleiner")
        m = c["material"]
        items = []
        slope = H / run
        for d_in, d_out in ((-0.1, -0.15), (-w, -w - 0.05)):
            pts = [(u0, z0), (u0 + run, z1), (u0 + run, z1 - 0.22), (u0 + 0.22 / slope, z0)]
            items.append(self._fp(v, c["side"], pts, d_out, d_in, m))
        for k in range(n):
            items.append(self._fbx(v, c["side"], u0 + k * tr, u0 + (k + 1) * tr, -w - 0.02, -0.12, z0 + (k + 1) * rise - 0.04, z0 + (k + 1) * rise, c["tread_material"]))
        # landing at the top with supports
        lu0, lu1 = u0 + run, u0 + run + c["landing"]
        items.append(self._fbx(v, c["side"], lu0, lu1, -w - 0.05, -0.02, z1 - 0.06, z1, c["tread_material"]))
        for uu in (lu1 - 0.1, lu0 + 0.05):
            items.append(self._fbx(v, c["side"], uu - 0.04, uu + 0.04, -w - 0.05, -w + 0.03, z0, z1 - 0.03, m))
        # handrail along the open side
        pts = [(u0, z0 + 0.9), (u0 + run, z1 + 0.9), (u0 + run, z1 + 0.95), (u0, z0 + 0.95)]
        items.append(self._fp(v, c["side"], pts, -w - 0.04, -w + 0.01, m))
        items.append(self._fbx(v, c["side"], lu0, lu1, -w - 0.04, -w + 0.01, z1 + 0.9, z1 + 0.95, m))
        self._comp_prox(f"Außentreppe {v['id']}-{c['side']}", items, z0, material="Stahl", cls="IfcStair")
