import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from shapely.geometry import box

from archaitect.siteintel import bim_api


class Project:
    def __init__(self):
        self.current = {"volumes": [{"id": "v1", "origin": [0, 0], "size": [4, 4]}], "components": [], "site": {"placement": {"x": 10, "y": 20, "rotation_deg": 90}}}
        self.saved = []

    def spec(self):
        return self.current

    def save(self, spec, note):
        self.saved.append(copy.deepcopy(spec))


@pytest.fixture
def project(monkeypatch):
    p = Project()
    monkeypatch.setattr(bim_api, '_project', lambda pid: p)
    monkeypatch.setattr(bim_api, '_site', lambda pid: (SimpleNamespace(site=box(-30, -30, 50, 50)), None, None))
    monkeypatch.setattr(bim_api, '_prepare', lambda pid, spec: (spec, []))
    monkeypatch.setattr(bim_api, '_sync_massing', lambda pid, spec: None)
    monkeypatch.setattr(bim_api, '_state', lambda pid, proj: {})
    return p


def test_add_uses_site_position_and_preserves_old_spec(project):
    bim_api.add_object('p', bim_api.AddObjectBody(kind='shrub', x=4, y=26))
    c = project.saved[0]['components'][0]
    assert c['x'] == 6 and c['y'] == 6
    assert project.current['components'] == []


def test_reject_collision_and_outside_before_saving(project):
    with pytest.raises(HTTPException) as collision:
        bim_api.add_object('p', bim_api.AddObjectBody(kind='tree', x=8, y=22))
    assert collision.value.status_code == 409
    with pytest.raises(HTTPException) as outside:
        bim_api.add_object('p', bim_api.AddObjectBody(kind='tree', x=49, y=45))
    assert outside.value.status_code == 422
    assert project.saved == []
