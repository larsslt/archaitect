from types import SimpleNamespace

from archaitect.siteintel import reference
from archaitect.bim import objects as O


def test_effective_shows_own_roof_limit_and_labels_basis():
    v = SimpleNamespace(max_stories=2, max_building_height_meters=10.0, setback_lines_offset_meters=None, grz=0.4, gfz=None,
                        roof_types_allowed=["sattel"], max_eave_height_meters=6.0, roof_pitch_min_deg=None, roof_pitch_max_deg=45.0)
    ctx = SimpleNamespace(reference={}, verified=v, src={"max_stories": "USER_LIMIT", "roof_types_allowed": "USER_LIMIT"})
    eff = reference.effective(ctx)
    assert eff["max_storeys"] == {"value": 2, "binding": True, "basis": "USER_LIMIT"}
    assert eff["roof_types"]["value"] == ["sattel"] and eff["roof_types"]["basis"] == "USER_LIMIT"
    assert eff["max_eave_height_m"]["value"] == 6.0 and eff["roof_pitch_max_deg"]["value"] == 45.0
    assert "gfz" not in eff


def test_last_building_can_be_deleted():
    s = {"volumes": [{"id": "H", "origin": [0, 0], "size": [10, 8], "storeys": 2}], "openings": [], "balconies": [], "components": [{"type": "tree", "x": 20, "y": 0}]}
    out = O.delete(s, "bld:H")
    assert out["volumes"] == [] and len(out["components"]) == 1
