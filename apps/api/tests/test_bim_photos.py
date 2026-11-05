"""Bilderwelt: automatic camera choice, 4K finishing, API state (Meta call mocked)."""
import io

from PIL import Image

from archaitect.siteintel import bim_photos as BP


def _spec():
    return {"volumes": [{"id": "A", "origin": [0, 0], "size": [9, 11], "base_z": 0.5, "storeys": 3, "storey_height": 2.8}],
            "components": [{"type": "sauna_hut", "x": 6.0, "y": -22.0, "width": 3.8, "depth": 3.0}], "description": "Fachwerkhaus"}


def _terrain():
    ring = [[-30, -60], [40, -60], [40, 25], [-30, 25], [-30, -60]]
    lake = [[2, -40], [14, -40], [14, -28], [2, -28], [2, -40]]
    return {"parcel_ring": ring, "lakes": [{"i": 3, "level": -3.0, "ring": lake}]}


def test_four_shots_inside_parcel_and_distinct():
    cams = BP.shots(_spec(), _terrain())
    assert [c["name"] for c in cams] == ["photo_main", "photo_close1", "photo_close2", "photo_aerial"]
    from shapely.geometry import Point, Polygon
    pg = Polygon(_terrain()["parcel_ring"])
    for c in cams[:3]:
        assert pg.contains(Point(c["position"][0], c["position"][1])), c["name"]      # never behind the fog bank
    assert cams[3]["position"][2] > 40                                                  # aerial really is high
    assert len({tuple(c["position"]) for c in cams}) == 4


def test_close2_looks_at_lake_and_hut_when_present():
    cams = BP.shots(_spec(), _terrain())
    t = cams[2]["target"]
    assert -35 < t[1] < -18 and 0 < t[0] < 14


def test_finish_gives_4k_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (2048, 1152), (90, 120, 80)).save(buf, "WEBP")
    out = BP.finish(buf.getvalue())
    im = Image.open(io.BytesIO(out))
    assert im.size == BP.TARGET and im.format == "JPEG"


def test_prompt_only_upscales():
    p = BP.prompt("main", _spec())
    assert "DO NOT change" in p and "screenshot" in p and "number and position of every window" in p
