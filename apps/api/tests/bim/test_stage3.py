"""Stage 3: compact openings, typologies, modern components, sawtooth roof, railing types, french door."""
import json
from pathlib import Path

import pytest

from archaitect.bim import catalog, library, typologies
from archaitect.bim.expand import expand_openings, expand_spec
from archaitect.bim.interpret import validate_spec, _system
from .test_catalog import one_house, win, classes

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent


# ---------------------------------------------------------------- compact notation
def test_storeys_and_repeat_expand_to_plain_openings():
    o = win(width=1.0)
    o.pop("storey", None)
    out = expand_openings([{**o, "storeys": [0, 1], "repeat": {"count": 3, "pitch": 2.0}}])
    assert len(out) == 6 and {x["storey"] for x in out} == {0, 1}
    assert sorted({x["offset"] for x in out}) == [o["offset"], o["offset"] + 2.0, o["offset"] + 4.0]
    assert all("repeat" not in x and "storeys" not in x for x in out)


def test_expand_is_idempotent_and_does_not_mutate_input():
    spec = one_house(openings=[{**win(), "repeat": {"count": 2, "pitch": 2.5}}])
    once = expand_spec(spec)
    assert "repeat" in spec["openings"][0] and len(once["openings"]) == 2
    assert expand_spec(once) == once


def test_repeat_pitch_smaller_than_width_is_a_repair_hint():
    probs = validate_spec(one_house(openings=[{**win(width=1.2), "repeat": {"count": 3, "pitch": 1.0}}]))
    assert probs and "pitch" in " ".join(probs)


def test_compact_spec_validates_and_builds():
    assert validate_spec(one_house(openings=[{**win(width=1.0), "repeat": {"count": 2, "pitch": 3.0}}])) == []


# ---------------------------------------------------------------- typologies and prompt
def test_typology_keys_are_in_prompt_and_schema():
    t = typologies.prompt_table()
    assert all(f"- {k}:" in t for k in typologies.KEYS)
    assert len(typologies.KEYS) >= 50
    assert {'bauhaus_haus','backsteinhaus_nord','reetdach_friesenhaus','alpenhaus_chalet'} <= set(typologies.KEYS)
    assert {'hotel','windmuehle','burg_schloss','moschee_pagode','sporthalle'} <= set(typologies.KEYS)
    assert "building_type" in _system()


def test_typology_recipes_only_name_existing_components_and_roofs():
    known = set(catalog.types()) | {"cornice"}
    for k, d in typologies.T.items():
        for word in ("technical_box", "solar", "ramp", "terrace", "carport", "retaining_wall", "stair_ext"):
            pass
        assert d["label"] and d["cues"] and d["recipe"], k
    assert {"solar", "technical_box", "ramp", "terrace", "carport", "retaining_wall", "stair_ext"} <= known


def test_materials_table_is_grouped_and_complete():
    t = library.prompt_table()
    for k in ("solar_panel", "metal_corrugated", "glass_curtain_blue", "roof_sedum", "fibre_cement_grey"):
        assert f"{k}=" in t
    assert library.problems() == []


# ---------------------------------------------------------------- spec 3
def test_modern_types_spec_is_valid():
    spec = json.loads((ROOT / "specs" / "moderne_typen.json").read_text(encoding="utf-8"))
    assert validate_spec(spec) == []


# ---------------------------------------------------------------- components
FLAT = {"type": "flat"}


@pytest.mark.parametrize("comp", [
    {"type": "solar", "mode": "flat", "cols": 3, "rows": 2},
    {"type": "technical_box", "width": 2.0, "depth": 1.5},
    {"type": "ramp", "side": "S", "width": 1.5, "length": 5.0, "height": 0.3},
    {"type": "terrace", "side": "S", "railing": "glass"},
    {"type": "terrace", "side": "S", "railing": "bars"},
    {"type": "terrace", "side": "S", "railing": "cable"},
    {"type": "terrace", "side": "S", "railing": "solid"},
    {"type": "carport", "side": "E", "kind": "shed"},
    {"type": "stair_ext", "side": "S", "z1": 3.0},
])
def test_stage3_components_build(comp):
    spec = one_house(roof=FLAT, components=[{"volume": "A", **comp}], size=(12.0, 9.0), storeys=1)
    assert validate_spec(spec) == []


def test_retaining_wall_builds_without_volume():
    spec = one_house(roof=FLAT, components=[{"type": "retaining_wall", "x0": -5.0, "y0": -4.0, "x1": 5.0, "y1": -4.0}])
    assert validate_spec(spec) == []
    assert "IfcWall" in classes(spec)


def test_pitched_solar_on_gable():
    spec = one_house(roof={"type": "gable", "ridge": "x", "pitch_deg": 30, "overhang": 0.4}, size=(12.0, 8.0),
                     components=[{"type": "solar", "volume": "A", "mode": "pitched", "slope": "S", "cols": 4, "rows": 2}])
    assert validate_spec(spec) == []


@pytest.mark.parametrize("comp,hint", [
    ({"type": "ramp", "side": "S", "length": 2.0, "height": 0.5}, "steil"),
    ({"type": "solar", "mode": "flat", "cols": 30, "rows": 12}, "passt nicht"),
    ({"type": "stair_ext", "side": "S", "z1": 3.0, "u": 7.0}, "Fassade"),
    ({"type": "retaining_wall", "x0": 0.0, "y0": 0.0, "x1": 3.0}, "Pflicht"),
    ({"type": "retaining_wall", "x0": 0.0, "y0": 0.0, "x1": 3.0, "y1": 3.0}, "achsparallel"),
])
def test_stage3_errors_are_repair_hints(comp, hint):
    c = {"volume": "A", **comp}
    probs = validate_spec(one_house(roof=FLAT, components=[c], size=(8.0, 6.0), storeys=1))
    assert probs and hint in " ".join(probs)


# ---------------------------------------------------------------- roofs, doors, railings
def test_sawtooth_roof():
    spec = one_house(roof={"type": "sawtooth", "teeth": 4, "pitch_deg": 14}, size=(20.0, 16.0))
    assert validate_spec(spec) == []
    c = classes(spec)
    assert any(e.PredefinedType == "SKYLIGHT" for e in c["IfcWindow"])


def test_sawtooth_too_steep_is_hint():
    probs = validate_spec(one_house(roof={"type": "sawtooth", "teeth": 2, "pitch_deg": 25}, size=(20.0, 30.0)))
    assert probs and "Sheddach" in " ".join(probs)


def test_french_door_and_glass_override():
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 2.0, "width": 2.0, "height": 2.3, "sill": 0.0, "kind": "door", "door_type": "french"}
    assert validate_spec(one_house(openings=[d, win(offset=5.0, glass="glass_curtain_blue", window_type="fixed")])) == []


@pytest.mark.parametrize("rt", ["rails", "bars", "glass", "solid", "cable"])
def test_balcony_railing_types(rt):
    spec = one_house(roof=FLAT, size=(10.0, 8.0))
    spec["balconies"] = [{"volume": "A", "side": "S", "level": 3.0, "offset": 2.0, "width": 3.0, "depth": 1.5, "thickness": 0.2,
                          "railing": {"type": rt, "height": 1.0, "sides": ["front", "left", "right"], "post_spacing": 0.5, "handrail_d": 0.04, "rail_d": 0.02, "rails_at": [0.5]}}]
    assert validate_spec(spec) == []
    assert "IfcRailing" in classes(spec)
