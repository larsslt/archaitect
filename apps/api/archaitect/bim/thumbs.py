"""Vorschau-Netze für die Bibliothek: jedes Beispielhaus und jedes Gartenobjekt als echtes 3D-Netz (dasselbe Modell wie im Entwurf).

Der Browser rendert daraus das Vorschaubild (Isometrie, transparenter Hintergrund). Hier wird nur gebaut und auf der Platte zwischengespeichert.
Objekte: ein Minimal-Entwurf ohne Gebäude mit genau einem Bauteil im Ursprung. Häuser: die Spec aus bim/specs."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from . import meshexport
from .catalog import C
from .ifcgen import build_ifc

from .objects import LIBRARY_OBJECTS

OBJECT_KINDS = tuple(LIBRARY_OBJECTS)
_SPECS = Path(__file__).resolve().parent / "specs"
_CACHE = Path(tempfile.gettempdir()) / "archaitect_thumbs"
_LOCK = threading.Lock()
_GEN = "t5"                      # bump when the preview format changes


EXTRA_COMPONENTS = frozenset({"pool", "pond", "tree", "shrub", "hedge", "flowerbed", "bench", "garden_set", "garden_light", "path", "fence", "parking"})
EXTRA_SITE_KEYS = ("pools", "paving", "paths", "hedges", "trees")


def house_only(spec: dict) -> dict:
    """The building without garden dressing: pool, trees, hedges, paths, paving and furniture are library objects of their own."""
    out = json.loads(json.dumps(spec))
    out["components"] = [c for c in out.get("components", []) if c.get("type") not in EXTRA_COMPONENTS]
    out.pop("pergolas", None)                # garden structures belong to the objects, not to the house
    boxes = [(v["origin"][0] - 0.3, v["origin"][1] - 0.3, v["origin"][0] + v["size"][0] + 0.3, v["origin"][1] + v["size"][1] + 0.3) for v in out.get("volumes", [])]
    if isinstance(out.get("furniture"), list):      # only furniture inside a volume footprint stays (no loose benches / tables in the garden)
        def inside(f):
            x, y = float(f["origin"][0]), float(f["origin"][1])
            return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes)
        out["furniture"] = [f for f in out["furniture"] if inside(f)]
    site = out.get("site")
    if isinstance(site, dict):
        for k in EXTRA_SITE_KEYS:
            site.pop(k, None)
    return out


def _object_spec(kind: str) -> dict:
    frame = json.loads((_SPECS / "garten.json").read_text(encoding="utf-8"))
    _cat, btype, over, _label = LIBRARY_OBJECTS[kind]
    comp = {k: p[1] for k, p in C[btype]["params"].items() if p[1] is not None}
    comp.update(over)
    comp.update(type=btype, x=0.0, y=0.0)
    keep = {k: frame[k] for k in ("spec_version", "levels", "storey_height", "slab_thickness", "defaults") if k in frame}
    return {**keep, "name": kind, "volumes": [], "openings": [], "components": [comp]}


def known(name: str, houses: tuple[str, ...]) -> bool:
    return name in OBJECT_KINDS or name in houses


def mesh_file(name: str, houses: tuple[str, ...]) -> Path:
    """Path of the cached preview mesh JSON; builds it on first use. ValueError for an unknown name."""
    if not known(name, houses):
        raise ValueError(name)
    src = _SPECS / f"{name}.json"
    if name in houses and src.exists():
        stamp = int(src.stat().st_mtime)
    else:                                       # garden objects: rebuild when a generator or the catalog changed
        stamp = int(max(p.stat().st_mtime for p in _SPECS.parent.glob("ifc_garden*.py")))
    out = _CACHE / f"{_GEN}_{name}_{stamp}.json"
    with _LOCK:
        if out.exists():
            return out
        _CACHE.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix="thumb_", dir=_CACHE))
        spec_path = work / "spec.json"
        if name in OBJECT_KINDS:
            spec = _object_spec(name)
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
        else:
            spec = house_only(json.loads(src.read_text(encoding="utf-8")))
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
        ifc = work / "m.ifc"
        build_ifc(str(spec_path), str(ifc))
        data = meshexport.build(ifc, None, spec)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps({"parts": data["parts"], "bounds": data["bounds"]}), encoding="utf-8")
        tmp.replace(out)
        for f in work.iterdir():
            f.unlink(missing_ok=True)
        work.rmdir()
    return out
