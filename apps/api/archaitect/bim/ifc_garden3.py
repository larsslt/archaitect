"""More library structures and decor (second batch): carport, outdoor kitchen, pool house, playhouse, trampoline, basketball, rock garden, arbor,
bird bath, urn planter, stone lantern, wood store, beehive, mailbox stele, car, garden bridge. Same convention as ifc_garden2: x, y = lower-left corner,
width (x), depth (y); built at z = 0 and lifted onto the lowest ground point by ``_g2``."""
from __future__ import annotations

import math


def _p(default, lo, hi, text):
    return ("n", default, lo, hi, text)


def _xy():
    return {"x": ("n", None, -300.0, 500.0, "linke untere Ecke x"), "y": ("n", None, -300.0, 500.0, "linke untere Ecke y")}


def _st(default, text="Material"):
    return ("st", default, None, None, text)


CATALOG = {
    "carport_free": {"label": "Freistehender Carport mit Stahlstützen, Flachdach und Blende", "tier": 5, "params": {
        **_xy(), "width": _p(5.2, 2.8, 9.0, "Breite"), "depth": _p(5.5, 4.5, 7.0, "Tiefe"), "height": _p(2.5, 2.2, 3.2, "Höhe"),
        "material": _st("alu_anthracite"), "roof_material": _st("roof_sedum", "Dach")}},
    "outdoor_kitchen": {"label": "Outdoor-Küche mit Grill, Spüle, Arbeitsplatte aus Naturstein und Barhockern", "tier": 5, "params": {
        **_xy(), "width": _p(3.4, 2.4, 6.0, "Breite"), "depth": _p(1.6, 1.2, 2.4, "Tiefe"), "material": _st("concrete_light", "Korpus"), "top_material": _st("stone_basalt_dark", "Platte")}},
    "pool_house": {"label": "Poolhaus mit Flachdach, Glasfront, Holzdeck und Holzlamellen", "tier": 5, "params": {
        **_xy(), "width": _p(5.0, 3.6, 8.0, "Breite"), "depth": _p(3.6, 3.0, 6.0, "Tiefe (ohne Deck)"), "wall_material": _st("plaster_white", "Wand"), "wood_material": _st("wood_thermo", "Holz")}},
    "playhouse": {"label": "Spielhaus auf Stelzen mit Satteldach, Leiter und Rutsche", "tier": 5, "params": {
        **_xy(), "width": _p(3.2, 2.4, 5.0, "Breite"), "depth": _p(1.8, 1.4, 3.0, "Tiefe"), "material": _st("wood_larch"), "roof_material": _st("paint_red_sweden", "Dach")}},
    "trampoline": {"label": "Rundes Trampolin mit Fangnetz, in Gartengrün", "tier": 5, "params": {
        **_xy(), "width": _p(3.8, 2.4, 5.0, "Durchmesser"), "depth": _p(3.8, 2.4, 5.0, "Durchmesser (gleich Breite)"), "material": _st("steel_black")}},
    "basketball": {"label": "Basketballfeld (Hof) mit Pfosten, Glas-Korbbrett, Korb und Linien", "tier": 5, "params": {
        **_xy(), "width": _p(6.0, 4.0, 10.0, "Breite"), "depth": _p(5.5, 4.0, 9.0, "Tiefe"), "material": _st("asphalt")}},
    "rock_garden": {"label": "Steingarten mit Findlingen, Kies und Ziergräsern", "tier": 5, "params": {
        **_xy(), "width": _p(3.6, 1.6, 8.0, "Breite"), "depth": _p(2.6, 1.4, 6.0, "Tiefe"), "material": _st("stone_granite_grey", "Findlinge")}},
    "arbor": {"label": "Rosenbogen aus Stahl und Holz mit Kletterrosen", "tier": 5, "params": {
        **_xy(), "width": _p(1.8, 1.2, 3.0, "Breite"), "depth": _p(0.8, 0.5, 1.4, "Tiefe"), "material": _st("steel_black")}},
    "bird_bath": {"label": "Vogeltränke: Steinsäule mit flacher Schale", "tier": 5, "params": {
        **_xy(), "width": _p(0.8, 0.5, 1.2, "Durchmesser"), "depth": _p(0.8, 0.5, 1.2, "Durchmesser (gleich Breite)"), "material": _st("stone_limestone")}},
    "planter_urn": {"label": "Große Pflanzurne (Amphoren-Form) mit Bepflanzung", "tier": 5, "params": {
        **_xy(), "width": _p(0.9, 0.6, 1.4, "Durchmesser"), "depth": _p(0.9, 0.6, 1.4, "Durchmesser (gleich Breite)"), "material": _st("plaster_terracotta")}},
    "stone_lantern": {"label": "Steinlaterne (japanisch) mit Sockel, Feuerkammer und Dach", "tier": 5, "params": {
        **_xy(), "width": _p(0.8, 0.5, 1.2, "Durchmesser"), "depth": _p(0.8, 0.5, 1.2, "Durchmesser (gleich Breite)"), "material": _st("stone_granite_grey")}},
    "wood_shed": {"label": "Holzlager mit gestapelten Scheiten, Pultdach und Rückwand", "tier": 5, "params": {
        **_xy(), "width": _p(3.0, 1.6, 6.0, "Breite"), "depth": _p(1.1, 0.8, 1.6, "Tiefe"), "material": _st("wood_thermo")}},
    "beehive": {"label": "Bienenstand: zwei Magazinbeuten auf Gestell mit Dach", "tier": 5, "params": {
        **_xy(), "width": _p(1.4, 0.8, 2.4, "Breite"), "depth": _p(0.7, 0.5, 1.0, "Tiefe"), "material": _st("paint_white")}},
    "mailbox_stele": {"label": "Briefkasten-Stele aus Beton mit Hausnummernschild", "tier": 5, "params": {
        **_xy(), "width": _p(0.6, 0.4, 1.0, "Breite"), "depth": _p(0.4, 0.3, 0.7, "Tiefe"), "height": _p(1.4, 1.1, 1.8, "Höhe"), "material": _st("concrete_exposed")}},
    "car": {"label": "Pkw (Kombi, vereinfacht) zur Maßstabsorientierung, Länge entlang y", "tier": 5, "params": {
        **_xy(), "width": _p(1.9, 1.6, 2.2, "Breite"), "depth": _p(4.7, 3.6, 5.4, "Länge"), "color": _st("paint_blue_dark", "Lack")}},
    "garden_bridge": {"label": "Gartenbrücke aus Holz mit Bogen und Geländer (Länge entlang x)", "tier": 5, "params": {
        **_xy(), "width": _p(3.6, 2.4, 6.0, "Länge"), "depth": _p(1.2, 0.9, 2.0, "Breite"), "material": _st("wood_cedar"), "frame_material": _st("steel_black", "Geländer")}},
}
LABEL = {"carport_free": "Carport", "outdoor_kitchen": "Outdoor-Küche", "pool_house": "Poolhaus", "playhouse": "Spielhaus", "trampoline": "Trampolin",
         "basketball": "Basketballfeld", "rock_garden": "Steingarten", "arbor": "Rosenbogen", "bird_bath": "Vogeltränke", "planter_urn": "Pflanzurne",
         "stone_lantern": "Steinlaterne", "wood_shed": "Holzlager", "beehive": "Bienenstand", "mailbox_stele": "Briefkasten-Stele", "car": "Pkw",
         "garden_bridge": "Gartenbrücke"}
OBJECTS = {
    "carport_free": ("Nebengebäude", "carport_free", {}, "Carport freistehend"),
    "carport_double": ("Nebengebäude", "carport_free", {"width": 6.0, "depth": 5.5, "roof_material": "roof_zinc_standing"}, "Doppelcarport"),
    "pool_house": ("Nebengebäude", "pool_house", {}, "Poolhaus"),
    "wood_shed": ("Nebengebäude", "wood_shed", {}, "Holzlager"),
    "outdoor_kitchen": ("Terrasse & Sitzen", "outdoor_kitchen", {}, "Outdoor-Küche"),
    "playhouse": ("Spiel & Sport", "playhouse", {}, "Spielhaus"),
    "trampoline": ("Spiel & Sport", "trampoline", {}, "Trampolin"),
    "basketball": ("Spiel & Sport", "basketball", {}, "Basketballfeld"),
    "rock_garden": ("Pflanzen", "rock_garden", {}, "Steingarten"),
    "arbor": ("Pflanzen", "arbor", {}, "Rosenbogen"),
    "beehive": ("Pflanzen", "beehive", {}, "Bienenstand"),
    "bird_bath": ("Dekoration", "bird_bath", {}, "Vogeltränke"),
    "planter_urn": ("Dekoration", "planter_urn", {}, "Pflanzurne"),
    "planter_urn_stone": ("Dekoration", "planter_urn", {"width": 1.1, "depth": 1.1, "material": "stone_limestone"}, "Pflanzurne Stein"),
    "stone_lantern": ("Dekoration", "stone_lantern", {}, "Steinlaterne"),
    "mailbox_stele": ("Dekoration", "mailbox_stele", {}, "Briefkasten-Stele"),
    "garden_bridge": ("Dekoration", "garden_bridge", {}, "Gartenbrücke"),
    "car": ("Mobilität", "car", {}, "Pkw blau"),
    "car_white": ("Mobilität", "car", {"color": "paint_white"}, "Pkw weiß"),
    "car_red": ("Mobilität", "car", {"color": "paint_red_bright", "depth": 4.1, "width": 1.75}, "Kleinwagen rot"),
    "car_black": ("Mobilität", "car", {"color": "paint_black", "depth": 4.9, "width": 1.95}, "Pkw schwarz"),
}


class Garden3Mixin:
    def _boulder(self, cx, cy, r, h, style, seed):
        k = [1.0, 0.82, 0.92, 0.7, 1.05, 0.88][seed % 6]
        prof = [(0.0, 0.0), (r * 0.8 * k, 0.0), (r * k, h * 0.35), (r * 0.9, h * 0.75), (r * 0.55, h * 0.97), (0.0, h)]
        return self._revolve(prof, cx, cy, style, 9)

    # ---------------------------------------------------------------- buildings
    def _c_carport_free(self, c, i, v=None):
        x, y, w, d, h, m, rm = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"], c["roof_material"]
        it = [self.box(x, y, -0.1, w, d, 0.1, "paving_concrete")]
        for px in (x + 0.15, x + w - 0.27):
            for py in (y + 0.15, y + d - 0.27):
                it.append(self.box(px, py, 0.0, 0.12, 0.12, h, m))
        it += [self.box(x, y, h, w, d, 0.16, m), self.box(x + 0.02, y + 0.02, h + 0.16, w - 0.04, d - 0.04, 0.12, rm)]
        cols = max(1, int(w // 2.6))
        for k in range(1, cols):
            it.append(self.box(x + w * k / cols - 0.1, y + d - 0.12, 0.0, 0.2, 0.12, h, "metal_panel_anthracite"))     # storage wall panel
        self._g2(c, "Carport", it, mat="Aluminium")

    def _c_outdoor_kitchen(self, c, i, v=None):
        x, y, w, d, m, tm = c["x"], c["y"], c["width"], c["depth"], c["material"], c["top_material"]
        it = [self.box(x, y, -0.1, w, d, 0.1, "paving_granite")]
        cw = 0.9
        for k in range(int(w / cw)):                              # base cabinets (back row)
            it.append(self.box(x + 0.02 + k * cw, y + d - 0.75, 0.0, cw - 0.04, 0.7, 0.86, m))
        it.append(self.box(x, y + d - 0.8, 0.86, w, 0.8, 0.05, tm))
        it.append(self.box(x + 0.0, y + d - 0.05, 0.91, w, 0.05, 0.35, tm))                         # splashback
        gx = x + w * 0.3
        grill = [self.box(gx, y + d - 0.7, 0.91, 0.9, 0.55, 0.28, "steel_galvanized"), self.box(gx + 0.02, y + d - 0.72, 1.12, 0.86, 0.4, 0.08, "steel_black"),
                 self.box(gx + 0.05, y + d - 0.78, 1.0, 0.8, 0.04, 0.03, "steel_black")]
        sx = x + w * 0.72
        it += [self.box(sx, y + d - 0.65, 0.88, 0.6, 0.45, 0.03, "metal_panel_silver"), self.cylinder((sx + 0.45, y + d - 0.2, 0.91), (sx + 0.45, y + d - 0.2, 1.15), 0.02, "chrome"),
               self.cylinder((sx + 0.45, y + d - 0.2, 1.15), (sx + 0.45, y + d - 0.4, 1.15), 0.015, "chrome")]
        bar = [self.box(x, y + 0.1, 0.0, w, 0.5, 1.05, m), self.box(x - 0.05, y + 0.05, 1.05, w + 0.1, 0.6, 0.05, tm)]
        stools = []
        for k in range(3):
            sx2 = x + w * (k + 0.5) / 3
            stools += [self._revolve([(0.0, 0.62), (0.17, 0.62), (0.17, 0.67), (0.0, 0.67)], sx2, y + 0.95, "leather_brown", 12), self.cylinder((sx2, y + 0.95, 0.0), (sx2, y + 0.95, 0.62), 0.025, "steel_black"),
                       self._revolve([(0.0, 0.0), (0.16, 0.0), (0.16, 0.02), (0.0, 0.02)], sx2, y + 0.95, "steel_black", 12)]
        self._g2(c, "Outdoor-Küche", it + bar, mat="Beton/Stein")
        self._g2(c, "Outdoor-Küche Grill", grill, mat="Stahl")
        self._g2(c, "Barhocker", stools, cls="IfcFurniture", mat="Leder/Stahl")

    def _c_pool_house(self, c, i, v=None):
        x, y, w, d, wm, wd = c["x"], c["y"], c["width"], c["depth"], c["wall_material"], c["wood_material"]
        deck = 1.6
        H, t = 2.8, 0.25
        y0 = y + deck
        it = [self.box(x, y0, -0.1, w, d, 0.2, "concrete_light")]
        g0, g1 = w * 0.18, w * 0.82
        it += [self.box(x, y0 + d - t, 0.1, w, t, H, wm), self.box(x, y0, 0.1, t, d - t, H, wm), self.box(x + w - t, y0, 0.1, t, d - t, H, wm),
               self.box(x + t, y0, 0.1 + 2.3, w - 2 * t, t, H - 2.3, wm), self.box(x + t, y0, 0.1, g0 - t, t, 2.3, wm), self.box(x + g1, y0, 0.1, w - g1 - t, t, 2.3, wm)]
        glass = [self.box(x + g0, y0 + 0.05, 0.1, g1 - g0, 0.04, 2.3, "glass_clear")]
        n = 4
        for k in range(n + 1):
            glass.append(self.box(x + g0 + (g1 - g0 - 0.06) * k / n, y0 + 0.02, 0.1, 0.06, 0.08, 2.3, "alu_anthracite"))
        glass += [self.box(x + g0, y0 + 0.02, 0.1, g1 - g0, 0.08, 0.05, "alu_anthracite"), self.box(x + g0, y0 + 0.02, 2.35, g1 - g0, 0.08, 0.05, "alu_anthracite")]
        slats = []
        k = 0
        while g1 + 0.06 + k * 0.14 < w - 0.3:                       # vertical timber slats on the right part of the front
            slats.append(self.box(x + g1 + 0.06 + k * 0.14, y0 - 0.06, 0.1, 0.06, 0.06, 2.3, wd))
            k += 1
        roof = [self.box(x - 0.5, y0 - 0.9, H + 0.1, w + 1.0, d + 1.1, 0.22, wd), self.box(x - 0.5, y0 - 0.9, H + 0.32, w + 1.0, d + 1.1, 0.1, "roof_gravel_flat")]
        decks = [self.box(x - 0.2, y, -0.05, w + 0.4, deck, 0.1, "terrace_decking")]
        for k in range(int((w + 0.4) / 0.4)):
            decks.append(self.box(x - 0.2 + k * 0.4, y, 0.05, 0.02, deck, 0.01, "timber_brown_dark"))
        self._g2(c, "Poolhaus", it, mat="Putz")
        self._g2(c, "Poolhaus Glasfront", glass, mat="Glas/Alu")
        self._g2(c, "Poolhaus Holzlamellen", slats, mat="Holz")
        self._g2(c, "Poolhaus Dach", roof, cls="IfcRoof", mat="Holz/Kies", predefined="FLAT_ROOF")
        self._g2(c, "Poolhaus Deck", decks, mat="Holz")

    def _c_playhouse(self, c, i, v=None):
        x, y, w, d, m, rm = c["x"], c["y"], c["width"], c["depth"], c["material"], c["roof_material"]
        hw = min(2.0, w - 1.0)
        hx = x + 0.1
        z0 = 1.1
        it = []
        for px in (hx, hx + hw - 0.12):
            for py in (y + 0.1, y + d - 0.22):
                it.append(self.box(px, py, 0.0, 0.12, 0.12, z0, m))
        it.append(self.box(hx - 0.05, y + 0.05, z0, hw + 0.1, d - 0.1, 0.08, m))
        body = [self.box(hx, y + d - 0.1, z0 + 0.08, hw, 0.1, 1.4, m), self.box(hx, y + 0.05, z0 + 0.08, 0.1, d - 0.1, 1.4, m), self.box(hx + hw - 0.1, y + 0.05, z0 + 0.08, 0.1, d - 0.1, 1.4, m),
                self.box(hx, y + 0.05, z0 + 0.08, 0.55, 0.1, 1.4, m), self.box(hx + hw - 0.55, y + 0.05, z0 + 0.08, 0.55, 0.1, 1.4, m), self.box(hx + 0.55, y + 0.05, z0 + 0.08 + 1.05, hw - 1.1, 0.1, 0.35, m),
                self.box(hx + 0.55, y + 0.05, z0 + 0.08, hw - 1.1, 0.1, 0.4, m)]
        body.append(self.box(hx + 0.6, y + 0.07, z0 + 0.5, hw - 1.2, 0.02, 0.55, "glass_clear"))
        rise = (d / 2 + 0.2) * math.tan(math.radians(32))
        zt = z0 + 1.48
        ym = y + d / 2
        roof = [self._prism([(y - 0.2, zt), (ym, zt + rise), (y + d + 0.2, zt), (y + d + 0.2, zt + 0.07), (ym, zt + rise + 0.07), (y - 0.2, zt + 0.07)], (hx - 0.2, 0.0, 0.0), (1, 0, 0), (0, 1, 0), hw + 0.4, rm)]
        gab = [self._prism([(y + 0.05, zt - 0.02), (y + d - 0.05, zt - 0.02), (ym, zt + rise * 0.82)], (hx, 0.0, 0.0), (1, 0, 0), (0, 1, 0), hw, m)]
        lad = [self.box(hx + hw + 0.1, y + 0.25, 0.0, 0.05, 0.05, z0 + 0.1, m), self.box(hx + hw + 0.1, y + 0.55, 0.0, 0.05, 0.05, z0 + 0.1, m)]
        for k in range(5):
            lad.append(self.box(hx + hw + 0.1, y + 0.25, 0.2 + k * 0.2, 0.05, 0.35, 0.04, m))
        sx0 = hx + hw + 0.2
        self._g2(c, "Spielhaus", it + body + gab, mat="Holz")
        self._g2(c, "Spielhaus Dach", roof, cls="IfcRoof", mat="Dach", predefined="GABLE_ROOF")
        self._g2(c, "Spielhaus Leiter", lad, mat="Holz")
        slide = []
        L = max(0.9, w - hw - 0.4)
        n = 10
        for k in range(n):
            xa = sx0 + 0.15 + L * k / n
            za = z0 + 0.05 - (z0 - 0.05) * (k / n) ** 1.3
            slide.append(self.box(xa, y + d - 0.75, max(0.02, za), L / n + 0.01, 0.55, 0.04, "metal_panel_silver"))
        self._g2(c, "Rutsche", slide, mat="Edelstahl")

    def _c_trampoline(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        it = [self._revolve([(0.0, 0.62), (R - 0.15, 0.62), (R - 0.15, 0.66), (0.0, 0.66)], cx, cy, "steel_black", 36),
              self._revolve([(R - 0.15, 0.6), (R, 0.6), (R, 0.72), (R - 0.15, 0.72)], cx, cy, "fabric_green", 36)]
        for k in range(8):
            a = 2 * math.pi * k / 8
            px, py = cx + (R - 0.08) * math.cos(a), cy + (R - 0.08) * math.sin(a)
            it += [self.cylinder((px, py, 0.0), (px, py, 0.62), 0.03, m)]
        net = []
        for k in range(8):
            a = 2 * math.pi * k / 8
            px, py = cx + (R - 0.1) * math.cos(a), cy + (R - 0.1) * math.sin(a)
            net.append(self.cylinder((px, py, 0.72), (px, py, 2.4), 0.02, m))
        net.append(self._revolve([(R - 0.12, 0.72), (R - 0.1, 0.72), (R - 0.1, 2.4), (R - 0.12, 2.4)], cx, cy, "glass_frosted", 36))
        net.append(self._revolve([(R - 0.14, 2.38), (R - 0.06, 2.38), (R - 0.06, 2.44), (R - 0.14, 2.44)], cx, cy, "fabric_green", 36))
        self._g2(c, "Trampolin", it, cls="IfcFurniture", mat="Stahl/Stoff")
        self._g2(c, "Trampolin Netz", net, mat="Netz")

    def _c_basketball(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        pad = [self.box(x, y, -0.1, w, d, 0.1, m)]
        for ax, ay, aw, ah in ((x + 0.15, y + 0.15, w - 0.3, 0.07), (x + 0.15, y + d - 0.22, w - 0.3, 0.07), (x + 0.15, y + 0.15, 0.07, d - 0.3), (x + w - 0.22, y + 0.15, 0.07, d - 0.3)):
            pad.append(self.box(ax, ay, 0.0, aw, ah, 0.01, "paint_white"))
        kc = (x + w / 2, y + d - 0.15)
        ring_pts = [(kc[0] + 1.72 * math.cos(math.pi * k / 24), kc[1] - 1.72 * math.sin(math.pi * k / 24)) for k in range(25)]   # free-throw half circle
        for p0, p1 in zip(ring_pts, ring_pts[1:]):
            pad.append(self.cylinder((p0[0], p0[1], 0.012), (p1[0], p1[1], 0.012), 0.025, "paint_white"))
        px = x + w / 2
        py = y + d - 0.6
        pole = [self.box(px - 0.07, py, 0.0, 0.14, 0.14, 3.6, "steel_black"), self.box(px - 0.04, py - 0.9, 3.4, 0.08, 0.95, 0.08, "steel_black")]
        board = [self.box(px - 0.9, py - 0.95, 2.9, 1.8, 0.05, 1.05, "glass_clear"), self.box(px - 0.9, py - 0.97, 2.9, 1.8, 0.03, 0.04, "steel_black"), self.box(px - 0.9, py - 0.97, 3.91, 1.8, 0.03, 0.04, "steel_black"),
                 self.box(px - 0.3, py - 0.97, 3.05, 0.6, 0.03, 0.04, "paint_red_bright"), self.box(px - 0.3, py - 0.97, 3.3, 0.6, 0.03, 0.04, "paint_red_bright")]
        hx, hy = px, py - 1.2
        ring = []
        pts = [(hx + 0.23 * math.cos(2 * math.pi * k / 16), hy + 0.23 * math.sin(2 * math.pi * k / 16)) for k in range(17)]
        for p0, p1 in zip(pts, pts[1:]):
            ring.append(self.cylinder((p0[0], p0[1], 3.05), (p1[0], p1[1], 3.05), 0.012, "paint_red_bright"))
        for k in range(0, 16, 2):                                    # net strings from the rim to a smaller bottom ring
            a = 2 * math.pi * k / 16
            ring.append(self.cylinder((hx + 0.23 * math.cos(a), hy + 0.23 * math.sin(a), 3.05), (hx + 0.12 * math.cos(a), hy + 0.12 * math.sin(a), 2.7), 0.004, "fabric_sand"))
        ring.append(self.box(px - 0.04, hy + 0.23, 3.02, 0.08, 0.18, 0.04, "paint_red_bright"))
        self._g2(c, "Basketballfeld", pad, mat="Asphalt")
        self._g2(c, "Basketballkorb Pfosten", pole + board, mat="Stahl/Glas")
        self._g2(c, "Basketballkorb", ring, mat="Stahl")

    # ---------------------------------------------------------------- garden features
    def _c_rock_garden(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        bed = [self.box(x, y, -0.1, w, d, 0.16, "gravel_light")]
        for ax, ay, aw, ah in ((x - 0.05, y - 0.05, w + 0.1, 0.07), (x - 0.05, y + d - 0.02, w + 0.1, 0.07), (x - 0.05, y - 0.05, 0.07, d + 0.1), (x + w - 0.02, y - 0.05, 0.07, d + 0.1)):
            bed.append(self.box(ax, ay, 0.0, aw, ah, 0.14, "steel_corten"))
        rocks = []
        spots = [(0.3, 0.4, 0.55, 0.5), (0.65, 0.65, 0.4, 0.35), (0.8, 0.3, 0.3, 0.28), (0.15, 0.8, 0.28, 0.3), (0.5, 0.25, 0.22, 0.2)]
        for k, (u, vv, r, h) in enumerate(spots):
            rocks.append(self._boulder(x + w * u, y + d * vv, r * min(1.0, w / 3.2), h * min(1.0, d / 2.4) + 0.1, m, k))
        grass = []
        for k in range(14):
            gx = x + 0.2 + ((k * 0.37) % 1) * (w - 0.4)
            gy = y + 0.2 + ((k * 0.61) % 1) * (d - 0.4)
            grass.append(self._revolve([(0.0, 0.0), (0.12, 0.05), (0.18, 0.35), (0.1, 0.62), (0.0, 0.75)], gx, gy, "grass_hair" if k % 2 else "foliage", 7))
        self._g2(c, "Steingarten", bed, mat="Kies")
        self._g2(c, "Steingarten Findlinge", rocks, mat="Granit")
        self._g2(c, "Steingarten Gräser", grass, cls="IfcGeographicElement", mat="Pflanzen", predefined="VEGETATION")

    def _c_arbor(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        H, r = 2.3, w / 2
        cx = x + w / 2
        it = []
        for px in (x + 0.04, x + w - 0.04):
            for py in (y + 0.06, y + d - 0.06):
                it.append(self.cylinder((px, py, 0.0), (px, py, H - r * 0.0), 0.02, m))
        arch = []
        n = 10
        for py in (y + 0.06, y + d - 0.06):
            pts = [(cx - r * math.cos(math.pi * k / n) * 0.96, py, H + r * 0.6 * math.sin(math.pi * k / n)) for k in range(n + 1)]
            for a, b in zip(pts, pts[1:]):
                arch.append(self.cylinder(a, b, 0.02, m))
        for k in range(1, n):
            ax = cx - r * math.cos(math.pi * k / n) * 0.96
            az = H + r * 0.6 * math.sin(math.pi * k / n)
            arch.append(self.cylinder((ax, y + 0.06, az), (ax, y + d - 0.06, az), 0.012, m))
        roses = []
        for k in range(8):
            side = x + 0.05 if k % 2 == 0 else x + w - 0.05
            zz = 0.5 + (k // 2) * 0.55
            roses.append(self._revolve([(0.0, zz - 0.18), (0.16, zz - 0.08), (0.2, zz), (0.14, zz + 0.12), (0.0, zz + 0.2)], side, y + d / 2, "foliage", 8))
        for k in range(5):
            ax = cx - r * math.cos(math.pi * (k + 0.5) / 5) * 0.9
            az = H + r * 0.6 * math.sin(math.pi * (k + 0.5) / 5)
            roses.append(self._revolve([(0.0, az - 0.12), (0.14, az - 0.05), (0.16, az + 0.03), (0.0, az + 0.14)], ax, y + d / 2, "paint_red_bright" if k % 2 else "foliage", 8))
        self._g2(c, "Rosenbogen", it + arch, mat="Stahl")
        self._g2(c, "Rosenbogen Rosen", roses, cls="IfcGeographicElement", mat="Pflanzen", predefined="VEGETATION")

    def _c_bird_bath(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        it = [self._revolve([(0.0, 0.0), (R * 0.45, 0.0), (R * 0.45, 0.08), (R * 0.25, 0.14), (R * 0.2, 0.7), (R * 0.28, 0.78), (R * 0.9, 0.86), (R, 0.92), (R * 0.92, 0.96), (R * 0.8, 0.9), (0.0, 0.88)], cx, cy, m, 24)]
        w = [self._revolve([(0.0, 0.89), (R * 0.82, 0.9), (R * 0.82, 0.915), (0.0, 0.915)], cx, cy, "water", 24)]
        self._g2(c, "Vogeltränke", it, mat="Stein")
        self._g2(c, "Vogeltränke Wasser", w, mat="Wasser")

    def _c_planter_urn(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        s = R / 0.45
        prof = [(0.0, 0.0), (0.26 * s, 0.0), (0.3 * s, 0.1), (0.4 * s, 0.4), (0.45 * s, 0.65), (0.4 * s, 0.9), (0.3 * s, 1.0), (0.34 * s, 1.06), (0.4 * s, 1.1), (0.36 * s, 1.14), (0.28 * s, 1.1), (0.0, 1.05)]
        it = [self._revolve(prof, cx, cy, m, 24)]
        pl = [self._revolve([(0.0, 1.0), (0.3 * s, 1.04), (0.4 * s, 1.25), (0.3 * s, 1.55), (0.12 * s, 1.75), (0.0, 1.85)], cx, cy, "foliage", 12),
              self._revolve([(0.0, 1.1), (0.34 * s, 1.14), (0.5 * s, 1.3), (0.34 * s, 1.34), (0.0, 1.36)], cx, cy, "boxwood", 12)]
        self._g2(c, "Pflanzurne", it, mat="Keramik/Stein")
        self._g2(c, "Pflanzurne Bepflanzung", pl, cls="IfcGeographicElement", mat="Pflanzen", predefined="VEGETATION")

    def _c_stone_lantern(self, c, i, v=None):
        cx, cy, R, m = c["x"] + c["width"] / 2, c["y"] + c["depth"] / 2, c["width"] / 2, c["material"]
        s = R / 0.4
        it = [self._revolve([(0.0, 0.0), (0.38 * s, 0.0), (0.38 * s, 0.1), (0.28 * s, 0.14), (0.0, 0.14)], cx, cy, m, 12),
              self._revolve([(0.0, 0.14), (0.1 * s, 0.14), (0.09 * s, 0.7), (0.0, 0.7)], cx, cy, m, 10),
              self._revolve([(0.0, 0.7), (0.34 * s, 0.7), (0.4 * s, 0.76), (0.28 * s, 0.82), (0.0, 0.82)], cx, cy, m, 10)]
        box = [self.box(cx - 0.14 * s, cy - 0.14 * s, 0.82, 0.28 * s, 0.28 * s, 0.3 * s, m), self.box(cx - 0.1 * s, cy - 0.145 * s, 0.86, 0.2 * s, 0.01, 0.2 * s, "glass_frosted")]
        top = [self._revolve([(0.0, 0.82 + 0.3 * s), (0.5 * s, 0.82 + 0.3 * s), (0.42 * s, 0.82 + 0.38 * s), (0.2 * s, 0.82 + 0.5 * s), (0.0, 0.82 + 0.62 * s)], cx, cy, m, 8),
               self._revolve([(0.0, 0.82 + 0.6 * s), (0.07 * s, 0.82 + 0.6 * s), (0.05 * s, 0.82 + 0.75 * s), (0.0, 0.82 + 0.78 * s)], cx, cy, m, 8)]
        self._g2(c, "Steinlaterne", it + box + top, mat="Naturstein")

    def _c_wood_shed(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        H = 2.0
        it = [self.box(x, y, 0.0, w, d, 0.08, "wood_pine")]
        for px in (x + 0.02, x + w - 0.1):
            it += [self.box(px, y + 0.02, 0.08, 0.08, 0.08, H, m), self.box(px, y + d - 0.1, 0.08, 0.08, 0.08, H - 0.35, m)]
        it += [self.box(x + 0.02, y + d - 0.06, 0.08, w - 0.04, 0.04, H - 0.35, m), self.box(x + 0.02, y + 0.02, 0.08 + H - 0.1, w - 0.04, 0.06, 0.08, m)]
        pts = [(y - 0.15, H + 0.1), (y + d + 0.15, H - 0.2), (y + d + 0.15, H - 0.1), (y - 0.15, H + 0.2)]
        roof = [self._prism(pts, (x - 0.15, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w + 0.3, "roof_zinc_standing")]
        logs = []
        cols, rows = int((w - 0.3) / 0.16), 8
        for r in range(rows):
            for k in range(cols):
                lx = x + 0.15 + 0.08 + k * 0.16 + (0.08 if r % 2 else 0.0)
                if lx > x + w - 0.15:
                    continue
                logs.append(self.cylinder((lx, y + 0.18, 0.2 + r * 0.14), (lx, y + d - 0.12, 0.2 + r * 0.14), 0.07, "wood_oak" if (k + r) % 3 else "wood_pine"))
        self._g2(c, "Holzlager", it, mat="Holz")
        self._g2(c, "Holzlager Dach", roof, cls="IfcRoof", mat="Zink", predefined="SHED_ROOF")
        self._g2(c, "Brennholz", logs, mat="Holz")

    def _c_beehive(self, c, i, v=None):
        x, y, w, d, m = c["x"], c["y"], c["width"], c["depth"], c["material"]
        it = []
        for hx in (x + 0.08, x + w / 2 + 0.06):
            hw = w / 2 - 0.14
            it += [self.box(hx, y + 0.08, 0.0, 0.05, d - 0.16, 0.35, "wood_weathered"), self.box(hx + hw - 0.05, y + 0.08, 0.0, 0.05, d - 0.16, 0.35, "wood_weathered"), self.box(hx, y + 0.08, 0.35, hw, d - 0.16, 0.04, "wood_weathered")]
            for k, st in enumerate((m, "paint_yellow", m)):
                it.append(self.box(hx + 0.01, y + 0.1, 0.39 + k * 0.24, hw - 0.02, d - 0.2, 0.23, st))
            it += [self.box(hx - 0.03, y + 0.06, 0.39 + 0.72, hw + 0.06, d - 0.12, 0.05, "zinc"), self.box(hx + hw * 0.2, y + 0.04, 0.39, hw * 0.6, 0.06, 0.03, "wood_oak")]
        self._g2(c, "Bienenstand", it, mat="Holz")

    def _c_mailbox_stele(self, c, i, v=None):
        x, y, w, d, h, m = c["x"], c["y"], c["width"], c["depth"], c["height"], c["material"]
        it = [self.box(x, y, -0.2, w, d, h + 0.2, m), self.box(x - 0.02, y - 0.02, h, w + 0.04, d + 0.04, 0.05, "steel_black")]
        front = [self.box(x + 0.06, y - 0.03, h - 0.55, w - 0.12, 0.03, 0.3, "steel_galvanized"), self.box(x + 0.1, y - 0.035, h - 0.5, w - 0.2, 0.01, 0.03, "steel_black"),
                 self.box(x + w / 2 - 0.12, y - 0.03, h - 0.95, 0.24, 0.03, 0.24, "brass"), self.box(x + 0.06, y - 0.035, h - 1.1, w - 0.12, 0.01, 0.1, "steel_black")]
        self._g2(c, "Briefkasten-Stele", it, mat="Beton")
        self._g2(c, "Briefkasten", front, mat="Stahl/Messing")

    def _c_car(self, c, i, v=None):
        x, y, w, L, col = c["x"], c["y"], c["width"], c["depth"], c["color"]
        zb, wr = 0.2, 0.33
        body = [self.box(x + 0.03, y + 0.35, zb, w - 0.06, L - 0.7, 0.55, col), self.box(x + 0.08, y + 0.05, zb + 0.08, w - 0.16, 0.32, 0.45, col), self.box(x + 0.08, y + L - 0.37, zb + 0.08, w - 0.16, 0.32, 0.45, col),
                self.box(x + 0.02, y + 0.12, zb - 0.05, w - 0.04, L - 0.24, 0.12, "steel_black")]
        cab_y0, cab_y1 = y + L * 0.27, y + L * 0.88
        cab = [self._prism([(cab_y0 - 0.45, zb + 0.55), (cab_y0, zb + 1.18), (cab_y1, zb + 1.2), (cab_y1 + 0.3, zb + 0.55)], (x + 0.12, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w - 0.24, col)]
        glass = [self._prism([(cab_y0 - 0.38, zb + 0.6), (cab_y0 + 0.02, zb + 1.12), (cab_y1 - 0.02, zb + 1.14), (cab_y1 + 0.24, zb + 0.6)], (x + 0.1, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w - 0.2, "glass_tinted_grey")]
        glass[0] = self._prism([(cab_y0 - 0.38, zb + 0.6), (cab_y0 + 0.02, zb + 1.12), (cab_y1 - 0.02, zb + 1.14), (cab_y1 + 0.24, zb + 0.6)], (x + 0.13, 0.0, 0.0), (1, 0, 0), (0, 1, 0), w - 0.26, "glass_tinted_grey")
        roof = [self.box(x + 0.16, cab_y0 + 0.05, zb + 1.16, w - 0.32, cab_y1 - cab_y0 - 0.1, 0.05, col)]
        wheels = []
        for wy in (y + L * 0.19, y + L * 0.81):
            for wx in (x + 0.02, x + w - 0.2):
                wheels += [self.cylinder((wx, wy, wr), (wx + 0.18, wy, wr), wr, "paint_black"), self.cylinder((wx - 0.0 + (0.0 if wx < x + w / 2 else 0.18), wy, wr), (wx + (-0.01 if wx < x + w / 2 else 0.19), wy, wr), wr * 0.62, "alu_white")]
        lights = [self.box(x + 0.12, y + 0.02, zb + 0.4, 0.3, 0.04, 0.1, "glass_clear"), self.box(x + w - 0.42, y + 0.02, zb + 0.4, 0.3, 0.04, 0.1, "glass_clear"),
                  self.box(x + 0.12, y + L - 0.06, zb + 0.5, 0.3, 0.04, 0.1, "paint_red_bright"), self.box(x + w - 0.42, y + L - 0.06, zb + 0.5, 0.3, 0.04, 0.1, "paint_red_bright")]
        self._g2(c, "Pkw Karosserie", body + cab + roof, cls="IfcBuildingElementProxy", mat="Lack")
        self._g2(c, "Pkw Verglasung", glass, mat="Glas")
        self._g2(c, "Pkw Räder", wheels, mat="Gummi")
        self._g2(c, "Pkw Leuchten", lights, mat="Glas")

    def _c_garden_bridge(self, c, i, v=None):
        x, y, L, w, m, fr = c["x"], c["y"], c["width"], c["depth"], c["material"], c["frame_material"]
        n = 12
        rise = 0.55
        deck, rail = [], []
        for k in range(n):
            t0, t1 = k / n, (k + 1) / n
            z = rise * math.sin(math.pi * (t0 + t1) / 2) + 0.15
            deck.append(self.box(x + L * t0, y, z - 0.08, L / n + 0.005, w, 0.08, m))
        for yy in (y + 0.04, y + w - 0.08):
            for k in range(n + 1):
                t = k / n
                z = rise * math.sin(math.pi * t) + 0.15
                rail.append(self.box(x + L * t - 0.03 if k < n else x + L - 0.06, yy, z, 0.06, 0.04, 0.9, fr))
            for k in range(n):
                a = rise * math.sin(math.pi * k / n) + 0.15 + 0.9
                b = rise * math.sin(math.pi * (k + 1) / n) + 0.15 + 0.9
                rail.append(self.cylinder((x + L * k / n, yy + 0.02, a), (x + L * (k + 1) / n, yy + 0.02, b), 0.025, fr))
        arches = []
        for yy in (y + 0.1, y + w - 0.14):
            pts = [(x + L * k / n, yy, rise * math.sin(math.pi * k / n) + 0.07) for k in range(n + 1)]
            for a, b in zip(pts, pts[1:]):
                arches.append(self.cylinder(a, b, 0.05, m))
        self._g2(c, "Gartenbrücke", deck + arches, mat="Holz")
        self._g2(c, "Gartenbrücke Geländer", rail, mat="Stahl")
