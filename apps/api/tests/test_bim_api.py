"""BIM house on the plot: save, place, rule check, terrain, 360° mesh, render job, language-model paths (Blender and the model are faked)."""
import json
import stat
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from siteintel_support import PARCELS, service_for

import archaitect.bim as bimpkg

SPECS = Path(bimpkg.__file__).resolve().parent / "specs"


@pytest.fixture()
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHAITECT_DB_PATH", str(tmp_path / "core.sqlite"))
    monkeypatch.setenv("ARCHAITECT_SITEINTEL_OSM", "0")
    for k in ("BIMRENDER_LLM_URL", "BIMRENDER_LLM_PROVIDER", "BIMRENDER_LLM_KEY", "META_API_KEY", "MODEL_API_KEY", "ARCHAITECT_BIM_LLM"):
        monkeypatch.delenv(k, raising=False)
    from archaitect.main import app
    from archaitect.siteintel import router as r
    from archaitect.siteintel.projects import ProjectStore
    p = PARCELS["darmstadt_wohn"]
    svc, _ = service_for("darmstadt_wohn")
    r.providers["service"] = svc
    r.providers["store"] = ProjectStore(tmp_path / "projects")
    c = TestClient(app)
    made = c.post("/siteintel/projects", json={"lat": p["lat"], "lon": p["lon"]})
    assert made.status_code == 200, made.text
    yield c, made.json()["id"], r
    r.providers.pop("service", None)
    r.providers.pop("store", None)


def house(name="stadthaus.json"):
    return json.loads((SPECS / name).read_text(encoding="utf-8"))


def put(c, pid, spec=None):
    r = c.put(f"/siteintel/projects/{pid}/bim/spec", json={"spec": spec or house(), "note": "Test"})
    assert r.status_code == 200, r.text
    return r.json()


def test_no_house_yet(api):
    c, pid, _ = api
    j = c.get(f"/siteintel/projects/{pid}/bim").json()
    assert j["exists"] is False and j["engine"]["ifcopenshell"] is True
    assert c.get(f"/siteintel/projects/{pid}/bim/mesh").status_code == 404


def test_save_places_house_inside_the_plot_and_derives_terrain(api):
    c, pid, _ = api
    j = put(c, pid)
    assert j["version"] == 1 and j["check"]["hard_ok"] is True, j["check"]
    assert "placement" in j["spec"]["site"] and "terrain" not in j["spec"]["site"]          # terrain is derived, never stored
    assert j["terrain"]["status"] in ("OK", "UNAVAILABLE")
    cards = c.get("/siteintel/projects").json()["projects"] if isinstance(c.get("/siteintel/projects").json(), dict) else c.get("/siteintel/projects").json()
    card = next(x for x in cards if x["id"] == pid)
    assert card["bim_version"] == 1 and card["has_house"] is True and card["design_version"] >= 1


def test_moving_the_house_out_of_the_plot_is_reported_not_hidden(api):
    c, pid, _ = api
    put(c, pid)
    r = c.post(f"/siteintel/projects/{pid}/bim/place", json={"x": 400, "y": 0}).json()
    assert r["check"]["hard_ok"] is False and r["version"] == 2
    assert r["exists"] is True          # Regression: ohne dieses Feld hielt die Oberfläche das Haus nach dem Verschieben für nicht vorhanden
    back = c.post(f"/siteintel/projects/{pid}/bim/place", json={"auto": True}).json()
    assert back["check"]["hard_ok"] is True and back["version"] == 3


def test_mesh_has_building_and_terrain(api):
    c, pid, _ = api
    j = put(c, pid)
    m = c.get(f"/siteintel/projects/{pid}/bim/mesh")
    assert m.status_code == 200
    d = m.json()
    names = [p["name"] for p in d["parts"]]
    assert len(names) > 5 and d["bounds"][5] > 3
    if j["terrain"]["status"] == "OK":
        assert "terrain" in names and d["terrain"]["fill_m3"] >= 0
    again = c.get(f"/siteintel/projects/{pid}/bim/mesh").json()
    assert again["version"] == 1


def test_patch_undo_and_invalid_patch(api):
    c, pid, _ = api
    put(c, pid)
    ok = c.post(f"/siteintel/projects/{pid}/bim/patch", json={"patch": [{"op": "replace", "path": "/name", "value": "Neuer Name"}]})
    assert ok.status_code == 200 and ok.json()["name"] == "Neuer Name" and ok.json()["version"] == 2
    bad = c.post(f"/siteintel/projects/{pid}/bim/patch", json={"patch": [{"op": "replace", "path": "/volumes/id=ZZZ/storeys", "value": 3}]})
    assert bad.status_code == 422
    assert c.get(f"/siteintel/projects/{pid}/bim").json()["version"] == 2
    back = c.post(f"/siteintel/projects/{pid}/bim/undo").json()
    assert back["version"] == 3 and back["name"] != "Neuer Name" and back["exists"] is True


def test_invalid_spec_is_rejected_with_reasons(api):
    c, pid, _ = api
    bad = house()
    bad["volumes"][0]["storeys"] = 0
    r = c.put(f"/siteintel/projects/{pid}/bim/spec", json={"spec": bad})
    assert r.status_code == 422 and r.json()["detail"]["problems"]


def test_without_language_model_creating_is_a_clear_503(api, monkeypatch):
    c, pid, _ = api
    from archaitect.siteintel import ai
    monkeypatch.setattr(ai, "status", lambda: {"ollama": {"ok": False}})
    r = c.post(f"/siteintel/projects/{pid}/bim/create", json={"text": "Villa mit Flachdach"})
    assert r.status_code == 503 and "Sprachmodell" in r.json()["detail"]


def test_create_from_text_with_fake_model(api, monkeypatch):
    c, pid, _ = api
    from archaitect.bim import interpret
    monkeypatch.setenv("BIMRENDER_LLM_URL", "http://fake")
    monkeypatch.setattr(interpret, "_llm", lambda messages, budget=None, phase="llm": json.dumps(house()))
    r = c.post(f"/siteintel/projects/{pid}/bim/create", json={"text": "Zweigeschossiges Stadthaus mit Satteldach"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok" and r.json()["version"] == 1 and r.json()["check"]["hard_ok"] is True
    q = c.post(f"/siteintel/projects/{pid}/bim/create", json={"text": "Haus"})
    monkeypatch.setattr(interpret, "_llm", lambda messages, budget=None, phase="llm": json.dumps({"questions": ["Wie viele Geschosse?"]}))
    assert c.post(f"/siteintel/projects/{pid}/bim/create", json={"text": "Haus"}).json()["status"] == "questions"
    assert q.status_code == 200


def test_render_job_with_fake_blender(api, tmp_path, monkeypatch):
    c, pid, r = api
    put(c, pid)
    fake = tmp_path / "blender"
    fake.write_text('#!/bin/sh\nprintf "\\211PNG fake" > "$BIM_OUT"\necho "terrain=$(grep -c terrain "$BIM_SPEC")"\n', encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    from archaitect.bim import api as bimapi
    monkeypatch.setattr(bimapi, "BLENDER", str(fake))
    job = c.post(f"/siteintel/projects/{pid}/bim/renders", json={"quality": "sketch"})
    assert job.status_code == 202, job.text
    jid = job.json()["id"]
    for _ in range(100):
        st = c.get(f"/siteintel/projects/{pid}/bim/renders/{jid}").json()
        if st["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert st["status"] == "done", st
    img = c.get(f"/siteintel/projects/{pid}/bim/renders/{jid}/image")
    assert img.status_code == 200 and img.content.startswith(b"\x89PNG")
    assert any(r["id"] == jid for r in c.get(f"/siteintel/projects/{pid}/bim/renders").json()["renders"])
    # the render spec carries the graded terrain, the stored spec does not
    sent = json.loads((r.store()._dir(pid) / "bim" / "model" / "renders" / jid / "spec.json").read_text(encoding="utf-8"))
    stored = c.get(f"/siteintel/projects/{pid}/bim").json()
    assert ("terrain" in sent["site"]) and ("terrain" not in stored["spec"]["site"])
    assert sent["site"]["terrain"]["status"] == stored["terrain"]["status"]


def test_render_without_blender_is_503(api, monkeypatch):
    c, pid, _ = api
    put(c, pid)
    from archaitect.bim import api as bimapi
    monkeypatch.setattr(bimapi, "BLENDER", "/nonexistent/blender")
    assert c.post(f"/siteintel/projects/{pid}/bim/renders", json={"quality": "sketch"}).status_code == 503


def test_library_houses_work_without_a_language_model(api):
    c, pid, _ = api
    lst = c.get(f"/siteintel/projects/{pid}/bim/library").json()["houses"]
    assert {"stadthaus", "villa_kubus", "fachwerkhaus", "fachwerk_gasthaus_lib"} <= {h["id"] for h in lst} and len(lst) >= 22
    r = c.post(f"/siteintel/projects/{pid}/bim/library/stadthaus")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["version"] == 1 and j["placement"] and j["check"]["results"]
    assert c.post(f"/siteintel/projects/{pid}/bim/library/unbekannt").status_code == 404


def test_terrain_cache_follows_a_refreshed_site_pack(api):
    import copy
    c, pid, r = api
    put(c, pid)
    store = r.providers["store"]
    tdir = store._dir(pid) / "bim" / "model" / "terrain"
    before = sorted(p.name for p in tdir.glob("v001_*.json"))
    assert len(before) == 1
    real = store.pack

    def shifted(p):
        pk = copy.deepcopy(real(p))
        g = pk["terrain"]["grid"]
        g["heights_m"] = [[(h + 5.0) if h is not None else h for h in row] for row in g["heights_m"]]
        return pk

    store.pack = shifted
    try:
        assert c.get(f"/siteintel/projects/{pid}/bim").status_code == 200
    finally:
        store.pack = real
    assert len(sorted(p.name for p in tdir.glob("v001_*.json"))) == 2


def test_provider_selection_prefers_meta_key_then_local_model(api, monkeypatch):
    from archaitect.siteintel import bim_api as B
    monkeypatch.setattr(B.ai, "status", lambda: {"ollama": {"ok": False}})
    assert B._provider() == "none" and B._configure_llm(False)
    monkeypatch.setenv("META_API_KEY", "test-not-a-key")
    assert B._provider() == "meta"
    assert B._configure_llm(True) is None
    import os
    assert os.environ["BIMRENDER_LLM_URL"] == "https://api.meta.ai" and os.environ["BIMRENDER_LLM_MODEL"] == "muse-spark-1.3"
    assert os.environ["BIMRENDER_LLM_PROVIDER"] == "meta" and os.environ["BIMRENDER_PROMPT"] == "full"
    assert B._provider() == "meta"                                   # stays meta after configuring (no false 'custom')
    monkeypatch.setenv("ARCHAITECT_BIM_LLM", "ollama")
    monkeypatch.setattr(B.ai, "status", lambda: {"ollama": {"ok": True}})
    assert B._provider() == "ollama"
    for k in ("BIMRENDER_LLM_URL", "BIMRENDER_LLM_PROVIDER", "BIMRENDER_LLM_KEY", "BIMRENDER_LLM_MODEL", "BIMRENDER_PROMPT", "BIMRENDER_LLM_MAX_TOKENS", "BIMRENDER_LLM_TIMEOUT"):
        os.environ.pop(k, None)


def test_versions_list_and_restore(api):
    c, pid, _ = api
    put(c, pid)
    c.post(f"/siteintel/projects/{pid}/bim/patch", json={"patch": [{"op": "replace", "path": "/name", "value": "Zweiter Name"}], "note": "umbenannt"})
    v = c.get(f"/siteintel/projects/{pid}/bim/versions").json()
    assert v["current"] == 2 and [x["version"] for x in v["versions"]] == [2, 1] and v["versions"][0]["note"] == "umbenannt"
    r = c.post(f"/siteintel/projects/{pid}/bim/restore/1").json()
    assert r["version"] == 3 and r["name"] != "Zweiter Name"
    assert c.post(f"/siteintel/projects/{pid}/bim/restore/99").status_code == 404


def test_damaged_mesh_cache_is_rebuilt(api):
    c, pid, r = api
    put(c, pid)
    assert c.get(f"/siteintel/projects/{pid}/bim/mesh").status_code == 200
    store = r.providers["store"]
    f = next((store._dir(pid) / "bim" / "model").glob("mesh_v*.json"))
    f.write_text(f.read_text(encoding="utf-8") + "{}", encoding="utf-8")        # simulates two overlapping writers
    again = c.get(f"/siteintel/projects/{pid}/bim/mesh")
    assert again.status_code == 200 and again.json()["parts"]


def test_unplaceable_new_example_preserves_existing_house(api,monkeypatch):
    c,pid,_=api
    put(c,pid)
    before=c.get(f'/siteintel/projects/{pid}/bim').json()
    from archaitect.siteintel import bim_api
    monkeypatch.setattr(bim_api,'_place_full',lambda *a,**k:(None,['Haus passt nicht auf die freie Fläche.']))
    monkeypatch.setattr(bim_api,'_configure_llm',lambda *a,**k:'kein Modell')      # never call a real (e.g. local Ollama) model from a test
    r=c.post(f'/siteintel/projects/{pid}/bim/library/mfh_lib',json={})
    assert r.status_code==422 and 'passt nicht' in r.text
    after=c.get(f'/siteintel/projects/{pid}/bim').json()
    assert after['version']==before['version'] and after['name']==before['name']


def test_full_placement_refuses_unchecked_footprint(api,monkeypatch):
    from archaitect.siteintel import bim_api
    from archaitect.bim import ifcgen
    _,pid,_=api
    ctx,_,_=bim_api._site(pid)
    monkeypatch.setattr(ifcgen,'build_ifc',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('test')))
    pl,notes=bim_api._place_full(house(),ctx)
    assert pl is None and 'nicht möglich' in notes[0]


def test_placement_rejects_attachment_over_existing_building(monkeypatch):
    from shapely.geometry import box
    from archaitect.siteintel import bim_api,bim_bridge
    from archaitect.siteintel.regs import SiteCtx,Existing
    from archaitect.bim.terrain import Placement
    from archaitect.bim import ifcgen
    ctx=SiteCtx(site=box(-10,-10,10,10),area_m2=400,existing=[Existing('old',box(4,-1,6,1),None,None)],neighbours=[],roads=[],verified=None,envelope=None)
    monkeypatch.setattr(bim_api,'place_spec',lambda *a,**k:(Placement(0,0,0),[]))
    monkeypatch.setattr(ifcgen,'build_ifc',lambda *a,**k:None)
    monkeypatch.setattr(bim_api.meshexport,'ifc_parts',lambda *a,**k:[])
    monkeypatch.setattr(bim_bridge,'footprint_from_parts',lambda parts:box(-1,-1,6,1))
    monkeypatch.setattr(bim_bridge,'refine_for_extras',lambda s,c,f,p:(p,None))
    pl,notes=bim_api._place_full(house(),ctx)
    assert pl is None and 'Bestandsgebäude' in notes[0]


def test_invalid_site_and_missing_volume_data_are_422(api):
    c,pid,_=api
    bad=house();bad['site']=None
    assert c.put(f'/siteintel/projects/{pid}/bim/spec',json={'spec':bad}).status_code==422
    bad=house();bad.pop('render',None);bad['volumes'][0].pop('origin')
    assert c.put(f'/siteintel/projects/{pid}/bim/spec',json={'spec':bad}).status_code==422
