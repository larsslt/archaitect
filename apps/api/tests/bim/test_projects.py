import json
from pathlib import Path

import pytest

from archaitect.bim.interpret import apply_answer, validate_spec
from archaitect.bim.projects import PatchError, Project, apply_patch, open_project

SPEC = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent / "specs" / "villa_kubus.json"


@pytest.fixture
def spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def test_replace_by_selector_and_index(spec):
    out = apply_patch(spec, [{"op": "replace", "path": "/volumes/id=B/size/0", "value": 9.0}])
    assert next(v for v in out["volumes"] if v["id"] == "B")["size"][0] == 9.0
    assert next(v for v in spec["volumes"] if v["id"] == "B")["size"][0] != 9.0  # input untouched


def test_selector_must_match_exactly_one(spec):
    with pytest.raises(PatchError, match="trifft"):
        apply_patch(spec, [{"op": "replace", "path": "/openings/volume=A/width", "value": 1.0}])


def test_failed_patch_changes_nothing(spec):
    ops = [{"op": "replace", "path": "/storey_height", "value": 3.2},
           {"op": "remove", "path": "/gibt_es_nicht"}]
    with pytest.raises(PatchError, match="Operation 2"):
        apply_patch(spec, ops)
    assert spec["storey_height"] != 3.2


def test_add_and_remove_in_list(spec):
    n = len(spec["pergolas"])
    out = apply_patch(spec, [{"op": "remove", "path": "/pergolas/name=Pergola Garten"}])
    assert len(out["pergolas"]) == n - 1
    out = apply_patch(out, [{"op": "add", "path": "/pergolas/-", "value": spec["pergolas"][0]}])
    assert len(out["pergolas"]) == n


def test_versions_undo_and_invalid_patch_saves_nothing(spec, tmp_path):
    proj = Project("t", root=tmp_path)
    assert proj.save(spec, "start") == 1
    res = apply_answer(proj, {"summary": "Haus höher", "patch": [{"op": "replace", "path": "/storey_height", "value": 3.2}]})
    assert res["status"] == "ok" and res["version"] == 2 and proj.spec()["storey_height"] == 3.2
    bad = apply_answer(proj, {"patch": [{"op": "replace", "path": "/volumes/id=Z/size/0", "value": 1}]})
    assert bad["status"] == "invalid" and proj.version == 2
    assert proj.undo() == 3 and proj.spec()["storey_height"] == spec["storey_height"]
    assert (tmp_path / "t" / "versions" / "v002.json").exists()  # nothing is deleted


def test_questions_are_passed_through(spec, tmp_path):
    proj = Project("q", root=tmp_path)
    proj.save(spec, "start")
    res = apply_answer(proj, {"questions": ["Welches Fenster?"]})
    assert res["status"] == "questions" and proj.version == 1


def test_open_project_restarts_only_on_changed_file(spec, tmp_path, monkeypatch):
    import archaitect.bim.projects as P
    monkeypatch.setattr(P, "OUT", tmp_path)
    f = tmp_path / "haus.json"
    f.write_text(json.dumps(spec), encoding="utf-8")
    p1 = P.open_project(str(f)); p2 = P.open_project(str(f))
    assert p1.version == p2.version == 1
    spec["storey_height"] = 3.1
    f.write_text(json.dumps(spec), encoding="utf-8")
    assert P.open_project(str(f)).version == 2
    with pytest.raises(FileNotFoundError):
        P.open_project("gibt-es-nicht")


def test_patched_villa_still_validates(spec):
    out = apply_patch(spec, [{"op": "replace", "path": "/volumes/id=B/size/0", "value": 8.5}])
    assert validate_spec(out) == []
