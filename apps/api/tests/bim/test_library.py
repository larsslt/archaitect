import json
from pathlib import Path

from archaitect.bim import library
from archaitect.bim.interpret import SCHEMA, validate_spec

SPEC = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent / "specs" / "villa_kubus.json"


def test_library_is_consistent():
    assert library.problems() == []
    assert set(library.spec_styles()) <= set(library.load())


def test_schema_enum_comes_from_library():
    assert SCHEMA["$defs"]["style"]["enum"] == library.spec_styles()
    assert "brick_red" in library.spec_styles() and "bark" not in library.spec_styles()


def test_new_material_is_accepted_and_unknown_is_rejected():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec["volumes"][2]["facade"] = "brick_red"
    assert validate_spec(spec) == []
    spec["volumes"][2]["facade"] = "marmor_pink"
    assert any("marmor_pink" in p for p in validate_spec(spec))


def test_ifc_uses_library_colours():
    from archaitect.bim.ifcgen import Builder
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec["volumes"][2]["facade"] = "brick_red"
    f = Builder(spec).build()
    col = next(s for st in f.by_type("IfcSurfaceStyle") if st.Name == "brick_red" for s in st.Styles).SurfaceColour
    assert (col.Red, col.Green, col.Blue) == tuple(library.rgb("brick_red"))
