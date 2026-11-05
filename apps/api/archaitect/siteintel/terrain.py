"""Terrain from the official DGM1 (1 m grid) via INSPIRE WCS 2.0.1, licence DL-DE Zero 2.0.

``read_float_tiff`` is a small dependency-free reader for the uncompressed float32 GeoTIFF the service returns (numpy/GDAL are not
required on the user's machine). Anything else (compressed, tiled, other sample type) is refused with a clear error instead of guessed.
"""
from __future__ import annotations
import math
import struct
from dataclasses import dataclass
from shapely.geometry import Point, Polygon
from shapely.prepared import prep
from .fetch import Fetcher, FetchResult

WCS_URL = 'https://inspire-hessen.de/raster/dgm1/ows'
SOURCE_INFO = 'https://www.geoportal.hessen.de/'
ATTRIBUTION = 'Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation: Digitales Geländemodell (DGM1)'
NODATA = -9999.0
_COMPASS = ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW']


@dataclass
class Grid:
    x0: float          # west edge (EPSG:25832, m)
    y0: float          # north edge
    dx: float
    dy: float
    w: int
    h: int
    z: list[float | None]   # row-major, row 0 = north

    def xy(self, col: int, row: int) -> tuple[float, float]:
        """Centre of a cell."""
        return self.x0 + (col + 0.5) * self.dx, self.y0 - (row + 0.5) * self.dy

    def at(self, col: int, row: int) -> float | None:
        return self.z[row * self.w + col] if 0 <= col < self.w and 0 <= row < self.h else None


def read_float_tiff(b: bytes) -> Grid:
    if b[:2] == b'II':
        e = '<'
    elif b[:2] == b'MM':
        e = '>'
    else:
        raise ValueError('kein TIFF')
    if struct.unpack(e + 'H', b[2:4])[0] != 42:
        raise ValueError('BigTIFF/unbekannt')
    off = struct.unpack(e + 'I', b[4:8])[0]
    n = struct.unpack(e + 'H', b[off:off + 2])[0]
    sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8}
    fmt = {1: 'B', 2: 'c', 3: 'H', 4: 'I', 6: 'b', 8: 'h', 9: 'i', 11: 'f', 12: 'd', 16: 'Q'}
    tags: dict[int, list] = {}
    for i in range(n):
        o = off + 2 + i * 12
        tag, typ, cnt = struct.unpack(e + 'HHI', b[o:o + 8])
        size = sizes.get(typ, 1) * cnt
        voff = o + 8 if size <= 4 else struct.unpack(e + 'I', b[o + 8:o + 12])[0]
        if typ == 5:
            vals = list(struct.unpack(e + f'{2 * cnt}I', b[voff:voff + 8 * cnt]))
        elif typ == 2:
            vals = [b[voff:voff + cnt]]
        else:
            vals = list(struct.unpack(e + f'{cnt}{fmt[typ]}', b[voff:voff + size]))
        tags[tag] = vals
    w, h = tags[256][0], tags[257][0]
    if tags.get(259, [1])[0] != 1 or 322 in tags:
        raise ValueError('komprimiertes oder gekacheltes TIFF wird nicht unterstützt')
    if tags.get(258, [0])[0] != 32 or tags.get(339, [1])[0] != 3 or tags.get(277, [1])[0] != 1:
        raise ValueError('kein float32-Einkanal-Raster')
    offs, cnts = tags[273], tags[279]
    raw = b''.join(b[o:o + c] for o, c in zip(offs, cnts))
    if len(raw) < w * h * 4:
        raise ValueError('Rasterdaten unvollständig')
    z = list(struct.unpack(e + f'{w * h}f', raw[:w * h * 4]))
    scale, tie = tags.get(33550), tags.get(33922)
    if not scale or not tie:
        raise ValueError('keine Georeferenz im TIFF')
    sx, sy = scale[0], scale[1]
    px, py, x, y = tie[0], tie[1], tie[3], tie[4]
    x_west, y_north = x - px * sx, y + py * sy
    # GTRasterTypeGeoKey 2 = PixelIsPoint: the tie point is a cell *centre*, not the corner
    keys = tags.get(34735, [])
    for i in range(4, len(keys) - 3, 4):
        if keys[i] == 1025 and keys[i + 3] == 2:
            x_west -= sx / 2
            y_north += sy / 2
    return Grid(x_west, y_north, sx, sy, w, h, [None if (v == NODATA or math.isnan(v) or v < -1000) else float(v) for v in z])


def get_dgm(fetcher: Fetcher, bbox: tuple[float, float, float, float], timeout: float = 10.0) -> tuple[Grid | None, FetchResult]:
    x0, y0, x1, y1 = (round(v) for v in bbox)
    url = (f'{WCS_URL}?SERVICE=WCS&VERSION=2.0.1&REQUEST=GetCoverage&COVERAGEID=he_dgm1&FORMAT=image/tiff'
           f'&SUBSET=E({x0},{x1})&SUBSET=N({y0},{y1})')
    res = fetcher.get('hessen-dgm1', url, {}, 90 * 86400, timeout, lambda b: b[:2] in (b'II', b'MM'))
    if res.body is None:
        return None, res
    try:
        return read_float_tiff(res.body), res
    except (ValueError, struct.error) as exc:
        res.error = str(exc)
        return None, res


def summarize(g: Grid, parcel_m: Polygon) -> dict:
    """Height statistics, slope and aspect over the parcel (cells whose centre lies inside), from central differences on the 1 m grid."""
    pp = prep(parcel_m)
    zs: list[float] = []
    slopes: list[float] = []
    ax = ay = 0.0
    for r in range(g.h):
        for c in range(g.w):
            z = g.at(c, r)
            if z is None or not pp.contains(Point(*g.xy(c, r))):
                continue
            zs.append(z)
            zl, zr, zu, zd = g.at(c - 1, r), g.at(c + 1, r), g.at(c, r - 1), g.at(c, r + 1)
            if None in (zl, zr, zu, zd):
                continue
            dzdx = (zr - zl) / (2 * g.dx)
            dzdy = (zu - zd) / (2 * g.dy)          # row 0 is north: up = +y
            slopes.append(math.hypot(dzdx, dzdy))
            ax -= dzdx
            ay -= dzdy                              # downslope direction
    if not zs:
        return {'cells': 0}
    mean_slope = sum(slopes) / len(slopes) if slopes else 0.0
    out = {'cells': len(zs), 'z_min_m': round(min(zs), 2), 'z_max_m': round(max(zs), 2), 'z_mean_m': round(sum(zs) / len(zs), 2), 'relief_m': round(max(zs) - min(zs), 2),
           'slope_mean_pct': round(mean_slope * 100, 1), 'slope_max_pct': round(max(slopes) * 100, 1) if slopes else None, 'height_reference': 'DHHN2016 (NHN), m'}
    if math.hypot(ax, ay) > 1e-6 and mean_slope > 0.01:
        bearing = (math.degrees(math.atan2(ax, ay)) + 360) % 360
        out['downslope_bearing_deg'] = round(bearing, 0)
        out['downslope_compass'] = _COMPASS[int((bearing + 22.5) // 45) % 8]
    else:
        out['downslope_compass'] = None
    return out


def downsample(g: Grid, max_side: int = 128) -> dict:
    step = max(1, math.ceil(max(g.w, g.h) / max_side))
    rows = []
    for r in range(0, g.h, step):
        rows.append([None if (v := g.at(c, r)) is None else round(v, 2) for c in range(0, g.w, step)])
    return {'x_west': g.x0, 'y_north': g.y0, 'cell_m': g.dx * step, 'cols': len(rows[0]) if rows else 0, 'rows': len(rows), 'row0_is_north': True, 'heights_m': rows}
