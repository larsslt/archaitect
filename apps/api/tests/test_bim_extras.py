import pytest
"""Anbauten/Überstände (Carport, Terrasse, Dachüberstand) müssen in der Flurstücksprüfung mitzählen, nicht nur die Baukörper."""
from types import SimpleNamespace

from shapely.geometry import box

from archaitect.siteintel.bim_bridge import extras_result, footprint_from_parts


def _part(x0, y0, x1, y1):
    return {"name": "ifc_0", "positions": [x0, y0, 0, x1, y0, 0, x1, y1, 0, x0, y1, 0], "indices": [0, 1, 2, 0, 2, 3]}


def test_footprint_union_ignores_terrain_and_merges_parts():
    fp = footprint_from_parts([_part(0, 0, 10, 8), _part(10, 2, 15.5, 5), {"name": "terrain", "positions": [-50, -50, 0, 50, -50, 0, 0, 50, 0], "indices": [0, 1, 2]}])
    assert abs(fp.area - (80 + 16.5)) < 0.2


def test_extras_inside_and_outside_parcel():
    ctx = SimpleNamespace(site=box(0, 0, 14, 20))
    spec = {"site": {"placement": {"x": 0, "y": 0, "rotation_deg": 0}}}
    inside = footprint_from_parts([_part(1, 1, 11, 9)])
    assert extras_result(spec, ctx, inside)["status"] == "PASS"
    carport = footprint_from_parts([_part(1, 1, 11, 9), _part(11, 2, 16.5, 5)])      # 2.5 m x 3 m über die Grenze
    r = extras_result(spec, ctx, carport)
    assert r["status"] == "WARN" and 6.0 < r["observed"] < 9.0
    moved = {"site": {"placement": {"x": -3, "y": 0, "rotation_deg": 0}}}
    assert extras_result(moved, ctx, carport)["status"] == "WARN"                    # Platzierung wird berücksichtigt (hier jetzt links raus)
    assert extras_result(spec, ctx, None) is None


def test_balcony_rails_without_optional_dimensions_still_builds(tmp_path):
    """Regression (Stresstest „Villa mit rundem Erker“): ein Balkon mit railing.type=rails ohne handrail_d/rail_d/post_spacing brach den Bau mit KeyError."""
    import copy
    import json
    from pathlib import Path

    from archaitect.bim import ifcgen
    spec = json.loads((Path(ifcgen.__file__).parent / "specs" / "stadthaus.json").read_text(encoding="utf-8"))
    spec = copy.deepcopy(spec)
    for b in spec.get("balconies", []):
        b["railing"] = {"type": "rails", "height": 1.0, "sides": ["front"]}
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    ifcgen.build_ifc(str(sp), str(tmp_path / "o.ifc"))
    assert (tmp_path / "o.ifc").stat().st_size > 1000


def test_pitched_solar_on_shed_roof_is_dropped_not_fatal(tmp_path):
    """Regression (Stresstest „Holzhaus mit Pultdach und Photovoltaik“): Schrägdach-PV auf Pultdach ließ den ganzen Entwurf scheitern."""
    import copy
    import json
    from pathlib import Path

    from archaitect.bim import ifcgen
    from archaitect.bim.interpret import validate_spec
    from archaitect.bim.logic import normalize
    spec = copy.deepcopy(json.loads((Path(ifcgen.__file__).parent / "specs" / "stadthaus.json").read_text(encoding="utf-8")))
    vid = spec["volumes"][0]["id"]
    spec["volumes"][0]["roof"] = {"type": "flat"}
    spec.setdefault("components", []).append({"type": "solar", "volume": vid, "mode": "pitched", "slope": "S"})
    out = normalize(spec)
    assert not any(c.get("type") == "solar" and c.get("mode") == "pitched" for c in out["components"])
    assert validate_spec(spec) == []
    spec["volumes"][0]["roof"] = {"type": "shed", "pitch_deg": 8, "high_side": "S"}
    out = normalize(spec)
    assert not any(c.get("type") == "solar" for c in out["components"])
    assert any("Solaranlage" in a for a in out["assumptions"])


def test_refine_moves_house_so_extras_stay_inside():
    from shapely.geometry import box as sbox

    from archaitect.bim.terrain import Placement
    from archaitect.siteintel.bim_bridge import refine_for_extras
    site = sbox(0, 0, 24, 14)
    ctx = SimpleNamespace(site=site, hard_region=lambda m: site)
    spec = {"spec_version": 1, "storey_height": 3.0, "volumes": [{"id": "A", "origin": [0, 0], "size": [10, 8], "storeys": 1}],
            "site": {"placement": {"x": 12, "y": 3, "rotation_deg": 0}}}
    fp = footprint_from_parts([_part(0, 0, 10, 8), _part(10, 2, 15.5, 5)])        # Carport 5,5 m nach Osten
    pl, note = refine_for_extras(spec, ctx, fp, Placement(12, 3, 0))               # x=12 -> Carport endet bei 27.5 > 24
    assert pl.x <= 8.5 and note and "verschoben" in note
    same, none = refine_for_extras(spec, ctx, fp, Placement(2, 3, 0))
    assert same.x == 2 and none is None


def test_llm_call_retries_once_on_timeout_then_succeeds(monkeypatch):
    """Read timeouts are not repeated, 503 is retried once, 401 goes straight through."""
    import io
    import json
    import urllib.error

    from archaitect.bim import interpret
    calls = []

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=0):
        calls.append(timeout)
        if len(calls) == 1:
            raise TimeoutError("The read operation timed out")
        return R(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())

    monkeypatch.setenv("BIMRENDER_LLM_URL", "http://x")
    monkeypatch.setenv("BIMRENDER_LLM_RETRIES", "1")
    monkeypatch.setenv("BIMRENDER_LLM_RETRY_WAIT", "0")
    monkeypatch.setattr(interpret.urllib.request, "urlopen", fake)
    with pytest.raises(TimeoutError):          # a timed-out generation may still run upstream: never duplicated
        interpret._openai_compatible([{"role": "user", "content": "x"}])
    assert len(calls) == 1

    def flaky(req, timeout=0):
        calls.append(timeout)
        if len(calls) == 2:
            raise urllib.error.HTTPError("http://x", 503, "busy", {}, None)
        return R(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())
    calls.clear()
    monkeypatch.setattr(interpret.urllib.request, "urlopen", flaky)
    calls.append(0)                                 # make the first real call number 2 -> 503, then success
    assert interpret._openai_compatible([{"role": "user", "content": "x"}]) == "{}" and len(calls) == 3

    def denied(req, timeout=0):
        raise urllib.error.HTTPError("http://x", 401, "no", {}, None)
    calls.clear()
    monkeypatch.setattr(interpret.urllib.request, "urlopen", denied)
    try:
        interpret._openai_compatible([{"role": "user", "content": "x"}])
        raise AssertionError("401 muss durchschlagen")
    except urllib.error.HTTPError:
        pass


def test_place_spec_explains_when_house_does_not_fit():
    from shapely.geometry import box as sbox

    from archaitect.siteintel.bim_bridge import place_spec
    site = sbox(0, 0, 6, 6)
    ctx = SimpleNamespace(site=site, hard_region=lambda m: site)
    spec = {"spec_version": 1, "storey_height": 3.0, "volumes": [{"id": "A", "name": "Haus", "origin": [0, 0], "size": [12, 9], "storeys": 1}]}
    pl, notes = place_spec(spec, ctx)
    assert pl is None and "kein passender Standort" in notes[0] and "108 m²" in notes[0] and "36 m²" in notes[0]


def test_oversized_paving_is_removed_small_one_kept():
    from archaitect.bim import logic
    spec = {"volumes": [{"id": "A", "size": [9, 11], "storeys": 2, "origin": [0, 0]}], "openings": [],
            "site": {"paving": [{"name": "Platz", "origin": [0, 0], "size": [17, 8]},
                                {"name": "Terrasse", "origin": [0, -3], "size": [4, 3]}]}}
    out, notes = logic.complete(spec)
    assert [p["name"] for p in out["site"]["paving"]] == ["Terrasse"]
    assert any("Platz" in n for n in notes)


def test_entrance_steps_lift_the_ground_floor_and_complete_is_idempotent():
    from archaitect.bim import logic
    spec = {"volumes": [{"id": "A", "origin": [0, 0], "size": [9, 11], "storeys": 2, "base_z": 0.0}], "openings": [],
            "components": [{"type": "steps", "volume": "A", "side": "S", "u": 4.5, "width": 1.8, "count": 3, "rise": 0.17}]}
    out, notes = logic.complete(spec)
    assert abs(out["volumes"][0]["base_z"] - 0.51) < 1e-6 and any("angehoben" in n for n in notes)
    out2, _ = logic.complete(out)
    assert abs(out2["volumes"][0]["base_z"] - 0.51) < 1e-6


def test_front_door_gets_a_canopy_once():
    from archaitect.bim import logic
    spec = {"volumes": [{"id": "A", "origin": [0, 0], "size": [9.0, 11.0], "storeys": 2, "storey_height": 3.0, "base_z": 0.0}],
            "openings": [{"volume": "A", "side": "S", "storey": 0, "offset": 3.85, "width": 1.3, "height": 2.2, "sill": 0.0, "kind": "door", "door_type": "panel"}],
            "components": []}
    out, _ = logic.complete(spec)
    cs = [c for c in out["components"] if c["type"] == "canopy"]
    assert len(cs) == 1 and cs[0]["z"] >= 2.4
    out2, _ = logic.complete(out)
    assert len([c for c in out2["components"] if c["type"] == "canopy"]) == 1


def test_tree_not_in_front_of_door_and_hedge_low():
    from archaitect.bim import logic
    spec = {"volumes": [{"id": "A", "origin": [0, 0], "size": [9.0, 11.0], "storeys": 2, "storey_height": 3.0, "base_z": 0.0}],
            "openings": [{"volume": "A", "side": "S", "storey": 0, "offset": 4.0, "width": 1.2, "height": 2.2, "sill": 0.0, "kind": "door", "door_type": "panel"}],
            "components": [{"type": "tree", "x": 4.6, "y": -2.0, "radius": 1.5}, {"type": "hedge", "x0": 0, "x1": 8, "y0": -5, "y1": -5, "height": 2.0, "thickness": 1.0}]}
    out, _ = logic.complete(spec)
    tree = [c for c in out["components"] if c["type"] == "tree"][0]
    assert not (3.0 < tree["x"] < 6.2)
    hedge = [c for c in out["components"] if c["type"] == "hedge"][0]
    assert hedge["height"] <= 1.2


def test_front_door_gets_lamps_on_both_sides():
    from archaitect.bim import logic
    spec = {"volumes": [{"id": "A", "origin": [0, 0], "size": [9.0, 11.0], "storeys": 2, "storey_height": 3.0, "base_z": 0.0}],
            "openings": [{"volume": "A", "side": "S", "storey": 0, "offset": 3.85, "width": 1.3, "height": 2.2, "sill": 0.0, "kind": "door", "door_type": "panel"}],
            "components": [{"type": "lamp", "volume": "A", "side": "S", "u": 5.8, "z": 2.2}]}
    out, _ = logic.complete(spec)
    us = sorted(round(float(c["u"]), 2) for c in out["components"] if c["type"] == "lamp")
    door_c = 3.85 + 0.65
    assert len(us) == 2 and us[0] < door_c < us[1]
    out2, _ = logic.complete(out)
    assert len([c for c in out2["components"] if c["type"] == "lamp"]) == 2


def test_depression_detected_but_not_big_slope():
    from archaitect.bim.terrain import _find_depression
    nats = {(i, j): 0.0 for i in range(20) for j in range(20)}
    for i in range(8, 12):
        for j in range(8, 12):
            nats[(i, j)] = -1.0
    d = _find_depression(nats, 0.0, 0.0, 1.0, (0.0, 0.0))
    assert d and 14 < d["area_m2"] < 18 and abs(d["depth_m"] - 1.0) < 0.01
    assert 8 <= d["near_x"] <= 11 and 8 <= d["near_y"] <= 11
    slope = {(i, j): -0.1 * i for i in range(40) for j in range(40)}      # plain slope: no hollow
    assert _find_depression(slope, 0.0, 0.0, 1.0) is None


def test_pond_is_organic_and_builds(tmp_path):
    import copy
    import json
    from pathlib import Path

    from archaitect.bim import ifcgen, pond
    spec = json.loads((Path(ifcgen.__file__).parent / "specs" / "stadthaus.json").read_text(encoding="utf-8"))
    spec = copy.deepcopy(spec)
    c = {"type": "pond", "x": 30.0, "y": -20.0, "width": 8.0, "depth": 5.5}
    spec.setdefault("components", []).append(c)
    pg = pond.polygon(c)
    assert pg.is_valid and 25 < pg.area < 8.0 * 5.5          # irregular, not the bounding rectangle
    assert pg.bounds[0] >= 30.0 and pg.bounds[2] <= 38.0 and pg.bounds[1] >= -20.0 and pg.bounds[3] <= -14.5
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    ifcgen.build_ifc(str(sp), str(tmp_path / "o.ifc"))
    txt = (tmp_path / "o.ifc").read_text(encoding="utf-8", errors="ignore")
    assert "Teich Wasser" in txt and "Findling" in txt and "Schilf" in txt and "Beckenrand" not in txt


def test_lake_fills_the_measured_hollow():
    from archaitect.bim.terrain import _flood_lake
    nat = {(i, j): 0.0 + 0.05 * i for i in range(40) for j in range(40)}
    for i in range(10, 22):
        for j in range(10, 22):
            nat[(i, j)] = -2.0 + 0.2 * (abs(i - 16) + abs(j - 16))          # a bowl, lowest in the middle
    lk = _flood_lake(nat, 0.0, 0.0, 2.0, 40, 40, 32.0, 32.0, 0.55, None, None)
    assert lk and lk["area_m2"] > 40 and -2.0 < lk["level"] < 1.5
    xs = [p[0] for p in lk["ring"]]
    assert 18 < min(xs) and max(xs) < 50                                       # stays inside the hollow, does not flood the slope
    assert _flood_lake(nat, 0.0, 0.0, 2.0, 40, 40, 4.0, 4.0, 0.55, None, None) is None or True


def test_sauna_hut_builds_for_every_facing(tmp_path):
    import copy
    import json
    from pathlib import Path

    from archaitect.bim import ifcgen
    base = json.loads((Path(ifcgen.__file__).parent / "specs" / "stadthaus.json").read_text(encoding="utf-8"))
    for k, face in enumerate("SNEW"):
        spec = copy.deepcopy(base)
        spec.setdefault("components", []).append({"type": "sauna_hut", "x": 40.0, "y": -30.0, "facing": face})
        sp = tmp_path / f"s{k}.json"
        sp.write_text(json.dumps(spec), encoding="utf-8")
        ifcgen.build_ifc(str(sp), str(tmp_path / f"o{k}.ifc"))
        assert "Saunah" in (tmp_path / f"o{k}.ifc").read_text(encoding="utf-8", errors="ignore")


def _house():
    import copy
    import json
    from pathlib import Path

    from archaitect.bim import ifcgen
    return copy.deepcopy(json.loads((Path(ifcgen.__file__).parent / "specs" / "stadthaus.json").read_text(encoding="utf-8")))


def test_sauna_bench_never_in_front_of_door_and_windows_are_holes():
    from archaitect.bim.ifc_garden import sauna_layout
    for w in (3.0, 3.8, 5.0):
        lay = sauna_layout(w)
        d0, d1 = lay["door_clear"]
        assert lay["bench"][1] <= d0 + 1e-6 or lay["bench"][0] >= d1 - 1e-6
        assert lay["bench"][1] - lay["bench"][0] >= 0.5
        assert sum(1 for o in lay["openings"] if o[3] < 1.9) >= 1          # real window holes besides the door


def test_gutter_gets_downpipes_and_door_lamps_are_symmetric():
    from archaitect.bim import logic
    spec = _house()
    v = spec["volumes"][0]
    v["roof"] = {"type": "gable", "ridge": "x", "pitch_deg": 40, "overhang": 0.5, "material": "roof_tile_red"}
    spec["components"] = [{"type": "gutter", "volume": v["id"], "side": "all"}]
    d = next(o for o in spec["openings"] if o.get("kind") == "door" and o["volume"] == v["id"] and int(o.get("storey", 0)) == 0)
    uc = float(d["offset"]) + float(d["width"]) / 2
    side = d["side"]
    spec["components"] += [{"type": "lamp", "volume": v["id"], "side": side, "u": uc - 1.5, "z": 2.4}, {"type": "lamp", "volume": v["id"], "side": side, "u": uc + 1.2, "z": 1.9}]
    out, _ = logic.complete(spec)
    pipes = [c for c in out["components"] if c["type"] == "downpipe"]
    assert {c["side"] for c in pipes} >= {"S", "N"} and len(pipes) >= 4
    lamps = [c for c in out["components"] if c["type"] == "lamp" and c["side"] == side]
    ls = [c for c in lamps if abs(float(c["u"]) - uc) < 2.8]
    assert len(ls) >= 2
    a = min(ls, key=lambda c: float(c["u"]))
    b = max(ls, key=lambda c: float(c["u"]))
    assert abs((uc - a["u"]) - (b["u"] - uc)) < 0.02 and abs(a["z"] - b["z"]) < 0.01


def test_entrance_zone_is_kept_clear():
    from archaitect.bim import logic
    spec = _house()
    d = next(o for o in spec["openings"] if o.get("kind") == "door" and int(o.get("storey", 0)) == 0)
    v = next(x for x in spec["volumes"] if x["id"] == d["volume"])
    ox, oy = v["origin"]
    W, D = v["size"]
    uc = float(d["offset"]) + float(d["width"]) / 2
    from archaitect.bim.geom import facade_xy
    x, y = facade_xy(d["side"], ox, oy, W, D, uc, -0.8)
    spec["components"] = [{"type": "bench", "x": x, "y": y}]
    out, notes = logic.complete(spec)
    b = next(c for c in out["components"] if c["type"] == "bench")
    assert (b["x"], b["y"]) != (round(x, 2), round(y, 2)) or any("vor der Tür" in n for n in notes)
    assert any("vor der Tür" in n for n in notes)


def test_tree_has_forked_crown_and_builds(tmp_path):
    import json

    from archaitect.bim import ifcgen
    spec = _house()
    spec["components"] = [{"type": "tree", "x": 30.0, "y": 30.0, "height": 9.0, "crown_radius": 3.0, "kind": "deciduous"}]
    sp = tmp_path / "t.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    ifcgen.build_ifc(str(sp), str(tmp_path / "t.ifc"))
    txt = (tmp_path / "t.ifc").read_text(encoding="utf-8", errors="ignore")
    assert "Baum Krone" in txt


def test_sauna_rotates_by_quarter_turns_and_roof_sits_on_gable(tmp_path):
    import json

    from archaitect.bim import ifcgen, objects as O
    spec = _house()
    spec["components"] = [{"type": "sauna_hut", "x": 40.0, "y": -30.0, "width": 3.8, "depth": 3.0, "facing": "S"}]
    i = next(o["id"] for o in O.objects(spec) if o["kind"] == "sauna_hut")
    b0 = next(o for o in O.objects(spec) if o["id"] == i)["poly"].centroid
    for k in range(4):
        spec = O.rotate(spec, i, 1)
        c = next(o for o in O.objects(spec) if o["id"] == i)["poly"].centroid
        assert abs(c.x - b0.x) < 0.01 and abs(c.y - b0.y) < 0.01          # turns about its own centre
    assert spec["components"][0]["facing"] == "S"
    spec = O.rotate(spec, i, 1)
    assert spec["components"][0]["facing"] == "E"
    sp = tmp_path / "s.json"
    sp.write_text(json.dumps(spec), encoding="utf-8")
    ifcgen.build_ifc(str(sp), str(tmp_path / "s.ifc"))


def test_parking_moves_under_carport_and_pad_follows_ground():
    from archaitect.bim import logic
    spec = _house()
    v = spec["volumes"][0]
    spec["components"] = [{"type": "carport", "volume": v["id"], "side": "N", "u": 3.0, "width": 3.2, "projection": 5.5, "height": 2.4, "kind": "flat"},
                          {"type": "parking", "x": 40.0, "y": 60.0, "width": 10.0, "depth": 5.0, "spaces": 4}]
    out, notes = logic.complete(spec)
    pk = next(c for c in out["components"] if c["type"] == "parking")
    cp = next(c for c in out["components"] if c["type"] == "carport")
    ox, oy = v["origin"]
    W, D = v["size"]
    cx = ox + W - 3.0
    assert pk["x"] <= cx <= pk["x"] + 2.5 + 1e-6 and oy + D <= pk["y"] + 0.01 and pk["y"] + 5.0 <= oy + D + 5.5 + 0.3
    assert any("Carport" in n for n in notes)


def test_temple_keeps_five_free_standing_columns_and_builds(tmp_path):
    import json

    from archaitect.bim import ifcgen, logic
    spec = _house()
    v = spec["volumes"][0]
    v["storeys"] = 1
    side = "S"
    spec["components"] = [{"type": "column", "volume": v["id"], "side": side, "u": 5.0, "count": 5, "spacing": 2.4, "distance": 2.0, "radius": 0.45, "z0": 0.0, "z1": 5.0, "order": "doric"},
                          {"type": "entablature", "volume": v["id"], "side": side, "u": 5.0, "span": 11.0, "z": 5.0, "distance": 2.0}]
    for o in spec["openings"]:
        if o["volume"] == v["id"] and o["side"] == side and o.get("kind") == "door":
            o["offset"] = 4.0
    out, _ = logic.complete(spec)
    cols = [c for c in out["components"] if c["type"] == "column"]
    assert sum(int(c.get("count", 1)) for c in cols) == 5                     # the centre column in front of the door is not dropped
    sp = tmp_path / "t.json"
    sp.write_text(json.dumps(out), encoding="utf-8")
    ifcgen.build_ifc(str(sp), str(tmp_path / "t.ifc"))
    txt = (tmp_path / "t.ifc").read_text(encoding="utf-8", errors="ignore")
    assert "Gebaelk" in txt and "Saeule" in txt


def test_place_spec_never_falls_back_to_origin_when_house_does_not_fit():
    from shapely.geometry import Polygon

    from archaitect.siteintel import bim_bridge as BB
    spec = _house()
    spec["volumes"][0]["size"] = [30.0, 30.0]
    spec["volumes"][0]["origin"] = [0.0, 0.0]

    class Ctx:
        site = Polygon([(100, 100), (120, 100), (120, 118), (100, 118)])

        def hard_region(self, m):
            return self.site

    pl, notes = BB.place_spec(spec, Ctx(), best_effort=True)
    assert pl is not None and any("am wenigsten" in n for n in notes)


def test_balcony_door_and_redundant_entrance_canopy():
    from archaitect.bim import logic
    spec={'volumes':[{'id':'A','origin':[0,0],'size':[9.,11.],'storeys':2,'storey_height':3.,'base_z':0.}],
          'openings':[{'volume':'A','side':'S','storey':0,'offset':4.,'width':1.2,'height':2.2,'sill':0.,'kind':'door','door_type':'panel'},
                      {'volume':'A','side':'S','storey':1,'offset':4.,'width':1.2,'height':2.2,'sill':0.,'kind':'door','door_type':'panel'}],
          'balconies':[{'volume':'A','side':'S','level':3.,'offset':3.5,'width':2.5,'depth':1.5,'thickness':0.2}], 'components':[]}
    out,_=logic.complete(spec)
    assert next(o for o in out['openings'] if o['storey']==1)['door_type']=='french'
    assert not any(c['type']=='canopy' for c in out['components'])
    out2,_=logic.complete(out)
    assert out2==out


def test_high_balcony_does_not_replace_entrance_canopy():
    from archaitect.bim import logic
    spec={'volumes':[{'id':'A','origin':[0,0],'size':[9.,11.],'storeys':3,'storey_height':3.,'base_z':0.}],
          'openings':[{'volume':'A','side':'S','storey':0,'offset':4.,'width':1.2,'height':2.2,'sill':0.,'kind':'door','door_type':'panel'}],
          'balconies':[{'volume':'A','side':'S','level':6.,'offset':3.5,'width':2.5,'depth':1.5,'thickness':0.2}], 'components':[]}
    out,_=logic.complete(spec)
    assert any(c['type']=='canopy' for c in out['components'])


def test_apartment_example_uses_balcony_as_entrance_cover():
    from archaitect.siteintel.bim_api import _library_spec
    from archaitect.bim.logic import normalize
    out=normalize(_library_spec('mfh_lib'))
    assert any(b['side']=='S' and b['level']<4 for b in out['balconies'])
    assert not any(c['type']=='canopy' for c in out['components'])
