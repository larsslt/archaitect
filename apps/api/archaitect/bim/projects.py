"""Projects = a spec that changes over time. Every change becomes a numbered version.

Layout:  out/<name>/versions/v001.json, v002.json, ...   (never overwritten)
         out/<name>/current.json                          (copy of the active version)
         out/<name>/history.json                          (version, parent, time, note)

Changes arrive as a patch (RFC 6902 subset: add / replace / remove). Besides numeric indices,
path segments may select array elements by value, e.g. /openings/volume=A&side=S&storey=0/width
or /volumes/id=B/size/0. A selector must match exactly one element.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_projects"


class PatchError(ValueError):
    pass


def _match(el, cond: str) -> bool:
    for part in cond.split("&"):
        k, _, v = part.partition("=")
        if not isinstance(el, dict) or str(el.get(k)) != v:
            return False
    return True


def _index(lst: list, seg: str, allow_end: bool = False) -> int:
    if seg == "-" and allow_end:
        return len(lst)
    if seg.isdigit():
        i = int(seg)
        if i < len(lst) or (allow_end and i == len(lst)):
            return i
        raise PatchError(f"Index {i} außerhalb der Liste (Länge {len(lst)})")
    if "=" in seg:
        hits = [i for i, e in enumerate(lst) if _match(e, seg)]
        if len(hits) != 1:
            raise PatchError(f"Selektor '{seg}' trifft {len(hits)} Elemente, nötig ist genau 1")
        return hits[0]
    raise PatchError(f"ungültiges Pfadsegment '{seg}'")


def _child(node, seg: str):
    if isinstance(node, dict):
        if seg not in node:
            raise PatchError(f"Schlüssel '{seg}' existiert nicht")
        return node[seg]
    if isinstance(node, list):
        return node[_index(node, seg)]
    raise PatchError(f"Pfad führt in einen Wert ('{seg}')")


def _segments(path: str) -> list[str]:
    if not path.startswith("/"):
        raise PatchError(f"Pfad muss mit / beginnen: '{path}'")
    return [s.replace("~1", "/").replace("~0", "~") for s in path[1:].split("/")]


def apply_patch(spec: dict, ops: list[dict]) -> dict:
    """Apply ops to a deep copy; any failure raises PatchError and changes nothing."""
    doc = copy.deepcopy(spec)
    for n, op in enumerate(ops, 1):
        try:
            kind, segs = op["op"], _segments(op["path"])
            node = doc
            for seg in segs[:-1]:
                node = _child(node, seg)
            last = segs[-1]
            if kind == "add":
                if isinstance(node, list):
                    node.insert(_index(node, last, allow_end=True), copy.deepcopy(op["value"]))
                elif isinstance(node, dict):
                    node[last] = copy.deepcopy(op["value"])
                else:
                    raise PatchError("Ziel ist kein Objekt oder Liste")
            elif kind == "replace":
                if isinstance(node, list):
                    node[_index(node, last)] = copy.deepcopy(op["value"])
                elif isinstance(node, dict) and last in node:
                    node[last] = copy.deepcopy(op["value"])
                else:
                    raise PatchError(f"'{last}' existiert nicht (replace braucht ein vorhandenes Ziel)")
            elif kind == "remove":
                if isinstance(node, list):
                    del node[_index(node, last)]
                elif isinstance(node, dict) and last in node:
                    del node[last]
                else:
                    raise PatchError(f"'{last}' existiert nicht")
            else:
                raise PatchError(f"unbekannte Operation '{kind}'")
        except KeyError as e:
            raise PatchError(f"Operation {n}: Feld {e} fehlt") from e
        except PatchError as e:
            raise PatchError(f"Operation {n} ({op.get('op')} {op.get('path')}): {e}") from e
    return doc


def _sha(spec: dict) -> str:
    return hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]


class Project:
    def __init__(self, name: str, root: Path | None = None):
        self.name = name
        self.dir = Path(root or OUT) / name
        self.versions_dir = self.dir / "versions"
        self.current_path = self.dir / "current.json"
        self.history_path = self.dir / "history.json"
        self.ifc_path = self.dir / "model.ifc"

    def exists(self) -> bool:
        return self.current_path.exists()

    def spec(self) -> dict:
        return json.loads(self.current_path.read_text(encoding="utf-8"))

    def history(self) -> list[dict]:
        if not self.history_path.exists():
            return []
        return json.loads(self.history_path.read_text(encoding="utf-8"))

    @property
    def version(self) -> int:
        h = self.history()
        return h[-1]["version"] if h else 0

    def _write(self, spec: dict, note: str, parent: int | None) -> int:
        hist = self.history()
        n = (hist[-1]["version"] if hist else 0) + 1
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(spec, indent=2, ensure_ascii=False)
        (self.versions_dir / f"v{n:03d}.json").write_text(text, encoding="utf-8")
        self.current_path.write_text(text, encoding="utf-8")
        hist.append({"version": n, "parent": parent, "note": note, "sha": _sha(spec),
                     "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
        self.history_path.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
        return n

    def save(self, spec: dict, note: str = "") -> int:
        """New version on top of the current one."""
        return self._write(spec, note, self.version or None)

    def undo(self) -> int:
        """Make the parent of the current version the active one again (as a new version, nothing is lost)."""
        hist = self.history()
        cur = hist[-1]
        if not cur["parent"]:
            raise PatchError("Es gibt keine frühere Version")
        parent = next(h for h in hist if h["version"] == cur["parent"])
        spec = json.loads((self.versions_dir / f"v{parent['version']:03d}.json").read_text(encoding="utf-8"))
        return self._write(spec, f"zurück auf v{parent['version']:03d}", parent["parent"])


def open_project(target: str) -> Project:
    """target = project name (continue) or path to a spec .json (start / restart from that file)."""
    if isinstance(target, Project):
        return target
    p = Path(target)
    if p.suffix == ".json" and p.exists():
        spec = json.loads(p.read_text(encoding="utf-8"))
        proj = Project(p.stem)
        if proj.exists() and _sha(proj.spec()) == _sha(spec):
            return proj
        proj.save(spec, f"Start aus {p.name}")
        return proj
    proj = Project(target)
    if not proj.exists():
        raise FileNotFoundError(f"Projekt '{target}' gibt es nicht. Mit einer Spezifikationsdatei starten, z.B. specs/{target}.json")
    return proj
