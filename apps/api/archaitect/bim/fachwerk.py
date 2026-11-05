"""Systematic timber-frame (Fachwerk) planner for one wall of one storey.

Rules (checked against construction references: Schwelle, Ständer/Eckständer/Türständer, Riegel closing openings, Fuß-/Kopfstreben
of about one third of the field, Andreaskreuz in Brüstungsgefachen, Rähm; hausjournal.net/fachwerk-bezeichnungen):
  1. Corner posts (Eckständer, 1.4x wider) at both wall ends.
  2. Every opening is flanked by two full-height posts (Ständer) directly at its jambs, so windows and doors always sit
     *between* posts and never behind a beam.
  3. Plain wall fields (no opening) are divided by additional posts into bays no wider than ~1.25x the target spacing.
  4. Every opening gets a lintel (Sturzriegel) and, for windows, a parapet rail (Brüstungsriegel) between its posts.
     A door gets a heavier lintel and no parapet.
  5. Every plain bay gets bracing from the chosen pattern (K-Strebe, Andreaskreuz, Mann, Fuß-/Kopfband, Raute); the field
     under a window gets a Andreaskreuz.
  6. ``validate`` checks the result: nothing outside the wall field, nothing across an opening, no unbraced plain field.

All coordinates are (u, z): u along the wall, z absolute. Pure functions, no IFC dependency, fully unit-testable.
"""
from __future__ import annotations

import math
import random

Rect = list[tuple[float, float]]
EPS = 1e-6


def rect(u0: float, u1: float, z0: float, z1: float) -> Rect:
    return [(u0, z0), (u1, z0), (u1, z1), (u0, z1)]


def seg(p0, p1, w: float) -> Rect:
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    n = math.hypot(dx, dz)
    if n < 1e-6:
        raise ValueError("zero length")
    nx, nz = -dz / n * w / 2, dx / n * w / 2
    return [(p0[0] + nx, p0[1] + nz), (p1[0] + nx, p1[1] + nz), (p1[0] - nx, p1[1] - nz), (p0[0] - nx, p0[1] - nz)]


def _merge(iv: list[list[float]], gap: float = 0.12) -> list[list[float]]:
    iv = sorted([list(x) for x in iv])
    out: list[list[float]] = []
    for a, b in iv:
        if out and a - out[-1][1] < gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _curve(p0, p1, bulge: float, w: float, n: int = 7):
    """Swept brace (Schweifstrebe): a quadratic arc from p0 to p1 whose middle is pushed sideways by ``bulge`` metres, as n overlapping beam pieces."""
    import math as _m
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    ln = _m.hypot(dx, dz) or 1.0
    nx, nz = -dz / ln, dx / ln
    pts = []
    for k in range(n + 1):
        t = k / n
        off = 4 * bulge * t * (1 - t)
        pts.append((p0[0] + dx * t + nx * off, p0[1] + dz * t + nz * off))
    return [seg(pts[k], pts[k + 1], w) for k in range(n)]


def _knees(a, b, zlo, zhi, L1):
    """Fuß-/Kopfbänder: jedes Band verbindet einen Ständer mit einem Riegel (beide Enden liegen auf Holz, nichts endet frei im Gefach)."""
    return [((a, zlo + L1), (a + L1, zlo)), ((b, zlo + L1), (b - L1, zlo)), ((a, zhi - L1), (a + L1, zhi)), ((b, zhi - L1), (b - L1, zhi))]


def plan_wall(L: float, zlo: float, zhi: float, ops, spacing: float = 1.2, bw: float = 0.14, pattern: str = "k_brace"):
    """Return (polys, posts, bays).

    ``ops``: iterable of (u0, u1, zb, zt, is_door). ``posts``: merged [u0, u1] intervals. ``bays``: (a, b, opening_or_None)."""
    ops = sorted((float(o[0]), float(o[1]), float(o[2]), float(o[3]), bool(o[4]) if len(o) > 4 else False) for o in ops)
    ops = [o for o in ops if o[1] > 0 and o[0] < L]
    ew = bw * 1.4
    iv = [[0.0, ew], [L - ew, L]]
    for o0, o1, *_ in ops:
        iv += [[max(0.0, o0 - bw), o0], [o1, min(L, o1 + bw)]]
    posts = _merge(iv)

    def opening_in(a: float, b: float):
        for o in ops:
            if o[0] >= a - 0.02 and o[1] <= b + 0.02:
                return o
        return None

    # split wide plain fields
    final: list[list[float]] = [posts[0]]
    for nxt in posts[1:]:
        a, b = final[-1][1], nxt[0]
        if b - a > 0.0 and opening_in(a, b) is None and b - a > spacing * 1.25:
            nb = max(2, round((b - a) / spacing))
            for k in range(1, nb):
                c = a + (b - a) * k / nb
                final.append([c - bw / 2, c + bw / 2])
        final.append(nxt)
    posts = final

    polys: list[Rect] = [rect(a, b, zlo, zhi) for a, b in posts if zhi - zlo > 0.3]
    bays = []
    for i in range(len(posts) - 1):
        a, b = posts[i][1], posts[i + 1][0]
        if b - a < 0.05:
            continue
        o = opening_in(a, b)
        bays.append((a, b, o))
        if o is not None:
            o0, o1, zb, zt, door = o
            lt = 0.2 if door else 0.16
            if zt + lt <= zhi:
                polys.append(rect(a, b, zt, zt + lt))
            if not door and zb - 0.16 >= zlo:
                polys.append(rect(a, b, zb - 0.16, zb))
                if pattern != "none" and zb - 0.16 - zlo >= 0.3 and b - a >= 0.5:      # field below the window: Andreaskreuz
                    for p0, p1 in (((a, zlo), (b, zb - 0.16)), ((b, zlo), (a, zb - 0.16))):
                        polys.append(seg(p0, p1, 0.1))
            continue
        if pattern == "none" or b - a < 0.3:
            continue
        sw, mid, zm = 0.13, (a + b) / 2, (zlo + zhi) / 2
        k = i
        if pattern == "mixed":       # Reichtum historischer Gefache: je Gefach ein anderes, aber stimmiges Strebenbild (deterministisch gewürfelt)
            hh = zhi - zlo
            square = 0.45 * hh <= b - a <= 1.35 * hh
            # Nach historischem Vorbild gesetzt statt gewürfelt: symmetrisch zur Wandmitte (gleiche Figur links und rechts, gespiegelt),
            # Eckfeld = Fußstrebe zur Wandmitte, danach ein fester Rhythmus, der je Geschoss um ein Feld verschoben ist.
            nb = len(posts) - 1
            d = min(i, nb - 1 - i)
            sto = int(round(zlo / 2.8))
            if b - a <= 0.55:
                pat = "k_brace"
            elif d == 0:
                pat = "k_brace"
            else:
                pat = ("man", "foot_head", "curved", "k_brace")[(d + sto) % 4] if square or (d + sto) % 4 != 0 else "foot_head"
            if pat == "curved":
                L1 = min(0.95, (b - a) * 0.5, hh * 0.45)
                for (p0, p1), sg in zip(_knees(a, b, zlo, zhi, L1), (1, -1, -1, 1)):
                    polys.extend(_curve(p0, p1, 0.12 * sg, sw))
                continue
            if pat == "k_brace":
                segs = [((a, zlo), (b, zhi))] if mid < L / 2 else [((b, zlo), (a, zhi))]
                if not square:
                    L1 = min(0.75, (b - a) * 0.45, hh * 0.4)
                    segs = _knees(a, b, zlo, zhi, L1)
            elif pat == "st_andrew":
                segs = [((a, zlo), (b, zhi)), ((b, zlo), (a, zhi))]
            elif pat == "man":      # Mann: Zwischenständer, an den zwei Streben von den unteren Ständerfüßen anlaufen
                polys.append(rect(mid - bw / 2, mid + bw / 2, zlo, zhi))
                segs = [((a, zlo), (mid - bw / 2, zlo + hh * 0.62)), ((b, zlo), (mid + bw / 2, zlo + hh * 0.62))]
            else:
                L1 = min(0.75, (b - a) * 0.45, hh * 0.4)
                segs = _knees(a, b, zlo, zhi, L1)
            for p0, p1 in segs:
                polys.append(seg(p0, p1, sw))
            continue
        if pattern == "k_brace":
            # Strebe steigt von den Eckständern zur Wandmitte (symmetrisch zur Wand, wie bei Fuß-/Kopfstreben üblich)
            # nur bei annähernd quadratigen Gefachen eine durchgehende Strebe; sehr breite/schmale Felder bekommen gleichmäßige 45°-Fuß-/Kopfstreben,
            # sonst wechseln Neigungen von Feld zu Feld und die Wand wirkt zufällig
            hh = zhi - zlo
            if 0.45 * hh <= b - a <= 1.35 * hh:
                segs = [((a, zlo), (b, zhi))] if mid < L / 2 else [((b, zlo), (a, zhi))]
            else:
                L1 = min(0.75, (b - a) * 0.45, hh * 0.4)
                segs = _knees(a, b, zlo, zhi, L1)
        elif pattern == "st_andrew":
            segs = [((a, zlo), (b, zhi)), ((b, zlo), (a, zhi))]
        elif pattern == "man":
            polys.append(rect(mid - bw / 2, mid + bw / 2, zlo, zhi))
            segs = [((a, zlo), (mid - bw / 2, zlo + (zhi - zlo) * 0.62)), ((b, zlo), (mid + bw / 2, zlo + (zhi - zlo) * 0.62))]
        elif pattern == "foot_head":
            L1 = min(0.75, (b - a) * 0.45, (zhi - zlo) * 0.4)
            segs = _knees(a, b, zlo, zhi, L1)
        elif pattern == "diamond":
            segs = [((a, zm), (mid, zlo)), ((mid, zlo), (b, zm)), ((b, zm), (mid, zhi)), ((mid, zhi), (a, zm))]
        else:
            segs = []
        for p0, p1 in segs:
            polys.append(seg(p0, p1, sw))
    return polys, posts, bays


def validate(L: float, zlo: float, zhi: float, ops, polys, bays, pattern: str = "foot_head") -> list[str]:
    """Problems of a planned wall; an empty list means: members stay in the field, none cross an opening, no plain field is bare."""
    from shapely.geometry import Polygon, box
    issues: list[str] = []
    field = box(-0.01, zlo - 0.01, L + 0.01, zhi + 0.01)
    holes = [box(o[0] + 0.01, o[2] + 0.01, o[1] - 0.01, o[3] - 0.01) for o in ops]
    for k, p in enumerate(polys):
        pg = Polygon(p)
        if not field.buffer(0.08).contains(pg):
            issues.append(f"Balken {k} liegt außerhalb des Wandfelds")
        for h in holes:
            if pg.intersection(h).area > 1e-4:
                issues.append(f"Balken {k} läuft durch eine Öffnung")
    if pattern != "none":
        diag = [Polygon(p) for p in polys if len({round(x, 3) for x, _ in p}) > 2 and len({round(z, 3) for _, z in p}) > 2]
        for a, b, o in bays:
            if o is None and b - a >= 0.3 and not any(d.centroid.x > a - 1e-3 and d.centroid.x < b + 1e-3 for d in diag):
                issues.append(f"Gefach {a:.2f}-{b:.2f} ohne Strebe")
    return issues


def _clip(polys, keep, holes):
    """Clip every member to the allowed area and cut openings out; returns plain point lists (largest piece when a member splits)."""
    from shapely.geometry import Polygon
    out = []
    for p in polys:
        g = Polygon(p).intersection(keep)
        for h in holes:
            g = g.difference(h)
        if g.is_empty:
            continue
        parts = [g] if g.geom_type == "Polygon" else [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]
        for q in parts:
            if q.area > 4e-3 and min(q.bounds[2] - q.bounds[0], q.bounds[3] - q.bounds[1]) > 0.025:
                out.append(list(q.exterior.coords)[:-1])
    return out


def plan_gable(L: float, z0: float, rise: float, ops, spacing: float = 1.2, bw: float = 0.14, pattern: str = "k_brace"):
    """Timber frame of a gable triangle (Giebeldreieck) of width L, eaves at z0, ridge at z0 + rise: posts, a Spannriegel at about a third of the
    height, braces rising to the middle, window frames. Every member is clipped to the triangle and never crosses an opening."""
    from shapely.geometry import Polygon, box
    if rise < 0.9 or L < 1.5:
        return []
    ops = [(float(o[0]), float(o[1]), float(o[2]), float(o[3]), bool(o[4]) if len(o) > 4 else False) for o in ops]
    base, _posts, bays = plan_wall(L, z0, z0 + rise, ops, spacing, bw, "none")      # posts + lintel/parapet rails, no braces
    tri = Polygon([(0.0, z0), (L, z0), (L / 2, z0 + rise)])
    keep = tri.buffer(-0.03)
    zr = z0 + rise * 0.36
    polys = list(base)
    polys.append(rect(0.0, L, zr, zr + 0.14))                                         # Spannriegel
    if pattern != "none":
        for a, b, o in bays:
            if o is not None or b - a < 0.45:
                continue
            mid = (a + b) / 2
            lo = (((a, z0), (b, zr)) if mid < L / 2 else ((b, z0), (a, zr)))
            polys.append(seg(lo[0], lo[1], 0.13))
            hi = rise * (1 - abs(2 * mid / L - 1))                                   # roof height at the bay centre
            if hi > rise * 0.36 + 0.7:
                up = (((a, zr + 0.14), (b, min(z0 + hi - 0.2, zr + 0.14 + (b - a)))) if mid < L / 2
                      else ((b, zr + 0.14), (a, min(z0 + hi - 0.2, zr + 0.14 + (b - a)))))
                polys.append(seg(up[0], up[1], 0.12))
    holes = [box(o[0] - 0.02, o[2] - 0.02, o[1] + 0.02, o[3] + 0.02) for o in ops]
    # the window frames of plan_wall touch the openings by design: only cut what really runs through
    holes = [h.buffer(-0.03) for h in holes]
    return _clip(polys, keep, holes)
