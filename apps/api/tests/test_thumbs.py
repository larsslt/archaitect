import json

import pytest

from archaitect.bim import thumbs

HOUSES = ("stadthaus",)


def test_unknown_name_rejected():
    with pytest.raises(ValueError):
        thumbs.mesh_file("../etc/passwd", HOUSES)


@pytest.mark.parametrize("kind", ["tree", "bench", "flowerbed"])
def test_object_preview_is_a_real_mesh(kind, tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "_CACHE", tmp_path)
    f = thumbs.mesh_file(kind, HOUSES)
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data["parts"] and data["bounds"] and all(p["positions"] and p["indices"] for p in data["parts"])
    assert thumbs.mesh_file(kind, HOUSES) == f          # cached


def test_house_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "_CACHE", tmp_path)
    data = json.loads(thumbs.mesh_file("stadthaus", HOUSES).read_text(encoding="utf-8"))
    assert len(data["parts"]) > 3


def test_every_library_object_has_a_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbs, "_CACHE", tmp_path)
    from archaitect.bim.objects import LIBRARY_OBJECTS
    for name in LIBRARY_OBJECTS:
        data = json.loads(thumbs.mesh_file(name, HOUSES).read_text(encoding="utf-8"))
        assert data["parts"], name
