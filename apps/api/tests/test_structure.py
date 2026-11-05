"""Structural repairs (structure.py) against the construction audit (audit.py)."""
import random
import sys
from pathlib import Path

from archaitect.bim import logic
from archaitect.bim.audit import audit

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))


def _spec(**kw):
    s = {"volumes": [{"id": "A", "origin": [0, 0], "size": [9.0, 11.0], "storeys": 2, "storey_height": 3.0, "base_z": 0.0,
                      "roof": {"type": "gable", "ridge": "y", "pitch_deg": 40, "overhang": 0.4, "material": "roof_tile_red"}}],
         "openings": [], "components": []}
    s.update(kw)
    return s


def test_openings_are_moved_into_the_wall_and_below_the_ceiling():
    s = _spec(openings=[{"volume": "A", "side": "S", "storey": 0, "offset": 8.5, "width": 2.0, "height": 2.9, "sill": 0.5, "kind": "window"},
                        {"volume": "A", "side": "S", "storey": 5, "offset": 1.0, "width": 1.0, "height": 1.2, "sill": 0.9, "kind": "window"}])
    out, _ = logic.complete(s)
    assert audit(out) == []
    assert len(out["openings"]) == 1 and out["openings"][0]["offset"] + out["openings"][0]["width"] <= 9.0


def test_overlapping_volume_is_pushed_out_and_floating_volume_lands():
    s = _spec()
    s["volumes"].append({"id": "B", "origin": [4.0, 3.0], "size": [5.0, 5.0], "storeys": 1, "storey_height": 3.0, "base_z": 0.0})
    s["volumes"].append({"id": "C", "origin": [-9.0, 0.0], "size": [4.0, 4.0], "storeys": 1, "storey_height": 3.0, "base_z": 6.0})
    out, notes = logic.complete(s)
    assert audit(out) == [] and any("verschoben" in n for n in notes) and any("schwebte" in n for n in notes)


def test_terrace_inside_other_volume_is_removed_and_gable_window_fits():
    s = _spec()
    s["volumes"].append({"id": "B", "origin": [9.0, 0.0], "size": [5.0, 5.0], "storeys": 1, "storey_height": 3.0, "base_z": 0.0})
    s["components"].append({"type": "terrace", "volume": "A", "side": "E", "u": 2.5, "width": 4.0, "depth": 3.0})
    s["openings"].append({"volume": "A", "side": "S", "storey": 2, "offset": 0.2, "width": 3.0, "height": 3.5, "sill": 0.0, "kind": "window"})
    out, _ = logic.complete(s)
    assert audit(out) == [] and not [c for c in out["components"] if c["type"] == "terrace"]


def test_bench_variants_stay_buildable():
    import construction_bench as cb
    rnd = random.Random(3)
    names = cb.bim_api.LIBRARY_HOUSES
    bad = 0
    for i in range(60):
        done, _ = logic.complete(cb.mutate(cb.bim_api._library_spec(names[i % len(names)]), rnd))
        bad += 1 if audit(done) else 0
    assert bad <= 3
