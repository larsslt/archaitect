"""Every library house must pass the plausibility rules and build as IFC + mesh."""
import json
import pytest

from archaitect.bim import logic, meshexport
from archaitect.bim.ifcgen import build_ifc
from archaitect.siteintel import bim_api


@pytest.mark.parametrize("name", bim_api.LIBRARY_HOUSES)
def test_library_house_builds(name, tmp_path):
    spec = bim_api._library_spec(name)
    spec, _ = logic.complete(spec)
    f = tmp_path / "s.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    ifc = build_ifc(f, tmp_path / "m.ifc")
    res = meshexport.build(ifc, None, spec)
    assert res["parts"]
    assert any(o["id"].startswith("bld:") for o in res["objects"])
