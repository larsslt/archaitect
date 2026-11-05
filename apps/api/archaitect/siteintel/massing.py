"""Building massing for the studio: one building = up to 12 volumes (main body, annexes, garage, stacked parts), each a rectangle,
a circle or a free polygon with its own storeys and roof. Coordinates are the project's local metric frame (x East, y North, metres).

This is a massing model for planning and rendering, not construction detail: walls have no thickness, roofs are ideal planes,
one building base level (the lowest natural ground under all footprints) is used for all heights.
"""
from __future__ import annotations
import math
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely import affinity
from shapely.geometry.polygon import orient

RoofType = Literal['flach', 'sattel', 'walm', 'pult', 'zelt', 'kegel']
Shape = Literal['rect', 'round', 'poly']
Role = Literal['main', 'annex', 'garage']
ROOF_DE = {'flach': 'Flachdach', 'sattel': 'Satteldach', 'walm': 'Walmdach', 'pult': 'Pultdach', 'zelt': 'Zeltdach', 'kegel': 'Kegeldach'}
ROOFS_BY_SHAPE: dict[str, set[str]] = {'rect': {'flach', 'sattel', 'walm', 'pult', 'zelt'}, 'round': {'flach', 'kegel'}, 'poly': {'flach'}}
PLINTH_M = 0.3            # Sockel: finished floor above ground
MAX_VOLUMES = 12


class Volume(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(default='Baukörper', max_length=60)
    role: Role = 'main'
    shape: Shape = 'rect'
    cx: float = 0.0
    cy: float = 0.0
    width_m: float = Field(default=10.0, gt=0.5, le=120)      # rect: along the rotated x axis; round: diameter
    depth_m: float = Field(default=8.0, gt=0.5, le=120)
    rotation_deg: float = Field(default=0.0, ge=-360, le=360)
    points: list[list[float]] | None = None                     # poly: absolute local ring (open or closed)
    elevation_m: float = Field(default=0.0, ge=0, le=60)       # start above the building base (stacked / cantilevered parts)
    storeys: int = Field(default=2, ge=1, le=12)                # Vollgeschosse of this volume
    storey_height_m: float = Field(default=2.9, ge=2.3, le=6.0)
    roof: RoofType = 'sattel'
    roof_pitch_deg: float = Field(default=35.0, ge=0, le=75)
    ridge_along: Literal['width', 'depth'] = 'width'            # sattel/walm ridge direction; pult rises towards +depth (or +width)
    facade_de: str = Field(default='', max_length=120)          # material/colour hint for rendering ("heller Putz", "Holz", ...)
    roof_material_de: str = Field(default='', max_length=80)

    @model_validator(mode='after')
    def _check(self):
        if self.shape == 'poly':
            if not self.points or len(self.points) < 3:
                raise ValueError('poly braucht mindestens drei Punkte')
            if not Polygon(self.points).is_valid:
                raise ValueError('poly ist kein gültiges (selbstüberschneidungsfreies) Polygon')
        if self.roof not in ROOFS_BY_SHAPE[self.shape]:
            raise ValueError(f'Dach {self.roof} passt nicht zur Form {self.shape}')
        if self.roof == 'flach':
            object.__setattr__(self, 'roof_pitch_deg', 0.0)
        return self

    # ---- geometry
    def footprint(self) -> Polygon:
        if self.shape == 'poly':
            return orient(Polygon(self.points), 1.0)
        if self.shape == 'round':
            return orient(Point(self.cx, self.cy).buffer(self.width_m / 2, 16), 1.0)
        r = Polygon([(-self.width_m / 2, -self.depth_m / 2), (self.width_m / 2, -self.depth_m / 2), (self.width_m / 2, self.depth_m / 2), (-self.width_m / 2, self.depth_m / 2)])
        r = affinity.rotate(r, self.rotation_deg, origin=(0, 0))
        return orient(affinity.translate(r, self.cx, self.cy), 1.0)

    @property
    def eave_m(self) -> float:
        """Wall height above the building base up to the eave (top of the last full storey + plinth), not counting elevation."""
        return PLINTH_M + self.storeys * self.storey_height_m

    def span_m(self) -> float:
        if self.shape == 'round':
            return self.width_m / 2
        if self.shape == 'poly':
            return 0.0
        perp = self.depth_m if self.ridge_along == 'width' else self.width_m
        if self.roof in ('sattel', 'walm'):
            return perp / 2
        if self.roof == 'pult':
            return perp
        if self.roof == 'zelt':
            return min(self.width_m, self.depth_m) / 2
        return 0.0

    @property
    def roof_rise_m(self) -> float:
        if self.roof == 'flach':
            return 0.0
        return math.tan(math.radians(self.roof_pitch_deg)) * self.span_m()

    @property
    def top_m(self) -> float:
        return self.elevation_m + self.eave_m + self.roof_rise_m

    def floor_area_m2(self) -> float:
        return self.footprint().area * self.storeys


class Massing(BaseModel):
    """The design state. ``version`` increments on every saved revision."""
    version: int = Field(default=1, ge=1)
    volumes: list[Volume] = Field(min_length=1, max_length=MAX_VOLUMES)
    demolish: list[str] = []                 # ids of existing on-site buildings assumed demolished
    source: Literal['manual', 'ai', 'suggest', 'initial'] = 'manual'
    prompt_de: str = Field(default='', max_length=4000)
    notes_de: list[str] = []

    @model_validator(mode='after')
    def _ids(self):
        ids = [v.id for v in self.volumes]
        if len(ids) != len(set(ids)):
            raise ValueError('Baukörper-IDs müssen eindeutig sein')
        return self

    def union(self):
        return unary_union([v.footprint() for v in self.volumes])

    def metrics(self) -> dict:
        main = [v for v in self.volumes if v.role != 'garage']
        fp_all = self.union().area
        fp_main = unary_union([v.footprint() for v in main]).area if main else 0.0
        gfa = sum(v.floor_area_m2() for v in main)
        return {'footprint_m2': round(fp_all, 1), 'footprint_main_m2': round(fp_main, 1), 'gross_floor_area_m2': round(gfa, 1),
                'max_storeys': max(effective_storeys(self.volumes).values()), 'top_m': round(max(v.top_m for v in self.volumes), 2), 'volumes': len(self.volumes)}


def default_massing(region: Polygon, living_m2: float | None, storeys: int | None, roof: str | None) -> Massing:
    """First massing: one main volume at the pole of inaccessibility of the region, aligned to its main axis, sized from the programme."""
    from shapely.ops import polylabel
    c = polylabel(region, 0.05)
    xs, ys = region.minimum_rotated_rectangle.exterior.coords.xy
    edges = [(math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]), math.atan2(ys[i + 1] - ys[i], xs[i + 1] - xs[i])) for i in range(4)]
    ang = (math.degrees(max(edges)[1]) + 90) % 180 - 90
    st = max(1, min(storeys or 2, 4))
    fp = max(60.0, min((living_m2 or 140.0) / st * 1.2, region.area * 0.5))
    w = math.sqrt(fp * 1.3)
    d = fp / w
    r = roof if roof in ('flach', 'sattel', 'walm', 'pult', 'zelt') else 'sattel'
    v = Volume(id='v1', name='Haupthaus', cx=round(c.x, 2), cy=round(c.y, 2), width_m=round(w, 1), depth_m=round(d, 1), rotation_deg=round(ang, 1), storeys=st, roof=r, roof_pitch_deg=0 if r == 'flach' else 35)
    for _ in range(80):
        if region.buffer(1e-6).covers(v.footprint()) or min(v.width_m, v.depth_m) < 4:
            break
        v = v.model_copy(update={'width_m': round(v.width_m * 0.95, 2), 'depth_m': round(v.depth_m * 0.95, 2)})
    return Massing(volumes=[v], source='initial')


def support_elevations(vols: list[Volume], notes: list[str]) -> list[Volume]:
    """A raised volume needs something to stand on: its elevation is limited to the eave height of the volumes below it, else it goes to the ground."""
    out = []
    for v in vols:
        if v.elevation_m <= 0:
            out.append(v)
            continue
        fp = v.footprint()
        below = [w for w in vols if w.id != v.id and w.elevation_m < v.elevation_m and w.footprint().intersection(fp).area > 0.25 * fp.area]
        top = max((w.elevation_m + w.eave_m for w in below), default=0.0)
        if top <= 0:
            if v.elevation_m > 1.0:
                notes.append(f'{v.name}: schwebte ohne Unterbau, auf den Boden gesetzt.')
            out.append(v.model_copy(update={'elevation_m': 0.0}))
        elif v.elevation_m > top + 0.01:
            out.append(v.model_copy(update={'elevation_m': round(top, 2)}))
        else:
            out.append(v)
    return out


def effective_storeys(vols: list[Volume]) -> dict[str, int]:
    """Vollgeschosse counted from the ground: a raised volume sitting on others adds its storeys to the highest support below it."""
    order = sorted(vols, key=lambda x: x.elevation_m)
    fps = {v.id: v.footprint() for v in vols}
    eff: dict[str, int] = {}
    for v in order:
        base = 0
        if v.elevation_m > 0.5:
            for w in order:
                if w.id == v.id or w.id not in eff or w.elevation_m >= v.elevation_m:
                    continue
                if fps[w.id].intersection(fps[v.id]).area > 0.05 * fps[v.id].area and w.elevation_m + w.eave_m <= v.elevation_m + 0.6:
                    base = max(base, eff[w.id])
            if base == 0:
                base = int(max(0.0, v.elevation_m - PLINTH_M) // 2.4)      # cantilever / stilts: count the storeys it floats above
        eff[v.id] = base + v.storeys
    return eff
