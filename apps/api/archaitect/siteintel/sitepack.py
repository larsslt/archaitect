"""Site pack: everything a later renderer / generator needs about the plot, georeferenced and with provenance.

One pack per parcel = JSON manifest (+ orthophoto as a separate file):
- local metric frame: origin = parcel centroid (EPSG:25832, rounded to mm), x = East, y = North, z = up. All geometry is given in this frame.
- ortho: official 20 cm aerial image of parcel + margin (exact bbox, pixel size, world file)
- terrain: DGM1 1 m heights (bare earth, no buildings) + slope/aspect over the parcel
- parcels (neighbour boundaries), buildings (footprints, floors; heights only as flagged estimates), official land use polygons
- orientation: true north offset (grid convergence), latitude/longitude for sun studies
- street frontage hint (nearest road land use), utilities section (states honestly that line data is not open data)
Nothing here is verified building law. Heights of neighbour buildings are estimates and flagged.
"""
from __future__ import annotations
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import shapely
from pyproj import Proj
from shapely.geometry import Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union
from . import cadastre, extract, geo, imagery, lod2, sources, terrain
from .fetch import Fetcher
from .models import SiteAssessment

SCHEMA = 'archaitect.site-pack/1'
_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix='sitepack')
_COMPASS = ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW']
PX_PER_M = 5.0            # 20 cm, the native resolution of the DOP20
MAX_SIDE_M = 400.0        # 2000 px: below the WMS limit of 3000 px
MIN_SIDE_M = 80.0

UTILITIES = [
    ('wasser', 'Trinkwasser'), ('abwasser', 'Schmutz-/Regenwasser (Kanal)'), ('gas', 'Gas'), ('strom', 'Strom'), ('telekom', 'Telekommunikation/Glasfaser'), ('fernwaerme', 'Fernwärme'),
]
UTILITIES_HOW_DE = ('Leitungsverläufe liegen bei den Netzbetreibern und sind in Hessen nicht als offene Geodaten verfügbar (nicht gefunden). '
                    'Der übliche Weg ist die Leitungsauskunft vor Planungs- und Baubeginn, z. B. über das kostenfreie Portal BIL (bil-leitungsauskunft.de, für Planer und Bauausführende; '
                    'Abdeckung der Betreiber in Hessen und Datenlieferung als Plan sind nicht bestätigt) oder direkt beim Wasser-, Gas-, Strom- und Netzbetreiber der Gemeinde. '
                    'Hausanschlusspunkte können im Planungsbrief als „vom Nutzer angegeben“ eingetragen werden.')


@dataclass
class SitePack:
    manifest: dict
    ortho: bytes | None
    ortho_media_type: str = 'image/png'


def _local(g: BaseGeometry, ox: float, oy: float) -> BaseGeometry:
    return shapely.transform(geo.to_m(g), lambda c: c - [ox, oy])


def _ring(g: BaseGeometry) -> list[list[float]] | None:
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda x: x.area)
    if g.geom_type != 'Polygon' or g.is_empty:
        return None
    return [[round(x, 2), round(y, 2)] for x, y in list(g.exterior.coords)]


def _compass(bearing: float) -> str:
    return _COMPASS[int((bearing + 22.5) // 45) % 8]


def _bearing(dx: float, dy: float) -> float:
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def build_sitepack(fetcher: Fetcher, a: SiteAssessment, margin_m: float = 30.0, with_ortho: bool = True,
                   site_ll: Polygon | None = None, origin: tuple[float, float] | None = None, site_ids: list[str] | None = None) -> SitePack:
    """``site_ll``/``site_ids``: several adjacent parcels planned together (union in WGS84); ``origin`` keeps the local frame of an existing project."""
    if a.parcel is None:
        raise ValueError('Ohne Flurstück kann kein Site-Pack erzeugt werden.')
    from datetime import datetime, timezone
    flags: list[str] = ['BUILDING_HEIGHTS_ESTIMATED_FROM_FLOORS', 'TERRAIN_IS_BARE_EARTH_DGM1', 'ORTHO_ACQUISITION_DATE_NOT_QUERIED', 'NO_UTILITY_LINES_IN_OPEN_DATA']
    parcel_ll = Polygon(a.parcel.ring_lonlat)
    union_ll = site_ll if site_ll is not None else parcel_ll
    pm = geo.to_m(union_ll)
    cx, cy = pm.centroid.x, pm.centroid.y
    ox, oy = origin if origin else (round(cx, 3), round(cy, 3))
    minx, miny, maxx, maxy = pm.bounds
    half = max((max(maxx - minx, maxy - miny) / 2) + margin_m, MIN_SIDE_M / 2)
    if half * 2 > MAX_SIDE_M:
        half = MAX_SIDE_M / 2
        flags.append('PACK_CLIPPED_TO_400M')
    bbox = (round(cx - half), round(cy - half), round(cx + half), round(cy + half))   # whole metres: stable cache keys
    side = bbox[2] - bbox[0]
    px = int(round(side * PX_PER_M))
    uc = union_ll.centroid
    k = max(1.0, half / 70.0)            # query radius grows with the plot
    clat, clon = (uc.y, uc.x) if site_ll is not None else (a.lat, a.lon)
    area_ll = box(*[v for v in (clon - 0.0013 * k, clat - 0.0009 * k, clon + 0.0013 * k, clat + 0.0009 * k)])

    f_ortho = _POOL.submit(imagery.get_map, fetcher, 'luftbild', tuple(float(v) for v in bbox), px, px, 'EPSG:25832', 'image/png') if with_ortho else None
    f_dgm = _POOL.submit(terrain.get_dgm, fetcher, tuple(float(v) for v in bbox))
    f_par = _POOL.submit(cadastre.parcels_around, fetcher, clat, clon, 0.0010 * k)
    f_bu = _POOL.submit(sources.query, sources.SOURCES['buildings'], fetcher, Point(clon, clat), 0.0011 * k)
    f_elu = _POOL.submit(sources.query, sources.SOURCES['elu'], fetcher, area_ll)
    f_lod = _POOL.submit(lod2.fetch, fetcher, sources.SOURCES['lod2'], clat, clon, 0.0011 * k)

    # ---- orientation
    conv = Proj('EPSG:25832').get_factors(a.lon, a.lat).meridian_convergence
    # ---- parcels
    me = a.parcel.national_reference
    ids = set(site_ids or [me])
    parcels = [{'id': p.national_reference, 'label': p.label, 'is_site': p.national_reference in ids, 'area_alkis_m2': p.area_alkis_m2,
                'ring': _ring(_local(Polygon(p.ring_lonlat), ox, oy))} for p in f_par.result()]
    if not any(p['id'] == me for p in parcels):
        parcels.append({'id': me, 'label': a.parcel.label, 'is_site': True, 'area_alkis_m2': a.parcel.area_alkis_m2, 'ring': _ring(_local(parcel_ll, ox, oy))})
    prim_local = _local(parcel_ll, ox, oy)
    for p in parcels:
        if p['id'] == me:
            p['ring'] = _ring(prim_local)
    site_local = _local(union_ll, ox, oy)      # the assessed parcel's own geometry, identical to the one in the MACE output
    # ---- buildings
    bo = f_bu.result()
    buildings = []
    for f in bo.features:
        if f.geometry is None:
            continue
        g = _local(f.geometry, ox, oy)
        ring = _ring(g)
        if ring is None or not box(-half - 20, -half - 20, half + 20, half + 20).intersects(g):
            continue
        use = (f.href('currentUse', 'currentUse>CurrentUse>currentUse') or '').rsplit('/', 1)[-1] or None
        fl = f.get('numberOfFloorsAboveGround')
        floors = int(float(fl)) if fl and fl.replace('.', '', 1).isdigit() else None
        buildings.append({'id': f.gml_id, 'ring': ring, 'footprint_m2': round(g.area, 1), 'use': use, 'floors': floors,
                          'height_est_m': round(floors * 2.9 + 1.5, 1) if floors else None, 'height_basis': 'ESTIMATE_FROM_FLOORS' if floors else None,
                          'on_site': bool(g.intersection(site_local).area / max(g.area, 0.1) >= 0.5)})
    # ---- measured heights (LoD2) for buildings, where available
    try:
        measured = lod2.match(buildings, f_lod.result(), lambda g: _local(g, ox, oy))
    except Exception:  # noqa: BLE001 - enrichment is optional
        measured = {}
    for bd in buildings:
        h = measured.get(bd['id'])
        if h:
            bd['height_est_m'], bd['height_basis'] = h, lod2.HEIGHT_BASIS
            if not bd.get('floors'):
                bd['floors'], bd['floors_basis'] = lod2.storeys_from_height(h), 'DERIVED_FROM_LOD2_HEIGHT'
    if measured:
        flags.append('BUILDING_HEIGHTS_MEASURED_LOD2_PARTIAL')
    # ---- land use
    eo = f_elu.result()
    landuse = []
    roads: list[BaseGeometry] = []
    for f in eo.features:
        if f.geometry is None:
            continue
        code, eng = extract.hilucs_parts(f.href('hilucsLandUse'))
        g = _local(f.geometry, ox, oy)
        ring = _ring(g)
        if ring is None:
            continue
        landuse.append({'code': code, 'label_de': extract.hilucs_label(code, eng), 'ring': ring})
        if (code or '').startswith('4_1_1'):
            roads.append(g)
    frontage = None
    if roads:
        rd = unary_union(roads)
        p_on, r_on = nearest_points(site_local.boundary, rd)
        dist = p_on.distance(r_on)
        if dist < 40:
            brg = _bearing(p_on.x - site_local.centroid.x, p_on.y - site_local.centroid.y)
            frontage = {'status': 'INDICATION', 'basis': 'ALKIS-Bodennutzung Straßenverkehr (4_1_1) nächstgelegen', 'distance_to_road_m': round(dist, 1), 'bearing_deg_from_centroid': round(brg), 'compass': _compass(brg),
                        'boundary_point_xy': [round(p_on.x, 2), round(p_on.y, 2)], 'note_de': 'Hinweis auf die Straßenseite des Flurstücks; Zufahrt, Zuwegung und Hausanschluss sind damit nicht festgelegt.'}
    # ---- terrain
    grid, dres = f_dgm.result()
    terr: dict
    if grid is None:
        flags.append('TERRAIN_UNAVAILABLE')
        terr = {'status': 'UNAVAILABLE', 'detail': dres.error}
    else:
        sm = terrain.summarize(grid, geo.to_m(union_ll))
        ds = terrain.downsample(grid)
        ds['x_west_local'] = round(ds.pop('x_west') - ox, 2)
        ds['y_north_local'] = round(ds.pop('y_north') - oy, 2)
        terr = {'status': 'OK', 'source': 'DGM1 Hessen (WCS)', 'cell_m_native': grid.dx, 'summary': sm, 'grid': ds, 'z_origin_m': sm.get('z_mean_m')}
    # ---- ortho
    ortho_bytes = None
    ortho_meta: dict = {'status': 'NOT_REQUESTED'}
    if f_ortho is not None:
        r = f_ortho.result()
        if r.body is not None:
            ortho_bytes = r.body
            pxm = side / px
            ortho_meta = {'status': 'OK', 'file': 'ortho.png', 'media_type': 'image/png', 'width_px': px, 'height_px': px, 'pixel_size_m': round(pxm, 4), 'bbox_epsg25832': list(bbox),
                          'bbox_local': [round(bbox[0] - ox, 2), round(bbox[1] - oy, 2), round(bbox[2] - ox, 2), round(bbox[3] - oy, 2)], 'layer': 'he_dop_rgb (Hessen DOP20)',
                          'world_file': '\n'.join(f'{v:.6f}' for v in (pxm, 0, 0, -pxm, bbox[0] + pxm / 2, bbox[3] - pxm / 2))}
        else:
            ortho_meta = {'status': 'UNAVAILABLE', 'detail': r.error}
            flags.append('ORTHO_UNAVAILABLE')
    # ---- utilities
    nearby = [{'label_de': h.label_de, 'distance_m': h.distance_m, 'share': h.share, 'basis': f'{h.layer} (nicht parzellenscharf)'} for h in a.planning
              if any(k in h.label_de for k in ('Gasleitung', 'Rohrleitung', 'Hochspannung', '110-kV'))]
    utilities = {'status': 'NOT_OPEN_DATA', 'how_de': UTILITIES_HOW_DE, 'media': [{'kind': k, 'label_de': l, 'status': 'NOT_OPEN_DATA'} for k, l in UTILITIES],
                 'nearby_infrastructure_regional': nearby, 'enquiry_portal': {'name': 'BIL Leitungsauskunft', 'url': 'https://bil-leitungsauskunft.de/', 'note': 'kostenfrei für Planer/Bauausführende laut Betreiber-Website; keine API gefunden'}}
    attributions = [
        {'id': 'dop', 'text': imagery.LAYERS['luftbild'].changed_attribution, 'licence': imagery.LICENCE_TEXT},
        {'id': 'dgm1', 'text': terrain.ATTRIBUTION + ' (verändert: abgeleitet)', 'licence': 'Datenlizenz Deutschland – Zero – Version 2.0'},
        {'id': 'alkis', 'text': 'Geobasisdaten © Hessische Verwaltung für Bodenmanagement und Geoinformation: ALKIS Flurstücke, Gebäude, Bodennutzung (verändert: transformiert)', 'licence': 'Datenlizenz Deutschland – Zero – Version 2.0'},
    ]
    manifest = {
        'schema_version': SCHEMA, 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'site': {'lat': a.lat, 'lon': a.lon, 'parcel_id': me, 'parcel_label': a.parcel.label, 'area_alkis_m2': a.parcel.area_alkis_m2,
                 'parcel_ids': sorted(ids, key=lambda i: (i != me, i)), 'primary_id': me, 'ring_local': _ring(site_local)},
        'frame': {'crs': 'EPSG:25832', 'origin_e': ox, 'origin_n': oy, 'axes': 'x=Ost, y=Nord, z=oben (Meter)', 'true_north_offset_deg': round(conv, 3),
                  'true_north_note_de': 'Winkel zwischen Gitter-Nord (Frame-y) und geografisch Nord; geografisch Nord = Frame-y gedreht um diesen Wert (Meridiankonvergenz).', 'latitude': a.lat, 'longitude': a.lon},
        'extent': {'bbox_local': [round(bbox[0] - ox, 2), round(bbox[1] - oy, 2), round(bbox[2] - ox, 2), round(bbox[3] - oy, 2)], 'side_m': side},
        'parcels': parcels, 'buildings': buildings, 'landuse': landuse, 'street_frontage': frontage, 'terrain': terr, 'ortho': ortho_meta, 'utilities': utilities,
        'quality_flags': flags, 'attribution': attributions,
        'modification_notice_de': 'Die Quellenangabe muss auf Veränderungen hinweisen (§ 18 HVGG): gerenderte oder bearbeitete Darstellungen tragen den Zusatz „verändert“.',
        'limits_de': ['Gebäudehöhen der Umgebung sind Schätzungen aus der Geschosszahl.', 'Das Gelände ist ein Geländemodell ohne Gebäude und Bäume (DGM1).',
                      'Das Luftbild zeigt den Zustand der letzten Befliegung (Aufnahmedatum nicht abgefragt), nicht zwingend den heutigen Bestand.',
                      'Keine Leitungs-, Baulasten- oder Eigentümerdaten.'],
    }
    return SitePack(manifest=manifest, ortho=ortho_bytes)
