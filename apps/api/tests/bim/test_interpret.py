import copy
import json
from pathlib import Path

from archaitect.bim.interpret import interpret, validate_spec
from archaitect.bim.logic import normalize

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
SPEC = json.loads((ROOT / "specs" / "villa_kubus.json").read_text(encoding="utf-8"))


import pytest


@pytest.mark.parametrize("name", ["villa_kubus.json", "stadthaus.json"])
def test_example_specs_are_valid(name):
    spec = json.loads((ROOT / "specs" / name).read_text(encoding="utf-8"))
    assert validate_spec(spec) == []


def test_schema_error_reported():
    bad = copy.deepcopy(SPEC)
    bad["openings"][0]["side"] = "X"
    assert any(p.startswith("schema") for p in validate_spec(bad))


def test_build_error_reported():
    bad = copy.deepcopy(SPEC)
    bad["openings"].append({**bad["openings"][0], "storey": 9, "offset": 0.5, "width": 1.0})
    problems = validate_spec(bad)           # an opening on a storey that does not exist is reported (with the valid range) so the model can repair it
    assert problems and "Geschoss 9" in problems[0] and "0..1" in problems[0]
    assert not any(p.startswith("build:") for p in problems)


def test_manual_provider_makes_bundle_without_network(tmp_path, monkeypatch):
    monkeypatch.delenv("BIMRENDER_LLM_URL", raising=False)
    r = interpret("Zweigeschossiges Haus mit Flachdach", out_dir=tmp_path)
    assert r["status"] == "manual" and Path(r["bundle"]).exists()


def test_copied_prompt_example_is_sent_back_for_a_new_design(tmp_path, monkeypatch):
    """qwen-class local models sometimes echo the example from the prompt; the interpreter asks once more."""
    import json
    from pathlib import Path
    import archaitect.bim as bimpkg
    from archaitect.bim import interpret as I
    specs = Path(bimpkg.__file__).resolve().parent / "specs"
    echo = (specs / "fachwerkhaus.json").read_text(encoding="utf-8")
    fresh = (specs / "stadthaus.json").read_text(encoding="utf-8")
    calls = []

    def fake(messages, budget=None, phase="llm"):
        calls.append(messages[-1]["content"])
        return echo if len(calls) == 1 else fresh

    monkeypatch.setenv("BIMRENDER_LLM_URL", "http://x")
    monkeypatch.setattr(I, "_llm", fake)
    res = I.interpret("Bungalow mit Walmdach", out_dir=tmp_path)
    assert res["status"] == "ok" and len(calls) == 2 and "NEUES Haus" in calls[1]
    assert json.loads(Path(res["spec"]).read_text(encoding="utf-8"))["name"] == json.loads(fresh)["name"]


def test_compact_prompt_fits_a_small_context_and_echo_gives_up(tmp_path, monkeypatch):
    from pathlib import Path
    import archaitect.bim as bimpkg
    from archaitect.bim import interpret as I
    full, small = I._system(False), I._system(True)
    assert len(small) < 0.6 * len(full) and len(small) < 50000 and "# Schema" in small and "NIE unverändert" in small
    monkeypatch.setenv("BIMRENDER_LLM_URL", "http://localhost:11434")
    assert I._compact() is True
    monkeypatch.setenv("BIMRENDER_PROMPT", "full")
    assert I._compact() is False
    echo = (Path(bimpkg.__file__).resolve().parent / "specs" / "fachwerkhaus.json").read_text(encoding="utf-8")
    monkeypatch.setattr(I, "_llm", lambda m, b=None, p="llm": echo)
    res = I.interpret("Bungalow", out_dir=tmp_path)
    assert res["status"] == "invalid" and "kopiert" in res["problems"][0]
