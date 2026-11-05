import json
from pathlib import Path

import pytest

import archaitect.bim.projects as P
from archaitect.bim import api

SPEC = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent / "specs" / "villa_kubus.json"


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.delenv("BIMRENDER_LLM_URL", raising=False)


def test_new_project_and_status():
    r = api.new_project(spec=str(SPEC))
    assert r == {"status": "ok", "project": "villa_kubus", "version": 1}
    s = api.status("villa_kubus")
    assert s["status"] == "ok" and s["cameras"] == ["hero_sw", "drone_se", "street_n"] and s["images"] == []


def test_errors_are_dicts_not_exceptions():
    assert api.new_project()["status"] == "error"
    assert api.status("gibt-es-nicht")["status"] == "error"
    assert api.render("gibt-es-nicht")["status"] == "error"
    api.new_project(spec=str(SPEC))
    assert api.render("villa_kubus", quality="mega")["status"] == "error"
    assert api.undo("villa_kubus")["status"] == "error"  # nothing to go back to


def test_apply_ok_invalid_and_undo():
    api.new_project(spec=str(SPEC))
    ok = api.apply("villa_kubus", {"summary": "Klinker", "patch": [{"op": "replace", "path": "/volumes/id=B/facade", "value": "brick_red"}]})
    assert ok["status"] == "ok" and ok["version"] == 2
    bad = api.apply("villa_kubus", [{"op": "replace", "path": "/volumes/id=B/facade", "value": "marmor_pink"}])
    assert bad["status"] == "invalid" and api.status("villa_kubus")["version"] == 2
    assert api.undo("villa_kubus")["version"] == 3
    assert api.status("villa_kubus")["history"][-1]["note"] == "zurück auf v001"


def test_revise_without_interpreter_writes_prompt_bundle():
    api.new_project(spec=str(SPEC))
    r = api.revise("villa_kubus", "Der linke Kubus soll aus Klinker sein.")
    assert r["status"] == "manual"
    text = Path(r["bundle"]).read_text(encoding="utf-8")
    assert "brick_red" in text and "Der linke Kubus" in text and '"volumes"' in text


def test_model3d_unknown_project_is_an_error_dict():
    assert api.model3d("gibt-es-nicht")["status"] == "error"
