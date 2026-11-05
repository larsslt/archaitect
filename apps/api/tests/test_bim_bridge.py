"""BIM spec <-> plot rules bridge (siteintel/bim_bridge.py)."""
from archaitect.siteintel import bim_bridge as B
from archaitect.siteintel.regs import site_ctx


def pack(w=30.0, d=40.0):
    ring = [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2], [-w / 2, -d / 2]]
    return {"parcels": [{"id": "1", "label": "1", "is_site": True, "area_alkis_m2": w * d, "ring": ring}], "buildings": [], "landuse": [],
            "terrain": {"status": "UNAVAILABLE"}, "site": {"parcel_ids": ["1"]}}


def spec(x=0.0, y=0.0, rot=0.0):
    return {"name": "T", "storey_height": 3.0,
            "volumes": [{"id": "A", "name": "Haus", "origin": [-5, -4], "size": [10, 8], "base_z": 0.0, "storeys": 2,
                         "roof": {"type": "gable", "ridge": "x", "pitch_deg": 35}},
                        {"id": "G", "name": "Garage", "origin": [5, -3], "size": [3, 6], "base_z": 0.0, "storeys": 1, "roof": {"type": "flat"}}],
            "site": {"placement": {"x": x, "y": y, "rotation_deg": rot}}}


def test_massing_follows_placement_and_roles():
    m, notes = B.spec_to_massing(spec(10, 5, 90))
    a, g = m.volumes[0], m.volumes[1]
    assert a.role == "main" and g.role == "garage" and a.roof == "sattel" and a.ridge_along == "width"
    assert abs(a.cx - 10) < 1e-6 and abs(a.cy - 5) < 1e-6 and a.rotation_deg == 90
    # the garage centre (6.5, 0) in spec frame rotated by 90 deg then moved by (10, 5)
    assert abs(g.cx - 10) < 1e-6 and abs(g.cy - (5 + 6.5)) < 1e-6


def test_house_outside_plot_fails_hard_and_placement_fixes_it():
    ctx = site_ctx(pack(), None, None)
    bad = B.check_spec(spec(60, 0), ctx)
    assert bad["hard_ok"] is False
    pl, notes = B.place_spec(spec(60, 0), ctx)
    assert pl is not None
    fixed = spec(pl.x, pl.y, pl.rotation_deg)
    ok = B.check_spec(fixed, ctx)
    assert ok["hard_ok"] is True, ok


def test_house_too_big_cannot_be_placed():
    s = spec()
    s["volumes"][0]["size"] = [45, 35]
    pl, notes = B.place_spec(s, site_ctx(pack(), None, None))
    assert pl is None and "kein passender Standort" in notes[0]


def test_setback_limit_shrinks_the_region():
    from archaitect.siteintel.dossier import PlanningLimits
    ctx = site_ctx(pack(), None, None, None, PlanningLimits(setback_lines_offset_meters=12.0))
    pl, notes = B.place_spec(spec(), ctx)
    assert pl is None          # 30 m wide plot minus 2 x 12 m leaves 6 m: the 10 m house cannot fit unless rotated; garage extends it


def test_automatic_placement_prefers_entrance_towards_adjacent_road():
    from shapely.geometry import box,Point
    from shapely import affinity
    from archaitect.bim.geom import facade_xy
    ctx=site_ctx(pack(),None,None)
    ctx.roads=[box(-15,-24,15,-20)]
    s=spec();s['openings']=[{'volume':'A','side':'N','storey':0,'kind':'door','door_type':'double','offset':4.,'width':1.2}]
    pl,notes=B.place_spec(s,ctx)
    assert pl is not None and any('Straßenfläche' in n for n in notes)
    v=s['volumes'][0]; o=s['openings'][0]
    def point(depth):
        p=Point(*facade_xy('N',*v['origin'],*v['size'],o['offset']+o['width']/2,depth))
        return affinity.translate(affinity.rotate(p,pl.rotation_deg,origin=(0,0)),pl.x,pl.y)
    assert ctx.roads[0].distance(point(-1)) < ctx.roads[0].distance(point(0))


def test_placement_checks_smaller_disconnected_free_region():
    from shapely.geometry import box,MultiPolygon
    ctx=site_ctx(pack(),None,None)
    ctx.site=MultiPolygon([box(0,0,20,4),box(25,0,33,8)])
    s=spec();s['volumes']=s['volumes'][:1];s['volumes'][0]['origin']=[0,0];s['volumes'][0]['size']=[5,5]
    pl,_=B.place_spec(s,ctx)
    assert pl is not None
    assert ctx.site.geoms[1].buffer(.02).covers(B.spec_to_massing({**s,'site':{'placement':{'x':pl.x,'y':pl.y,'rotation_deg':pl.rotation_deg}}})[0].volumes[0].footprint())


def test_refinement_moves_attachment_clear_of_existing_building():
    from shapely.geometry import box
    from archaitect.siteintel.regs import SiteCtx,Existing
    from archaitect.bim.terrain import Placement
    ctx=SiteCtx(site=box(0,0,20,12),area_m2=240,existing=[Existing('old',box(12,4,14,8),None,None)],neighbours=[],roads=[],verified=None,envelope=None)
    s=spec();s['volumes']=s['volumes'][:1];s['volumes'][0]['origin']=[0,0];s['volumes'][0]['size']=[4,4]
    footprint=box(0,0,7,4)
    pl,note=B.refine_for_extras(s,ctx,footprint,Placement(6,4,0))
    placed=B.affinity.translate(footprint,pl.x,pl.y)
    assert placed.intersection(ctx.existing[0].poly).area <= 0.05
    assert note and 'verschoben' in note
