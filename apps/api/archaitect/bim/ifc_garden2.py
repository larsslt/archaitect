"""Library garden structures and decor (pergola, pavilion, greenhouse, garage, fountain, ...). All are box-footprint components:
x, y = lower-left corner, width (x) and depth (y). Built at z = 0 and lifted onto the lowest ground point of the footprint."""
from __future__ import annotations

import math

from .ifc_garden3 import CATALOG as _C3, LABEL as _L3, OBJECTS as _O3, Garden3Mixin

P = ("n",)


def _p(default, lo, hi, text):
    return ("n", default, lo, hi, text)


def _xy():
    return {"x": ("n", None, -300.0, 500.0, "linke untere Ecke x"), "y": ("n", None, -300.0, 500.0, "linke untere Ecke y")}


def _st(default, text="Material"):
    return ("st", default, None, None, text)


CATALOG = {
    "pergola": {"label": "Freistehende Pergola mit Pfosten, Balken und Sparren (Terrasse, Sitzplatz)", "tier": 5, "params": {
        **_xy(), "width": _p(4.0, 2.0, 12.0, "Breite"), "depth": _p(3.0, 2.0, 8.0, "Tiefe"), "height": _p(2.6, 2.2, 3.5, "Höhe"),
        "material": _st("wood_larch"), "frame_material": _st("steel_black", "Beschläge")}},
    "gazebo": {"label": "Gartenpavillon mit Satteldach, Brüstung und Pfosten", "tier": 5, "params": {
        **_xy(), "width": _p(3.6, 2.4, 6.0, "Breite"), "depth": _p(3.6, 2.4, 6.0, "Tiefe"),
        "material": _st("wood_cedar"), "roof_material": _st("roof_copper_patina", "Dach")}},
    "greenhouse": {"label": "Gewächshaus mit Glaswänden, Alurahmen, Sockel und Glassatteldach", "tier": 5, "params": {
        **_xy(), "width": _p(3.0, 2.0, 8.0, "Breite (Firstrichtung)"), "depth": _p(2.4, 1.8, 5.0, "Tiefe"),
        "frame_material": _st("alu_anthracite", "Rahmen")}},
    "garden_house": {"label": "Gartenhaus / Geräteschuppen mit Pultdach, Tür und Fenster", "tier": 5, "params": {
        **_xy(), "width": _p(3.0, 2.0, 6.0, "Breite"), "depth": _p(2.4, 1.8, 5.0, "Tiefe"),
        "wall_material": _st("paint_green_dark", "Wand"), "roof_material": _st("roof_bitumen", "Dach")}},
    "garage": {"label": "Garage mit Flachdach, Sektionaltor und Seitentür (Breite 3,2 = Einzel, 5,8 = Doppel)", "tier": 5, "params": {
        **_xy(), "width": _p(3.2, 2.8, 7.0, "Breite (Toröffnung)"), "depth": _p(6.0, 5.0, 8.0, "Tiefe"), "height": _p(2.6, 2.3, 3.4, "Höhe"),
        "wall_material": _st("plaster_white", "Wand"), "door_material": _st("alu_anthracite", "Tor")}},
    "fountain": {"label": "Brunnen: runde Steinschale mit Wasser, Mittelsäule, Schale und Fontäne", "tier": 5, "params": {
        **_xy(), "width": _p(3.0, 1.6, 6.0, "Durchmesser"), "depth": _p(3.0, 1.6, 6.0, "Durchmesser (gleich Breite)"),
        "material": _st("stone_limestone", "Stein")}},
    "firepit": {"label": "Feuerstelle: Steinring mit Glut und vier Holzblock-Sitzen", "tier": 5, "params": {
        **_xy(), "width": _p(2.8, 1.8, 5.0, "Durchmesser"), "depth": _p(2.8, 1.8, 5.0, "Durchmesser (gleich Breite)"),
        "material": _st("stone_field", "Stein")}},
    "raised_bed": {"label": "Hochbeet aus Holz mit Erde und Kräutern/Gemüse", "tier": 5, "params": {
        **_xy(), "width": _p(2.4, 0.8, 6.0, "Breite"), "depth": _p(1.2, 0.8, 2.0, "Tiefe"), "height": _p(0.8, 0.4, 1.0, "Höhe"),
        "material": _st("wood_larch")}},
    "sunloungers": {"label": "Zwei Sonnenliegen mit Beistelltisch und Sonnenschirm", "tier": 5, "params": {
        **_xy(), "width": _p(2.6, 2.0, 4.0, "Breite"), "depth": _p(2.2, 2.0, 3.0, "Tiefe"),
        "material": _st("wood_thermo"), "cushion_material": _st("fabric_sand", "Auflage")}},
    "bike_shed": {"label": "Fahrradüberdachung mit Stahlstützen, Gründach und Anlehnbügeln", "tier": 5, "params": {
        **_xy(), "width": _p(3.0, 1.8, 8.0, "Breite"), "depth": _p(2.0, 1.4, 3.0, "Tiefe"), "material": _st("steel_black")}},
    "bin_store": {"label": "Mülltonnenbox mit Holzlamellen und Klappdeckeln", "tier": 5, "params": {
        **_xy(), "width": _p(2.0, 1.2, 4.0, "Breite"), "depth": _p(0.9, 0.7, 1.4, "Tiefe"), "material": _st("wood_thermo")}},
    "sculpture": {"label": "Skulptur: Steinsockel mit Cortenstahl-Stele und Kugel", "tier": 5, "params": {
        **_xy(), "width": _p(1.2, 0.8, 3.0, "Sockelbreite"), "depth": _p(1.2, 0.8, 3.0, "Sockeltiefe"), "height": _p(2.2, 1.2, 4.0, "Gesamthöhe"),
        "material": _st("stone_granite_grey", "Sockel")}},
    "hottub": {"label": "Whirlpool: runde Holzwanne mit Wasser, Deckelhälfte und Stufe", "tier": 5, "params": {
        **_xy(), "width": _p(2.3, 1.6, 3.2, "Durchmesser"), "depth": _p(2.3, 1.6, 3.2, "Durchmesser (gleich Breite)"),
        "material": _st("wood_cedar")}},
    "swing_set": {"label": "Schaukelgestell mit zwei Schaukeln und Sandkasten", "tier": 5, "params": {
        **_xy(), "width": _p(3.2, 2.4, 5.0, "Breite"), "depth": _p(2.4, 2.0, 4.0, "Tiefe"), "material": _st("wood_larch")}},
    "planter_wall": {"label": "Pflanzmauer: Gabionenband mit Gräsern und Stauden", "tier": 5, "params": {
        **_xy(), "width": _p(4.0, 1.5, 10.0, "Breite"), "depth": _p(0.6, 0.4, 1.2, "Tiefe"), "height": _p(0.7, 0.4, 1.2, "Höhe"),
        "material": _st("stone_basalt_dark")}},
}
CATALOG.update(_C3)
TYPES = frozenset(CATALOG)
LABEL = {"pergola": "Pergola", "gazebo": "Pavillon", "greenhouse": "Gewächshaus", "garden_house": "Gartenhaus", "garage": "Garage", "fountain": "Brunnen",
         "firepit": "Feuerstelle", "raised_bed": "Hochbeet", "sunloungers": "Sonnenliegen", "bike_shed": "Fahrradüberdachung", "bin_store": "Mülltonnenbox",
         "sculpture": "Skulptur", "hottub": "Whirlpool", "swing_set": "Schaukel", "planter_wall": "Pflanzmauer"}
# id -> (category, base type, overrides, label)
OBJECTS = {
    "pergola": ("Terrasse & Sitzen", "pergola", {}, "Pergola"),
    "pergola_large": ("Terrasse & Sitzen", "pergola", {"width": 6.0, "depth": 4.0, "material": "wood_thermo"}, "Pergola groß"),
    "gazebo": ("Terrasse & Sitzen", "gazebo", {}, "Pavillon"),
    "gazebo_white": ("Terrasse & Sitzen", "gazebo", {"width": 4.4, "depth": 4.4, "material": "paint_white", "roof_material": "roof_zinc_standing"}, "Pavillon weiß"),
    "sunloungers": ("Terrasse & Sitzen", "sunloungers", {}, "Sonnenliegen"),
    "firepit": ("Terrasse & Sitzen", "firepit", {}, "Feuerstelle"),
    "hottub": ("Wasser & Pool", "hottub", {}, "Whirlpool"),
    "fountain": ("Wasser & Pool", "fountain", {}, "Brunnen"),
    "fountain_large": ("Wasser & Pool", "fountain", {"width": 4.6, "depth": 4.6, "material": "stone_marble_white"}, "Brunnen groß"),
    "greenhouse": ("Nebengebäude", "greenhouse", {}, "Gewächshaus"),
    "greenhouse_large": ("Nebengebäude", "greenhouse", {"width": 5.0, "depth": 3.0}, "Gewächshaus groß"),
    "garden_house": ("Nebengebäude", "garden_house", {}, "Gartenhaus"),
    "garden_house_grey": ("Nebengebäude", "garden_house", {"width": 3.6, "depth": 2.8, "wall_material": "paint_anthracite", "roof_material": "roof_zinc_standing"}, "Gartenhaus anthrazit"),
    "garage": ("Nebengebäude", "garage", {}, "Garage"),
    "garage_double": ("Nebengebäude", "garage", {"width": 5.8, "wall_material": "brick_red"}, "Doppelgarage"),
    "bike_shed": ("Nebengebäude", "bike_shed", {}, "Fahrradüberdachung"),
    "bin_store": ("Nebengebäude", "bin_store", {}, "Mülltonnenbox"),
    "raised_bed": ("Pflanzen", "raised_bed", {}, "Hochbeet"),
    "raised_bed_long": ("Pflanzen", "raised_bed", {"width": 4.0, "height": 0.6}, "Hochbeet lang"),
    "planter_wall": ("Pflanzen", "planter_wall", {}, "Pflanzmauer"),
    "sculpture": ("Möbel & Licht", "sculpture", {}, "Skulptur"),
    "swing_set": ("Spiel & Sport", "swing_set", {}, "Schaukel mit Sandkasten"),
}


LABEL.update(_L3)
OBJECTS.update(_O3)


class Garden2Mixin(Garden3Mixin):
    # ---- helpers -------------------------------------------------------------------------------------------------
    def _g2(self, c, name, items, cls="IfcBuildingElementProxy", mat="Holz", predefined="USERDEFINED"):
        x, y, w, d = c["x"], c["y"], c["width"], c["depth"]
        g = min(self.ground_z((x, y)), self.ground_z((x + w, y)), self.ground_z((x, y + d)), self.ground_z((x + w, y + d)))
        self.element(cls, name, items, z_ref=0.0, predefined=predefined, material=mat, dz=g)

    def _gable_x(self, x0, x1, y0, y1, z, rise, style, thick=0.1):
        """Gable roof with the ridge along x; the profile is the footprint in y plus the given rise."""
        ym = (y0 + y1) / 2
        pts = [(y0, z), (ym, z + rise), (y1, z), (y1, z + thick), (ym, z + rise + thick), (y0, z + thick)]
        return self._prism(pts, (x0, 0.0, 0.0), (1, 0, 0), (0, 1, 0), x1 - x0, style)

    def _round_items(self, cx, cy, prof, style, n=28):
        return self._revolve(prof, cx, cy, style, n)

    # ---- structures ----------------------------------------------------------------------------------------------
    def _c_pergola(self, c, i, v=None):
        x, y, w, d, h, m, fm = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"], c["frame_material"]
        it = [self.box(x - 0.05, y - 0.05, -0.2, w + 0.1, d + 0.1, 0.2, "paving_granite")]
        it = []
        for px in (x, x + w - 0.14):
            for py in (y, y + d - 0.14):
                it.append(self.box(px, py, -0.2, 0.14, 0.14, h + 0.2, m))
                it.append(self.box(px - 0.03, py - 0.03, -0.2, 0.2, 0.2, 0.16, "stone_granite_grey"))
        for py in (y - 0.1, y + d - 0.04):
            it.append(self.box(x - 0.25, py, h, w + 0.5, 0.14, 0.22, m))
        n = max(5, int(w / 0.4))
        for k in range(n + 1):
            sx = x - 0.2 + (w + 0.4 - 0.08) * k / n
            it.append(self.box(sx, y - 0.3, h + 0.22, 0.08, d + 0.6, 0.12, m))
        for px in (x, x + w - 0.14):                  # diagonal-free: steel shoe plates and a top rail brace
            it.append(self.box(px + 0.02, y + d / 2 - 0.05, h - 0.12, 0.10, 0.10, 0.12, fm))
        it.append(self.box(x + w / 2 - 0.07, y - 0.1, h - 0.08, 0.14, d + 0.2, 0.08, m))
        self._g2(c, "Pergola", it)

    def _c_gazebo(self, c, i, v=None):
        x, y, w, d, m, rm = c["x"], c["y"], c["width"], c["depth"], c["material"], c["roof_material"]
        H = 2.45
        it = [self.box(x, y, -0.05, w, d, 0.2, "stone_granite_grey"), self.box(x + 0.1, y + 0.1, 0.15, w - 0.2, d - 0.2, 0.06, "terrace_decking")]
        for px in (x + 0.1, x + w - 0.3):
            for py in (y + 0.1, y + d - 0.3):
                it.append(self.box(px, py, 0.21, 0.2, 0.2, H, m))
        for py in (y + 0.1, y + d - 0.2):
            it += [self.box(x + 0.3, py + 0.04, 0.5, w - 0.6, 0.06, 0.06, m), self.box(x + 0.3, py + 0.04, 1.0, w - 0.6, 0.06, 0.06, m)]
            for k in range(1, 8):
                it.append(self.box(x + 0.3 + (w - 0.6) * k / 8 - 0.02, py + 0.04, 0.55, 0.04, 0.06, 0.45, m))
        for px in (x + 0.1, x + w - 0.2):
            it += [self.box(px + 0.04, y + 0.3, 0.5, 0.06, d - 0.6, 0.06, m), self.box(px + 0.04, y + 0.3, 1.0, 0.06, d - 0.6, 0.06, m)]
        it += [self.box(x + 0.1, y + d / 2 - 0.4, 0.43, w - 0.2, 0.8, 0.04, m) if False else self.box(x + 0.35, y + d - 0.75, 0.43, w - 0.7, 0.4, 0.05, m)]
        z = 0.21 + H
        it += [self.box(x + 0.05, y + 0.05, z, w - 0.1, 0.18, 0.22, m), self.box(x + 0.05, y + d - 0.23, z, w - 0.1, 0.18, 0.22, m)]
        self._g2(c, "Pavillon", it)
        rise = (d / 2 + 0.4) * math.tan(math.radians(24))
        self._g2(c, "Pavillon Dach", [self._gable_x(x - 0.4, x + w + 0.4, y - 0.4, y + d + 0.4, z + 0.22, rise, rm, 0.08)], cls="IfcRoof", mat="Dach", predefined="GABLE_ROOF")

    def _c_greenhouse(self, c, i, v=None):
        x, y, w, d, fr = c["x"], c["y"], c["width"], c["depth"], c["frame_material"]
        H, g = 1.9, "glass_clear"
        it = [self.box(x - 0.05, y - 0.05, -0.25, w + 0.1, d + 0.1, 0.55, "stone_granite_grey")]
        body = [self.box(x, y + d - 0.03, 0.3, w, 0.03, H - 0.3, g), self.box(x, y, 0.3, 0.03, d, H - 0.3, g), self.box(x + w - 0.03, y, 0.3, 0.03, d, H - 0.3, g)]
        dw = 0.8
        body += [self.box(x, y, 0.3, w / 2 - dw / 2, 0.03, H - 0.3, g), self.box(x + w / 2 + dw / 2, y, 0.3, w / 2 - dw / 2, 0.03, H - 0.3, g)]
        n = max(2, int(w / 0.75))
        for k in range(n + 1):
            px = x + (w - 0.04) * k / n
            body += [self.box(px, y - 0.02, 0.3, 0.04, 0.05, H - 0.3, fr), self.box(px, y + d - 0.04, 0.3, 0.04, 0.05, H - 0.3, fr)]
        for py in (y, y + d - 0.04):
            body += [self.box(x, py, 0.3, 0.04, 0.04, H - 0.3, fr), self.box(x + w - 0.04, py, 0.3, 0.04, 0.04, H - 0.3, fr)]
        for zz in (0.3, 1.0, H - 0.05):
            body += [self.box(x, y - 0.02, zz, w, 0.04, 0.04, fr), self.box(x, y + d - 0.04, zz, w, 0.04, 0.04, fr)]
        body += [self.box(x + w / 2 - dw / 2 - 0.03, y - 0.02, 0.3, 0.04, 0.05, H - 0.3, fr), self.box(x + w / 2 + dw / 2 - 0.01, y - 0.02, 0.3, 0.04, 0.05, H - 0.3, fr),
                 self.box(x + w / 2 - dw / 2, y - 0.02, 1.55, dw, 0.04, 0.04, fr), self.box(x + w / 2 - dw / 2, y - 0.03, 0.3, dw, 0.03, 1.25, g),
                 self.box(x + w / 2 + dw / 2 - 0.12, y - 0.05, 0.9, 0.03, 0.03, 0.15, fr)]
        # staging bench and pots inside
        body += [self.box(x + 0.15, y + d - 0.65, 0.8, w - 0.3, 0.5, 0.04, "wood_pine")] + [self.box(x + 0.2 + k * (w - 0.5) / 4, y + d - 0.6, 0.84, 0.28, 0.28, 0.2, "terracotta" if False else "plaster_terracotta") for k in range(5)]
        for k in range(5):
            cx = x + 0.34 + k * (w - 0.5) / 4
            body.append(self._revolve([(0.0, 1.04), (0.14, 1.1), (0.2, 1.25), (0.1, 1.42), (0.0, 1.45)], cx, y + d - 0.46, "foliage", 10))
        self._g2(c, "Gewächshaus Sockel", it, mat="Stein")
        self._g2(c, "Gewächshaus Verglasung", body, mat="Glas/Alu")
        rise = d / 2 * math.tan(math.radians(25))
        ym = y + d / 2
        roof = [self._prism([(y, H), (ym, H + rise), (y + d, H), (y + d, H + 0.03), (ym, H + rise + 0.03), (y, H + 0.03)], (x - 0.06, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w + 0.12, g),
                self.box(x - 0.06, ym - 0.03, H + rise, w + 0.12, 0.06, 0.06, fr)]
        for k in range(n + 1):
            px = x + (w - 0.04) * k / n
            roof.append(self._prism([(y, H), (ym, H + rise), (ym, H + rise + 0.05), (y, H + 0.05)], (px, 0.0, 0.0), (1, 0, 0), (0, 1, 0), 0.04, fr))
            roof.append(self._prism([(ym, H + rise), (y + d, H), (y + d, H + 0.05), (ym, H + rise + 0.05)], (px, 0.0, 0.0), (1, 0, 0), (0, 1, 0), 0.04, fr))
        self._g2(c, "Gewächshaus Dach", roof, cls="IfcRoof", mat="Glas", predefined="GABLE_ROOF")

    def _c_garden_house(self, c, i, v=None):
        x, y, w, d, wm, rm = c["x"], c["y"], c["width"], c["depth"], c["wall_material"], c["roof_material"]
        H, t = 2.25, 0.12
        it = [self.box(x - 0.05, y - 0.05, -0.2, w + 0.1, d + 0.1, 0.3, "stone_granite_grey"), self.box(x, y, 0.1, w, d, 0.1, "wood_pine")]
        dx0, dx1, wz0, wz1, wx0, wx1 = 0.35, 1.25, 0.9, 1.7, w - 1.2, w - 0.4
        it += [self.box(x, y + d - t, 0.2, w, t, H, wm), self.box(x, y + t, 0.2, t, d - 2 * t, H, wm), self.box(x + w - t, y + t, 0.2, t, d - 2 * t, H, wm)]
        it += [self.box(x, y, 0.2, dx0, t, H, wm), self.box(x + dx1, y, 0.2, wx0 - dx1, t, H, wm), self.box(x + wx1, y, 0.2, w - wx1, t, H, wm),
               self.box(x + dx0, y, 0.2 + 2.0, dx1 - dx0, t, H - 2.0, wm), self.box(x + wx0, y, 0.2, wx1 - wx0, t, wz0, wm), self.box(x + wx0, y, 0.2 + wz1, wx1 - wx0, t, H - wz1, wm)]
        it += [self.box(x + dx0, y - 0.02, 0.2, dx1 - dx0, 0.04, 2.0, "wood_oak"), self.box(x + dx1 - 0.2, y - 0.04, 1.0, 0.03, 0.03, 0.18, "steel_black"),
               self.box(x + wx0 + 0.02, y + t / 2, 0.2 + wz0 + 0.02, wx1 - wx0 - 0.04, 0.02, wz1 - wz0 - 0.04, "glass_clear")]
        for xa, xb, za, zb in ((wx0 - 0.05, wx1 + 0.05, wz0 - 0.05, wz0), (wx0 - 0.05, wx1 + 0.05, wz1, wz1 + 0.05), (wx0 - 0.05, wx0, wz0, wz1), (wx1, wx1 + 0.05, wz0, wz1)):
            it.append(self.box(x + xa, y - 0.03, 0.2 + za, xb - xa, 0.05, zb - za, "paint_white"))
        it += [self.box(x + wx0 - 0.1, y - 0.12, 0.2 + wz0 - 0.1, wx1 - wx0 + 0.2, 0.1, 0.05, wm)]
        self._g2(c, "Gartenhaus", it)
        r0, r1 = 0.15, 0.5
        zb, zt = 0.2 + H, 0.2 + H + 0.5
        pts = [(y - 0.4, zb + 0.15), (y + d + 0.3, zt), (y + d + 0.3, zt + 0.1), (y - 0.4, zb + 0.25)]
        self._g2(c, "Gartenhaus Dach", [self._prism(pts, (x - 0.25, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w + 0.5, rm)], cls="IfcRoof", mat="Dach", predefined="SHED_ROOF")

    def _c_garage(self, c, i, v=None):
        x, y, w, d, h, wm, dm = c["x"], c["y"], c["width"], c["depth"], c["height"], c["wall_material"], c["door_material"]
        t, ow = 0.24, min(c["width"] - 0.4, 2.5 if c["width"] < 4 else 5.0)
        ox = x + (w - ow) / 2
        oh = 2.2
        it = [self.box(x, y, -0.2, w, d, 0.2, "concrete_light"), self.box(x, y + d - t, 0, w, t, h, wm), self.box(x, y + t, 0, t, d - 2 * t, h, wm),
              self.box(x + w - t, y + t, 0, t, d - 2 * t, h, wm), self.box(x, y, 0, ox - x, t, h, wm), self.box(ox + ow, y, 0, x + w - ox - ow, t, h, wm),
              self.box(ox, y, oh, ow, t, h - oh, wm), self.box(x, y, h, w, d, 0.28, "concrete_light"), self.box(x - 0.08, y - 0.08, h + 0.28, w + 0.16, d + 0.16, 0.06, "zinc")]
        door = []
        n = 5
        for k in range(n):
            door.append(self.box(ox + 0.03, y - 0.03, 0.03 + (oh - 0.06) * k / n, ow - 0.06, 0.05, (oh - 0.06) / n - 0.01, dm))
        door += [self.box(ox - 0.06, y - 0.05, 0.0, 0.06, 0.08, oh + 0.06, "steel_black"), self.box(ox + ow, y - 0.05, 0.0, 0.06, 0.08, oh + 0.06, "steel_black"),
                 self.box(ox - 0.06, y - 0.05, oh, ow + 0.12, 0.08, 0.06, "steel_black"), self.box(ox + ow / 2 - 0.2, y - 0.07, 1.0, 0.4, 0.03, 0.04, "chrome")]
        self._g2(c, "Garage", it, mat="Putz")
        self._g2(c, "Garagentor", door, cls="IfcDoor", mat="Aluminium", predefined="USERDEFINED")

    def _c_fountain(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        rb = R * 0.97
        basin = [(0.0, -0.1), (rb, -0.1), (rb, 0.0), (rb, 0.55), (rb - 0.18, 0.55), (rb - 0.18, 0.08), (0.0, 0.08)]
        it = [self._revolve([(0.0, -0.2), (R, -0.2), (R, 0.0), (R - 0.05, 0.0), (0.0, 0.0)], cx, cy, "paving_granite", 40),
              self._revolve([(rb - 0.18, 0.0), (rb, 0.0), (rb, 0.55), (rb + 0.04, 0.55), (rb + 0.04, 0.62), (rb - 0.22, 0.62), (rb - 0.22, 0.55), (rb - 0.18, 0.55)], cx, cy, m, 40)]
        it.append(self._revolve([(0.0, 0.0), (rb - 0.18, 0.0), (rb - 0.18, 0.0 + 0.001)][:2] + [(rb - 0.18, 0.0)], cx, cy, m, 8)) if False else None
        it = [s for s in it if s is not None]
        water = [self._revolve([(0.0, 0.46), (rb - 0.19, 0.46), (rb - 0.19, 0.48), (0.0, 0.48)], cx, cy, "water", 40)]
        col = [self._revolve([(0.0, 0.0), (0.42, 0.0), (0.42, 0.18), (0.26, 0.24), (0.2, 0.5), (0.16, 1.2), (0.28, 1.28), (0.34, 1.42), (0.0, 1.42)], cx, cy, m, 28),
               self._revolve([(0.0, 1.42), (0.6, 1.5), (0.78, 1.72), (0.72, 1.74), (0.52, 1.6), (0.0, 1.58)], cx, cy, m, 28),
               self._revolve([(0.0, 1.58), (0.5, 1.6), (0.0, 1.62)], cx, cy, "water", 28), self._revolve([(0.0, 1.6), (0.05, 1.6), (0.03, 2.35), (0.0, 2.4)], cx, cy, "water", 10)]
        self._g2(c, "Brunnen Becken", it, mat="Stein")
        self._g2(c, "Brunnen Wasser", water, cls="IfcBuildingElementProxy", mat="Wasser")
        self._g2(c, "Brunnen Säule", col, mat="Stein")

    def _c_firepit(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        it = [self._revolve([(0.0, -0.15), (R, -0.15), (R, 0.02), (0.0, 0.02)], cx, cy, "gravel_light", 36)]
        ring = []
        n = 12
        for k in range(n):
            a = 2 * math.pi * k / n
            px, py = cx + 0.55 * math.cos(a), cy + 0.55 * math.sin(a)
            ring.append(self._revolve([(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.32)], px, py, m, 8))
            ring.append(self._revolve([(0.0, 0.3), (0.18, 0.3), (0.0, 0.36)], px, py, m, 8))
        ember = [self._revolve([(0.0, 0.04), (0.42, 0.04), (0.35, 0.16), (0.0, 0.2)], cx, cy, "steel_corten", 14), self._revolve([(0.0, 0.2), (0.14, 0.2), (0.05, 0.42), (0.0, 0.46)], cx, cy, "paint_red_bright", 8)]
        seats = []
        for k in range(4):
            a = math.pi / 4 + k * math.pi / 2
            px, py = cx + (R - 0.45) * math.cos(a), cy + (R - 0.45) * math.sin(a)
            seats.append(self._revolve([(0.0, 0.0), (0.26, 0.0), (0.28, 0.2), (0.26, 0.42), (0.0, 0.42)], px, py, "wood_weathered", 12))
        self._g2(c, "Feuerstelle Grund", it, mat="Kies")
        self._g2(c, "Feuerstelle Steinring", ring, mat="Stein")
        self._g2(c, "Feuerstelle Glut", ember, mat="Stahl")
        self._g2(c, "Feuerstelle Sitzblöcke", seats, cls="IfcFurniture", mat="Holz")

    def _c_raised_bed(self, c, i, v=None):
        x, y, w, d, h, m = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"]
        t = 0.05
        it = []
        for k in range(int(h / 0.2)):
            z = k * 0.2
            it += [self.box(x, y, z, w, t, 0.19, m), self.box(x, y + d - t, z, w, t, 0.19, m), self.box(x, y + t, z, t, d - 2 * t, 0.19, m), self.box(x + w - t, y + t, z, t, d - 2 * t, 0.19, m)]
        for cx, cy in ((x, y), (x + w - 0.08, y), (x, y + d - 0.08), (x + w - 0.08, y + d - 0.08)):
            it.append(self.box(cx, cy, 0.0, 0.08, 0.08, h + 0.04, m))
        it.append(self.box(x + t, y + t, 0.0, w - 2 * t, d - 2 * t, h - 0.08, "soil_dark"))
        it.append(self.box(x - 0.03, y - 0.03, h, w + 0.06, 0.12, 0.04, m) if False else self.box(x - 0.02, y - 0.02, h + 0.0, w + 0.04, 0.06, 0.04, m))
        pl = []
        cols = max(2, int(w / 0.5))
        rows = max(1, int(d / 0.45))
        for a in range(cols):
            for b in range(rows):
                px = x + 0.15 + (w - 0.3) * (a + 0.5) / cols
                py = y + 0.15 + (d - 0.3) * (b + 0.5) / rows
                s = 0.16 + 0.05 * ((a * 3 + b * 5) % 3)
                pl.append(self._revolve([(0.0, h - 0.08), (s * 0.5, h - 0.04), (s, h + 0.08), (s * 0.7, h + 0.22), (0.0, h + 0.3)], px, py, "foliage" if (a + b) % 3 else "boxwood", 8))
        self._g2(c, "Hochbeet", it)
        self._veg("Hochbeet Pflanzen", pl, at=[(x + w / 2, y + d / 2)]) if False else self._g2(c, "Hochbeet Pflanzen", pl, cls="IfcGeographicElement", mat="Pflanzen", predefined="VEGETATION")

    def _c_sunloungers(self, c, i, v=None):
        x, y, w, d, m, cm = c["x"], c["y"], c["width"], c["depth"], c["material"], c["cushion_material"]
        it = [self.box(x - 0.1, y - 0.1, -0.1, w + 0.2, d + 0.2, 0.1, "terrace_decking")]
        L, Wd = 1.9, 0.62
        for k, off in enumerate((0.2, 1.1)):
            ly = y + 0.15
            lx = x + off
            it += [self.box(lx, ly, 0.22, Wd, 1.0, 0.07, m), self.box(lx + 0.02, ly + 0.0, 0.0, 0.05, 0.9, 0.23, "steel_black"), self.box(lx + Wd - 0.07, ly, 0.0, 0.05, 0.9, 0.23, "steel_black")]
            it += [self.box(lx + 0.03, ly + 0.0, 0.29, Wd - 0.06, 0.98, 0.07, cm)]
            back = [(ly + 1.0, 0.29), (ly + 1.0 + 0.9 * math.cos(math.radians(60)), 0.29 + 0.9 * math.sin(math.radians(60))),
                    (ly + 1.0 + 0.9 * math.cos(math.radians(60)) - 0.06 * math.sin(math.radians(60)), 0.29 + 0.9 * math.sin(math.radians(60)) + 0.06 * math.cos(math.radians(60))), (ly + 1.0, 0.36)]
            it.append(self._prism(back, (lx + 0.03, 0.0, 0.0), (1, 0, 0), (0, 1, 0), Wd - 0.06, cm))
            it.append(self.box(lx + 0.03, ly + 1.0 - 0.0, 0.0, Wd - 0.06, 0.05, 0.3, "steel_black") if False else self.box(lx + 0.03, ly + 1.0, 0.0, Wd - 0.06, 0.05, 0.03, "steel_black"))
        tx = x + 0.2 + Wd + 0.1 + 0.0
        it += [self._revolve([(0.0, 0.0), (0.22, 0.0), (0.22, 0.42), (0.0, 0.42)], x + w - 0.45, y + 0.55, m, 16)]
        self._g2(c, "Sonnenliegen", it, cls="IfcFurniture", mat="Holz/Stoff")
        px, py = x + 0.9, y + d - 0.45
        self._g2(c, "Sonnenschirm", [self.cylinder((px, py, 0.0), (px, py, 2.45), 0.025, "steel_black"), self._revolve([(0.0, 2.6), (0.7, 2.42), (1.3, 2.2), (1.28, 2.15)], px, py, "fabric_sand", 16)], mat="Stoff")

    def _c_bike_shed(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        H = 2.2
        it = [self.box(x, y, -0.1, w, d, 0.1, "paving_concrete")]
        n = max(2, int(w / 1.5) + 1)
        for k in range(n):
            px = x + 0.05 + (w - 0.2) * k / (n - 1)
            it += [self.box(px, y + 0.05, 0.0, 0.08, 0.08, H, m), self.box(px, y + d - 0.13, 0.0, 0.08, 0.08, H - 0.25, m)]
        it += [self.box(x - 0.1, y - 0.0, H - 0.04, w + 0.2, 0.06, 0.08, m), self.box(x - 0.1, y + d - 0.1, H - 0.29, w + 0.2, 0.06, 0.08, m)]
        pts = [(y - 0.15, H + 0.0), (y + d + 0.15, H - 0.2), (y + d + 0.15, H - 0.2 + 0.14), (y - 0.15, H + 0.14)]
        roof = [self._prism(pts, (x - 0.2, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w + 0.4, "roof_sedum")]
        for k in range(max(3, int(w / 0.6))):                  # wheel-bending racks
            px = x + 0.3 + (w - 0.6) * k / max(2, int(w / 0.6) - 1)
            it += [self.box(px, y + 0.35, 0.0, 0.03, 0.03, 0.75, "steel_galvanized"), self.box(px, y + 0.35, 0.72, 0.03, 1.1, 0.03, "steel_galvanized"), self.box(px, y + 1.42, 0.0, 0.03, 0.03, 0.75, "steel_galvanized")]
        self._g2(c, "Fahrradüberdachung", it, mat="Stahl")
        self._g2(c, "Fahrradüberdachung Dach", roof, cls="IfcRoof", mat="Gründach", predefined="SHED_ROOF")

    def _c_bin_store(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        H = 1.25
        it = [self.box(x, y, -0.05, w, d, 0.1, "paving_concrete")]
        for px in (x, x + w - 0.07):
            for py in (y, y + d - 0.07):
                it.append(self.box(px, py, 0.0, 0.07, 0.07, H, m))
        n = int(H / 0.1)
        for k in range(n):
            z = 0.08 + k * 0.1
            it += [self.box(x + 0.07, y + d - 0.03, z, w - 0.14, 0.03, 0.07, m), self.box(x + 0.0, y + 0.07, z, 0.03, d - 0.14, 0.07, m), self.box(x + w - 0.03, y + 0.07, z, 0.03, d - 0.14, 0.07, m)]
            if k % 1 == 0 and k < n - 5:
                it.append(self.box(x + 0.07, y, z, w - 0.14, 0.03, 0.07, m))
        k = max(1, int(w / 1.0))
        for j in range(k):
            xa = x + 0.1 + (w - 0.2) * j / k
            it.append(self.box(xa + 0.02, y - 0.04, H, (w - 0.2) / k - 0.04, d + 0.06, 0.05, "alu_anthracite"))
            it.append(self.box(xa + 0.2, y - 0.07, H + 0.02, (w - 0.2) / k - 0.4, 0.03, 0.03, "steel_black"))
        self._g2(c, "Mülltonnenbox", it)
        bins = []
        for j in range(k):
            bx = x + 0.1 + (w - 0.2) * (j + 0.5) / k
            bins.append(self.box(bx - 0.22, y + 0.15, 0.0, 0.44, d - 0.3, 1.0, "plastic_grey" if False else "metal_panel_anthracite"))
        self._g2(c, "Mülltonnen", bins, mat="Kunststoff")

    def _c_sculpture(self, c, i, v=None):
        x, y, w, d, h, m = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"]
        cx, cy = x + w / 2, y + d / 2
        it = [self.box(x, y, -0.15, w, d, 0.15 + 0.35, m), self.box(x + 0.1, y + 0.1, 0.35, w - 0.2, d - 0.2, 0.08, "stone_basalt_dark")]
        st = [self.box(cx - 0.18, cy - 0.06, 0.43, 0.36, 0.12, h - 0.43 - 0.35, "steel_corten"), self.box(cx - 0.12, cy - 0.04, h - 0.35 - 0.01, 0.24, 0.08, 0.1, "steel_corten")]
        st += [self._revolve([(0.0, h - 0.34), (0.2, h - 0.3), (0.34, h - 0.14), (0.3, h), (0.12, h + 0.0 if False else h - 0.02), (0.0, h)], cx, cy, "brass", 20)]
        self._g2(c, "Skulptur Sockel", it, mat="Stein")
        self._g2(c, "Skulptur", st, mat="Stahl/Messing")

    def _c_hottub(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        it = [self._revolve([(0.0, -0.1), (R, -0.1), (R, 0.0), (0.0, 0.0)], cx, cy, "terrace_decking", 36),
              self._revolve([(0.0, 0.0), (R - 0.15, 0.0), (R - 0.1, 0.95), (R - 0.22, 0.95), (R - 0.24, 0.12), (0.0, 0.12)][:1] + [(R - 0.1, 0.0), (R - 0.05, 0.95), (R - 0.2, 0.95), (R - 0.22, 0.05)] if False else
                            [(R - 0.2, 0.0), (R, 0.0), (R + 0.0, 0.95), (R - 0.2, 0.95)], cx, cy, m, 36),
              self._revolve([(R - 0.22, 0.95), (R + 0.04, 0.95), (R + 0.04, 1.0), (R - 0.22, 1.0)], cx, cy, "wood_oak", 36)]
        it.append(self._revolve([(0.0, 0.0), (R - 0.2, 0.0), (R - 0.2, 0.05), (0.0, 0.05)], cx, cy, "metal_panel_silver", 24))
        water = [self._revolve([(0.0, 0.78), (R - 0.205, 0.78), (R - 0.205, 0.8), (0.0, 0.8)], cx, cy, "water", 36)]
        cover = [self.box(cx - R - 0.05, cy - 0.0, 1.0, R * 2 + 0.1, R + 0.05, 0.12, "fabric_grey")]
        steps = [self.box(cx - 0.45, cy - R - 0.42, 0.0, 0.9, 0.4, 0.4, m), self.box(cx - 0.45, cy - R - 0.1, 0.0, 0.9, 0.1, 0.65, m)]
        self._g2(c, "Whirlpool", it)
        self._g2(c, "Whirlpool Wasser", water, mat="Wasser")
        self._g2(c, "Whirlpool Abdeckung", cover, mat="Stoff")
        self._g2(c, "Whirlpool Stufe", steps)

    def _c_swing_set(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        H = 2.3
        fy = y + 0.4
        it = []
        for px in (x + 0.1, x + w - 0.2):
            it += [self.cylinder((px + 0.05, fy - 0.45, 0.0), (px + 0.05, fy + 0.0, H), 0.05, m), self.cylinder((px + 0.05, fy + 0.45, 0.0), (px + 0.05, fy, H), 0.05, m),
                   self.box(px, fy - 0.45 - 0.03, -0.05, 0.1, 0.06, 0.1, "stone_granite_grey"), self.box(px, fy + 0.45 - 0.03, -0.05, 0.1, 0.06, 0.1, "stone_granite_grey")]
        it.append(self.cylinder((x + 0.05, fy, H), (x + w - 0.1, fy, H), 0.06, m))
        for k, sx in enumerate((x + w * 0.3, x + w * 0.7)):
            it += [self.cylinder((sx - 0.2, fy, H), (sx - 0.2, fy, 0.55), 0.008, "steel_galvanized"), self.cylinder((sx + 0.2, fy, H), (sx + 0.2, fy, 0.55), 0.008, "steel_galvanized"),
                   self.box(sx - 0.25, fy - 0.1, 0.5, 0.5, 0.2, 0.05, "paint_red_bright" if k == 0 else "paint_blue_light")]
        sb = [self.box(x + w / 2 - 0.9, y + d - 1.5, -0.1, 1.8, 1.4, 0.1, "gravel_light")]
        sb = [self.box(x + 0.2, y + d - 1.2, 0.0, 1.2, 1.0, 0.04, "gravel_light")]
        for ax, ay, aw, ah in ((x + 0.14, y + d - 1.26, 1.32, 0.06), (x + 0.14, y + d - 0.26, 1.32, 0.06), (x + 0.14, y + d - 1.2, 0.06, 1.0), (x + 1.4, y + d - 1.2, 0.06, 1.0)):
            sb.append(self.box(ax, ay, 0.0, aw, ah, 0.25, m))
        self._g2(c, "Schaukelgestell", it, cls="IfcFurniture", mat="Holz/Stahl")
        self._g2(c, "Sandkasten", sb, mat="Holz/Sand")

    def _c_planter_wall(self, c, i, v=None):
        x, y, w, d, h, m = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"]
        it = [self.box(x - 0.03, y - 0.03, -0.2, w + 0.06, d + 0.06, 0.2, "concrete_light")]
        n = max(2, int(w / 1.0))
        for k in range(n):
            xa = x + w * k / n
            it += [self.box(xa + 0.01, y, 0.0, w / n - 0.02, d, h, m), self.box(xa + 0.01, y - 0.015, 0.0, w / n - 0.02, 0.02, h, "steel_galvanized")]
        it.append(self.box(x - 0.02, y - 0.03, h, w + 0.04, d + 0.06, 0.06, "stone_ashlar_light"))
        pl = []
        for a in range(int(w / 0.35)):
            px = x + 0.2 + (w - 0.4) * (a + 0.5) / int(w / 0.35)
            for b, py in enumerate((y + d * 0.3, y + d * 0.7)):
                s = 0.12 + 0.05 * ((a + b) % 3)
                pl.append(self._revolve([(0.0, h + 0.04), (s * 0.4, h + 0.1), (s, h + 0.32), (s * 0.5, h + 0.55 + 0.1 * ((a * 7 + b) % 3)), (0.0, h + 0.65)], px, py, "foliage" if (a + b) % 2 else "boxwood", 8))
        self._g2(c, "Pflanzmauer", it, mat="Stein")
        self._g2(c, "Pflanzmauer Bepflanzung", pl, cls="IfcGeographicElement", mat="Pflanzen", predefined="VEGETATION")
