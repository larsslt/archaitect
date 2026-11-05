"""Regression tests for the failed house generation ("build: ('A', 'S', 1)", Nov 2026).

Cause: a model answer put a terrace on the roof of a one-storey volume (z = 3.0 m); logic.complete() derived storey 1 from z and
created an automatic door in a wall that does not exist. Fixed in logic.py (no door, note instead); references are now checked
before the IFC build, every model answer is stored, and one budget limits all model calls."""
import copy
import json
import time

import pytest

from archaitect.bim import interpret
from archaitect.bim.interpret import Budget, BudgetExhausted, check_references, validate_spec
from archaitect.bim.logic import complete


def base_spec():
    return {
        "spec_version": 1, "name": "Test", "description": "t", "assumptions": [],
        "levels": [{"name": "EG", "elevation": 0.0}, {"name": "Dach", "elevation": 3.0}],
        "storey_height": 3.0, "slab_thickness": 0.3,
        "defaults": {"wall_thickness": 0.3, "parapet_height": 0.6,
                     "window": {"frame_width": 0.06, "frame_depth": 0.08, "reveal_depth": 0.12,
                                "glass": "glass_clear", "frame": "alu_anthracite", "sill_board": True}},
        "building_type": "moderner_kubus",
        "volumes": [{"id": "A", "name": "EG", "origin": [0, 0], "size": [6, 4], "base_z": 0.0, "storeys": 1,
                     "storey_height": 3.0, "wall_thickness": 0.3, "facade": "plaster_white",
                     "roof": {"type": "flat", "overhang": 0.3, "material": "roof_bitumen"}}],
        "openings": [{"volume": "A", "side": "S", "storey": 0, "offset": 0.5, "width": 2.0, "height": 2.2, "sill": 0.0,
                      "kind": "window", "window_type": "fixed", "glass": "glass_clear"}],
        "components": [],
    }


ROOF_TERRACE = {"type": "terrace", "volume": "A", "side": "S", "u": 3.0, "width": 4.0, "depth": 1.4, "z": 3.0,
                "thickness": 0.15, "material": "terrace_decking", "railing": "glass"}


def test_minimal_spec_is_valid():
    assert validate_spec(base_spec()) == []


def test_terrace_on_roof_of_one_storey_volume_builds_without_auto_door():
    """The exact failing case: terrace at z=3.0 on a 1-storey volume. Used to raise KeyError ('A','S',1)."""
    spec = base_spec()
    spec["components"].append(copy.deepcopy(ROOF_TERRACE))
    assert validate_spec(spec) == []
    done, notes = complete(copy.deepcopy(spec))
    assert not [o for o in done["openings"] if o.get("storey", 0) >= 1], "no door may be placed at a storey without a wall"
    assert any("Terrasse" in n and "keine Tür" in n for n in notes), notes


def test_terrace_at_storey_with_wall_still_gets_its_door():
    spec = base_spec()
    spec["volumes"][0]["storeys"] = 2
    spec["levels"].append({"name": "OG", "elevation": 6.0})
    t = copy.deepcopy(ROOF_TERRACE)
    t["z"] = 3.0
    spec["components"].append(t)
    done, _ = complete(copy.deepcopy(spec))
    assert [o for o in done["openings"] if o["volume"] == "A" and o["side"] == "S" and o.get("storey") == 1]
    assert validate_spec(spec) == []


def test_check_references_names_unknown_volume_and_side_and_storey():
    spec = base_spec()
    spec["openings"] += [
        {**spec["openings"][0], "volume": "Z"},
        {**spec["openings"][0], "side": "Q"},
        {**spec["openings"][0], "storey": 1, "offset": 3.0},
    ]
    msgs = check_references(spec)
    text = "\n".join(msgs)
    assert len(msgs) >= 3
    assert "Z" in text and "Q" in text
    assert "0" in text  # the valid storey range is named so the model can repair it


def test_wrong_opening_reference_is_reported_before_the_ifc_build():
    spec = base_spec()
    spec["openings"].append({**spec["openings"][0], "storey": 2, "offset": 3.0})
    problems = validate_spec(spec)
    assert problems and not any(p.startswith("build:") for p in problems), problems


def test_gable_walls_only_exist_on_gable_sides():
    spec = base_spec()
    spec["volumes"][0]["roof"] = {"type": "gable", "pitch": 35, "ridge": "x", "overhang": 0.3, "material": "roof_tiles"}
    walls, _ = interpret._volume_walls(spec["volumes"][0])
    assert 0 in walls


def test_unexpected_build_error_keeps_type_and_location(monkeypatch):
    class Boom:
        def __init__(self, spec): pass
        def build(self): raise KeyError(("A", "S", 1))
    from archaitect.bim import ifcgen
    monkeypatch.setattr(ifcgen, "Builder", Boom)
    problems = validate_spec(base_spec())
    assert problems and "KeyError" in problems[-1] and ".py" in problems[-1], problems


# ---------------------------------------------------------------- budget
def test_budget_limits_calls_and_time():
    b = Budget(seconds=100, calls=2)
    assert b.take("generate") <= 100
    b.take("repair1")
    with pytest.raises(BudgetExhausted):
        b.take("repair2")
    t = Budget(seconds=10, calls=5)
    with pytest.raises(BudgetExhausted):
        t.take("generate", min_seconds=20)


def test_budget_timeout_shrinks_with_time_used():
    b = Budget(seconds=100, calls=3)
    first = b.take("a")
    time.sleep(0.05)
    assert b.take("b") < first


# ---------------------------------------------------------------- interpret: diagnostics + targeted repair of invalid answers
def fake_llm(monkeypatch, answers):
    monkeypatch.setenv("BIMRENDER_LLM_URL", "https://example.invalid")
    seen = []

    def llm(messages, budget=None, phase="llm"):
        seen.append([m for m in messages])
        interpret._TL.meta = {"model": "test-model", "finish_reason": "stop", "usage": {"total_tokens": 1}, "seconds": 0.0}
        if budget is not None:
            budget.take(phase, min_seconds=0)
        return json.dumps(answers.pop(0))
    monkeypatch.setattr(interpret, "_llm", llm)
    return seen


def test_invalid_answer_gets_one_targeted_repair_and_all_answers_are_stored(monkeypatch, tmp_path):
    bad = base_spec()
    bad["openings"].append({**bad["openings"][0], "storey": 1, "offset": 3.0})
    good = base_spec()
    seen = fake_llm(monkeypatch, [bad, good])
    res = interpret.interpret("Haus", out_dir=tmp_path, repair_rounds=1, budget=Budget(seconds=270, calls=4))
    assert res["status"] == "ok"
    assert len(seen) == 2
    repair_prompt = seen[1][-1]["content"]
    assert "gezielt korrigieren" in repair_prompt and "Geschoss" in repair_prompt
    files = sorted((tmp_path / "diagnostics").glob("*.json"))
    assert [f.name.split("_", 1)[1] for f in files] == ["generate.json", "repair1.json"]
    first = json.loads(files[0].read_text())
    assert first["status"] == "invalid" and first["problems"] and first["raw_answer"]
    assert first["meta"]["model"] == "test-model"
    assert "key" not in json.dumps(first).lower().replace("keyword", "")


def test_still_invalid_after_budgeted_repair_returns_problems_and_diagnostics(monkeypatch, tmp_path):
    bad = base_spec()
    bad["openings"].append({**bad["openings"][0], "storey": 1, "offset": 3.0})
    fake_llm(monkeypatch, [copy.deepcopy(bad), copy.deepcopy(bad)])
    res = interpret.interpret("Haus", out_dir=tmp_path, repair_rounds=1, budget=Budget(seconds=270, calls=4))
    assert res["status"] == "invalid" and res["problems"] and res["diagnostics"]


def test_exhausted_call_budget_stops_repairs(monkeypatch, tmp_path):
    bad = base_spec()
    bad["openings"].append({**bad["openings"][0], "storey": 1, "offset": 3.0})
    fake_llm(monkeypatch, [copy.deepcopy(bad), copy.deepcopy(bad)])
    with pytest.raises(BudgetExhausted):
        interpret.interpret("Haus", out_dir=tmp_path, repair_rounds=3, budget=Budget(seconds=270, calls=1))


def test_repair_is_skipped_when_too_little_time_is_left(monkeypatch, tmp_path):
    bad = base_spec()
    bad["openings"].append({**bad["openings"][0], "storey": 1, "offset": 3.0})
    seen = fake_llm(monkeypatch, [bad])
    res = interpret.interpret("Haus", out_dir=tmp_path, repair_rounds=2, budget=Budget(seconds=30, calls=4))
    assert res["status"] == "invalid" and len(seen) == 1
    assert any("Reparatur übersprungen" in p for p in res["problems"])


# ---------------------------------------------------------------- fit against the real free polygon (not bounding box / area)
class _Ctx:
    def __init__(self, region):
        self.region = region
        self.site = region
        self.roads = []

    def hard_region(self, massing):
        return self.region


def _l_region():
    from shapely.geometry import Polygon
    # 10 x 10 bounding box, area 64 m2, arms only 4 m wide (e.g. site minus an existing building / cut-out)
    return Polygon([(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)])


def _house(w, d):
    spec = base_spec()
    spec["volumes"][0]["size"] = [w, d]
    return spec


def test_house_fitting_bounding_box_and_area_but_not_the_polygon_is_not_placed():
    from archaitect.siteintel.bim_bridge import place_spec
    region = _l_region()
    spec = _house(6, 6)                                  # 36 m2 < 64 m2 and 6x6 inside the 10x10 box - but it covers the cut-out
    assert region.bounds[2] - region.bounds[0] >= 6 and spec["volumes"][0]["size"][0] * spec["volumes"][0]["size"][1] < region.area
    pl, notes = place_spec(spec, _Ctx(region), best_effort=False)
    assert pl is None and notes


def test_house_that_fits_the_polygon_is_placed_inside_it():
    from archaitect.siteintel.bim_bridge import place_spec, _ground_footprint
    from shapely import affinity
    region = _l_region()
    spec = _house(3.5, 6)
    pl, _ = place_spec(spec, _Ctx(region))
    assert pl is not None
    fp = _ground_footprint(spec)
    c = fp.centroid
    shape = affinity.translate(affinity.rotate(affinity.translate(fp, -c.x, -c.y), pl.rotation_deg, origin=(0, 0)), c.x, c.y)
    shape = affinity.translate(affinity.rotate(fp, pl.rotation_deg, origin=(0, 0)), pl.x, pl.y)
    assert region.buffer(0.01).covers(shape)


def test_placement_can_use_the_full_outline_incl_outer_components():
    from archaitect.siteintel.bim_bridge import place_spec
    from shapely.geometry import box
    region = _l_region()
    spec = _house(3, 3)
    pl, _ = place_spec(spec, _Ctx(region))
    assert pl is not None                                           # the bare volume fits somewhere
    pl2, notes = place_spec(spec, _Ctx(region), footprint=box(0, 0, 8, 8))   # volume + terrace/columns would not fit the L-shaped region
    assert pl2 is None and notes


def test_garden_elements_do_not_count_as_building_outline():
    from archaitect.siteintel.bim_bridge import built_parts
    parts = [{"obj": "bld:A"}, {"obj": "comp.0"}, {"obj": "comp.1"}, {"obj": "comp.2"}, {"obj": None}]
    spec = {"components": [{"type": "terrace"}, {"type": "pond"}, {"type": "hedge"}]}
    assert [p["obj"] for p in built_parts(parts, spec)] == ["bld:A", "comp.0", None]


def test_demolition_only_when_explicitly_requested():
    from archaitect.siteintel.bim_bridge import wants_demolition
    assert wants_demolition("Haus bauen, Bestand als Abriss annehmen")
    assert wants_demolition(None, "Ja, die Bestandsgebäude werden abgerissen")
    assert not wants_demolition("Modernes Haus mit Garten")
    assert not wants_demolition("Bitte ohne Abriss des Bestands planen")
    assert not wants_demolition("Der Bestand darf nicht abgerissen werden")


def test_demolished_buildings_are_not_kept_in_the_massing():
    from archaitect.siteintel.bim_bridge import spec_to_massing
    spec = base_spec()
    assert spec_to_massing(spec)[0].demolish == []
    spec["site"] = {"demolish": ["b1", "b2"]}
    assert spec_to_massing(spec)[0].demolish == ["b1", "b2"]


# ---------------------------------------------------------------- automatic shrinking and frame adaptation
def test_scale_plan_keeps_heights_and_usable_openings():
    from archaitect.siteintel.autofit import scale_plan
    spec = base_spec()
    spec["components"].append({"type": "terrace", "volume": "A", "side": "S", "u": 3.0, "width": 4.0, "depth": 1.4, "z": 0.0, "thickness": 0.15, "material": "terrace_decking", "railing": "glass"})
    small = scale_plan(spec, 0.6)
    v = small["volumes"][0]
    assert v["size"] == [3.6, 2.4] and v["storeys"] == 1 and v["storey_height"] == 3.0
    o = small["openings"][0]
    assert o["width"] >= 0.5 and o["offset"] + o["width"] <= 3.6
    assert small["components"][0]["depth"] == 1.4 and small["components"][0]["width"] == 2.4
    assert validate_spec(small) == []


def test_shrink_to_fit_finds_largest_passing_scale_and_respects_minimum():
    from archaitect.siteintel.autofit import shrink_to_fit
    spec = base_spec()
    spec["volumes"][0]["size"] = [10, 8]
    r = shrink_to_fit(spec, lambda c: c["volumes"][0]["size"][0] <= 8.2)
    assert r is not None and r[1] == 0.8
    assert shrink_to_fit(spec, lambda c: False) is None            # nothing fits -> caller asks instead of producing a doll house
    assert shrink_to_fit(spec, lambda c: c["volumes"][0]["size"][0] <= 1.0) is None   # below the usable minimum


def test_explicit_dimensions_and_storeys_are_detected():
    from archaitect.siteintel.autofit import has_explicit_dimensions, has_explicit_storeys
    assert has_explicit_dimensions("Haus 12 x 8 m") and has_explicit_dimensions("140 m² Grundfläche") and has_explicit_dimensions("10 m breit")
    assert not has_explicit_dimensions("Ein modernes Haus mit Terrasse")
    assert has_explicit_storeys("dreigeschossig mit Flachdach".replace("dreigeschossig", "3 Etagen")) and has_explicit_storeys("2-geschossig")
    assert not has_explicit_storeys("Haus mit Dachpool")


def test_reduce_to_frame_removes_top_storeys_with_their_openings():
    from archaitect.siteintel.autofit import reduce_to_frame
    spec = base_spec()
    spec["volumes"][0]["storeys"] = 4
    spec["levels"] = [{"name": f"L{i}", "elevation": 3.0 * i} for i in range(5)]
    spec["openings"].append({**spec["openings"][0], "storey": 3, "offset": 3.0})
    out, notes = reduce_to_frame(spec, 3, None, validate_spec)
    assert out["volumes"][0]["storeys"] == 3 and all(o["storey"] < 3 for o in out["openings"]) and notes
    same, none = reduce_to_frame(spec, 5, 20.0, validate_spec)
    assert same["volumes"][0]["storeys"] == 4 and not none
    h, _ = reduce_to_frame(spec, None, 9.5, validate_spec)
    assert h["volumes"][0]["storeys"] == 3


def test_small_annex_does_not_block_shrinking_the_main_volume():
    from archaitect.siteintel.autofit import candidate_scales
    spec = base_spec()
    spec["volumes"][0]["size"] = [8, 6]
    spec["volumes"].append({**spec["volumes"][0], "id": "C", "size": [5, 3.5], "origin": [9, 0]})
    scales = candidate_scales(spec)
    assert scales and scales[0] == 0.95 and scales[-1] >= 0.58     # main volume keeps a habitable short side of ~3.5 m
