"""Catalog components, stage 4: loggia (vorgesetzt), buttress, pylon sign, parking area."""
from __future__ import annotations

from .geom import side_length


class Components4Mixin:
    def _c_loggia(self, c, v, i):
        base = float(v["base_z"])
        sh = float(v.get("storey_height", self.storey_h))
        st = c["storey"]
        if st >= int(v["storeys"]):
            raise ValueError(f"components[{i}] (loggia): Geschoss {st} gibt es nicht (Volumen hat {v['storeys']} Geschosse, 0 = Erdgeschoss)")
        z = base + st * sh
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u = c["u"] if c["u"] is not None else L / 2
        a, b, dep = u - c["width"] / 2, u + c["width"] / 2, c["depth"]
        if a < 0.2 or b > L - 0.2:
            raise ValueError(f"components[{i}] (loggia): Breite {c['width']} m um u={u:.1f} passt nicht auf die Fassade ({L} m)")
        fac = c["wall_material"] or v.get("facade", "plaster_white")
        t = 0.16
        clear = sh - 0.2
        sd = c["side"]
        items = [self._fbx(v, sd, a - 0.05, b + 0.05, -dep - 0.05, 0.0, z - 0.2, z, c["slab_material"]),
                 self._fbx(v, sd, a, a + t, -dep, -0.01, z, z + clear, fac),
                 self._fbx(v, sd, b - t, b, -dep, -0.01, z, z + clear, fac)]
        if c["ceiling"]:
            items.append(self._fbx(v, sd, a - 0.05, b + 0.05, -dep - 0.05, 0.0, z + clear, z + clear + 0.2, c["slab_material"]))
        self._comp_prox(f"Loggia {v['id']}-{sd}-{st}", items, z, material="Stahlbeton")
        if c["railing"] != "none":
            rl = self._railing_items(v, sd, a + t, b - t, dep, z, c["railing"], c["railing_height"], c["railing_material"], ("front",))
            self._comp_prox(f"Loggiabrüstung {v['id']}-{sd}-{st}", rl, z, material="Stahl", cls="IfcRailing", predefined="GUARDRAIL")

    def _c_buttress(self, c, v, i):
        base = float(v["base_z"])
        z0 = base + c["z0"]
        top = self._vtop(v)
        z1 = z0 + c["height"] if c["height"] is not None else top - 0.4
        if z1 - z0 < 1.0:
            raise ValueError(f"components[{i}] (buttress): Höhe unter 1 m")
        W, D = v["size"]
        L = side_length(c["side"], W, D)
        u0, p, w = c["u"], c["projection"], c["width"]
        if u0 is None:
            u0 = w / 2 + 0.3
        last = u0 + (c["count"] - 1) * c["pitch"]
        if u0 - w / 2 < 0.0 or last + w / 2 > L:
            raise ValueError(f"components[{i}] (buttress): Pfeiler liegen außerhalb der Fassade ({L} m); count/pitch/u anpassen")
        zm = z0 + (z1 - z0) * 0.5
        pts = [(0.0, z0), (-p, z0), (-p, zm), (-p * 0.45, z1 - 0.6), (-p * 0.45, z1), (0.0, z1)]
        items = [self._sprism_at(v, c["side"], pts, u0 + k * c["pitch"] - w / 2, w, c["material"]) for k in range(c["count"])]
        self._comp_prox(f"Strebepfeiler {v['id']}-{c['side']}", items, z0, material="Naturstein")

    def _c_pylon(self, c, v, i):
        x, y, h, w = c["x"], c["y"], c["height"], c["width"]
        if x is None or y is None:
            raise ValueError(f"components[{i}] (pylon): x und y sind Pflicht")
        z0 = c["z0"]
        d = 0.35
        items = [self.box(x - 0.2, y - d / 2, z0, 0.4, d, h, c["material"]),
                 self.box(x - w / 2, y - d / 2 - 0.05, z0 + h * 0.62, w, d + 0.1, h * 0.36, c["sign_material"])]
        self._comp_prox("Pylon", items, z0, material="Stahl")

    def _c_parking(self, c, v, i):
        x, y, w, d, n = c["x"], c["y"], c["width"], c["depth"], c["spaces"]
        if x is None or y is None:
            raise ValueError(f"components[{i}] (parking): x und y sind Pflicht")
        gz = [self.ground_z((x + w * i / 3, y + d * j / 3)) for i in range(4) for j in range(4)]
        z0 = max(float(c["z0"]), max(gz) - 0.02)                 # the pad sits on the highest ground point, its body reaches down to the lowest: no gaps, nothing buried
        zb = min(gz) - 0.15 if max(gz) - min(gz) > 0.03 else z0
        items = [self.box(x, y, zb, w, d, z0 + 0.05 - zb, c["material"])]
        bay = w / n
        if bay < 2.2:
            raise ValueError(f"components[{i}] (parking): Stellplatzbreite {bay:.2f} m zu schmal (min 2,2 m); weniger spaces oder größere width")
        for k in range(n + 1):
            xx = min(max(x + k * bay, x + 0.05), x + w - 0.05)
            items.append(self.box(xx - 0.05, y + 0.1, z0 + 0.04, 0.1, d - 0.2, 0.025, c["line_material"]))
        self.element("IfcSlab", "Stellplätze", items, z_ref=z0, predefined="BASESLAB", material="Asphalt")
