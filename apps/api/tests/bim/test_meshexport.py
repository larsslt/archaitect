import json
from pathlib import Path

import archaitect.bim as bim
from archaitect.bim import meshexport, terrain as T
from archaitect.bim.ifcgen import build_ifc

SPEC = Path(bim.__file__).resolve().parent / "specs" / "villa_kubus.json"


def test_villa_mesh_and_terrain_part(tmp_path):
    ifc = tmp_path / "m.ifc"
    build_ifc(str(SPEC), str(ifc))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    n = 40
    rows = [[round(100 + 0.1 * (-40 + 0.5 + c * 2), 3) for c in range(n)] for r in range(n)]
    pack = {"terrain": {"status": "OK", "cell_m_native": 1.0, "grid": {"x_west_local": -40, "y_north_local": 40, "cell_m": 2.0, "heights_m": rows}},
            "site": {"ring_local": [[-30, -30], [30, -30], [30, 30], [-30, 30], [-30, -30]]}}
    spec["site"] = {**spec.get("site", {}), "placement": {"x": -15, "y": -4, "rotation_deg": 0}}
    t = T.build_terrain(pack, spec)
    out = meshexport.build(ifc, t)
    names = [p["name"] for p in out["parts"]]
    assert "terrain" in names and len(out["parts"]) >= 5
    for p in out["parts"]:
        assert len(p["indices"]) % 3 == 0 and max(p["indices"]) < len(p["positions"]) // 3
    lo, hi = out["bounds"][2], out["bounds"][5]
    assert hi > 6 and lo < 0.5            # the villa is taller than 6 m, terrain dips below the pad
    json.dumps(out, allow_nan=False)
    assert out["terrain"]["fill_m3"] > 0


def test_without_terrain_only_building(tmp_path):
    ifc = tmp_path / "m.ifc"
    build_ifc(str(SPEC), str(ifc))
    out = meshexport.build(ifc, None)
    assert "terrain" not in [p["name"] for p in out["parts"]] and out["terrain"] is None


def test_every_library_house_exports_valid_json(tmp_path):
    """NaN (unset IFC transparency) is not valid JSON and made the browser drop the whole mesh."""
    for name in ("stadthaus", "fachwerkhaus", "garten"):
        spec = Path(bim.__file__).resolve().parent / "specs" / f"{name}.json"
        ifc = tmp_path / f"{name}.ifc"
        build_ifc(str(spec), str(ifc))
        out = meshexport.build(ifc, None)
        json.dumps(out, allow_nan=False)
        assert all(0.0 < p["opacity"] <= 1.0 for p in out["parts"])
