from archaitect.bim import logic


def _spec(level):
    return {"storey_height": 3.0, "volumes": [{"id": "v1", "origin": [0, 0], "size": [10, 8], "storeys": 2, "base_z": 0.0}],
            "openings": [{"volume": "v1", "side": "S", "storey": 0, "kind": "door", "offset": 4.0, "width": 1.0, "sill": 0.0, "height": 2.1, "door_type": "panel"}],
            "balconies": [{"volume": "v1", "side": "S", "level": level, "offset": 3.0, "width": 3.0, "depth": 1.5}],
            "components": [{"type": "canopy", "volume": "v1", "side": "S", "u": 4.5, "width": 2.2, "z": 2.5}]}


def test_canopy_not_under_balcony():
    notes = []
    s = _spec(3.0)
    logic._clip_roofing_parts(s, notes)
    assert not [c for c in s["components"] if c["type"] == "canopy"], notes


def test_canopy_kept_without_balcony():
    notes = []
    s = _spec(3.0)
    s["balconies"] = []
    logic._clip_roofing_parts(s, notes)
    assert [c for c in s["components"] if c["type"] == "canopy"]


def test_bay_is_lifted_above_entrance_door():
    s = {"storey_height": 3.0, "volumes": [{"id": "A", "origin": [0, 0], "size": [11, 10], "storeys": 3, "base_z": 0.0}],
         "openings": [{"volume": "A", "side": "N", "storey": 0, "kind": "door", "offset": 4.9, "width": 1.2, "sill": 0.0, "height": 2.4, "door_type": "panel"}],
         "balconies": [], "components": [{"type": "bay", "volume": "A", "side": "N", "u": 5.5, "width": 3.0, "z0": 0.0, "z1": 6.0},
                                           {"type": "canopy", "volume": "A", "side": "N", "u": 5.5, "width": 2.8, "z": 2.6}]}
    notes = []
    logic._bays_clear_entrance(s, notes)
    bay = next(c for c in s["components"] if c["type"] == "bay")
    assert bay["z0"] >= 3.0, notes
