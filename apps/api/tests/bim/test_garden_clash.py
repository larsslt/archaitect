"""Clash resolution (parts vs openings) and garden objects."""
import pytest

from archaitect.bim.interpret import validate_spec
from archaitect.bim.logic import audit, complete, normalize
from .test_catalog import classes, one_house, win

FLAT = {"type": "flat"}


def test_downpipe_moves_clear_of_window():
    spec = one_house(roof=FLAT, openings=[win(offset=1.0, width=1.2)], components=[{"type": "downpipe", "volume": "A", "side": "S", "u": 1.5}])
    out, notes = complete(spec)
    u = out["components"][0]["u"]
    assert not (1.0 - 0.1 < u < 2.2 + 0.1) and notes


def test_part_without_free_space_is_removed_with_note():
    wins = [win(offset=0.4 + k * 1.4, width=1.2) for k in range(5)]  # wall almost completely open
    out, notes = complete(one_house(roof=FLAT, openings=wins, components=[{"type": "pilaster", "volume": "A", "side": "S", "u": 3.0, "width": 0.4, "z0": 0.0}]))
    assert not [c for c in out["components"] if c["type"] == "pilaster"] and any("entfernt" in n for n in notes)


def test_untouched_group_stays_one_component():
    comps = [{"type": "column", "volume": "A", "side": "S", "u": 4.0, "count": 2, "spacing": 2.0, "z1": 3.0}]
    out, notes = complete(one_house(roof=FLAT, components=comps))
    assert out["components"][0].get("count") == 2 and not notes


def test_overlapping_windows_are_resolved():
    out, notes = complete(one_house(roof=FLAT, openings=[win(offset=1.0, width=2.0), win(offset=2.0, width=2.0)], size=(10.0, 6.0)))
    assert len(out["openings"]) == 2
    assert audit(out) == [w for w in audit(out) if "überlappen" not in w]
    assert notes


def test_door_wins_over_window():
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 2.0, "width": 1.2, "height": 2.2, "sill": 0.0, "kind": "door"}
    out, _ = complete(one_house(roof=FLAT, openings=[win(offset=1.0, width=1.5), d], size=(10.0, 6.0)))
    assert any(o["kind"] == "door" and o["offset"] == 2.0 for o in out["openings"])
    ws = [o for o in out["openings"] if o["kind"] == "window"]
    assert not ws or ws[0]["offset"] + ws[0]["width"] <= 2.0 - 0.1


def test_canopy_is_clipped_beside_window():
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 3.0, "width": 1.2, "height": 2.1, "sill": 0.0, "kind": "door"}
    w = win(offset=4.6, width=1.2, sill=2.2, height=0.6)
    c = {"type": "canopy", "volume": "A", "side": "S", "u": 3.6, "width": 3.6, "z": 2.4}
    out, notes = complete(one_house(roof=FLAT, openings=[d, w], components=[c], size=(10.0, 6.0)))
    cc = out["components"][0]
    assert cc["u"] + cc["width"] / 2 <= 4.6 - 0.05


def test_bay_removes_windows_behind():
    c = {"type": "bay", "volume": "A", "side": "S", "u": 2.0, "width": 2.4}
    out, notes = complete(one_house(roof=FLAT, openings=[win(offset=1.4, width=1.2)], components=[c], size=(10.0, 6.0)))
    assert not out["openings"] and notes


def test_window_stays_below_cornice():
    c = {"type": "cornice", "volume": "A", "side": "all", "height": 0.5}
    w = win(sill=0.8, height=2.2)  # top 3.0 = storey height
    out, _ = complete(one_house(roof=FLAT, openings=[w], components=[c]))
    assert out["openings"][0]["sill"] + out["openings"][0]["height"] <= 3.0 - 0.5


@pytest.mark.parametrize("comp", [
    {"type": "tree", "x": 12.0, "y": 3.0, "height": 8.0, "crown_radius": 3.0},
    {"type": "tree", "x": 12.0, "y": 3.0, "height": 6.0, "crown_radius": 1.4, "kind": "conifer"},
    {"type": "hedge", "x0": 0.0, "y0": -5.0, "x1": 10.0, "y1": -5.0},
    {"type": "shrub", "x": 11.0, "y": 1.0, "pot": True},
    {"type": "flowerbed", "x": 0.0, "y": -4.0},
    {"type": "path", "points": [[3.0, -6.0], [3.0, -2.0], [8.0, -2.0]]},
    {"type": "pool", "x": 12.0, "y": -8.0},
    {"type": "bench", "x": 12.0, "y": 1.0},
    {"type": "garden_set", "x": 13.0, "y": 3.0},
    {"type": "garden_light", "x": 11.0, "y": -3.0, "count": 3, "axis": "x"},
])
def test_garden_objects_build(comp):
    spec = one_house(roof=FLAT, components=[comp], size=(8.0, 6.0))
    assert validate_spec(spec) == []


@pytest.mark.parametrize("comp,hint", [
    ({"type": "tree"}, "Pflicht"),
    ({"type": "tree", "x": 0.0, "y": 0.0, "height": 3.0, "crown_radius": 2.5}, "Stamm"),
    ({"type": "path", "points": [[0.0, 0.0], [3.0, 0.0], [6.0, 0.0]]}, "Richtung"),
    ({"type": "path", "points": [[0.0, 0.0], [3.0, 2.0]]}, "achsparallel"),
    ({"type": "hedge", "x0": 0.0, "y0": 0.0, "x1": 3.0, "y1": 3.0}, "achsparallel"),
])
def test_garden_errors_are_repair_hints(comp, hint):
    probs = validate_spec(one_house(roof=FLAT, components=[comp], size=(8.0, 6.0)))
    assert probs and hint in " ".join(probs)


def test_garden_object_inside_building_is_flagged():
    spec = one_house(roof=FLAT, components=[{"type": "bench", "x": 2.0, "y": 2.0}], size=(8.0, 6.0))
    assert any("Gebäude" in w for w in audit(spec))


def test_garden_spec_is_valid():
    import json
    from pathlib import Path
    s = json.loads((Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent / "specs" / "garten.json").read_text(encoding="utf-8"))
    assert validate_spec(s) == [] and audit(normalize(s)) == []
