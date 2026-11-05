import pytest

from archaitect.bim import objects as O


def spec():
    return {"volumes": [{"id": "A", "origin": [0, 0], "size": [9, 11], "storeys": 2, "base_z": 0},
                        {"id": "B", "origin": [9, 0], "size": [4, 6], "storeys": 1, "base_z": 0},     # touches A -> same building
                        {"id": "G", "origin": [30, 0], "size": [5, 5], "storeys": 1, "base_z": 0}],  # separate building
            "openings": [{"volume": "G", "side": "S"}, {"volume": "A", "side": "S"}],
            "site": {"pools": [{"name": "Pool", "origin": [0, 20], "size": [4, 8]}], "trees": [{"name": "Baum", "position": [20, 20], "crown_radius": 3, "height": 8}]},
            "components": [{"type": "tree", "x": 25, "y": 5}]}


def test_objects_group_touching_volumes():
    ids = [o["id"] for o in O.objects(spec())]
    assert ids[:2] == ["bld:A", "bld:G"] and "site.pools.0" in ids and "site.trees.0" in ids and "comp.0" in ids


def test_move_moves_only_that_object():
    s = O.move(spec(), "site.pools.0", 2, 1)
    assert s["site"]["pools"][0]["origin"] == [2, 21] and s["volumes"][0]["origin"] == [0, 0] and s["site"]["trees"][0]["position"] == [20, 20]
    s = O.move(spec(), "bld:A", 0, 3)
    assert [v["origin"] for v in s["volumes"]] == [[0, 3], [9, 3], [30, 0]]


def test_overlap_is_refused_and_delete_works():
    with pytest.raises(ValueError, match="würde in"):
        O.move(spec(), "bld:G", -20, 0)
    s = O.delete(spec(), "comp.0")
    assert s["components"] == []
    s = O.delete(spec(), "bld:G")
    assert [v["id"] for v in s["volumes"]] == ["A", "B"] and all(o["volume"] != "G" for o in s["openings"])
    last = O.delete(O.delete(spec(), "bld:G"), "bld:A")      # the last building may be deleted too (undo restores it)
    assert last["volumes"] == []
