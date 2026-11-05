"""HTTP surface of the BIM building pipeline (text/photo -> spec -> IFC -> sketch/final render, 360° mesh, plans) on the plot of a project.

Mounted into the siteintel router. One building per project: ``<project>/bim/model/`` holds numbered spec versions (bim.projects.Project).
The spec carries ``site.placement`` (position on the plot); the graded terrain (DGM1 + building pad) is DERIVED from plot data + spec on demand
and never stored in a version, so a changed placement or house always gets matching ground.
The rule check uses the existing verified rule engine through ``bim_bridge``; missing law inputs stay UNKNOWN.
No paid API: the language model is the local Ollama (or whatever ``BIMRENDER_LLM_URL`` points to, configured server-side).
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..bim import api as bim, checks as bim_checks, meshexport, terrain as bterrain
from ..bim.projects import PatchError, Project
from . import ai
from .bim_bridge import check_spec, place_spec
from .safe_route import SafeRoute

log = logging.getLogger("archaitect.bim_api")

bim_router = APIRouter(route_class=SafeRoute)
QUALITIES = bim.QUALITIES
_JOB_LOCK = threading.Lock()
_PROCS: dict[str, subprocess.Popen] = {}
_JID = re.compile(r"^j_[0-9a-f]{10}$")
MAX_WAITING = 1


def _generator_hash() -> str:
    """Cache key for everything derived from the generator code: a changed IFC/mesh generator must not be served stale files."""
    import hashlib
    h = hashlib.sha1()
    for f in sorted(Path(bim.__file__).parent.glob("*.py")):
        if f.name.startswith(("ifc", "logic", "expand", "meshexport", "terrain", "fachwerk", "objects")):
            h.update(f.read_bytes())
    return h.hexdigest()[:6]


_GEN = _generator_hash()


def _R():
    from . import router as R            # late import: router includes this module at the end
    return R


def _project(pid: str, must_exist: bool = True) -> Project:
    R = _R()
    R._need(pid)
    proj = Project("model", root=R.store()._dir(pid) / "bim")
    if must_exist and not proj.exists():
        raise HTTPException(404, "Für dieses Projekt gibt es noch keinen Hausentwurf.")
    return proj


def _site(pid: str):
    from .design_api import ctx_for
    return ctx_for(pid)


# ------------------------------------------------------------------------------------------------ language model (local, no paid default)
META_BASE = "https://api.meta.ai"
META_MODEL = "muse-spark-1.3"


def _provider() -> str:
    """Which model answers: 'custom' (BIMRENDER_LLM_URL set by the operator), 'meta' (Meta AI key in the backend environment), 'ollama' (local) or 'none'.
    ARCHAITECT_BIM_LLM=ollama|meta forces one; the key itself never leaves the backend process."""
    forced = os.environ.get("ARCHAITECT_BIM_LLM", "").lower()
    if os.environ.get("BIMRENDER_LLM_URL") and os.environ.get("BIMRENDER_LLM_PROVIDER") not in ("meta", "ollama"):
        return "custom"
    if forced != "ollama" and (os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        return "meta"
    if forced != "meta" and ai.status().get("ollama", {}).get("ok"):
        return "ollama"
    return "none"


def _configure_llm(with_images: bool) -> str | None:
    """Point the interpreter at the configured model. Returns None if one is available, else a German explanation."""
    prov = _provider()
    if prov == "custom":
        return None
    if prov == "meta":
        os.environ["BIMRENDER_LLM_URL"] = META_BASE
        os.environ["BIMRENDER_LLM_PROVIDER"] = "meta"
        os.environ["BIMRENDER_LLM_MODEL"] = os.environ.get("ARCHAITECT_META_MODEL", META_MODEL)
        os.environ["BIMRENDER_LLM_KEY"] = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY", "")
        os.environ.setdefault("BIMRENDER_LLM_MAX_TOKENS", "12000")
        os.environ.setdefault("BIMRENDER_LLM_TIMEOUT", "120")
        os.environ.setdefault("BIMRENDER_LLM_RETRIES", "0")
        os.environ.setdefault("BIMRENDER_LLM_REASONING", "low")
        os.environ["BIMRENDER_PROMPT"] = "full"
        return None
    if prov == "ollama":
        os.environ["BIMRENDER_LLM_URL"] = ai.ollama_host()
        os.environ["BIMRENDER_LLM_PROVIDER"] = "ollama"
        os.environ.pop("BIMRENDER_PROMPT", None)
        return None
    return ("Kein Sprachmodell erreichbar. META_API_KEY in .env.local eintragen und neu starten "
            "oder lokales Ollama (qwen3:8b) starten. Ohne Modell geht der Entwurf nur über die Beispielhäuser oder als Spezifikation (JSON).")


def _model_for(with_images: bool) -> None:
    if os.environ.get("BIMRENDER_LLM_PROVIDER") == "meta":
        return                                                   # one multimodal model
    os.environ["BIMRENDER_LLM_MODEL"] = (os.environ.get("ARCHAITECT_OLLAMA_VISION", "qwen2.5vl:7b") if with_images
                                         else os.environ.get("ARCHAITECT_OLLAMA_MODEL", "qwen3:8b"))


# ------------------------------------------------------------------------------------------------ terrain (derived)
def _atomic_write(path: Path, text: str) -> None:
    """Concurrent requests (the page asks for the mesh twice) must never leave a half-written cache file behind."""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_json_cache(path: Path):
    """Cached JSON or None when missing / damaged (a damaged cache is deleted and rebuilt)."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        path.unlink(missing_ok=True)
        return None


def terrain_for(pid: str, proj: Project, spec: dict | None = None) -> dict:
    spec = spec or proj.spec()
    R = _R()
    pack = R.store().pack(pid)
    import hashlib
    src = hashlib.sha1(json.dumps([pack.get("terrain"), (pack.get("site") or {}).get("ring_local")], sort_keys=True, default=str).encode()).hexdigest()[:8]
    f = proj.dir / "terrain" / f"v{proj.version:03d}_{src}_t5.json"      # a refreshed site pack (new DGM/parcel) invalidates the cache
    cached = _read_json_cache(f)
    if cached is not None:
        return cached
    t = bterrain.build_terrain(pack, spec)
    t["src_hash"] = src
    _atomic_write(f, json.dumps(t))
    return t


def _terrain_summary(t: dict) -> dict:
    return {k: v for k, v in t.items() if k not in ("z", "pad_ring", "parcel_ring")}


def _engine() -> dict:
    try:
        import ifcopenshell  # noqa: F401
        ifc = True
    except ImportError:
        ifc = False
    blender = Path(bim.BLENDER)
    return {"ifcopenshell": ifc, "blender": blender.exists(), "blender_path": str(blender),
            "llm": _provider() != "none", "llm_provider": _provider(), "qualities": QUALITIES}


def _site_facts(ctx) -> dict:
    """Plot facts for the side panel: only what the site data really say (unknown stays absent)."""
    from . import reference
    near = [e for e in ctx.neighbours if e.poly.distance(ctx.site) < reference.RADIUS_M]
    out: dict = {"area_m2": round(ctx.area_m2, 1), "parcels": len(ctx.parcel_ids or []),
                 "existing": [{"floors": e.floors, "height_m": e.height_m, "footprint_m2": round(e.poly.area, 1)} for e in ctx.existing],
                 "neighbours_60m": len(near), "reference": getattr(ctx, "reference", None)}
    try:
        out["effective"] = reference.effective(ctx)
    except Exception:  # noqa: BLE001 - optional context
        out["effective"] = {}
    return out


def _request_facts(pid: str, meta: dict) -> dict:
    """What an enquiry to an authority needs to name the plot exactly (only recorded values; nothing guessed)."""
    out: dict = {"label": meta.get("parcel_label"), "gemeinde": meta.get("gemeinde"), "address": meta.get("address") or {}, "area_m2": meta.get("area_m2")}
    try:
        a = _R().store().assessment(pid)
        pr = a.parcel
        if pr is not None:
            out.update({"zaehler": pr.zaehler, "nenner": pr.nenner, "flur": pr.flur, "gemarkung_nr": pr.gemarkung_nr, "national_reference": pr.national_reference})
        out["protections"] = sorted({x.kind for x in (a.protections or [])})
    except Exception:  # noqa: BLE001 - optional
        out.setdefault("protections", [])
    return out


def _own_limits(pid: str):
    lim = _R().store().limits(pid)
    return lim.model_dump() if lim else None


def _state(pid: str, proj: Project) -> dict:
    spec = proj.spec()
    ctx, pack, meta = _site(pid)
    t = terrain_for(pid, proj, spec)
    rules = check_spec(spec, ctx, _footprint(pid, proj))
    from .planning_api import context_evidence
    research = context_evidence(pid)
    rule_message = (f"{len(research.get('plans') or [])} Planfassungen und {len(research.get('evidence') or [])} Fundstellen recherchiert. "
                    "Teilgebiet, Änderungen, Höhenbezug und nicht übernommene Festsetzungen sind noch zu prüfen.") if research.get('state')=='done' else "Kommunale Planrecherche noch nicht abgeschlossen oder für diese Flurstücksauswahl veraltet."
    rules['results'].append({'id':'MUNICIPAL_PLAN_REVIEW','label_de':'Kommunale Planunterlagen','status':'UNKNOWN','hard':False,
      'basis':'MUNICIPAL_CATALOG_UNVERIFIED','source_de':'Amtlicher Hessen-Katalog / Originaldokumente','message_de':rule_message})
    if rules.get('overall')=='PASS':rules['overall']='UNKNOWN'

    from ..bim import rooms as rooms_mod
    return {"project": pid, "exists": True, "version": proj.version, "history": proj.history(), "name": spec.get("name"), "spec": spec,
            "placement": (spec.get("site") or {}).get("placement") or {"x": 0.0, "y": 0.0, "rotation_deg": 0.0},
            "warnings": bim_checks.warnings(spec), "rooms": rooms_mod.analyze(spec), "cameras": bim.camera_names(spec),
            "check": rules, "terrain": _terrain_summary(t), "engine": _engine(), "site": {**_site_facts(ctx), "limits": _own_limits(pid), "request": _request_facts(pid, meta)},
            "references": _R().store().references(pid)}


def _sync_massing(pid: str, spec: dict) -> None:
    """Keep the rule engine's design history in step with the house (progress card, revisions); a rule violation never blocks saving the house."""
    from .bim_bridge import spec_to_massing
    m, _ = spec_to_massing(spec)
    if m is None:
        return
    try:
        _R().store().save_design(pid, m, None)
    except (ValueError, OSError):
        pass


def _place_full(spec: dict, ctx, keep_rotation: bool = False, best_effort: bool = False, _full_fp=None):
    """place_spec on the volumes, then nudge so that carport/terrace/overhangs stay inside the plot too (needs a throw-away IFC build)."""
    from .bim_bridge import footprint_from_parts, built_parts, refine_for_extras, extras_result, spec_to_massing
    pl, notes = place_spec(spec, ctx, keep_rotation, best_effort, footprint=_full_fp)
    if pl is None:
        return pl, notes
    try:
        import tempfile
        from ..bim.ifcgen import build_ifc
        with tempfile.TemporaryDirectory() as d:
            sp, ifc = Path(d) / "s.json", Path(d) / "o.ifc"
            sp.write_text(json.dumps(spec), encoding="utf-8")
            build_ifc(str(sp), str(ifc))
            parts = meshexport.ifc_parts(ifc)
            fp = footprint_from_parts(built_parts(parts, spec))       # garden elements never block the placement of the house
        pl, note = refine_for_extras(spec, ctx, fp, pl)
        if note:
            notes.append(note)
        if fp is None or fp.is_empty:
            return None, ['Die vollständige Grundstücksprüfung der Bauteile war nicht möglich.']
        positioned = {**spec, 'site': {**(spec.get('site') or {}),
                      'placement': {'x': pl.x, 'y': pl.y, 'rotation_deg': pl.rotation_deg}}}
        extra = extras_result(positioned, ctx, fp)
        if extra and extra['status'] == 'WARN':
            if _full_fp is None and not fp.is_empty:     # search again with the real outline (terrace, columns, canopy ...) before giving up
                return _place_full(spec, ctx, keep_rotation, best_effort, _full_fp=fp)
            return None, [extra['message_de'] + ' Entwurf kleiner gestalten und erneut versuchen.']
        from shapely import affinity
        placed_fp = affinity.translate(affinity.rotate(fp, pl.rotation_deg, origin=(0, 0)), pl.x, pl.y)
        massing, _ = spec_to_massing(positioned)
        if massing and any(placed_fp.intersection(e.poly).area > 0.05 for e in ctx.kept(massing)):
            if _full_fp is None:
                return _place_full(spec, ctx, keep_rotation, best_effort, _full_fp=fp)
            return None, ['Außenbauteile überschneiden ein Bestandsgebäude. Entwurf kleiner gestalten oder an anderer Stelle planen.']
    except Exception:  # noqa: BLE001
        return None, ['Die vollständige Grundstücksprüfung der Bauteile war nicht möglich. Bitte erneut versuchen.']
    return pl, notes


def _prepare(pid: str, spec: dict) -> tuple[dict, list[str]]:
    """Cameras, a placement inside the buildable region, validation. Raises HTTPException(422) with all problems."""
    from ..bim.interpret import validate_spec
    from ..bim.logic import normalize
    notes: list[str] = []
    try:
        bim.ensure_cameras(spec)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as e:
        raise HTTPException(422, {'message':'Der Entwurf enthält unvollständige Gebäudeangaben.', 'problems':[str(e)]}) from e
    site = spec.setdefault("site", {})
    if not isinstance(site, dict):
        raise HTTPException(422, {'message':'Ungültige Grundstücksdaten im Entwurf.', 'problems':[]})
    site.pop("terrain", None)                              # derived, never stored
    problems = validate_spec(spec)
    if problems:
        raise HTTPException(422, {"message": "Der Entwurf ist nicht baubar.", "problems": problems})
    spec = normalize(spec)
    site = spec.setdefault("site", {})
    if "placement" not in site:
        ctx, _, _ = _site(pid)
        pl, n = _place_full(spec, ctx)
        notes += n
        if pl is None:
            raise HTTPException(422, {"message": n[0] if n else "Das Haus passt nicht auf die verfügbare Fläche.", "problems": n})
        site["placement"] = {"x": pl.x, "y": pl.y, "rotation_deg": pl.rotation_deg}
    return spec, notes


def _check_new_house(pid: str, spec: dict):
    """Refuse a new proposal when it violates recorded hard inputs; unknown law stays open."""
    from .massing import MAX_VOLUMES
    if sum(not v.get('hidden') for v in spec.get('volumes', [])) > MAX_VOLUMES:
        raise HTTPException(422, {'message':'Zu viele Baukörper für die vollständige Grundstücksprüfung.', 'problems':[]})
    ctx, _, _ = _site(pid)
    result = check_spec(spec, ctx)
    if result.get('status') == 'NO_BUILDING':
        raise HTTPException(422, {'message':'Kein Baukörper für die Grundstücksprüfung vorhanden.', 'problems':[]})
    failures = [r.get('message_de', r.get('label_de', 'Prüfung fehlgeschlagen'))
                for r in result.get('results', []) if r.get('hard') and r.get('status') == 'FAIL']
    if failures:
        raise HTTPException(422, {'message':'Der Entwurf passt nicht zu den Grundstücks- oder eingetragenen Bauvorgaben.', 'problems':failures})


# ------------------------------------------------------------------------------------------------ read
@bim_router.get("/projects/{pid}/bim")
def get_bim(pid: str):
    R = _R()
    R._need(pid)
    proj = _project(pid, must_exist=False)
    if not proj.exists():
        return {"project": pid, "version": 0, "exists": False, "engine": _engine(), "references": R.store().references(pid)}
    return {"exists": True, **_state(pid, proj)}


@bim_router.get("/projects/{pid}/bim/spec/{version}")
def get_version(pid: str, version: int):
    proj = _project(pid)
    f = proj.versions_dir / f"v{version:03d}.json"
    if not f.exists():
        raise HTTPException(404, "Version nicht gefunden.")
    return json.loads(f.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ write
class SpecBody(BaseModel):
    spec: dict
    note: str = Field(default="", max_length=200)


@bim_router.put("/projects/{pid}/bim/spec")
def put_spec(pid: str, body: SpecBody):
    """Save a complete spec as a new version (e.g. from the editor or a file). Validated like an interpreter answer."""
    proj = _project(pid, must_exist=False)
    spec, notes = _prepare(pid, body.spec)
    proj.save(spec, body.note or "Spezifikation gespeichert")
    _sync_massing(pid, spec)
    return {**_state(pid, proj), "notes_de": notes}


class CreateBody(BaseModel):
    text: str = Field(default="", max_length=6000)
    answers: str | None = Field(default=None, max_length=3000)
    reference_ids: list[str] = Field(default=[], max_length=4)


def _validate_quiet(spec: dict) -> list[str]:
    from ..bim.interpret import validate_spec
    try:
        return validate_spec(copy.deepcopy(spec))
    except Exception as e:  # noqa: BLE001
        return [f"{type(e).__name__}: {e}"]


def _shrink(pid: str, raw: dict, ctx):
    """The design does not fit the free plot area: scale the plan down (heights stay) to the largest size that passes placement and all hard checks."""
    from . import autofit
    from .bim_bridge import place_spec
    last: dict = {}

    def quick(cand: dict) -> bool:
        try:
            return place_spec(copy.deepcopy(cand), ctx)[0] is not None
        except Exception:  # noqa: BLE001
            return False

    def accepts(cand: dict) -> bool:
        try:
            spec, notes = _prepare(pid, copy.deepcopy(cand))
            _check_new_house(pid, spec)
        except HTTPException:
            return False
        last["spec"], last["notes"] = spec, notes
        return True

    found = autofit.shrink_to_fit(raw, accepts, quick)
    if not found:
        return None
    _, scale = found
    before = _footprint_m2(raw)
    after = _footprint_m2(last["spec"])
    return last["spec"], [f"Der Entwurf passte nicht auf die freie Fläche und wurde automatisch auf {round(scale * 100)} % der Abmessungen verkleinert "
                          f"(Grundfläche {before:.0f} → {after:.0f} m², Höhen unverändert). Wunschmaße nennen, wenn etwas anderes gewollt ist.", *last["notes"]]


def _footprint_m2(spec: dict) -> float:
    from .bim_bridge import _ground_footprint
    fp = _ground_footprint(spec)
    return float(fp.area) if fp is not None else 0.0


@bim_router.post("/projects/{pid}/bim/create")
def create(pid: str, body: CreateBody):
    """Text (and/or photos from the project's references) -> building spec -> first or next version, placed inside the buildable region."""
    R = _R()
    R._need(pid)
    if not body.text.strip() and not body.reference_ids:
        raise HTTPException(422, "Bitte beschreibe das Haus oder wähle ein Foto.")
    from .generation_fit import brief as fit_brief, conflicts, correction_request
    from .bim_bridge import wants_demolition
    ctx, _, _ = _site(pid)
    geometry_data = fit_brief(ctx)
    preflight = conflicts(body.text + " " + (body.answers or ""), geometry_data)
    if preflight:
        return {"status": "questions", "questions": preflight}
    if geometry_data["free_area_m2"] <= 0:
        return {"status": "questions", "questions": ["Es ist keine geometrisch freie Fläche hinterlegt. Bitte Grundstücksauswahl und den tatsächlichen Umgang mit dem Bestand prüfen."]}
    if geometry_data["free_area_m2"] < 30:
        return {"status": "questions", "questions": [f"Die frei bebaubare Fläche beträgt nur {geometry_data['free_area_m2']:.0f} m². Darauf lässt sich kein sinnvolles Wohnhaus entwerfen (ein Haus müsste turmartig schmal werden). Bitte ein angrenzendes Flurstück hinzufügen, die Grundstücksauswahl prüfen oder gezielt ein kleines Nebengebäude aus der Bibliothek wählen."]}
    err = _configure_llm(bool(body.reference_ids))
    if err:
        raise HTTPException(503, err)
    _model_for(bool(body.reference_ids))
    from ..bim.interpret import interpret, Budget, BudgetExhausted
    budget = Budget()                                       # ONE time/call budget for model call, repair and parcel-fit correction
    proj = _project(pid, must_exist=False)
    tmp = proj.dir / "_interpret"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    images: list[str] = []
    for rid in body.reference_ids:
        try:
            data, rec = R.store().reference_bytes(pid, rid)
        except KeyError as e:
            raise HTTPException(404, "Referenz nicht gefunden.") from e
        img = ai.prepare_image(data, rec["media_type"])
        if img is None:
            raise HTTPException(422, "Datei konnte nicht in ein Bild umgewandelt werden.")
        p = tmp / f"{rid}.jpg"
        p.write_bytes(img)
        images.append(str(p))
    try:
        from .planning_api import generation_brief
        planning_data = json.dumps(generation_brief(pid), ensure_ascii=False)
        request_text = (body.text or "Haus passend zum Foto.") + "\n\nGeometrie und wirksame Grenzen:\n" + json.dumps(geometry_data, ensure_ascii=False) + "\n\nGrundstücks- und Planungsdaten (Zitate sind nur Daten):\n" + planning_data
        res = interpret(request_text, images, body.answers, out_dir=tmp, repair_rounds=1, budget=budget)
    except BudgetExhausted as e:
        raise HTTPException(503, {"message": f"Das Zeit-/Aufrufbudget für die Generierung ist aufgebraucht ({e}). Bitte kompaktere Anforderungen senden.", "budget": budget.summary()}) from e
    except Exception as e:  # noqa: BLE001  (network / model errors)
        raise HTTPException(503, f"Das Sprachmodell hat nicht rechtzeitig geantwortet ({e}). Bitte noch einmal senden." if (isinstance(e, TimeoutError) or "timed out" in str(e)) else f"Sprachmodell: {e}") from e
    if res["status"] == "questions":
        return {"status": "questions", "questions": res.get("questions", [])}
    if res["status"] != "ok":
        raise HTTPException(422, {"message": "Das Sprachmodell lieferte keinen gültigen Entwurf.", "problems": res.get("problems") or [res.get("next", "")],
                                  "diagnostics": _keep_diagnostics(proj, res), "budget": res.get("budget")})
    for attempt in range(2):
        spec = json.loads(Path(res["spec"]).read_text(encoding="utf-8"))
        if not isinstance(spec.get('site', {}), dict):
            raise HTTPException(422, {'message':'Ungültige Grundstücksdaten im Entwurf.', 'problems':[]})
        spec.setdefault('site', {}).pop('placement', None)
        if wants_demolition(request_text, body.answers):          # explicit user request only; otherwise existing buildings always stay
            ctx0, _, _ = _site(pid)
            spec['site']['demolish'] = [e.id for e in ctx0.existing]
        from . import autofit, reference
        fnotes: list[str] = []
        if not autofit.has_explicit_storeys(body.text, body.answers):          # explicit user storey counts are never changed
            frame = reference.effective(ctx)
            spec, fnotes = autofit.reduce_to_frame(spec, (frame.get("max_storeys") or {}).get("value"), (frame.get("max_height_m") or {}).get("value"),
                                                   lambda c: _validate_quiet(c))
        raw_spec = copy.deepcopy(spec)
        try:
            spec, notes = _prepare(pid, spec)
            _check_new_house(pid, spec)
            notes = [*fnotes, *notes]
            break
        except HTTPException as failure:
            if failure.status_code != 422:
                raise
            if not autofit.has_explicit_dimensions(body.text, body.answers):   # explicit user dimensions are never changed
                shrunk = _shrink(pid, raw_spec, ctx)
                if shrunk:
                    spec, notes = shrunk
                    notes = [*fnotes, *notes]
                    break
            if attempt:
                return {"status": "questions", "questions": ["Unter den aktuellen Vorgaben konnte kein passender Entwurf gefunden werden. " + (failure.detail.get("message") if isinstance(failure.detail, dict) else str(failure.detail)) + (" Sollen die Bestandsgebäude auf dem Grundstück als Abriss angenommen werden? Antworte dann z. B. „Abriss der Bestandsgebäude ja“." if _site(pid)[0].existing else "")]}
            try:
                res = interpret(correction_request(request_text, failure.detail), images, body.answers, out_dir=tmp, repair_rounds=1, budget=budget)
            except BudgetExhausted as error:
                raise HTTPException(503, {"message": "Der Entwurf passte nicht auf die freie Fläche und die Anpassung ließ sich im Zeit-/Aufrufbudget nicht abschließen "
                                                     f"({error}). Bitte kompaktere Anforderungen angeben.", "problems": [str(failure.detail)], "budget": budget.summary()}) from error
            except Exception as error:
                log.warning("fit correction failed", exc_info=True)
                raise HTTPException(503, {"message": f"Die Anpassung des Entwurfs konnte nicht abgeschlossen werden ({type(error).__name__}: {error}). Bitte erneut versuchen.", "problems": [str(failure.detail)]}) from error
            if res.get("status") == "questions":
                return {"status": "questions", "questions": res.get("questions", [])}
            if res.get("status") != "ok":
                return {"status": "questions", "questions": ["Der Entwurf ließ sich nicht passend anlegen. Bitte kompaktere Anforderungen angeben oder die hinterlegten Grundstücksvorgaben prüfen."]}
    proj.save(spec, (body.text or "aus Foto")[:80])
    _sync_massing(pid, spec)
    R.store().touch(pid)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


LIBRARY_HOUSES = ("stadthaus", "villa_kubus", "fachwerkhaus", "fachwerk_gasthaus_lib", "alpin_lib", "bungalow_lib", "stadtvilla_lib", "mfh_lib", "kubus_lib", "landhaus_lib", "scheune_lib", "loft_lib", "holzhaus_lib", "passivhaus_lib", "hochhaus_lib", "einfamilienhaus_lib", "gruenderzeit_lib", "tiny_lib", "kita_lib", "cafe_lib", "klassik_lib", "pultdach_lib", "reetdach_lib", "mediterran_lib", "kapelle_lib", "speicher_lib", "orangerie_lib", "schloss_lib", "rathaus_lib", "hangvilla_lib", "jugendstil_lib", "gutshof_lib", "palais_lib", "lodge_lib", "muehle_lib", "palladio_lib")      # complete example houses; the other spec files are component catalogues


def _keep_diagnostics(proj, res: dict) -> str | None:
    """Copy the model answers of a failed generation out of the temporary folder (it is wiped on the next attempt). Returns the folder name."""
    src = Path(res.get("diagnostics") or "")
    if not src.is_dir():
        return None
    dst = proj.dir / "diagnostics" / time.strftime("%Y%m%d-%H%M%S")
    try:
        shutil.copytree(src, dst)
    except OSError:
        return None
    return str(dst.relative_to(proj.dir))


def _library_spec(name: str) -> dict:
    if name not in LIBRARY_HOUSES:
        raise HTTPException(404, "Beispielhaus nicht gefunden.")
    f = Path(bim.__file__).resolve().parent / "specs" / f"{name}.json"
    from ..bim.thumbs import house_only
    return house_only(json.loads(f.read_text(encoding="utf-8")))


@bim_router.get("/projects/{pid}/bim/library")
def library(pid: str):
    """Ready-made example houses: usable without a language model; they are placed and graded like any other house."""
    _R()._need(pid)
    out = []
    for n in LIBRARY_HOUSES:
        s = _library_spec(n)
        out.append({"id": n, "name": s.get("name") or n, "description": (s.get("description") or "")[:240]})
    from ..bim.objects import LIBRARY_OBJECTS
    return {"houses": out, "objects": [{"id": k, "category": v[0], "label": v[3]} for k, v in LIBRARY_OBJECTS.items()]}


@bim_router.get("/projects/{pid}/bim/thumb/{name}")
def thumb_mesh(pid: str, name: str):
    """Preview mesh (same model as in the design) of an example house or garden object for the library thumbnails."""
    from ..bim import thumbs
    _R()._need(pid)
    try:
        f = thumbs.mesh_file(name, LIBRARY_HOUSES)
    except ValueError:
        raise HTTPException(404, "Unbekanntes Bibliothekselement.") from None
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Vorschau konnte nicht gebaut werden: {e}") from e
    return FileResponse(f, media_type="application/json", headers={"Cache-Control": "public, max-age=86400"})


@bim_router.post("/projects/{pid}/bim/library/{name}")
def from_library(pid: str, name: str):
    _R()._need(pid)
    proj = _project(pid, must_exist=False)
    original = _library_spec(name)
    try:
        spec, notes = _prepare(pid, original)
        _check_new_house(pid, spec)
    except HTTPException as failure:
        if failure.status_code != 422:
            raise
        from .generation_fit import brief as fit_brief
        ctx, _, _ = _site(pid)
        err = _configure_llm(False)
        if err:
            raise HTTPException(422, {"message": "Diese Vorlage benötigt eine Anpassung an das Grundstück. Dafür ist aktuell kein Modell verfügbar.", "problems": [str(failure.detail)]}) from failure
        _model_for(False)
        from ..bim.interpret import interpret
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            request = ("Passe diese Hausvorlage an die verfügbare Grundstücksgeometrie und hinterlegten Grenzen an. "
                       "Die Vorlagenmaße sind keine festen Nutzermaße: kompakter neu dimensionieren; Fenster, Türen, Treppen und Anbauten müssen funktionsfähige Maße behalten. "
                       "Gebäudestil beibehalten; kein bloßes Skalieren aller Bauteile. Wenn unmöglich, konkrete Rückfrage stellen.\nVorlage:\n"
                       + json.dumps(original, ensure_ascii=False) + "\nGrundstück:\n" + json.dumps(fit_brief(ctx), ensure_ascii=False))
            try:
                from ..bim.interpret import Budget
                result = interpret(request, [], None, out_dir=directory, repair_rounds=1, budget=Budget())
            except Exception as error:
                raise HTTPException(503, "Die Grundstücksanpassung der Vorlage konnte nicht abgeschlossen werden.") from error
            if result.get("status") == "questions":
                return {"status": "questions", "questions": result.get("questions", [])}
            if result.get("status") != "ok":
                raise HTTPException(422, "Die Vorlage ließ sich nicht zuverlässig anpassen. Bitte eine kompaktere Vorlage wählen.")
            adapted = json.loads(Path(result["spec"]).read_text(encoding="utf-8"))
            if not isinstance(adapted.get('site', {}), dict):
                raise HTTPException(422, "Ungültige Grundstücksdaten im angepassten Entwurf.")
            adapted.setdefault('site', {}).pop('placement', None)
            spec, notes = _prepare(pid, adapted)
            _check_new_house(pid, spec)
            notes.insert(0, "Hausvorlage wurde für dieses Grundstück neu dimensioniert.")
    proj.save(spec, f"Beispielhaus {name}")
    _sync_massing(pid, spec)
    _R().store().touch(pid)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


class I18nBody(BaseModel):
    texts: list[str] = Field(max_length=40)


_I18N_LOCK = threading.Lock()


def _i18n_file() -> Path:
    base = Path(os.environ.get("ARCHAITECT_LOCAL", "")) if os.environ.get("ARCHAITECT_LOCAL") else Path(__file__).resolve().parents[3] / ".local"
    base.mkdir(parents=True, exist_ok=True)
    return base / "i18n_en_cache.json"


@bim_router.post("/i18n/en")
def i18n_en(body: I18nBody):
    """German UI/API sentences -> English (UI language switch). Cached on disk; the model only sees the strings, no project data beyond them.
    Names, numbers, units and legal terms (§, HBO, BauGB ...) are kept; nothing is added."""
    texts = [t.strip()[:2000] for t in body.texts if t and t.strip()]
    f = _i18n_file()
    with _I18N_LOCK:
        try:
            cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        except (OSError, ValueError):
            cache = {}
    out = {t: cache[t] for t in texts if t in cache}
    miss = [t for t in texts if t not in cache]
    if miss and _configure_llm(False) is None:
        from ..bim import interpret as _ip
        msgs = [{"role": "system", "content": "You translate German UI text of a house-planning app into natural English. Keep numbers, units, names, street names, parcel numbers, abbreviations (HBO, BauGB, GRZ, GFZ, ALKIS, LoD2) and section signs unchanged. Tokens like {0}, {1} are number placeholders: keep every one of them exactly once, unchanged. Do not add or omit information; keep hedges like 'not verified'. Answer ONLY with JSON {\"t\": [..]} holding exactly one English string per input, in the same order."},
                {"role": "user", "content": json.dumps(miss, ensure_ascii=False)}]
        try:
            raw = _ip._openai_compatible(msgs, phase="i18n") if os.environ.get("BIMRENDER_LLM_PROVIDER") != "ollama" else _ip._ollama(msgs)
            arr = json.loads(raw).get("t", [])
            if isinstance(arr, list) and len(arr) == len(miss):
                for k, v in zip(miss, arr):
                    if isinstance(v, str) and v.strip() and sorted(re.findall(r"\{\d+\}", k)) == sorted(re.findall(r"\{\d+\}", v)):
                        out[k] = v.strip(); cache[k] = v.strip()
                with _I18N_LOCK:
                    f.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        except Exception:  # noqa: BLE001 - translation is best effort; the UI stays German for these strings
            log.warning("i18n translation failed", exc_info=True)
    return {"map": out}


class I18nTreeBody(BaseModel):
    data: dict | list


@bim_router.post("/i18n/tree")
def i18n_tree(body: I18nTreeBody):
    """Translate the free-text values of an export JSON (keys/ids/codes untouched)."""
    from .i18n_tree import translate_tree
    return {"data": translate_tree(body.data)}


class ReviseBody(BaseModel):
    text: str = Field(min_length=3, max_length=3000)


def _sauna_hint(tj: dict, d: dict) -> str:
    """Where a hut next to the lake can stand: on the bank closest to the house, 4.5 m back from the waterline, door towards the water."""
    import math
    lk = (tj.get("lakes") or [None])[0]
    if not lk:
        return ""
    ring = lk["ring"]
    cx = sum(p[0] for p in ring) / len(ring)
    cy = sum(p[1] for p in ring) / len(ring)
    px, py = min(ring, key=lambda p: (p[0] - d["near_x"]) ** 2 + (p[1] - d["near_y"]) ** 2)
    dx, dy = px - cx, py - cy
    ln = math.hypot(dx, dy) or 1.0
    hx, hy = px + dx / ln * 5.0, py + dy / ln * 5.0
    face = ("W" if dx > 0 else "E") if abs(dx) > abs(dy) else ("S" if dy > 0 else "N")
    w, dd = 3.8, 3.0
    fw, fd = (w, dd + 1.5) if face in "SN" else (dd + 1.5, w)
    return (f"SAUNAHÜTTE am See: Komponente sauna_hut mit x={round(hx - fw / 2, 1)}, y={round(hy - fd / 2, 1)}, width={w}, depth={dd}, facing={face} "
            f"(Tür zum Wasser; steht auf Punktfundamenten, funktioniert am Hang). ")


def _terrain_hint(pid: str, proj: Project, text: str) -> str:
    """Facts about the ground the language model cannot see: a real hollow of the parcel is where a pond belongs."""
    import re
    if not re.search(r"teich|see\b|senke|mulde|pool|wasser|garten|einkerbung|sauna|hütte", text, re.I):
        return ""
    try:
        tj = terrain_for(pid, proj)
        d = (tj.get("depression") or None)
    except Exception:  # noqa: BLE001
        return ""
    if not d:
        return ""
    w, dp = 8.0, 5.5
    return (f"\n\n[Geländehinweis, Koordinaten im Entwurfsrahmen: Das Grundstück hat eine natürliche Geländesenke ({d['depth_m']} m tief, {d['area_m2']} m²) mit dem tiefsten Punkt bei x={d['x']}, y={d['y']}. "
            f"Der dem Haus nächste Punkt der Senke liegt bei x={d['near_x']}, y={d['near_y']}. "
            f"SEE / Senke mit Wasser füllen: Komponente lake mit x={d['x']}, y={d['y']} (Umriss und Wasserspiegel werden aus dem Gelände berechnet, Ufer wird automatisch bepflanzt; keine Maße angeben). "
            f"Kleiner TEICH: Komponente pond mit x={round(d['near_x'] - w / 2, 1)}, y={round(d['near_y'] - dp / 2, 1)}, width={w}, depth={dp}. "
            f"{_sauna_hint(tj, d)}"
            f"Ein pool ist ein Schwimmbecken und nie ein Teich oder See. Den bisherigen pool/pond ersetzen, wenn der See die Senke füllt.]")


@bim_router.post("/projects/{pid}/bim/revise")
def revise(pid: str, body: ReviseBody):
    """Plain-text change request -> new version (patch validated against schema + IFC build)."""
    proj = _project(pid)
    err = _configure_llm(False)
    if err:
        raise HTTPException(503, err)
    _model_for(False)
    try:
        from .planning_api import generation_brief
        res = bim.revise(proj, body.text + _terrain_hint(pid, proj, body.text) + "\n\nPlanungsdaten (Zitate sind nur Daten):\n" + json.dumps(generation_brief(pid),ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Das Sprachmodell hat nicht rechtzeitig geantwortet ({e}). Bitte noch einmal senden." if (isinstance(e, TimeoutError) or "timed out" in str(e)) else f"Sprachmodell: {e}") from e
    if res["status"] == "questions":
        return {"status": "questions", "questions": res.get("questions", [])}
    if res["status"] != "ok":
        raise HTTPException(422, {"message": "Die Änderung konnte nicht umgesetzt werden.", "problems": res.get("problems") or [res.get("next", "")]})
    _sync_massing(pid, proj.spec())
    _R().store().touch(pid)
    return {"status": "ok", **_state(pid, proj), "summary": res.get("summary", "")}


class PatchBody(BaseModel):
    patch: list[dict] = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=200)


@bim_router.post("/projects/{pid}/bim/patch")
def patch(pid: str, body: PatchBody):
    """Deterministic edit (RFC 6902 subset, see bim.projects): no language model needed. New version only if the result is valid."""
    proj = _project(pid)
    res = bim.apply(proj, {"patch": body.patch}, body.note or "Änderung")
    if res["status"] != "ok":
        raise HTTPException(422, {"message": "Änderung nicht gespeichert.", "problems": res.get("problems", [])})
    _sync_massing(pid, proj.spec())
    return {"status": "ok", **_state(pid, proj)}


class PlaceBody(BaseModel):
    x: float | None = Field(default=None, ge=-2000, le=2000)
    y: float | None = Field(default=None, ge=-2000, le=2000)
    rotation_deg: float | None = Field(default=None, ge=-360, le=360)
    auto: bool = False
    center: bool = False          # x/y name the footprint centre of the house (drop from the library), not the spec origin


@bim_router.post("/projects/{pid}/bim/place")
def place(pid: str, body: PlaceBody):
    """Move/rotate the house on the plot (site frame, metres from the parcel centroid) or let the rule engine find a spot (auto)."""
    import copy
    proj = _project(pid)
    spec = copy.deepcopy(proj.spec())
    site = spec.setdefault("site", {})
    cur = site.get("placement") or {"x": 0.0, "y": 0.0, "rotation_deg": 0.0}
    notes: list[str] = []
    if body.auto:
        ctx, _, _ = _site(pid)
        pl, notes = _place_full(spec, ctx)
        if pl is None:
            raise HTTPException(422, {"message": notes[0] if notes else "Keine Position gefunden.", "problems": notes})
        site["placement"] = {"x": pl.x, "y": pl.y, "rotation_deg": pl.rotation_deg}
        _check_new_house(pid, spec)
    else:
        rot = body.rotation_deg if body.rotation_deg is not None else cur["rotation_deg"]
        px, py = (body.x if body.x is not None else cur["x"]), (body.y if body.y is not None else cur["y"])
        vols = spec.get("volumes") or []
        if body.center and vols and body.x is not None and body.y is not None:
            import math
            cx = sum(v["origin"][0] + v["size"][0] / 2 for v in vols) / len(vols)
            cy = sum(v["origin"][1] + v["size"][1] / 2 for v in vols) / len(vols)
            a = math.radians(float(rot))
            px, py = round(body.x - (math.cos(a) * cx - math.sin(a) * cy), 3), round(body.y - (math.sin(a) * cx + math.cos(a) * cy), 3)
        site["placement"] = {"x": px, "y": py, "rotation_deg": rot}
    proj.save(spec, "Position auf dem Grundstück")
    _sync_massing(pid, spec)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


class MoveBody(BaseModel):
    dx: float = Field(ge=-500, le=500)       # site frame (east), metres
    dy: float = Field(ge=-500, le=500)       # site frame (north), metres


def _to_spec_frame(spec: dict, dx: float, dy: float) -> tuple[float, float]:
    """Site-frame displacement -> spec (house) frame: undo the placement rotation."""
    import math
    a = math.radians(float((((spec.get("site") or {}).get("placement")) or {}).get("rotation_deg", 0.0)))
    c, s = math.cos(a), math.sin(a)
    return dx * c + dy * s, -dx * s + dy * c


@bim_router.get("/projects/{pid}/bim/objects")
def list_objects(pid: str):
    """Selectable objects (buildings, pool, trees, paving …) with ids as used by the 360° view."""
    from ..bim import objects as O
    return {"objects": O.public(_project(pid).spec())}


class AddObjectBody(BaseModel):
    kind: str
    x: float = Field(ge=-500, le=500, allow_inf_nan=False)
    y: float = Field(ge=-500, le=500, allow_inf_nan=False)


@bim_router.post("/projects/{pid}/bim/objects")
def add_object(pid: str, body: AddObjectBody):
    """Add a library object at a site-frame position; preserve all earlier versions."""
    from ..bim.objects import LIBRARY_OBJECTS
    if body.kind not in LIBRARY_OBJECTS:
        raise HTTPException(422, "Unbekanntes Bibliotheksobjekt.")
    import copy
    from shapely import affinity
    from shapely.geometry import Point
    from ..bim import objects as O
    proj = _project(pid)
    spec = copy.deepcopy(proj.spec())
    pl = (spec.get("site") or {}).get("placement") or {"x": 0, "y": 0, "rotation_deg": 0}
    x, y = _to_spec_frame(spec, body.x - pl.get("x", 0), body.y - pl.get("y", 0))
    from ..bim.catalog import C
    base = LIBRARY_OBJECTS[body.kind][1]
    component = {key: param[1] for key, param in C[base]["params"].items() if param[1] is not None}
    component.update(LIBRARY_OBJECTS[body.kind][2])
    component.update({"type": base, "x": round(x, 3), "y": round(y, 3)})
    spec.setdefault("components", []).append(component)
    oid = f"comp.{len(spec['components']) - 1}"
    me = next(o for o in O.objects(spec) if o["id"] == oid)
    if base in ("tree", "shrub", "garden_light"):
        me["poly"] = Point(x, y).buffer({"tree": float(component.get("crown_radius", 3.0)), "shrub": float(component.get("radius", 0.7)), "garden_light": 0.3}[base])
    elif base == "garden_set":
        me["poly"] = Point(x, y).buffer(2.0)
    elif base == "bench":
        from shapely.geometry import box
        me["poly"] = box(x, y - 0.1, x + float(component.get("length", 1.6)), y + 0.6)
    for other in O.objects(spec):
        if other["id"] != oid and me["poly"].intersection(other["poly"]).area > O.MIN_OVERLAP_M2 and not O._benign(me, other):
            raise HTTPException(409, f"Der Platz überschneidet sich mit „{other['label']}“.")
    ctx, _, _ = _site(pid)
    footprint = affinity.translate(affinity.rotate(me["poly"], pl.get("rotation_deg", 0), origin=(0, 0)), pl.get("x", 0), pl.get("y", 0))
    if not ctx.site.covers(footprint):
        raise HTTPException(422, "Bitte das Objekt vollständig innerhalb des Grundstücks platzieren.")
    new, notes = _prepare(pid, spec)
    proj.save(new, "Gartenobjekt hinzugefügt")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


@bim_router.post("/projects/{pid}/bim/objects/{oid}/move")
def move_object(pid: str, oid: str, body: MoveBody):
    """Move ONE object (not the others). Refuses overlaps with other objects; the grid is 0.5 m."""
    import copy
    from ..bim import objects as O
    proj = _project(pid)
    spec = copy.deepcopy(proj.spec())
    dx, dy = _to_spec_frame(spec, round(body.dx * 2) / 2, round(body.dy * 2) / 2)
    try:
        new = O.move(spec, oid, dx, dy)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    new, notes = _prepare(pid, new)
    proj.save(new, "Objekt verschoben")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


class RotBody(BaseModel):
    quarters: int = Field(ge=-3, le=3)


@bim_router.post("/projects/{pid}/bim/objects/{oid}/rotate")
def rotate_object(pid: str, oid: str, body: RotBody):
    """Turn ONE object by quarter turns (sauna hut: facing S/E/N/W around its centre)."""
    import copy
    from ..bim import objects as O
    proj = _project(pid)
    try:
        new = O.rotate(copy.deepcopy(proj.spec()), oid, body.quarters)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    new, notes = _prepare(pid, new)
    proj.save(new, "Objekt gedreht")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


@bim_router.delete("/projects/{pid}/bim/objects/{oid}")
def delete_object(pid: str, oid: str):
    import copy
    from ..bim import objects as O
    proj = _project(pid)
    try:
        new = O.delete(copy.deepcopy(proj.spec()), oid)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    new, notes = _prepare(pid, new)
    proj.save(new, "Objekt gelöscht")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


@bim_router.post("/projects/{pid}/bim/volumes/{vid}/delete")
def delete_volume(pid: str, vid: str):
    """Delete one part (volume) of a building."""
    import copy
    from ..bim import objects as O
    proj = _project(pid)
    try:
        new = O.delete_volume(copy.deepcopy(proj.spec()), vid)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    new, notes = _prepare(pid, new)
    proj.save(new, f"Bauteil {vid} gelöscht")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": notes}


@bim_router.post("/projects/{pid}/bim/volumes/{vid}/detach")
def detach_volume(pid: str, vid: str):
    """Make one part its own building so that it can be moved on its own."""
    import copy
    from ..bim import objects as O
    proj = _project(pid)
    try:
        new = O.detach_volume(copy.deepcopy(proj.spec()), vid)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    proj.save(new, f"Bauteil {vid} als eigenes Gebäude")
    _sync_massing(pid, new)
    return {"status": "ok", **_state(pid, proj), "notes_de": []}


@bim_router.get("/projects/{pid}/bim/versions")
def versions(pid: str):
    """All saved versions (newest first) so that an earlier design can be picked again."""
    proj = _project(pid)
    return {"current": proj.version, "versions": [{"version": h["version"], "note": h.get("note", ""), "time": h.get("time", "")} for h in reversed(proj.history())]}


@bim_router.post("/projects/{pid}/bim/restore/{version}")
def restore(pid: str, version: int):
    """Make an earlier version the active one again (saved as a new version, nothing is lost)."""
    proj = _project(pid)
    f = proj.versions_dir / f"v{version:03d}.json"
    if not f.exists():
        raise HTTPException(404, "Version nicht gefunden.")
    proj.save(json.loads(f.read_text(encoding="utf-8")), f"zurück auf Version {version}")
    _sync_massing(pid, proj.spec())
    _R().store().touch(pid)
    return {"status": "ok", **_state(pid, proj)}


@bim_router.post("/projects/{pid}/bim/undo")
def undo(pid: str):
    proj = _project(pid)
    try:
        proj.undo()
    except PatchError as e:
        raise HTTPException(409, str(e)) from e
    return {"status": "ok", **_state(pid, proj)}


# ------------------------------------------------------------------------------------------------ models: IFC, 360° mesh, plans
def _ifc_for(pid: str, proj: Project) -> Path:
    from ..bim.ifcgen import build_ifc
    ter = terrain_for(pid, proj)
    f = proj.dir / f"v{proj.version:03d}_{ter.get('src_hash', 'flat')}_{_GEN}.ifc"      # trees/hedges stand on the graded ground
    if not f.exists():
        build_ifc(str(proj.current_path), str(f), terrain=ter if ter.get("status") == "OK" else None)
    return f


@bim_router.get("/projects/{pid}/bim/mesh")
def mesh(pid: str):
    """Building + graded terrain as compact mesh JSON for the browser 360° view."""
    proj = _project(pid)
    return FileResponse(_mesh_file(pid, proj), media_type="application/json", headers={"Cache-Control": "no-cache"})


_BUILD_LOCK = __import__("threading").RLock()      # one IFC/mesh build at a time: two requests must not write the same files


def _mesh_file(pid: str, proj: Project) -> Path:
    with _BUILD_LOCK:
        return _mesh_file_locked(pid, proj)


def _mesh_file_locked(pid: str, proj: Project) -> Path:
    t = terrain_for(pid, proj)
    f = proj.dir / f"mesh_v{proj.version:03d}_{t.get('src_hash', 'flat')}_{_GEN}.json"
    if _read_json_cache(f) is None:
        try:
            data = meshexport.build(_ifc_for(pid, proj), t, proj.spec())
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"3D-Modell konnte nicht aufgebaut werden: {e}") from e
        data["version"] = proj.version
        _atomic_write(f, json.dumps(data))
        for old in proj.dir.glob("mesh_v*.json"):
            if old != f:
                old.unlink(missing_ok=True)
    return f


def _footprint(pid: str, proj: Project):
    """Plan of the whole model (spec frame), cached per version; None if the model cannot be built (the rule check then just skips the extras row)."""
    from shapely import wkt
    f = proj.dir / f"fp_v{proj.version:03d}_{_GEN}.wkt"
    if f.exists():
        txt = f.read_text(encoding="utf-8")
        return wkt.loads(txt) if txt else None
    try:
        from .bim_bridge import footprint_from_parts
        fp = footprint_from_parts(json.loads(_mesh_file(pid, proj).read_text(encoding="utf-8"))["parts"])
    except Exception:  # noqa: BLE001
        return None
    f.write_text(fp.wkt if fp is not None else "", encoding="utf-8")
    for old in proj.dir.glob("fp_v*.wkt"):
        if old != f:
            old.unlink(missing_ok=True)
    return fp


@bim_router.get("/projects/{pid}/bim/ifc")
def ifc_download(pid: str):
    proj = _project(pid)
    return FileResponse(_ifc_for(pid, proj), media_type="application/x-step", filename=f"haus-v{proj.version:03d}.ifc")


@bim_router.get("/projects/{pid}/bim/plans")
def plans(pid: str):
    proj = _project(pid)
    res = bim.plans(proj)
    if res["status"] != "ok":
        raise HTTPException(422, res.get("message", "Grundriss fehlgeschlagen."))
    return res


@bim_router.get("/projects/{pid}/bim/plans/{version}/{name}")
def plan_file(pid: str, version: int, name: str, lang: str = "de"):
    proj = _project(pid)
    if not re.match(r"^plan_[A-Za-z0-9_\-]{1,40}\.svg$", name):
        raise HTTPException(404, "Plan nicht gefunden.")
    f = proj.dir / "plans" / f"v{version:03d}" / name
    if not f.exists():
        raise HTTPException(404, "Plan nicht gefunden.")
    if lang == "en":
        from fastapi.responses import Response
        svg = f.read_text(encoding="utf-8")
        svg = re.sub(r"Schnitt in ([\d.]+) m Höhe", r"Section at \1 m height", svg)
        lv = {"EG": "Ground floor", "OG": "First floor", "OG1": "First floor", "OG2": "Second floor", "OG3": "Third floor", "OG4": "Fourth floor", "DG": "Attic", "Dach": "Roof", "UG": "Basement", "KG": "Basement"}
        svg = re.sub(r">(EG|OG[0-9]?|DG|UG|KG|Dach)(\s+·)", lambda m: ">" + lv[m.group(1)] + m.group(2), svg)
        for de, en in (("Schlafzimmer", "Bedroom"), ("Wohnzimmer", "Living room"), ("Küche", "Kitchen"), ("Bad", "Bathroom"), ("Flur", "Hallway"), ("Treppe", "Stairs")):
            svg = re.sub(rf">{de}(\s*[0-9]*)<", rf">{en}\1<", svg)
        return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "no-cache"})
    return FileResponse(f, media_type="image/svg+xml")


# ------------------------------------------------------------------------------------------------ render jobs (local Blender/Cycles, one at a time)
def _jdir(proj: Project, jid: str) -> Path:
    if not _JID.match(jid):
        raise HTTPException(404, "Auftrag nicht gefunden.")
    return proj.dir / "renders" / jid


def _jwrite(d: Path, rec: dict) -> None:
    tmp = d / "job.json.tmp"
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "job.json")


def _jread(d: Path) -> dict:
    f = d / "job.json"
    if not f.exists():
        raise HTTPException(404, "Auftrag nicht gefunden.")
    rec = json.loads(f.read_text(encoding="utf-8"))
    if rec["status"] in ("queued", "running") and rec["id"] not in _PROCS and not _is_waiting(rec["id"]):
        rec = {**rec, "status": "failed", "error": "Der Dienst wurde während des Renderns neu gestartet."}
        _jwrite(d, rec)
    return rec


_WAITING: set[str] = set()


def _is_waiting(jid: str) -> bool:
    return jid in _WAITING


class RenderBody(BaseModel):
    quality: str = Field(default="preview", pattern="^(sketch|draft|preview|final)$")
    camera: str | None = None


def _run_job(proj: Project, d: Path, rec: dict, spec_file: Path, ifc: Path, out: Path) -> None:
    _WAITING.add(rec["id"])
    with _JOB_LOCK:
        _WAITING.discard(rec["id"])
        rec = _jread_raw(d)
        if rec["status"] == "cancelled":
            return
        rec.update(status="running", started=time.time())
        _jwrite(d, rec)
        t0 = time.time()
        cmd, env = bim.blender_env(ifc, spec_file, rec["camera"], rec["quality"], out)
        try:
            p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            _PROCS[rec["id"]] = p
            log, _ = p.communicate(timeout=int(os.environ.get("ARCHAITECT_RENDER_TIMEOUT", "3600")))
            rc = p.returncode
        except subprocess.TimeoutExpired:
            p.kill()
            log, rc = "Zeitüberschreitung", -9
        except OSError as e:
            log, rc = str(e), 127
        finally:
            _PROCS.pop(rec["id"], None)
        rec = _jread_raw(d)
        if rec["status"] == "cancelled":
            return
        ok = rc == 0 and out.exists()
        rec.update(status="done" if ok else "failed", seconds=round(time.time() - t0, 1),
                   error=None if ok else "Rendern fehlgeschlagen: " + "\n".join((log or "").splitlines()[-6:]))
        _jwrite(d, rec)


def _jread_raw(d: Path) -> dict:
    return json.loads((d / "job.json").read_text(encoding="utf-8"))


@bim_router.post("/projects/{pid}/bim/renders", status_code=202)
def create_render(pid: str, body: RenderBody):
    proj = _project(pid)
    if not Path(bim.BLENDER).exists():
        raise HTTPException(503, f"Blender nicht gefunden ({bim.BLENDER}). Pfad über die Umgebungsvariable BLENDER setzen.")
    if len(_WAITING) >= MAX_WAITING and _JOB_LOCK.locked():
        raise HTTPException(429, "Es läuft bereits ein Render und ein weiterer wartet.")
    spec = proj.spec()
    cams = bim.camera_names(spec)
    cam = body.camera if body.camera in cams else cams[0]
    jid = "j_" + uuid.uuid4().hex[:10]
    d = proj.dir / "renders" / jid
    d.mkdir(parents=True, exist_ok=True)
    t = terrain_for(pid, proj, spec)
    render_spec = {**spec, "site": {**(spec.get("site") or {}), "terrain": t}}
    spec_file = d / "spec.json"
    spec_file.write_text(json.dumps(render_spec, ensure_ascii=False), encoding="utf-8")
    ifc = _ifc_for(pid, proj)
    out = d / f"v{proj.version:03d}_{cam}_{body.quality}.png"
    rec = {"id": jid, "status": "queued", "version": proj.version, "camera": cam, "quality": body.quality, "created": time.time(),
           "image": out.name, "terrain": t.get("status") == "OK", "error": None}
    _jwrite(d, rec)
    threading.Thread(target=_run_job, args=(proj, d, rec, spec_file, ifc, out), daemon=True, name=f"bim-render-{jid}").start()
    return rec


@bim_router.get("/projects/{pid}/bim/renders")
def list_renders(pid: str):
    proj = _project(pid)
    root = proj.dir / "renders"
    out = []
    if root.exists():
        for d in sorted(root.glob("j_*"), key=lambda p: p.stat().st_mtime, reverse=True)[:40]:
            try:
                out.append(_jread(d))
            except (HTTPException, ValueError):
                continue
    return {"renders": out}


@bim_router.get("/projects/{pid}/bim/renders/{jid}")
def render_status(pid: str, jid: str):
    return _jread(_jdir(_project(pid), jid))


@bim_router.get("/projects/{pid}/bim/renders/{jid}/image")
def render_image(pid: str, jid: str):
    d = _jdir(_project(pid), jid)
    rec = _jread(d)
    f = d / rec["image"]
    if rec["status"] != "done" or not f.exists():
        raise HTTPException(404, "Noch kein Bild.")
    return FileResponse(f, media_type="image/png")


@bim_router.post("/projects/{pid}/bim/renders/{jid}/cancel")
def cancel_render(pid: str, jid: str):
    d = _jdir(_project(pid), jid)
    rec = _jread(d)
    if rec["status"] in ("queued", "running"):
        rec.update(status="cancelled", error=None)
        _jwrite(d, rec)
        p = _PROCS.get(jid)
        if p is not None:
            p.terminate()
    return rec


# ------------------------------------------------------------------------------------------------ Bilderwelt: 4 photo-real 4K images per project
_PHOTO_IDS = ("main", "close1", "close2", "aerial")
_PHOTO_BUSY: set[str] = set()


def _pdir(proj: Project) -> Path:
    d = proj.dir / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pread(proj: Project) -> dict:
    f = _pdir(proj) / "state.json"
    try:
        rec = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        rec = {}
    if rec.get("status") == "running" and proj.dir.name not in _PHOTO_BUSY:
        rec = {**rec, "status": "failed", "error": "Der Dienst wurde während der Erzeugung neu gestartet."}
        _pwrite(proj, rec)
    return rec


def _pwrite(proj: Project, rec: dict) -> None:
    f = _pdir(proj) / "state.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _photo_job(pid: str, proj: Project, ids: list[str]) -> None:
    from . import bim_photos as BP
    key = proj.dir.name
    try:
        spec = proj.spec()
        t = terrain_for(pid, proj, spec)
        cams = {c["name"]: c for c in BP.shots(spec, t)}
        render_spec = {**spec, "site": {**(spec.get("site") or {}), "terrain": t},
                       "render": {**(spec.get("render") or {}), "cameras": list(cams.values())}}
        d = _pdir(proj)
        sf = d / "spec.json"
        sf.write_text(json.dumps(render_spec, ensure_ascii=False), encoding="utf-8")
        for sid in ids:
            rec = _pread(proj)
            if rec.get("status") == "cancelled":
                return
            rec["shots"][sid].update(status="rendering", error=None)
            _pwrite(proj, rec)
            t0 = time.time()
            try:
                src = d / f"src_{sid}.png"
                BP.capture(cams[f"photo_{sid}"], src, pid=pid)
                rec = _pread(proj)
                rec["shots"][sid].update(status="photo")
                _pwrite(proj, rec)
                raw, usage = BP.meta_edit(src.read_bytes(), BP.prompt(sid, spec))
                (d / f"{sid}.jpg").write_bytes(BP.finish(raw))
                rec = _pread(proj)
                rec["shots"][sid].update(status="done", version=proj.version, seconds=round(time.time() - t0, 1), tokens=usage.get("total_tokens"),
                                         image=f"{sid}.jpg", time=time.time(), error=None)
                _pwrite(proj, rec)
            except Exception as e:  # noqa: BLE001
                rec = _pread(proj)
                rec["shots"][sid].update(status="failed", error=str(e)[:400])
                _pwrite(proj, rec)
        rec = _pread(proj)
        rec["status"] = "done"
        _pwrite(proj, rec)
    except Exception as e:  # noqa: BLE001
        rec = _pread(proj)
        rec.update(status="failed", error=str(e)[:400])
        _pwrite(proj, rec)
    finally:
        _PHOTO_BUSY.discard(key)


class PhotoBody(BaseModel):
    shots: list[str] | None = None


@bim_router.post("/projects/{pid}/bim/photos", status_code=202)
def create_photos(pid: str, body: PhotoBody | None = None):
    from . import bim_photos as BP
    proj = _project(pid)
    if not Path(bim.BLENDER).exists():
        raise HTTPException(503, f"Blender nicht gefunden ({bim.BLENDER}).")
    if not BP.api_key():
        raise HTTPException(503, "Meta-Schlüssel fehlt: META_API_KEY in .env.local eintragen und die API neu starten.")
    if proj.dir.name in _PHOTO_BUSY:
        raise HTTPException(429, "Die Bilderwelt wird bereits erzeugt.")
    ids = [s for s in (body.shots if body and body.shots else _PHOTO_IDS) if s in _PHOTO_IDS]
    if not ids:
        raise HTTPException(422, "Unbekannte Ansicht.")
    old = _pread(proj)
    shots = {s: {"status": "queued", **{k: v for k, v in (old.get("shots", {}).get(s) or {}).items() if k in ("image", "version", "time")}} for s in _PHOTO_IDS}
    for s in ids:
        shots[s] = {"status": "queued"}
    rec = {"status": "running", "version": proj.version, "created": time.time(), "shots": shots, "error": None}
    _PHOTO_BUSY.add(proj.dir.name)
    _pwrite(proj, rec)
    threading.Thread(target=_photo_job, args=(pid, proj, ids), daemon=True, name=f"bim-photos-{pid}").start()
    return rec


@bim_router.get("/projects/{pid}/bim/photos")
def list_photos(pid: str):
    proj = _project(pid)
    rec = _pread(proj)
    from . import bim_photos as BP
    return {**({"status": "idle", "shots": {}} | rec), "labels": {s[0]: {"label": s[1], "note": s[2]} for s in BP.SHOTS}, "current_version": proj.version}


@bim_router.get("/projects/{pid}/bim/photos/export")
def export_photos(pid: str):
    import zipfile
    proj = _project(pid)
    rec = _pread(proj)
    files = [(s, (_pdir(proj) / v["image"])) for s, v in rec.get("shots", {}).items() if v.get("image") and (_pdir(proj) / v["image"]).exists()]
    if not files:
        raise HTTPException(404, "Noch keine Bilder.")
    z = _pdir(proj) / "bilderwelt.zip"
    names = {"main": "1_hauptansicht", "close1": "2_closeup_links", "close2": "3_closeup_garten", "aerial": "4_lageansicht"}
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
        for s, f in files:
            zf.write(f, f"{names.get(s, s)}_4k.jpg")
    return FileResponse(z, media_type="application/zip", filename="bilderwelt.zip")


@bim_router.get("/projects/{pid}/bim/photos/{shot}")
def photo_image(pid: str, shot: str):
    proj = _project(pid)
    if shot not in _PHOTO_IDS:
        raise HTTPException(404, "Unbekannte Ansicht.")
    f = _pdir(proj) / f"{shot}.jpg"
    if not f.exists():
        raise HTTPException(404, "Noch kein Bild.")
    return FileResponse(f, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
