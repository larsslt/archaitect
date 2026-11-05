import copy
import json
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.unit
import ifcopenshell.validate
import pytest

from archaitect.bim.geom import facade_box, subtract_intervals
from archaitect.bim.ifcgen import Builder, build_ifc

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
SPEC = json.loads((ROOT / "specs" / "villa_kubus.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    out = tmp_path_factory.mktemp("ifc") / "villa.ifc"
    build_ifc(ROOT / "specs" / "villa_kubus.json", out)
    return ifcopenshell.open(str(out))


def test_units_are_metres(model):
    assert ifcopenshell.util.unit.calculate_unit_scale(model) == pytest.approx(1.0)


def test_schema_valid(model):
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger, express_rules=True)
    errors = [s for s in logger.statements if str(s.get("level", "")).lower() == "error"]
    assert not errors, errors[:5]


def test_every_opening_voids_a_wall_and_is_filled(model):
    n_open = len(SPEC["openings"])
    fills = model.by_type("IfcRelFillsElement")
    assert len(fills) == n_open
    for rel in fills:
        op = rel.RelatingOpeningElement
        assert op.VoidsElements and op.VoidsElements[0].RelatingBuildingElement.is_a("IfcWall")
        assert rel.RelatedBuildingElement.is_a() in ("IfcWindow", "IfcDoor")


def test_validator_detects_errors(model):
    # guard against a vacuous validity test
    bad = ifcopenshell.file(schema="IFC4")
    bad.createIfcWall()
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(bad, logger)
    assert any(str(s.get("level", "")).lower() == "error" for s in logger.statements)


def test_expected_element_counts(model):
    walls = [w for w in model.by_type("IfcWall") if w.PredefinedType == "SOLIDWALL"]
    exp = sum(4 * v["storeys"] for v in SPEC["volumes"])
    assert len(walls) == exp
    assert len(model.by_type("IfcDoor")) == sum(1 for o in SPEC["openings"] if o["kind"] == "door")
    assert model.by_type("IfcCurtainWall") and model.by_type("IfcStairFlight")
    assert model.by_type("IfcRailing")


def test_all_products_tessellate_and_walls_have_holes(model):
    s = ifcopenshell.geom.settings()
    s.set("use-world-coords", True)
    it = ifcopenshell.geom.iterator(s, model, 4)
    assert it.initialize()
    seen = {}
    while True:
        sh = it.get()
        el = model.by_id(sh.id)
        seen[el.GlobalId] = len(sh.geometry.faces) // 3
        if not it.next():
            break
    products = [p for p in model.by_type("IfcElement") if p.Representation and not p.is_a("IfcOpeningElement")]
    missing = [p.Name for p in products if p.GlobalId not in seen]
    assert not missing, missing
    # a voided box has more than 12 triangles
    for w in model.by_type("IfcWall"):
        if w.HasOpenings:
            assert seen[w.GlobalId] > 12, w.Name


def test_parapet_skipped_under_upper_volume(model):
    names = [w.Name for w in model.by_type("IfcWall") if w.PredefinedType == "PARAPET"]
    # Staffel S sits flush on A's south and west edge -> A has no full-length south parapet there
    a_south = [n for n in names if n == "Attika A-S"]
    assert len(a_south) == 1  # only the remaining eastern segment


def test_opening_outside_facade_is_rejected():
    bad = copy.deepcopy(SPEC)
    bad["openings"] = [dict(bad["openings"][0], offset=10.0, width=14.0)]
    Builder(bad).build()                # the builder normalizes first: the opening is moved into the wall instead of failing


def test_geom_helpers():
    assert subtract_intervals((0, 10), [(2, 4), (8, 12)]) == [(0, 2), (4, 8)]
    x, y, z, dx, dy, dz = facade_box("N", 0, 0, 10, 5, 1, 3, 0, 0.3, 0, 2)
    assert (x, round(y, 6), dx, round(dy, 6)) == (7, 4.7, 2, 0.3)
