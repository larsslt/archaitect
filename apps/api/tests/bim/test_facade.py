"""Pitched roof, gable openings, dormers, timber balcony, hand-placed facade members and the detail-pass helpers."""
import copy
import json
from pathlib import Path

import ifcopenshell
import pytest

from archaitect.bim import detail
from archaitect.bim.ifcgen import Builder
from archaitect.bim.interpret import validate_spec
from archaitect.bim.logic import normalize

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
FW = json.loads((ROOT / "specs" / "fachwerkhaus.json").read_text(encoding="utf-8"))


def classes(spec):
    f = Builder(spec).build()
    out = {}
    for e in f.by_type("IfcProduct"):
        out.setdefault(e.is_a(), []).append(e)
    return out


def test_example_is_valid_and_has_roof_dormers_balcony():
    assert validate_spec(FW) == []
    c = classes(FW)
    assert len(c["IfcRoof"]) == 4  # main roof + 3 dormer roofs
    assert any("Gaube" in (w.Name or "") for w in c["IfcWall"])
    assert any(r.Name == "Holzbalkon Bruestung" for r in c["IfcRailing"])


def test_opening_outside_gable_triangle_is_rejected():
    s = copy.deepcopy(FW)
    s["openings"] = [o for o in s["openings"] if not (o["side"] == "S" and o["storey"] == 2)]
    s["openings"].append({"volume": "A", "side": "S", "storey": 2, "offset": 0.1, "width": 1.0, "height": 2.0, "sill": 0.0, "kind": "window"})
    assert validate_spec(s) == []       # repaired, not rejected: the window is shortened to fit the triangle
    o = [o for o in normalize(s)["openings"] if o["side"] == "S" and o["storey"] == 2]
    assert not o or o[0]["height"] < 2.0      # shortened, or removed when the triangle is too small there


def test_dormer_too_tall_or_on_wrong_slope_rejected():
    s = copy.deepcopy(FW)
    s["dormers"] = [{"volume": "A", "slope": "S", "offset": 2.0, "width": 1.6}]
    assert validate_spec(s) == []       # wrong slope -> moved to an existing slope
    assert normalize(s)["dormers"][0]["slope"] in ("W", "E")
    s["dormers"] = [{"volume": "A", "slope": "W", "offset": 2.0, "width": 1.6, "inset": 0.3, "wall_height": 4.0}]
    assert validate_spec(s) == []       # too tall -> lowered / shrunk / removed, never an IFC error
    dm = normalize(s).get("dormers", [])
    assert not dm or dm[0]["wall_height"] < 4.0


def test_facade_elements_replace_auto_frame_and_validate_range():
    s = copy.deepcopy(FW)
    before = sum(1 for m in classes(s)["IfcMember"] if "Fachwerk A-S" in (m.Name or ""))
    assert before > 0
    s["facade_elements"] = [{"volume": "A", "side": "S", "items": [{"post": [0.1, 0.7, 5.0], "w": 0.2}, {"beam": [0, 8.5, 0.7], "h": 0.18},
                                                                 {"brace": [0.2, 0.9, 1.0, 2.0]}, {"poly": [[3, 5], [3.2, 5.3], [2.8, 5.3]]}]}]
    c = classes(s)["IfcMember"]
    assert not any("Fachwerk A-S" in (m.Name or "") for m in c) and any("Fassadendetail A-S" in (m.Name or "") for m in c)
    s["facade_elements"][0]["items"].append({"post": [9.5, 0, 2]})
    assert "outside the facade" in " ".join(validate_spec(s))
    s["facade_elements"][0]["items"][-1] = {"wibble": 1}
    assert "unknown item" in " ".join(validate_spec(s))


def test_facade_context_and_elevation_camera():
    ctx = detail.facade_context(FW, "A", "S")
    assert ctx["fassadenlaenge_L"] == 8.5 and ctx["vollgeschosse"] == 2
    assert ctx["giebel"]["max_hoehe_ueber_traufe_bei_u"]["4.0"] > 4.5 and ctx["oeffnungen"]
    cam = detail.elevation_camera(FW, "A", "S")
    assert cam["name"] == "elev_A_S" and cam["position"][1] < 0 and cam["lens_mm"] == 85.0
    east = detail.elevation_camera(FW, "A", "E")
    assert east["position"][0] > FW["volumes"][0]["size"][0]
