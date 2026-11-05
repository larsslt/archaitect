import pytest

from archaitect.bim import objects as O


def _spec():
    return {"volumes": [{"id": "H", "origin": [0, 0], "size": [10, 8], "storeys": 2}, {"id": "G", "origin": [10, 0], "size": [4, 6], "storeys": 1},
                        {"id": "D", "origin": [2, 2], "size": [3, 3], "storeys": 1, "base_z": 5.8}],
            "openings": [{"volume": "G", "side": "S"}, {"volume": "H", "side": "S"}], "balconies": [], "components": [{"type": "chimney", "volume": "D"}]}


def test_touching_volumes_form_one_building_until_detached():
    s = _spec()
    assert len([o for o in O.objects(s) if o["kind"] == "house"]) == 1
    s2 = O.detach_volume(s, "G")
    houses = [o for o in O.objects(s2) if o["kind"] == "house"]
    assert len(houses) == 2 and any(o["volumes"] == ["G"] for o in houses)


def test_detach_twice_refused():
    s = O.detach_volume(_spec(), "G")
    with pytest.raises(ValueError):
        O.detach_volume(s, "G")


def test_delete_volume_removes_its_parts():
    s = O.delete_volume(_spec(), "D")
    assert [v["id"] for v in s["volumes"]] == ["H", "G"] and s["components"] == [] and len(s["openings"]) == 2
    s = O.delete_volume(_spec(), "G")
    assert [o["volume"] for o in s["openings"]] == ["H"]


def test_last_volume_cannot_be_deleted():
    s = _spec()
    s["volumes"] = s["volumes"][:1]
    with pytest.raises(ValueError):
        O.delete_volume(s, "H")
    with pytest.raises(ValueError):
        O.delete_volume(_spec(), "X")
