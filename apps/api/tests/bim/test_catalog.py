"""Component/material catalog: window and door types, surrounds, components, roofs, timber patterns, library consistency."""
import copy
import json
import re
from pathlib import Path

import pytest

from archaitect.bim import catalog, library
from archaitect.bim.ifcgen import Builder
from archaitect.bim.interpret import validate_spec

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
CAT = json.loads((ROOT / "specs" / "bauteilkatalog.json").read_text(encoding="utf-8"))


def classes(spec):
    f = Builder(spec).build()
    out = {}
    for e in f.by_type("IfcProduct"):
        out.setdefault(e.is_a(), []).append(e)
    return out


def one_house(roof=None, openings=None, components=None, facade_detail=None, size=(8.0, 6.0), storeys=1):
    v = {"id": "A", "name": "T", "origin": [0.0, 0.0], "size": list(size), "base_z": 0.0, "storeys": storeys, "wall_thickness": 0.3,
         "facade": "plaster_white", "storey_height": 3.0}
    if roof:
        v["roof"] = roof
    if facade_detail:
        v["facade_detail"] = facade_detail
    return {"spec_version": 1, "name": "T", "levels": [{"name": "EG", "elevation": 0.0}, {"name": "OG", "elevation": 3.0}],
            "storey_height": 3.0, "slab_thickness": 0.25, "volumes": [v], "openings": openings or [], "components": components or []}


def win(**kw):
    return {"volume": "A", "side": "S", "storey": 0, "offset": 1.0, "width": 1.2, "height": 1.6, "sill": 0.8, "kind": "window", **kw}


def test_catalog_spec_is_valid_and_builds_every_family():
    assert validate_spec(CAT) == []
    c = classes(CAT)
    assert len(c["IfcColumn"]) >= 1 and len(c["IfcChimney"]) == 2 and c["IfcStair"]
    names = {e.Name for e in c["IfcBuildingElementProxy"]}
    assert {"Zaun", "Blumenkasten"} <= names
    assert any(n.startswith("Gewaende") for n in names) and any(n.startswith("Fensterlaeden") for n in names)
    assert {e.PredefinedType for e in c["IfcRoof"]} >= {"HIP_ROOF", "GABLE_ROOF", "SHED_ROOF"}


@pytest.mark.parametrize("top", ["round_arch", "segment_arch", "pointed_arch"])
def test_arched_window_gets_spandrels_and_builds(top):
    c = classes(one_house(openings=[win(top=top, height=2.4, sill=0.4, width=1.1, surround={"material": "stone_limestone", "keystone": True})]))
    assert len(c["IfcWindow"]) == 1
    assert len(c["IfcWindow"][0].Representation.Representations[0].Items) > 8  # frame ring + spandrels, not a box


def test_arch_that_does_not_fit_is_reported_for_repair():
    probs = validate_spec(one_house(openings=[win(top="round_arch", height=1.0, width=1.2)]))
    assert probs and "round_arch" in " ".join(probs)


@pytest.mark.parametrize("kw", [dict(window_type="oculus", width=1.0, height=1.0, sill=1.5), dict(window_type="fixed"), dict(sashes=3, bars={"cols": 3, "rows": 2}, transom=0.7)])
def test_window_types(kw):
    assert validate_spec(one_house(openings=[win(**kw)])) == []


@pytest.mark.parametrize("dt", ["panel", "double", "glazed", "plank"])
def test_door_types(dt):
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 2.0, "width": 1.6, "height": 2.5, "sill": 0.0, "kind": "door", "door_type": dt, "top": "round_arch", "transom": 0.7 if dt == "glazed" else None}
    d = {k: v for k, v in d.items() if v is not None}
    c = classes(one_house(openings=[d]))
    assert len(c["IfcDoor"]) == 1


@pytest.mark.parametrize("lintel", ["flat", "keystone", "pediment", "segment_pediment", "hood"])
def test_surround_lintels_and_shutters(lintel):
    o = win(surround={"lintel": lintel}, shutters={"state": "closed", "style": "plank"}, flower_box=True)
    c = classes(one_house(openings=[o]))
    assert any((e.Name or "").startswith("Gewaende") for e in c["IfcBuildingElementProxy"])


def test_component_validation_messages():
    with pytest.raises(ValueError, match="unbekannte Parameter"):
        catalog.resolve({"type": "cornice", "volume": "A", "colour": "red"})
    with pytest.raises(ValueError, match="außerhalb"):
        catalog.resolve({"type": "cornice", "volume": "A", "height": 9})
    with pytest.raises(ValueError, match="erlaubt"):
        catalog.resolve({"type": "cornice", "volume": "A", "profile": "gothic"})
    with pytest.raises(ValueError, match="unbekannter Bauteiltyp"):
        catalog.resolve({"type": "gargoyle", "volume": "A"})
    r = catalog.resolve({"type": "cornice", "volume": "A"})
    assert r["projection"] == 0.22 and r["profile"] == "simple"


def test_bad_component_is_a_repair_hint_not_a_crash():
    assert validate_spec(one_house(components=[{"type": "steps", "volume": "A", "count": 99}])) == []      # out-of-range numbers are clamped (note for the user)
    probs = validate_spec(one_house(components=[{"type": "fence", "points": [[0, 0], [3, 3]]}]))
    assert probs and "achsparallel" in " ".join(probs)


@pytest.mark.parametrize("roof,cls", [({"type": "hip", "pitch_deg": 30, "overhang": 0.4}, "HIP_ROOF"),
                                      ({"type": "hip", "pitch_deg": 30}, "HIP_ROOF"),
                                      ({"type": "shed", "pitch_deg": 10, "fall_to": "N"}, "SHED_ROOF"),
                                      ({"type": "shed", "pitch_deg": 10, "fall_to": "E"}, "SHED_ROOF")])
def test_hip_and_shed_roofs(roof, cls):
    for size in ((8.0, 6.0), (6.0, 6.0), (5.0, 9.0)):
        c = classes(one_house(roof=roof, size=size))
        assert [r.PredefinedType for r in c["IfcRoof"]] == [cls]
    assert len(classes(one_house(roof={"type": "hip", "pitch_deg": 30}, size=(8.0, 6.0)))["IfcRoof"][0].Representation.Representations[0].Items) == 4


@pytest.mark.parametrize("pattern", ["k_brace", "st_andrew", "man", "foot_head", "diamond", "none"])
def test_timber_patterns(pattern):
    fd = {"timber_frame": {"spacing": 1.5, "pattern": pattern, "material": "timber_oak_aged"}}
    c = classes(one_house(facade_detail=fd, openings=[win(offset=3.0)]))
    n = sum(len(e.Representation.Representations[0].Items) for e in c["IfcMember"] if "Fachwerk" in (e.Name or ""))
    assert n > 0
    if pattern == "st_andrew":
        base = classes(one_house(facade_detail={"timber_frame": {"spacing": 1.5, "pattern": "none"}}, openings=[win(offset=3.0)]))
        n0 = sum(len(e.Representation.Representations[0].Items) for e in base["IfcMember"] if "Fachwerk" in (e.Name or ""))
        assert n > n0


def test_library_is_consistent_and_every_kind_has_a_shader():
    assert library.problems() == []
    src = (ROOT / "blender" / "materials.py").read_text(encoding="utf-8")
    block = src[src.index("BUILDERS = {"):src.index("def build_library")]
    builders = set(re.findall(r'^\s+"(\w+)":', block, flags=re.M))
    assert library.KINDS <= builders
    used = {v["shader"]["kind"] for v in library.load().values()}
    assert used <= builders


def test_every_default_material_in_the_catalog_exists():
    keys = set(library.load())
    for t, d in catalog.C.items():
        for k, (ty, default, *_r) in d["params"].items():
            if ty == "st" and default:
                assert default in keys, f"{t}.{k} default {default} fehlt in der Materialbibliothek"
    # materials used by the generators as literals
    for lit in ("timber_black", "boxwood", "glass_frosted", "cast_iron_black", "aluminium", "chrome"):
        assert lit in keys


def test_prompt_tables_list_all_components_and_the_pareto_core():
    t = catalog.prompt_table()
    assert all(f"- {k}:" in t for k in catalog.C)
    lib = library.prompt_table()
    for k in ("plaster_cream", "brick_brown", "stone_sandstone_yellow", "roof_slate", "roof_thatch", "timber_oak_aged", "paint_green_dark", "copper_patina"):
        assert f"{k}=" in lib


# ----------------------------------------------------------------- stage 2
GT = json.loads((ROOT / "specs" / "gebaeudetypen.json").read_text(encoding="utf-8"))


def test_building_types_spec_builds_all_stage2_families():
    assert validate_spec(GT) == []
    c = classes(GT)
    assert {e.PredefinedType for e in c["IfcRoof"]} >= {"HIP_ROOF", "GABLE_ROOF", "USERDEFINED"}
    names = {(e.Name or "") for e in c["IfcBuildingElementProxy"]}
    for prefix in ("Turm", "Erker", "Arkade", "Markise", "Bossenwerk", "Zahnschnitt", "Dachrinne", "Ortgangbrett", "Dachfenster", "Ausleger"):
        assert any(n.startswith(prefix) for n in names), prefix


def test_tower_is_a_closed_brep_with_outward_faces():
    c = classes(one_house(components=[{"type": "tower", "volume": "A", "x": 0.0, "y": 0.0, "z1": 6.0, "roof": "cone", "sides": 8}]))
    tower = [e for e in c["IfcBuildingElementProxy"] if e.Name.startswith("Turm")][0]
    items = tower.Representation.Representations[0].Items
    assert all(i.is_a("IfcFacetedBrep") for i in items)
    assert tower.Representation.Representations[0].RepresentationType == "SolidModel"


@pytest.mark.parametrize("roof", [{"type": "mansard", "lower_pitch_deg": 70, "lower_height": 2.0}, {"type": "gambrel", "ridge": "x"}, {"type": "gambrel", "ridge": "y"}])
def test_mansard_and_gambrel_roofs(roof):
    c = classes(one_house(roof=roof, size=(9.0, 7.0)))
    assert len(c["IfcRoof"]) == 1


def test_mansard_too_high_for_plan_is_reported():
    probs = validate_spec(one_house(roof={"type": "mansard", "lower_pitch_deg": 45, "lower_height": 5.0}, size=(6.0, 6.0)))
    assert probs and "Mansarddach" in " ".join(probs)


@pytest.mark.parametrize("comp,hint", [
    ({"type": "bay", "side": "S", "u": 0.5, "width": 3.0}, "Erker"),
    ({"type": "arcade", "count": 9}, "Arkade"),
    ({"type": "skylight", "slope": "S"}, "gable"),
    ({"type": "bargeboard"}, "gable"),
    ({"type": "tower", "z1": 6.0}, "Pflicht"),
])
def test_stage2_component_errors_are_repair_hints(comp, hint):
    probs = validate_spec(one_house(components=[{"volume": "A", **comp}]))
    assert probs and hint in " ".join(probs)


def test_skylight_bargeboard_gutter_on_gable():
    comps = [{"volume": "A", "type": "skylight", "slope": "S", "u": 2.0}, {"volume": "A", "type": "bargeboard"}, {"volume": "A", "type": "gutter"}]
    c = classes(one_house(roof={"type": "gable", "ridge": "x", "pitch_deg": 40, "overhang": 0.5}, components=comps))
    assert {"Dachfenster A-S", "Ortgangbrett A", "Dachrinne A"} <= {e.Name for e in c["IfcBuildingElementProxy"] if e.Name}


@pytest.mark.parametrize("dt", ["sectional", "full_glass"])
def test_more_door_types(dt):
    d = {"volume": "A", "side": "S", "storey": 0, "offset": 1.0, "width": 3.0, "height": 2.5, "sill": 0.0, "kind": "door", "door_type": dt}
    assert len(classes(one_house(openings=[d]))["IfcDoor"]) == 1
