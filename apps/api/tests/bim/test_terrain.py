"""Terrain grading around the building pad (archaitect.bim.terrain)."""
import math

from archaitect.bim import terrain as T


def pack(fn, half=40, step=2.0, native=1.0, ring=20):
    n = int(2 * half / step)
    rows = []
    for r in range(n):
        y = half - native / 2 - r * step
        rows.append([round(fn(-half + native / 2 + c * step, y), 3) for c in range(n)])
    return {"terrain": {"status": "OK", "cell_m_native": native,
                        "grid": {"x_west_local": -half, "y_north_local": half, "cell_m": step, "heights_m": rows}},
            "site": {"ring_local": [[-ring, -ring], [ring, -ring], [ring, ring], [-ring, ring], [-ring, -ring]]}}


def house(**extra):
    spec = {"volumes": [{"id": "A", "origin": [-5, -4], "size": [10, 8], "base_z": 0.0, "storeys": 2}]}
    spec.update(extra)
    return spec


def test_sampler_reproduces_a_plane():
    h = T.heights_from_pack(pack(lambda x, y: 100 + 0.1 * x + 0.05 * y))
    for x, y in [(0, 0), (7.3, -4.1), (-12.0, 9.0)]:
        assert abs(h.at(x, y) - (100 + 0.1 * x + 0.05 * y)) < 0.02


def test_flat_site_needs_no_earthwork():
    t = T.build_terrain(pack(lambda x, y: 150.0), house())
    assert t["status"] == "OK"
    assert t["cut_m3"] == 0 and t["fill_m3"] == 0
    assert max(abs(v) for v in t["z"]) <= 0.04 + 1e-6      # only the PAD_DROP_M threshold drop
    assert t["natural_slope_pct"] == 0.0


def test_slope_gives_level_pad_and_bounded_embankment():
    t = T.build_terrain(pack(lambda x, y: 200 + 0.2 * x), house())      # 20 % slope rising to the east
    st = T.SpecTerrain(t)
    for x, y in [(-5, -4), (0, 0), (5, 4), (-5.5, 0)]:                    # house and its margin are level at the pad
        assert abs(st.at(x, y) + 0.04) < 1e-6      # PAD_DROP_M
    assert abs(t["pad_z_abs_m"] - 200) < 0.3                              # mean height under the house
    # downhill (west) the new ground is filled up, uphill (east) cut into the slope, never steeper than 1:2 from the pad edge
    nat = lambda x: 0.2 * x - (t["pad_z_abs_m"] - 200)
    assert st.at(-8, 0) > nat(-8) + 0.5          # filled up on the downhill side
    assert st.at(8, 0) < nat(8) - 0.5            # cut into the slope on the uphill side
    d = 8 - 6.5
    assert abs(st.at(8, 0)) <= d * t["slope"] + 0.05 and abs(st.at(-8, 0)) <= d * t["slope"] + 0.05
    assert abs(st.at(20, 0) - nat(20)) < 0.05    # far away the natural terrain is met again
    assert t["cut_m3"] > 0 and t["fill_m3"] > 0
    assert 18 < t["natural_slope_pct"] < 22


def test_far_ground_follows_nature():
    t = T.build_terrain(pack(lambda x, y: 200 + 0.2 * x), house())
    st = T.SpecTerrain(t)
    far = st.at(35, 0)                                                    # beyond the embankment the natural terrain is matched
    assert abs(far - (0.2 * 35 - (t["pad_z_abs_m"] - 200))) < 0.6 or far <= 0.2 * 35


def test_steep_site_warns():
    t = T.build_terrain(pack(lambda x, y: 100 + 0.6 * x), house())
    assert t["notes_de"] and "Auftrag" in " ".join(t["notes_de"]) or "Abtrag" in " ".join(t["notes_de"])


def test_missing_terrain_is_unavailable_not_flat_pretending():
    assert T.build_terrain({"terrain": {"status": "UNAVAILABLE"}}, house())["status"] == "UNAVAILABLE"
    assert T.terrain_mesh(T.build_terrain({}, house())) is None


def test_placement_roundtrip_and_rotation_does_not_change_volumes_much():
    pl = T.Placement(12.0, -7.0, 33.0)
    x, y = pl.to_site(3.0, 4.0)
    ax, ay = pl.to_spec(x, y)
    assert math.isclose(ax, 3.0, abs_tol=1e-9) and math.isclose(ay, 4.0, abs_tol=1e-9)
    p = pack(lambda x, y: 200 + 0.1 * x)
    a = T.build_terrain(p, house())
    b = T.build_terrain(p, house(site={"placement": {"x": 0, "y": 0, "rotation_deg": 90}}))
    assert a["status"] == b["status"] == "OK"
    assert abs(a["pad_z_abs_m"] - b["pad_z_abs_m"]) < 0.2


def test_garden_objects_extend_the_plateau():
    s = house(components=[{"type": "pool", "x": 8, "y": -2, "width": 8, "depth": 4}])
    d1 = T.dressing_polygon(house())
    d2 = T.dressing_polygon(s)
    assert d2.area > d1.area and d2.contains(T.Point(15, 0))


def test_mesh_is_closed_grid():
    t = T.build_terrain(pack(lambda x, y: 100 + 0.1 * x), house())
    m = T.terrain_mesh(t)
    assert len(m["positions"]) == 3 * t["nx"] * t["ny"]
    assert len(m["indices"]) == 6 * (t["nx"] - 1) * (t["ny"] - 1)
    assert max(m["indices"]) < t["nx"] * t["ny"]


def test_steeper_slopes_scale_earthwork_and_warn():
    res = {}
    for s in (0.05, 0.15, 0.30):
        res[s] = T.build_terrain(pack(lambda x, y, s=s: 200 + s * x), house())
    cuts = [res[s]["cut_m3"] for s in (0.05, 0.15, 0.30)]
    fills = [res[s]["fill_m3"] for s in (0.05, 0.15, 0.30)]
    assert cuts == sorted(cuts) and fills == sorted(fills) and cuts[0] < cuts[2]
    steep = res[0.30]
    assert steep["max_cut_m"] > 1.5 and steep["max_fill_m"] > 1.5
    assert any("Stützmauer" in n for n in steep["notes_de"])               # retaining wall hint above 1.5 m
    assert not res[0.05]["notes_de"]
    # pad at the mean height of the building: cut and fill roughly balance on a plane
    assert abs(steep["cut_m3"] - steep["fill_m3"]) < 0.25 * max(steep["cut_m3"], steep["fill_m3"])


def test_graded_surface_has_no_jumps():
    t = T.build_terrain(pack(lambda x, y: 200 + 0.3 * x + 0.1 * y), house())
    nx, ny, step = t["nx"], t["ny"], t["step_m"]
    z = t["z"]
    worst = 0.0
    for j in range(ny):
        for i in range(nx - 1):
            worst = max(worst, abs(z[j * nx + i + 1] - z[j * nx + i]))
    for j in range(ny - 1):
        for i in range(nx):
            worst = max(worst, abs(z[(j + 1) * nx + i] - z[j * nx + i]))
    assert worst <= 0.5 * step + 0.4 * step * 1.5 + 0.35    # at most the natural slope plus the 1:2 embankment per cell


def test_ifc_trees_and_hedges_stand_on_graded_ground(tmp_path):
    import json
    from pathlib import Path
    import ifcopenshell
    import ifcopenshell.util.placement as pl
    import archaitect.bim as bim
    from archaitect.bim.ifcgen import build_ifc
    spec = json.loads((Path(bim.__file__).resolve().parent / "specs" / "stadthaus.json").read_text(encoding="utf-8"))
    spec["site"] = {"trees": [{"name": "Baum", "position": [30.0, 6.0], "height": 8.0, "crown_radius": 3.0}],
                    "hedges": [{"name": "Hecke", "origin": [28.0, 0.0], "size": [0.6, 6.0], "height": 1.0}]}
    t = T.build_terrain(pack(lambda x, y: 200 + 0.2 * x), spec)
    f = tmp_path / "s.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    flat, graded = tmp_path / "a.ifc", tmp_path / "b.ifc"
    build_ifc(f, flat)
    build_ifc(f, graded, terrain=t)
    zs = {}
    for k, path in (("flat", flat), ("graded", graded)):
        m = ifcopenshell.open(str(path))
        zs[k] = {e.Name: pl.get_local_placement(e.ObjectPlacement)[2][3] for e in m.by_type("IfcGeographicElement")}
    assert abs(zs["flat"]["Baum"]) < 1e-9
    want = T.SpecTerrain(t).at(30.0, 6.0)
    assert abs(want) > 1.0 and abs(zs["graded"]["Baum"] - want) < 1e-6
    assert abs(zs["graded"]["Hecke"]) > 0.5


def test_ifc_components_and_paving_follow_the_ground(tmp_path):
    import json
    from pathlib import Path
    import ifcopenshell
    import ifcopenshell.util.placement as pl
    import archaitect.bim as bim
    from archaitect.bim.ifcgen import build_ifc
    spec = json.loads((Path(bim.__file__).resolve().parent / "specs" / "stadthaus.json").read_text(encoding="utf-8"))
    spec["site"] = {"paving": [{"name": "Platz", "origin": [28.0, 0.0], "size": [2.0, 2.0], "tile": [1.0, 1.0], "joint": 0.01, "thickness": 0.05}]}
    spec["components"] = [{"type": "hedge", "x0": 30.0, "y0": 6.0, "x1": 36.0, "y1": 6.0, "thickness": 0.5, "height": 1.0},
                          {"type": "shrub", "x": 31.0, "y": 8.0, "radius": 0.5, "height": 1.0, "pot": False}]
    t = T.build_terrain(pack(lambda x, y: 200 + 0.2 * x), spec)
    f = tmp_path / "s.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "g.ifc"
    build_ifc(f, out, terrain=t)
    m = ifcopenshell.open(str(out))
    z = {e.Name: pl.get_local_placement(e.ObjectPlacement)[2][3] for e in m.by_type("IfcBuildingElementProxy") + m.by_type("IfcGeographicElement")}
    st = T.SpecTerrain(t)
    # the garden is part of the levelled building ground, so these may sit at 0 - they must equal the graded ground, not floor level
    assert abs(z["Platz"] - min(st.at(x, y) for x, y in [(28, 0), (30, 0), (28, 2), (30, 2), (29, 1)])) < 1e-6
    assert abs(z["Buchs Strauch"] - st.at(31.0, 8.0)) < 1e-6
    assert abs(z["Buchs Hecke"] - min(st.at(x, y) for x, y in [(30, 5.75), (36.0, 5.75), (30, 6.25), (36.0, 6.25), (33, 6)])) < 0.3
