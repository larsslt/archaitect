"""Programmatic interface of bimrender. The CLI and any UI call only these functions.

Every function returns a plain dict with a "status" key:
  ok | questions | manual | invalid | error
so a UI can render the result without knowing anything about Blender, IFC or the interpreter.

A project (`name`) is a spec with a version history, stored in out/<name>/ (see projects.py).
Typical flow:  new_project -> render(sketch) -> revise ... -> render(sketch) -> render(final)
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from . import projects
from .projects import PatchError, Project, open_project

ROOT = Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
QUALITIES = ["sketch", "draft", "preview", "final"]


def _err(msg: str, **kw) -> dict:
    return {"status": "error", "message": msg, **kw}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))
    return s.strip("_") or "projekt"


def camera_names(spec: dict) -> list[str]:
    cams = spec.get("render", {}).get("cameras", {})
    return list(cams) if isinstance(cams, dict) else [c.get("name") for c in cams]


def blender_env(ifc, spec, camera, quality, out, extra_env: dict | None = None) -> tuple[list[str], dict]:
    """Command line and environment of a headless render (shared by run_blender and cancellable jobs)."""
    import site
    env = dict(os.environ, BIM_SP=site.getsitepackages()[0], BIM_IFC=str(Path(ifc).resolve()),
               BIM_SPEC=str(Path(spec).resolve()), BIM_CAMERA=camera, BIM_QUALITY=quality,
               BIM_OUT=str(Path(out).resolve()), **(extra_env or {}))
    return [BLENDER, "-b", "--factory-startup", "-P", str(ROOT / "blender" / "render_ifc.py")], env


def run_blender(ifc, spec, camera, quality, out, quiet=True, extra_env: dict | None = None) -> tuple[int, str]:
    """Run render_ifc.py headless. Returns (exit code, last log lines)."""
    import site
    env = dict(os.environ, BIM_SP=site.getsitepackages()[0], BIM_IFC=str(Path(ifc).resolve()),
               BIM_SPEC=str(Path(spec).resolve()), BIM_CAMERA=camera, BIM_QUALITY=quality,
               BIM_OUT=str(Path(out).resolve()), **(extra_env or {}))
    cmd = [BLENDER, "-b", "--factory-startup", "-P", str(ROOT / "blender" / "render_ifc.py")]
    if not quiet:
        return subprocess.call(cmd, env=env), ""
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return p.returncode, "\n".join((p.stdout + p.stderr).splitlines()[-25:])


# ---------------------------------------------------------------------------- projects
def new_project(name: str | None = None, text: str | None = None, spec: str | None = None,
                images: list[str] | None = None, answers: str | None = None) -> dict:
    """Start a project from a spec file or from text/images (via the interpreter)."""
    if spec:
        try:
            proj = open_project(spec)
        except (FileNotFoundError, ValueError) as e:
            return _err(str(e))
        return {"status": "ok", "project": proj.name, "version": proj.version}
    if not text:
        return _err("Weder Spezifikationsdatei noch Text angegeben")
    from .interpret import interpret
    res = interpret(text, images or [], answers)
    if res["status"] != "ok":
        return res
    data = json_load(res["spec"])
    ensure_cameras(data)
    proj = Project(name or _slug(data.get("name", "")))
    if proj.exists():
        return _err(f"Projekt '{proj.name}' gibt es schon; anderen Namen wählen")
    v = proj.save(data, text[:80])
    import shutil
    for i, im in enumerate(images or [], 1):
        try:
            shutil.copy(im, proj.dir / f"reference_{i}{Path(im).suffix.lower()}")
        except OSError:
            pass
    from .checks import warnings
    return {"status": "ok", "project": proj.name, "version": v, "warnings": warnings(data)}


def ensure_cameras(spec: dict) -> None:
    """Interpreter output often has no camera setup: derive three default views from the volumes."""
    render = spec.setdefault("render", {})
    if render.get("cameras"):
        return
    vols = spec.get("volumes") or []
    if not vols:
        return
    x0 = min(v["origin"][0] for v in vols)
    y0 = min(v["origin"][1] for v in vols)
    x1 = max(v["origin"][0] + v["size"][0] for v in vols)
    y1 = max(v["origin"][1] + v["size"][1] for v in vols)
    h = max(v.get("base_z", 0.0) + v.get("storeys", 1) * spec.get("storey_height", 3.0) for v in vols)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = max(x1 - x0, y1 - y0, h * 2)
    tgt = [round(cx, 1), round(cy, 1), round(h * 0.4, 1)]
    render["cameras"] = [
        {"name": "hero_sw", "position": [round(cx - r * 1.1, 1), round(y0 - r * 1.5, 1), 1.65], "target": tgt, "lens_mm": 22},
        {"name": "drone_se", "position": [round(cx + r * 1.6, 1), round(y0 - r * 1.5, 1), round(h * 1.8, 1)], "target": tgt, "lens_mm": 30},
        {"name": "street_n", "position": [round(cx, 1), round(y1 + r * 1.6, 1), 1.7], "target": tgt, "lens_mm": 26},
    ]
    render.setdefault("sun", {"azimuth_deg": 225.0, "elevation_deg": 32.0})


def json_load(path) -> dict:
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))


def status(target: str) -> dict:
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    spec = proj.spec()
    images = sorted(p.name for p in proj.dir.glob("v*_*.png"))
    from .checks import warnings
    from . import rooms as R
    return {"status": "ok", "project": proj.name, "version": proj.version, "title": spec.get("name"),
            "warnings": warnings(spec), "rooms": R.analyze(spec),
            "levels": [l["name"] for l in R.levels(spec)], "functions": {k: v[0] for k, v in R.FUNCTIONS.items()},
            "cameras": camera_names(spec), "history": proj.history(), "images": images,
            "ifc": str(proj.ifc_path) if proj.ifc_path.exists() else None, "dir": str(proj.dir),
            "references": sorted(p.name for p in proj.dir.glob("reference_*"))}


COMPARE_TASK = """# Aufgabe: Abgleich Referenz gegen Modell

Die ersten Bilder sind die Referenz des Nutzers, das letzte Bild ist der aktuelle Render des Modells (Vorskizze aus der Spezifikation unten).
Vergleiche streng und konkret: Dachform und Neigung, Anzahl Vollgeschosse, Proportion (Breite zu Höhe), Fassadenmaterial und Muster
(Fachwerk, Sockel), Anzahl und Lage der Fenster/Türen je Geschoss und Seite, Balkon, Giebelöffnungen, Materialien.
Antworte nur mit JSON: {"uebereinstimmung_prozent": Zahl 0-100, "abweichungen": ["...", ...] (höchstens 8, wichtigste zuerst),
"aenderung": "ein zusammenhängender Änderungswunsch in einfachen Sätzen, der nur Dinge enthält, die die Spezifikation ausdrücken kann
(Volumen, roof, facade_detail, Öffnungen, Balkon, Materialien). Leer, wenn nichts Sinnvolles zu ändern ist."}
Erfinde keine Abweichungen: Was gleich aussieht, nicht erwähnen. Was die Spezifikation nicht ausdrücken kann (Gauben, Blumenkästen,
Nachbarhäuser), gehört nicht in "aenderung".

# Aktuelle Spezifikation
"""


def compare(target: str, apply: bool = True, camera: str | None = None) -> dict:
    """Vision check of the latest sketch against the stored reference image(s); optionally apply the proposed change."""
    import json as _json
    from .interpret import _image_part, _llm, _system
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    refs = sorted(proj.dir.glob("reference_*"))
    if not refs:
        return _err("Zu diesem Projekt gibt es kein Referenzbild (nur Projekte aus Bild + Text haben eines)")
    import os
    if not os.environ.get("BIMRENDER_LLM_URL"):
        return {"status": "manual", "bundle": "", "next": "Kein Sprachmodell verbunden."}
    spec = proj.spec()
    cams = camera_names(spec)
    cam = camera if camera in cams else cams[0]
    latest = proj.dir / f"v{proj.version:03d}_{cam}_sketch.png"
    if not latest.exists():
        r = render(target, "sketch", cam)
        if r.get("status") != "ok":
            return r
    content = [{"type": "text", "text": COMPARE_TASK + _json.dumps(spec, ensure_ascii=False)}] + \
              [_image_part(str(p)) for p in refs] + [_image_part(str(latest))]
    raw = _llm([{"role": "system", "content": _system()}, {"role": "user", "content": content}])
    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError as e:
        return _err(f"Antwort des Sprachmodells ist kein JSON: {e}")
    dev = [str(x) for x in data.get("abweichungen", [])][:8]
    change = str(data.get("aenderung") or "").strip()
    pct = data.get("uebereinstimmung_prozent")
    text = f"Übereinstimmung etwa {pct} %." if pct is not None else ""
    if dev:
        text += "\nAbweichungen:\n- " + "\n- ".join(dev)
    out = {"status": "ok", "project": proj.name, "version": proj.version, "hinweis": text, "applied": False,
           "abweichungen": dev, "aenderung": change}
    if apply and change:
        res = revise(target, change)
        if res.get("status") != "ok":
            return {**out, "status": res.get("status", "error"), "problems": res.get("problems"), "message": res.get("message"),
                    "hinweis": text + "\nÄnderung nicht übernommen."}
        out.update(applied=True, version=res.get("version", proj.version), summary="Abgleich mit Referenz: " + change[:100])
    return out


def has_timber(target: str) -> bool:
    try:
        return any((v.get("facade_detail") or {}).get("timber_frame") for v in open_project(target).spec().get("volumes", []))
    except (FileNotFoundError, ValueError):
        return False


def detail(target: str, sides=None, rounds: int = 2) -> dict:
    """Facade detail pass (timber frame, brackets) from the reference image, see detail.py."""
    from .detail import run
    return run(target, sides, rounds)


def revise(target: str, text: str) -> dict:
    """Plain-text change request -> new version (needs the interpreter, see interpret.py)."""
    from .interpret import revise as _revise
    try:
        return _revise(open_project(target), text)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))


def apply(target: str, answer, note: str = "") -> dict:
    """Apply an interpreter answer (patch list/dict or full spec) as a new version."""
    from .interpret import apply_answer
    try:
        return apply_answer(open_project(target), answer, note)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))


def undo(target: str) -> dict:
    try:
        proj = open_project(target)
        return {"status": "ok", "version": proj.undo(), "summary": "zurück"}
    except (FileNotFoundError, ValueError, PatchError) as e:
        return _err(str(e))


# ---------------------------------------------------------------------------- rendering
def render(target: str, quality: str = "sketch", camera: str = "hero_sw") -> dict:
    """Build the IFC from the current version and render it. quality: sketch | draft | preview | final."""
    if quality not in QUALITIES:
        return _err(f"quality muss eines von {QUALITIES} sein")
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    names = camera_names(proj.spec())
    if camera not in names:
        camera = names[0]
    t0 = time.time()
    from .ifcgen import build_ifc
    try:
        build_ifc(str(proj.current_path), str(proj.ifc_path))
    except Exception as e:
        return _err(f"IFC-Aufbau fehlgeschlagen: {e}")
    out = proj.dir / f"v{proj.version:03d}_{camera}_{quality}.png"
    rc, tail = run_blender(proj.ifc_path, proj.current_path, camera, quality, out)
    if rc or not out.exists():
        return _err("Render fehlgeschlagen", log=tail)
    return {"status": "ok", "project": proj.name, "version": proj.version, "camera": camera, "quality": quality,
            "image": str(out), "scene": str(out.with_suffix(".blend")), "ifc": str(proj.ifc_path),
            "seconds": round(time.time() - t0)}


# ---------------------------------------------------------------------------- rooms
def _mutate(target: str, fn, note: str) -> dict:
    """Edit a copy of the current spec; save as a new version only if it validates."""
    import copy
    from .interpret import validate_spec
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    spec = copy.deepcopy(proj.spec())
    try:
        extra = fn(spec) or {}
    except (KeyError, ValueError) as e:
        return _err(str(e.args[0]) if e.args else str(e))
    problems = validate_spec(spec)
    if problems:
        return {"status": "invalid", "problems": problems}
    v = proj.save(spec, note)
    from . import rooms as R
    return {"status": "ok", "project": proj.name, "version": v, "summary": note, "rooms": R.analyze(spec), **extra}


def _unique_name(spec: dict, level: str, base: str) -> str:
    names = {r["name"] for r in spec.get("rooms", []) if r["level"] == level}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def room_add(target: str, level: str, rect, function: str, name: str | None = None) -> dict:
    from . import rooms as R

    def fn(spec):
        if function not in R.FUNCTIONS:
            raise ValueError(f"Funktion '{function}' unbekannt")
        R.level_elev(spec, level)
        rc = R.snap_rect(rect)
        if rc[2] - rc[0] < 0.5 or rc[3] - rc[1] < 0.5:
            raise ValueError("Raum zu klein (mindestens 0,5 m je Seite)")
        nm = _unique_name(spec, level, (name or R.FUNCTIONS[function][0]).strip())
        spec.setdefault("rooms", []).append({"id": R.next_id(spec), "name": nm, "function": function, "level": level, "rect": rc})
        return {"room": nm}
    return _mutate(target, fn, f"Raum {name or R.FUNCTIONS.get(function, ('?',))[0]} ({level})")


def room_set(target: str, room_id: str, name: str | None = None, function: str | None = None, rect=None) -> dict:
    from . import rooms as R

    def fn(spec):
        r = next((x for x in spec.get("rooms", []) if x["id"] == room_id), None)
        if not r:
            raise ValueError(f"Raum {room_id} gibt es nicht")
        if function:
            if function not in R.FUNCTIONS:
                raise ValueError(f"Funktion '{function}' unbekannt")
            r["function"] = function
        if name:
            r["name"] = name.strip()
        if rect:
            r["rect"] = R.snap_rect(rect)
    return _mutate(target, fn, f"Raum {room_id} geändert")


def room_delete(target: str, room_id: str) -> dict:
    def fn(spec):
        n = len(spec.get("rooms", []))
        spec["rooms"] = [r for r in spec.get("rooms", []) if r["id"] != room_id]
        if len(spec["rooms"]) == n:
            raise ValueError(f"Raum {room_id} gibt es nicht")
    return _mutate(target, fn, f"Raum {room_id} gelöscht")


def rooms_clear(target: str, level: str) -> dict:
    def fn(spec):
        spec["rooms"] = [r for r in spec.get("rooms", []) if r["level"] != level]
    return _mutate(target, fn, f"Räume {level} entfernt")


def rooms_walls(target: str, level: str) -> dict:
    """Interior walls along the room boundaries of one level (replaces earlier generated ones)."""
    from . import rooms as R

    def fn(spec):
        elev = R.level_elev(spec, level)
        new = R.partitions_from_rooms(spec, level)
        if not new:
            raise ValueError("Auf diesem Geschoss gibt es keine Räume, aus denen Wände entstehen könnten")
        # the room layout is the new truth for this level: earlier interior walls of the level are replaced
        spec["partitions"] = [p for p in spec.get("partitions", []) if abs(float(p["z"]) - elev) > 0.05] + new
        doors = R.door_plan(spec, level)
        removed = R.clean_furniture(spec, level, new, doors)
        vols = {v["id"]: v for v in spec.get("volumes", [])}
        spec["openings"] = [o for o in spec.get("openings", [])
                            if not (o.get("internal") and abs(float(vols[o["volume"]].get("base_z", 0.0)) + int(o["storey"]) *
                                                              float(vols[o["volume"]].get("storey_height", spec.get("storey_height", 3.0))) - elev) < 0.2)]
        passages = R.passage_openings(spec, level)
        spec["openings"].extend(passages)
        return {"walls": len(new), "doors": sum(len(p.get("doors", [])) for p in new) + len(passages),
                "moebel_entfernt": removed}
    return _mutate(target, fn, f"Innenwände aus Räumen {level}")


def rooms_furnish(target: str, level: str) -> dict:
    """Furniture matching the room functions of one level (see rooms.furnish)."""
    from . import rooms as R

    def fn(spec):
        R.level_elev(spec, level)
        if not [r for r in spec.get("rooms", []) if r["level"] == level]:
            raise ValueError("Auf diesem Geschoss gibt es keine Räume")
        return R.furnish(spec, level)
    return _mutate(target, fn, f"Möbel passend zu den Räumen {level}")


def rooms_auto(target: str, level: str, brief: str = "", mode: str = "divide") -> dict:
    from .roomplan import auto_rooms
    try:
        res = auto_rooms(open_project(target), level, brief, mode)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    if res.get("status") == "ok":
        from . import rooms as R
        res["project"] = open_project(target).name
        res["rooms_all"] = R.analyze(open_project(target).spec())
    return res


def plans(target: str) -> dict:
    """Floor plans (SVG, one per storey) cut from the IFC of the current version."""
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    t0 = time.time()
    from .ifcgen import build_ifc
    from .plan import build_plans
    try:
        out = proj.dir / "plans" / f"v{proj.version:03d}"
        out.mkdir(parents=True, exist_ok=True)
        for old in list(out.glob("plan_*.svg")) + list(out.glob("plan_*.json")):
            old.unlink()
        spec = proj.spec()
        ifc = out / "model.ifc"  # own file: a running render may be reading the project IFC
        build_ifc(str(proj.current_path), str(ifc))
        res = build_plans(ifc, out, spec.get("name", ""), spec=spec)
    except Exception as e:
        return _err(f"Grundriss fehlgeschlagen: {e}")
    if not res:
        return _err("Keine Geschosse mit Wänden gefunden")
    return {"status": "ok", "project": proj.name, "version": proj.version, "plans": res,
            "seconds": round(time.time() - t0)}


GLB_FORMAT = "2"  # bump when the GLB export changes (old files are regenerated)


def model3d(target: str) -> dict:
    """GLB of the current version for a turnable 3D view (simplified materials, no grass/leaves)."""
    try:
        proj = open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return _err(str(e))
    glb = proj.dir / f"v{proj.version:03d}.glb"
    stamp = proj.dir / ".glb_format"
    if not stamp.exists() or stamp.read_text() != GLB_FORMAT:
        for old in proj.dir.glob("v*.glb"):
            old.unlink()
        stamp.write_text(GLB_FORMAT)
    if glb.exists():
        return {"status": "ok", "project": proj.name, "version": proj.version, "glb": str(glb), "seconds": 0}
    t0 = time.time()
    from .ifcgen import build_ifc
    try:
        build_ifc(str(proj.current_path), str(proj.ifc_path))
    except Exception as e:
        return _err(f"IFC-Aufbau fehlgeschlagen: {e}")
    rc, tail = run_blender(proj.ifc_path, proj.current_path, camera_names(proj.spec())[0], "sketch",
                           proj.dir / "_unused.png", extra_env={"BIM_GLB": str(glb)})
    if rc or not glb.exists():
        return _err("3D-Export fehlgeschlagen", log=tail)
    return {"status": "ok", "project": proj.name, "version": proj.version, "glb": str(glb),
            "seconds": round(time.time() - t0)}
