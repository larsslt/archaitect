"""Envelope check (curtain wall gaps) and floor plans."""
import copy
import json
from pathlib import Path

import pytest

from archaitect.bim import checks

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
SPEC = json.loads((ROOT / "specs" / "villa_kubus.json").read_text(encoding="utf-8"))


def test_villa_envelope_is_closed():
    assert checks.envelope_gaps(SPEC) == []


def test_gap_in_glass_wall_is_found():
    s = copy.deepcopy(SPEC)
    s["curtain_walls"][0]["faces"] = [f for f in s["curtain_walls"][0]["faces"]
                                      if not (f["side"] == "W" and f.get("span"))]
    gaps = checks.envelope_gaps(s)
    assert len(gaps) == 1 and "West" in gaps[0] and "–9.0 m" in gaps[0]


def test_floor_plans(tmp_path):
    from archaitect.bim.ifcgen import build_ifc
    from archaitect.bim.plan import build_plans
    ifc = tmp_path / "m.ifc"
    build_ifc(str(ROOT / "specs" / "villa_kubus.json"), str(ifc))
    res = build_plans(ifc, tmp_path, "T")
    assert [r["storey"] for r in res] == ["EG", "OG1", "OG2"]
    eg = res[0]
    assert eg["width_m"] == pytest.approx(29.0, abs=0.1) and eg["depth_m"] == pytest.approx(9.0, abs=0.1)
    svg = Path(eg["svg"]).read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "<path" in svg
