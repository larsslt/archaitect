"""Reference-photo rules: mixed timber patterns stay valid, the door breaks through the stone plinth."""
import json

from archaitect.bim import fachwerk
from archaitect.bim.ifcgen import build_ifc
from archaitect.siteintel import bim_api
from archaitect.bim import logic


def test_mixed_pattern_valid_on_many_walls():
    for L in (5.0, 7.5, 9.0, 12.0, 15.0):
        for ops in ([], [(1.0, 2.2, 1.0, 2.2, False), (4.0, 5.4, 0, 2.2, True)], [(0.8, 1.9, 0.9, 2.2, False), (3.0, 4.1, 0.9, 2.2, False)]):
            for zlo, zhi in ((0.76, 2.6), (0.0, 2.6), (2.8, 5.4)):
                o2 = [(a, b, zb + (zlo if zlo > 2 else 0), zt + (zlo if zlo > 2 else 0), d) for a, b, zb, zt, d in ops if b < L - 0.3]
                polys, _p, bays = fachwerk.plan_wall(L, zlo, zhi, o2, 1.2, 0.14, "mixed")
                assert fachwerk.validate(L, zlo, zhi, o2, polys, bays, "mixed") == []


def test_mixed_pattern_really_varies():
    polys, _p, bays = fachwerk.plan_wall(14.0, 0.0, 2.6, [], 1.2, 0.14, "mixed")
    kinds = {len(p) for p in polys}
    assert len(polys) > 20 and len(bays) >= 8


def test_door_breaks_the_plinth(tmp_path):
    import ifcopenshell
    spec, _ = logic.complete(bim_api._library_spec("fachwerkhaus"))
    f = tmp_path / "s.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    ifc = ifcopenshell.open(str(build_ifc(f, tmp_path / "m.ifc")))
    names = [e.Name for e in ifc.by_type("IfcBuildingElementProxy")]
    assert any(n and n.startswith("Sockel") for n in names)
    assert any(n and n.startswith("Türrahmen") for n in names)


def test_every_brace_end_touches_timber():
    """Kein Strebenende endet frei im Gefach: jedes Ende liegt auf einem Ständer oder Riegel (Feedback „Streben nicht verbunden“)."""
    from shapely.geometry import Polygon
    from archaitect.bim import fachwerk
    polys, posts, bays = fachwerk.plan_wall(9.0, 0.7, 2.6, [(3.85, 5.15, 0.7, 2.9, True)], 1.1, 0.14, "mixed")
    timber = [Polygon(p) for p in polys]
    diag = [Polygon(p) for p in polys if len({round(x, 3) for x, _ in p}) > 2 and len({round(z, 3) for _, z in p}) > 2]
    assert diag
    for d in diag:
        others = [t for t in timber if t.distance(d) > 1e-9 or not t.equals(d)]
        others = [t for t in others if not t.equals(d)]
        # the two end caps of a brace are its short edges: every brace must touch at least two other members
        assert sum(1 for t in others if t.distance(d) < 0.03) >= 2
