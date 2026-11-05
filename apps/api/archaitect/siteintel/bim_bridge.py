"""Bridge between the BIM building spec (archaitect.bim) and the plot rules (regs.py).

The spec lives in its own frame (origin near the house, floor level 0, axis-aligned volumes). ``spec["site"]["placement"]`` = {x, y, rotation_deg}
puts it on the plot (site frame of the site pack). For the rule check every spec volume becomes a ``massing.Volume`` in the site frame, so the
existing verified rule engine (GRZ/GFZ, Baufenster, Abstandsflächen, Höhen, Dachform) judges the same building that is rendered.
Anything the massing cannot express is listed in the notes; missing law inputs stay UNKNOWN in ``regs.evaluate``.
"""
from __future__ import annotations

import math
import re

from shapely import affinity
from shapely.geometry import Polygon, box, Point
from shapely.ops import polylabel, unary_union

from ..bim.terrain import Placement
from .massing import MAX_VOLUMES, Massing, Volume
from .regs import evaluate, limits

_ROOF = {"flat": "flach", "gable": "sattel", "hip": "walm", "shed": "pult", "mansard": "sattel", "gambrel": "sattel", "sawtooth": "flach"}
_GARAGE_WORDS = ("garage", "carport", "stellplatz")
EPS = 0.02


def _vol_poly(v: dict) -> Polygon:
    ox, oy = v["origin"]
    return box(ox, oy, ox + v["size"][0], oy + v["size"][1])


def spec_to_massing(spec: dict) -> tuple[Massing | None, list[str]]:
    """Massing in the SITE frame from the spec's volumes (with the spec's placement)."""
    notes: list[str] = []
    pl = Placement.from_spec(spec)
    vols = [v for v in spec.get("volumes", []) if not v.get("hidden")]
    if not vols:
        return None, ["Keine Baukörper im Entwurf."]
    vols = sorted(vols, key=lambda v: -v["size"][0] * v["size"][1])
    if len(vols) > MAX_VOLUMES:
        notes.append(f"{len(vols)} Baukörper: für die Regelprüfung werden die {MAX_VOLUMES} größten gezählt.")
        vols = vols[:MAX_VOLUMES]
    default_h = float(spec.get("storey_height", 3.0))
    out: list[Volume] = []
    for i, v in enumerate(vols):
        r = v.get("roof") or {}
        rt = _ROOF.get(r.get("type", "flat"), "flach")
        if r.get("type") in ("mansard", "gambrel", "sawtooth"):
            notes.append(f"{v.get('name', v['id'])}: Dachform {r['type']} wird für die Regelprüfung als {'Flachdach' if rt == 'flach' else 'Satteldach'} gerechnet.")
        name = v.get("name") or v["id"]
        role = "garage" if any(w in name.lower() for w in _GARAGE_WORDS) else ("main" if i == 0 else "annex")
        cx, cy = v["origin"][0] + v["size"][0] / 2, v["origin"][1] + v["size"][1] / 2
        sx, sy = pl.to_site(cx, cy)
        ridge = r.get("ridge", "x")
        out.append(Volume(id=str(v["id"])[:40], name=str(name)[:60], role=role, shape="rect", cx=round(sx, 3), cy=round(sy, 3),
                          width_m=max(0.6, float(v["size"][0])), depth_m=max(0.6, float(v["size"][1])), rotation_deg=pl.rotation_deg % 360,
                          elevation_m=min(60.0, max(0.0, float(v.get("base_z", 0.0)))), storeys=max(1, min(12, int(v.get("storeys", 1)))),
                          storey_height_m=max(2.3, min(6.0, float(v.get("storey_height", default_h)))), roof=rt,
                          roof_pitch_deg=0.0 if rt == "flach" else max(3.0, min(75.0, float(r.get("pitch_deg", 35.0)))),
                          ridge_along="width" if ridge == "x" else "depth"))
    site = spec.get("site") if isinstance(spec.get("site"), dict) else {}
    demolish = [str(i) for i in (site.get("demolish") or []) if isinstance(i, (str, int))]       # only set when the user explicitly asked for demolition
    return Massing(volumes=out, source="manual", demolish=demolish, prompt_de=(spec.get("name") or "")[:200], notes_de=notes), notes


def footprint_from_parts(parts: list[dict]):
    """Ground-plan union (spec frame) of everything the model contains except the terrain: walls, roof overhangs, carport, terrace, steps, garden elements.
    The volume massing alone misses those, so they could leave the plot unnoticed."""
    import numpy as np
    import shapely
    tris = []
    for p in parts:
        if p.get("name") == "terrain" or not p.get("indices"):
            continue
        P = np.asarray(p["positions"], float).reshape(-1, 3)[:, :2]
        I = np.asarray(p["indices"], int).reshape(-1, 3)
        t = P[I]
        a2 = np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
        tris.append(t[a2 > 1e-6])
    if not tris:
        return None
    t = np.concatenate(tris)
    polys = shapely.polygons(np.concatenate([t, t[:, :1]], axis=1))
    return shapely.union_all(shapely.buffer(polys, 0.005)).simplify(0.02)


_DEMOLISH = re.compile(r"abriss|abriß|abreiß|abgerissen|abgebrochen|abbruch|abbrechen|rückbau|niederreiß|niedergerissen", re.I)
_NEGATION = re.compile(r"\b(kein|keine|keinen|keinem|ohne|nicht|nie|niemals)\b", re.I)


def wants_demolition(*texts: str | None) -> bool:
    """True only if the user explicitly asks for demolition of the existing buildings (and does not negate it). Never assumed otherwise."""
    for t in texts:
        for m in _DEMOLISH.finditer(t or ""):
            if not _NEGATION.search((t or "")[max(0, m.start() - 30):m.start()]):
                return True
    return False


GARDEN_COMPONENTS = {"tree", "hedge", "shrub", "flowerbed", "path", "pool", "pond", "lake", "bench", "garden_set", "garden_light", "parking", "fence", "lamp", "sign"}


def built_parts(parts: list[dict], spec: dict) -> list[dict]:
    """Parts that are buildings or built attachments (terrace, canopy, carport, steps ...). Garden elements (pond, path, hedge, trees, parking ...) are left out:
    they may not block the placement of the house, they are only reported (PARCEL_EXTRAS) when they leave the plot."""
    comps = spec.get("components") or []
    out = []
    for p in parts:
        obj = str(p.get("obj") or "")
        if obj.startswith("comp."):
            try:
                if str(comps[int(obj.split(".", 1)[1])].get("type")) in GARDEN_COMPONENTS:
                    continue
            except (ValueError, IndexError, AttributeError):
                pass
        out.append(p)
    return out


def extras_result(spec: dict, ctx, footprint) -> dict | None:
    """Result row: does the complete model footprint stay inside the plot? (Complements the PARCEL rule, which only sees the volumes.)"""
    if footprint is None or footprint.is_empty:
        return None
    fp = affinity.rotate(footprint, Placement.from_spec(spec).rotation_deg, origin=(0, 0))
    pl = Placement.from_spec(spec)
    fp = affinity.translate(fp, pl.x, pl.y)
    out = fp.difference(ctx.site.buffer(0.05)).area
    base = {"id": "PARCEL_EXTRAS", "label_de": "Anbauten & Überstände im Flurstück", "basis": "PARCEL_GEOMETRY", "hard": False,
            "source_de": "Gebäudemodell (Grundriss aller Bauteile) gegen ALKIS-Flurstück", "observed": round(out, 2), "limit": 0}
    if out > 0.1:
        return {**base, "status": "WARN", "message_de": f"{out:.1f} m² von Anbauten, Dachüberständen oder Gartenelementen (z. B. Carport, Terrasse, Treppe) ragen über die Flurstücksgrenze. "
                "Bauteil verkleinern oder Haus verschieben."}
    return {**base, "status": "PASS", "message_de": "Auch Anbauten, Dachüberstände und Gartenelemente liegen im Flurstück."}


def check_spec(spec: dict, ctx, footprint=None) -> dict:
    """Rule check of the placed spec. The result has the same shape as ``regs.evaluate`` plus ``bim_notes_de``.
    ``footprint`` (optional, spec frame) = plan of the whole model, see ``footprint_from_parts``."""
    m, notes = spec_to_massing(spec)
    if m is None:
        return {"results": [], "hard_ok": True, "bim_notes_de": notes, "status": "NO_BUILDING"}
    res = evaluate(m, ctx)
    res["bim_notes_de"] = notes
    res["limits"] = limits(m, ctx)
    extra = extras_result(spec, ctx, footprint)
    if extra:
        res["results"] = [*res["results"], extra]
        if extra["status"] == "WARN" and res.get("overall") == "PASS":
            res["overall"] = "WARN"
    return res


def _ground_footprint(spec: dict) -> Polygon | None:
    vols = spec.get("volumes", [])
    lo = min((float(v.get("base_z", 0.0)) for v in vols), default=0.0)
    polys = [_vol_poly(v) for v in vols if float(v.get("base_z", 0.0)) <= max(0.5, lo + 0.5)]      # incl. a raised ground floor (Hochparterre, entrance steps)
    polys += [box(c["origin"][0], c["origin"][1], c["origin"][0] + c["size"][0], c["origin"][1] + c["size"][1]) for c in spec.get("curtain_walls", [])]
    return unary_union(polys) if polys else None


def _rect_dims(g) -> tuple[float, float]:
    xs, ys = g.minimum_rotated_rectangle.exterior.coords.xy
    return math.hypot(xs[1] - xs[0], ys[1] - ys[0]), math.hypot(xs[2] - xs[1], ys[2] - ys[1])


def place_spec(spec: dict, ctx, keep_rotation: bool = False, best_effort: bool = False, footprint: Polygon | None = None) -> tuple[Placement | None, list[str]]:
    """Find a placement inside the hard region (plot, Baufenster, minus kept existing buildings), close to its pole of inaccessibility.
    Tries the region's main axis and the cardinal axes; returns (None, notes) if the building cannot fit without being resized."""
    notes: list[str] = []
    fp = footprint if footprint is not None and not footprint.is_empty else _ground_footprint(spec)   # footprint incl. terrace/columns/canopy when given
    m, _ = spec_to_massing(spec)
    if fp is None or m is None:
        return None, ["Kein Baukörper zum Platzieren."]
    region = ctx.hard_region(m)
    if region.is_empty:
        return None, ["Keine geometrisch freie Fläche auf dem Grundstück. Bauvorgaben bleiben zusätzlich zu prüfen."]
    pole_region = max(region.geoms, key=lambda g: g.area) if hasattr(region, "geoms") else region
    c0 = fp.centroid
    fp0 = affinity.translate(fp, -c0.x, -c0.y)                      # footprint around its own centre
    pole = polylabel(pole_region, 0.1)
    xs, ys = region.minimum_rotated_rectangle.exterior.coords.xy
    edge = max(((math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]), math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i])) for i in range(4)))[1]
    main = math.degrees(edge) % 90
    cur = Placement.from_spec(spec).rotation_deg
    cands = [cur] if keep_rotation else [cur, main, (main + 90) % 360, 0.0, 90.0]
    roads = [r for r in getattr(ctx, 'roads', []) if r.distance(ctx.site) <= 1.0]
    entrances = [o for o in spec.get('openings', []) if o.get('kind') == 'door' and int(o.get('storey', 0)) == 0 and o.get('side') in ('N','S','E','W')
                 and o.get('door_type', 'panel') in ('panel','double')]
    def _on_balcony(o):      # a door that opens onto a balcony / terrace is never the front door
        return any(x.get('volume') == o.get('volume') and x.get('side') == o.get('side') and float(x.get('offset', 0)) < float(o['offset']) + float(o['width']) and float(o['offset']) < float(x.get('offset', 0)) + float(x.get('width', 0)) for x in spec.get('balconies', []))
    entrances = [o for o in entrances if not _on_balcony(o)]
    entrance = entrances[0] if len(entrances) == 1 and roads else None
    vol = next((v for v in spec.get('volumes', []) if entrance and v['id'] == entrance.get('volume')), None)
    if entrance and vol and not keep_rotation:
        cands = list(dict.fromkeys([*cands, (cur + 180) % 360, (main + 180) % 360, (main + 270) % 360, 180.0, 270.0]))
    else:
        entrance = None
    def candidate(x, y, rot):
        a = math.radians(rot)
        return Placement(round(x - (math.cos(a) * c0.x - math.sin(a) * c0.y), 3), round(y - (math.sin(a) * c0.x + math.cos(a) * c0.y), 3), round(float(rot), 2))
    def road_penalty(pl):
        if entrance is None or vol is None:return 0.0
        from ..bim.geom import facade_xy
        u = float(entrance['offset']) + float(entrance['width']) / 2
        def world(depth):
            x, y = facade_xy(entrance['side'], *vol['origin'], *vol['size'], u, depth)
            a = math.radians(pl.rotation_deg)
            return Point(pl.x + x * math.cos(a) - y * math.sin(a), pl.y + x * math.sin(a) + y * math.cos(a))
        door, outside = world(0), world(-1)
        road = min(roads, key=lambda r:r.distance(door))
        return 0.25 * road.distance(door) + (6.0 if road.distance(outside) >= road.distance(door) else 0.0)
    best: tuple[float, Placement] | None = None
    minx, miny, maxx, maxy = region.bounds
    step = 1.0
    reg = region.buffer(EPS)
    for rot in cands:
        shape = affinity.rotate(fp0, rot, origin=(0, 0))
        y = miny
        while y <= maxy:
            x = minx
            while x <= maxx:
                if reg.covers(affinity.translate(shape, x, y)):
                    pl = candidate(x, y, rot)
                    d = math.hypot(x - pole.x, y - pole.y) + (0.0 if rot == cur else 0.5) + road_penalty(pl)
                    if best is None or d < best[0]:
                        best = (d, pl)
                x += step
            y += step
        if best is not None and rot == cur and entrance is None:
            break
    if best is None and not keep_rotation:
        # second pass: every 10 degrees, finer grid - an oblique plot often takes the house only at an angle
        for rot in range(0, 360 if entrance is not None else 180, 10):
            shape = affinity.rotate(fp0, rot, origin=(0, 0))
            y = miny
            while y <= maxy:
                x = minx
                while x <= maxx:
                    if reg.covers(affinity.translate(shape, x, y)):
                        pl = candidate(x, y, rot)
                        d = math.hypot(x - pole.x, y - pole.y) + 0.5 + road_penalty(pl)
                        if best is None or d < best[0]:
                            best = (d, pl)
                    x += 0.5
                y += 0.5
    if best is None and best_effort:
        # nothing fits entirely: still place it - where it leaves the buildable region the least (never at an arbitrary default, never crooked)
        part: tuple[float, Placement] | None = None
        for rot in [main, (main + 90) % 360, *range(0, 180, 15)]:
            shape = affinity.rotate(fp0, rot, origin=(0, 0))
            for yy in range(int(miny), int(maxy) + 1):
                for xx in range(int(minx), int(maxx) + 1):
                    over = (affinity.translate(shape, xx, yy).difference(reg).area + 0.02 * math.hypot(xx - pole.x, yy - pole.y)
                            + (0.0 if abs((rot - main) % 90) < 0.01 else 4.0))      # square to the plot unless that costs real overhang
                    if part is None or over < part[0]:
                        a = math.radians(rot)
                        part = (over, Placement(round(xx - (math.cos(a) * c0.x - math.sin(a) * c0.y), 3), round(yy - (math.sin(a) * c0.x + math.cos(a) * c0.y), 3), round(float(rot), 2)))
        w, d = sorted(_rect_dims(fp))
        rw, rd = sorted(_rect_dims(region))
        msg = (f"Das Haus (Grundfläche {fp.area:.0f} m², etwa {w:.0f} × {d:.0f} m) passt nicht ganz in den bebaubaren Bereich "
               f"({region.area:.0f} m², etwa {rw:.0f} × {rd:.0f} m nach Abzug von Grenze, Baufenster und Bestand). Ich habe es dort platziert, wo es am wenigsten übersteht (rot markiert); "
               "schreibe z. B. „kompakter, höchstens {:.0f} m²“ oder wähle ein größeres Flurstück.".format(region.area * 0.7))
        return (part[1] if part else None), [msg]
    if best is None:
        w, d = sorted(_rect_dims(fp))
        rw, rd = sorted(_rect_dims(region))
        return None, [f"Für das Haus (Grundfläche {fp.area:.0f} m², etwa {w:.0f} × {d:.0f} m) wurde auf dem Suchraster kein passender Standort in der geometrisch freien Fläche gefunden "
                      f"({region.area:.0f} m², etwa {rw:.0f} × {rd:.0f} m nach Abzug von Bestand und gegebenenfalls einem eingetragenen Baufenster). "
                      "Versuche einen kompakteren Entwurf; ein Bestandsgebäude lässt sich in den Projektdaten als Abriss annehmen, wenn dies tatsächlich vorgesehen ist." ]
    notes.append("Haus geometrisch auf die freie Fläche gesetzt; baurechtliche Prüfung bleibt offen." if best[1] != Placement.from_spec(spec) else "Position unverändert.")
    if entrance is not None:notes.append('Eingang anhand angrenzender Straßenfläche näherungsweise ausgerichtet; Zufahrt und Adresse sind nicht bestätigt.')
    return best[1], notes


def refine_for_extras(spec: dict, ctx, footprint, pl: Placement, radius: float = 8.0, step: float = 0.5) -> tuple[Placement, str | None]:
    """Shift a valid placement (same rotation) so that the whole model - carport, terrace, roof overhang - leaves the plot as little as possible,
    while the volumes stay inside the hard region. Returns the (possibly unchanged) placement and a note."""
    m, _ = spec_to_massing(spec)
    base = _ground_footprint(spec)
    if footprint is None or footprint.is_empty or m is None or base is None:
        return pl, None
    region = ctx.hard_region(m).buffer(EPS)
    site = ctx.site.buffer(0.05)
    existing = unary_union([e.poly for e in ctx.kept(m)]) if hasattr(ctx, 'kept') and ctx.kept(m) else None

    def at(p: Placement, g):
        return affinity.translate(affinity.rotate(g, p.rotation_deg, origin=(0, 0)), p.x, p.y)

    def conflicts(p: Placement) -> tuple[float, float]:
        placed = at(p, footprint)
        return placed.difference(site).area, placed.intersection(existing).area if existing is not None else 0.0

    out, overlap = conflicts(pl)
    if out <= 0.1 and overlap <= 0.05:
        return pl, None
    best, best_s = pl, out + overlap
    n = int(radius / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            p = Placement(round(pl.x + i * step, 3), round(pl.y + j * step, 3), pl.rotation_deg)
            if not region.covers(at(p, base)):
                continue
            outside, collision = conflicts(p)
            s = outside + collision + 0.002 * math.hypot(i, j) * step
            if s < best_s:
                best, best_s = p, s
    if best is pl:
        return pl, "Für Anbauten wurde auf dem Suchraster keine konfliktfreie Verschiebung gefunden."
    outside, collision = conflicts(best)
    return best, ("Haus samt Anbauten verschoben, damit sie im Flurstück und außerhalb des Bestands liegen." if outside <= 0.1 and collision <= 0.05
                  else f"Haus verschoben; {outside + collision:.1f} m² Bauteile liegen weiterhin außerhalb oder im Bestand.")
