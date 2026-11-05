"""Rooms: model, automatic detection, hints, partitions, API and the geometric check of the LLM answer."""
import copy
import json
from pathlib import Path

import pytest

import archaitect.bim.projects as P
from archaitect.bim import api, roomplan
from archaitect.bim import rooms as R

ROOT = Path(__import__("archaitect.bim", fromlist=["x"]).__file__).resolve().parent
SPEC = json.loads((ROOT / "specs" / "villa_kubus.json").read_text(encoding="utf-8"))


def with_rooms(*rooms):
    s = copy.deepcopy(SPEC)
    s["rooms"] = [{"id": f"r{i + 1:03d}", "level": "EG", **r} for i, r in enumerate(rooms)]
    return s


def test_function_enum_matches_schema():
    schema = json.loads((ROOT / "schema.json").read_text(encoding="utf-8"))
    assert set(schema["properties"]["rooms"]["items"]["properties"]["function"]["enum"]) == set(R.FUNCTIONS)


def test_windows_found_automatically():
    s = with_rooms({"name": "Wohnen", "function": "wohnen", "rect": [11.36, 0.36, 25.0, 5.5]})
    a = R.analyze(s)[0]
    assert a["glass_area"] == pytest.approx(30.8, abs=0.1) and a["hints"] == []
    assert {w["side"] for w in a["windows"]} == {"S"}


def test_stair_tower_recognised():
    s = with_rooms({"name": "Treppenhaus", "function": "treppe", "rect": [8.12, 0.12, 10.88, 8.88]})
    assert R.analyze(s)[0]["stair"] is True


def test_hints_no_window_and_overlap_and_outside():
    s = with_rooms({"name": "Innen", "function": "wohnen", "rect": [2.0, 3.0, 5.0, 6.0]},
                   {"name": "Zweiter", "function": "bad", "rect": [4.0, 5.0, 6.0, 7.0]},
                   {"name": "Draussen", "function": "flur", "rect": [29.0, 0.0, 32.0, 3.0]})
    h = {a["name"]: a["hints"] for a in R.analyze(s)}
    assert any("ohne Fenster" in x for x in h["Innen"])
    assert any("überlappt" in x for x in h["Zweiter"])
    assert any("hinaus" in x for x in h["Draussen"])


def test_partitions_follow_shared_edges_not_outer_walls():
    s = with_rooms({"name": "A1", "function": "wohnen", "rect": [11.36, 0.36, 20.0, 8.64]},
                   {"name": "A2", "function": "essen", "rect": [20.0, 0.36, 28.64, 8.64]})
    walls = R.partitions_from_rooms(s, "EG")
    assert len(walls) == 1 and walls[0]["start"][0] == walls[0]["end"][0] == 20.0


def test_validate_divide_checks_geometry():
    clean, probs = roomplan.validate_divide(SPEC, "EG", [
        {"name": "Atelier 1", "function": "atelier", "rect": [0.36, 1.36, 7.64, 5.0]},
        {"name": "Atelier 2", "function": "atelier", "rect": [0.36, 5.0, 7.64, 8.64]},
        {"name": "Treppe", "function": "treppe", "rect": [8.12, 0.12, 10.88, 8.88]},
        {"name": "Wohnen A", "function": "wohnen", "rect": [11.36, 0.36, 17.12, 8.64]},
        {"name": "Wohnen B", "function": "wohnen", "rect": [17.12, 0.36, 22.88, 8.64]},
        {"name": "Wohnen C", "function": "wohnen", "rect": [22.88, 0.36, 28.64, 8.64]}])
    assert probs == [] and len(clean) == 6
    _, probs = roomplan.validate_divide(SPEC, "EG", [
        {"name": "Klein", "function": "wohnen", "rect": [11.36, 0.36, 15.0, 4.0]},
        {"name": "Ueber", "function": "wohnen", "rect": [14.0, 0.36, 18.0, 4.0]},
        {"name": "Falsch", "function": "gibtsnicht", "rect": [0.36, 1.36, 7.64, 8.64]}])
    text = " ".join(probs)
    assert "überlappen" in text and "aufgeteilt" in text and "unbekannt" in text and "Treppenhaus fehlt" in text


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "OUT", tmp_path)
    api.new_project(spec=str(ROOT / "specs" / "villa_kubus.json"))
    return "villa_kubus"


def test_room_api_roundtrip_and_ifc(proj, tmp_path):
    r = api.room_add(proj, "EG", [11.36, 0.36, 25.0, 5.5], "wohnen")
    assert r["status"] == "ok" and r["rooms"][0]["name"] == "Wohnen"
    api.room_add(proj, "EG", [11.36, 5.5, 20.0, 8.64], "wohnen")
    names = [x["name"] for x in api.status(proj)["rooms"]]
    assert names == ["Wohnen", "Wohnen 2"]
    assert api.room_set(proj, "r002", name="Büro", function="arbeiten")["status"] == "ok"
    assert api.room_add(proj, "EG", [1, 1, 1.2, 1.2], "wohnen")["status"] == "error"
    assert api.room_add(proj, "XX", [11.36, 0.36, 25.0, 5.5], "wohnen")["status"] == "error"
    w = api.rooms_walls(proj, "EG")
    assert w["status"] == "ok" and w["walls"] >= 1
    from archaitect.bim.ifcgen import build_ifc
    import ifcopenshell
    ifc = build_ifc(str(P.open_project(proj).current_path), tmp_path / "m.ifc")
    spaces = ifcopenshell.open(str(ifc)).by_type("IfcSpace")
    assert sorted(s.Name for s in spaces) == ["Büro", "Wohnen"]
    assert api.room_delete(proj, "r001")["status"] == "ok" and len(api.status(proj)["rooms"]) == 1
    assert api.rooms_clear(proj, "EG")["status"] == "ok" and api.status(proj)["rooms"] == []


def test_narrow_corridor_and_oversized_room_rejected():
    _, probs = roomplan.validate_divide(SPEC, "EG", [
        {"name": "Flur", "function": "flur", "rect": [11.36, 0.36, 12.36, 8.64]},
        {"name": "Riese", "function": "schlafen", "rect": [12.36, 0.36, 28.64, 8.64]}])
    text = " ".join(probs)
    assert "Flur nur 1.00 m breit" in text and "zu groß für schlafen" in text


def test_doors_follow_room_edges():
    s = with_rooms({"name": "Flur", "function": "flur", "rect": [11.36, 3.0, 28.64, 4.5]},
                   {"name": "Schlafen", "function": "schlafen", "rect": [11.36, 4.5, 20.0, 8.64]},
                   {"name": "Bad", "function": "bad", "rect": [20.0, 4.5, 24.0, 8.64]},
                   {"name": "Kind", "function": "kind", "rect": [11.36, 0.36, 20.0, 3.0]})
    doors = R.door_plan(s, "EG")
    pairs = {frozenset(d["between"]) for d in doors}
    assert frozenset(("Flur", "Schlafen")) in pairs and frozenset(("Flur", "Bad")) in pairs
    assert frozenset(("Flur", "Kind")) in pairs
    walls = R.partitions_from_rooms(s, "EG")
    assert sum(len(w.get("doors", [])) for w in walls) == len(doors)
    for w in walls:
        L = abs(w["end"][0] - w["start"][0]) + abs(w["end"][1] - w["start"][1])
        for d in w.get("doors", []):
            assert 0 <= d["offset"] and d["offset"] + d["width"] <= L + 1e-6


def test_furniture_in_walls_removed_and_ifc_builds(proj, tmp_path):
    api.room_add(proj, "EG", [11.36, 0.36, 20.0, 4.5], "wohnen")
    api.room_add(proj, "EG", [11.36, 4.5, 20.0, 8.64], "schlafen")
    spec = P.open_project(proj).spec()
    spec.setdefault("furniture", []).extend([
        {"name": "Bett quer", "origin": [14.0, 4.2, 0.0], "size": [2.0, 0.6, 0.5]},
        {"name": "Sofa", "origin": [12.0, 1.0, 0.0], "size": [2.0, 0.9, 0.8]}])
    P.open_project(proj).save(spec, "test furniture")
    r = api.rooms_walls(proj, "EG")
    assert r["status"] == "ok" and r["doors"] >= 1 and "Bett quer" in r["moebel_entfernt"]
    names = [f["name"] for f in P.open_project(proj).spec().get("furniture", [])]
    assert "Sofa" in names and "Bett quer" not in names


def test_tower_door_and_auto_furniture(proj):
    api.room_add(proj, "OG1", [11.36, 0.36, 20.0, 3.0], "kind")
    api.room_add(proj, "OG1", [11.36, 3.0, 20.0, 4.8], "flur")
    api.room_add(proj, "OG1", [11.36, 4.8, 20.0, 8.64], "schlafen")
    api.room_add(proj, "OG1", [8.12, 0.12, 10.88, 8.88], "treppe")
    r = api.rooms_walls(proj, "OG1")
    assert r["status"] == "ok" and r["doors"] >= 3
    ops = [o for o in P.open_project(proj).spec()["openings"] if o.get("internal")]
    assert len(ops) == 1 and ops[0]["volume"] == "A" and ops[0]["side"] == "W"
    f = api.rooms_furnish(proj, "OG1")
    assert f["status"] == "ok" and f["moebel_gesetzt"] >= 3
    spec = P.open_project(proj).spec()
    assert all(x.get("auto") == "OG1" and x["origin"][2] == 3.3 for x in spec["furniture"] if x.get("auto"))
    # re-running replaces, does not duplicate
    n = len([x for x in spec["furniture"] if x.get("auto")])
    api.rooms_furnish(proj, "OG1")
    assert len([x for x in P.open_project(proj).spec()["furniture"] if x.get("auto")]) == n
