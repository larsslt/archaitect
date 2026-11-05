"""Logic layer: balconies/terraces/stairs get doors, canopies clear the door, audit warnings."""
from archaitect.bim.expand import expand_spec
from archaitect.bim.interpret import validate_spec
from archaitect.bim.logic import audit, complete, normalize
from .test_catalog import one_house, win

FLAT = {"type": "flat"}


def bal(**kw):
    b = {"volume": "A", "side": "S", "level": 3.0, "offset": 2.0, "width": 3.0, "depth": 1.5, "thickness": 0.2}
    b.update(kw)
    return b


def doors(spec, storey=None):
    return [o for o in spec["openings"] if o["kind"] == "door" and (storey is None or o["storey"] == storey)]


def test_balcony_without_opening_gets_french_door():
    spec = one_house(roof=FLAT, storeys=2, size=(10.0, 8.0))
    spec["balconies"] = [bal()]
    out, notes = complete(spec)
    d = doors(out, 1)
    assert len(d) == 1 and d[0]["door_type"] == "french" and 2.0 <= d[0]["offset"] and d[0]["offset"] + d[0]["width"] <= 5.0
    assert notes and "Balkon" in notes[0] and out["auto_notes"]


def test_window_mostly_inside_balcony_becomes_door():
    spec = one_house(roof=FLAT, storeys=2, size=(10.0, 8.0), openings=[win(storey=1, offset=2.8, width=1.2)])
    spec["balconies"] = [bal()]
    out, _ = complete(spec)
    assert len(out["openings"]) == 1 and out["openings"][0]["kind"] == "door"


def test_window_barely_touching_balcony_stays_and_door_is_added():
    spec = one_house(roof=FLAT, storeys=2, size=(10.0, 8.0), openings=[win(storey=1, offset=4.7, width=1.2)])
    spec["balconies"] = [bal()]
    out, _ = complete(spec)
    assert len(out["openings"]) == 2 and any(o["kind"] == "window" for o in out["openings"])


def test_existing_door_is_kept_and_complete_is_idempotent():
    d = {"volume": "A", "side": "S", "storey": 1, "offset": 2.5, "width": 1.0, "height": 2.2, "sill": 0.0, "kind": "door"}
    spec = one_house(roof=FLAT, storeys=2, size=(10.0, 8.0), openings=[d])
    spec["balconies"] = [bal()]
    out, notes = complete(spec)
    assert out["openings"] == spec["openings"] and not notes
    once = normalize(one_house(roof=FLAT, storeys=2, size=(10.0, 8.0)) | {"balconies": [bal()]})
    assert normalize(once) == once


def test_terrace_steps_and_ramp_get_entrance_doors():
    comps = [{"type": "terrace", "volume": "A", "side": "S", "u": 3.0, "width": 4.0},
             {"type": "steps", "volume": "A", "side": "N", "u": 4.0, "width": 1.6},
             {"type": "ramp", "volume": "A", "side": "E", "u": 4.0, "width": 1.5, "length": 4.0, "height": 0.3}]
    out, _ = complete(one_house(roof=FLAT, size=(10.0, 8.0), components=comps))
    sides = {o["side"] for o in doors(out, 0)}
    assert sides == {"S", "N", "E"}


def test_external_stair_snaps_to_floor_and_adds_landing_door():
    comp = {"type": "stair_ext", "volume": "A", "side": "S", "u": 1.0, "z1": 2.7}
    out, notes = complete(one_house(roof=FLAT, storeys=2, size=(14.0, 8.0), components=[comp]))
    assert out["components"][0]["z1"] == 3.0
    assert doors(out, 1) and any("Podest" in n for n in notes)


def test_canopy_is_raised_above_door():
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 3.0, "width": 1.2, "height": 2.6, "sill": 0.0, "kind": "door"}
    c = {"type": "canopy", "volume": "A", "side": "S", "u": 3.6, "z": 2.4}
    out, _ = complete(one_house(roof=FLAT, size=(10.0, 8.0), openings=[d], components=[c]))
    assert out["components"][0]["z"] >= 2.75


def test_audit_flags_overlaps_and_missing_entrance():
    spec = one_house(roof=FLAT, openings=[win(offset=1.0, width=2.0), win(offset=2.0, width=2.0)])
    w = audit(spec)
    assert any("überlappen" in x for x in w) and any("Kein Eingang" in x for x in w)


def test_validated_spec_with_balcony_builds_with_door():
    spec = one_house(roof=FLAT, storeys=2, size=(10.0, 8.0))
    spec["balconies"] = [bal()]
    assert validate_spec(spec) == []
    assert any(o.get("auto") for o in normalize(spec)["openings"])


def test_new_stage4_components_build_and_loggia_gets_door():
    comps = [{"type": "loggia", "volume": "A", "side": "S", "storey": 1, "u": 4.0},
             {"type": "buttress", "volume": "A", "side": "N", "count": 3, "pitch": 3.0},
             {"type": "pylon", "x": -5.0, "y": -5.0},
             {"type": "parking", "x": -12.0, "y": -10.0, "spaces": 5}]
    spec = one_house(roof=FLAT, storeys=2, size=(12.0, 8.0), components=comps)
    assert validate_spec(spec) == []
    assert any(o.get("auto") and o["storey"] == 1 for o in normalize(spec)["openings"])


def test_stage4_errors_are_repair_hints():
    for comp, hint in [({"type": "parking", "x": 0.0, "y": 0.0, "spaces": 20, "width": 10.0}, "schmal"),
                       ({"type": "pylon"}, "Pflicht"),
                       ({"type": "buttress", "volume": "A", "count": 10, "pitch": 5.0}, "außerhalb")]:
        probs = validate_spec(one_house(roof=FLAT, storeys=2, size=(12.0, 8.0), components=[comp]))
        assert probs and hint in " ".join(probs), comp
