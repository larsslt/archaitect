"""Text/image -> building spec, vendor-neutral.

No paid API is called unless BIMRENDER_LLM_URL is set explicitly. Providers:
  - "manual" (default): writes a prompt bundle (system prompt, user text, image paths) to disk.
    Any assistant or a person answers it; the answer is validated with `bimrender check`.
  - "ollama" (BIMRENDER_LLM_URL=http://127.0.0.1:11434): local, free, no key.
  - "openai-compatible": POSTs to BIMRENDER_LLM_URL (/v1/chat/completions), which covers Ollama,
    LM Studio, vLLM and hosted OpenAI-compatible endpoints (e.g. Meta Llama API). Key from
    BIMRENDER_LLM_KEY, model from BIMRENDER_LLM_MODEL.
Every answer is validated against schema.json AND by building the IFC in memory; errors are fed back
for up to `repair_rounds` corrections.
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYSTEM_PROMPT = (ROOT / "interpreter" / "SYSTEM_PROMPT.md").read_text(encoding="utf-8")
from . import catalog, library, typologies
from .expand import expand_spec
from .logic import normalize
SCHEMA = json.loads((Path(__file__).parent / "schema.json").read_text(encoding="utf-8"))
SCHEMA["properties"]["components"]["items"]["properties"]["type"]["enum"] = catalog.types()
SCHEMA["properties"]["building_type"] = {"enum": typologies.KEYS}
SCHEMA["$defs"]["style"] = {"enum": library.spec_styles()}
EXAMPLE = (ROOT / "specs" / "villa_kubus.json").read_text(encoding="utf-8")
EXAMPLE2 = json.dumps(json.loads((ROOT / "specs" / "fachwerkhaus.json").read_text(encoding="utf-8")), ensure_ascii=False)


log = logging.getLogger("archaitect.bim.interpret")
_TL = threading.local()   # metadata of the last model call of this thread (model, finish_reason, usage, seconds)


class BudgetExhausted(RuntimeError):
    """The shared time/call budget of one generation is used up."""


class Budget:
    """One budget for every model call of a single generation (transport retry, truncation retry, JSON repair, parcel-fit correction).

    Nested retries can no longer multiply the waiting time unnoticed: each HTTP call takes one unit and its timeout is cut to the time left."""

    def __init__(self, seconds: float | None = None, calls: int | None = None):
        self.seconds = float(seconds if seconds is not None else os.environ.get("BIMRENDER_TOTAL_BUDGET_S", "270"))
        self.calls_left = int(calls if calls is not None else os.environ.get("BIMRENDER_MAX_CALLS", "4"))
        self.started = time.monotonic()
        self.log: list[dict] = []

    def remaining(self) -> float:
        return self.seconds - (time.monotonic() - self.started)

    def take(self, phase: str, min_seconds: float = 20.0) -> float:
        """Reserve one model call and return the timeout it may use (seconds)."""
        if self.calls_left <= 0:
            raise BudgetExhausted(f"Aufrufbudget erschöpft (Phase {phase}).")
        if self.remaining() < min_seconds:
            raise BudgetExhausted(f"Zeitbudget erschöpft (Phase {phase}, noch {max(0.0, self.remaining()):.0f} s von {self.seconds:.0f} s).")
        self.calls_left -= 1
        return self.remaining()

    def note(self, **entry) -> None:
        self.log.append(entry)

    def summary(self) -> dict:
        return {"seconds_total": round(time.monotonic() - self.started, 1), "calls": list(self.log)}


def _volume_walls(v: dict) -> tuple[set[int], set[str]]:
    """Storey indices that have walls (0..n-1) and, for a gable roof, the gable sides that also have a wall at index n."""
    n = int(v.get("storeys", 1))
    idx = set(range(n))
    roof = v.get("roof") or {}
    gable_sides: set[str] = set()
    if roof.get("type") == "gable":
        gable_sides = {"W", "E"} if roof.get("ridge", "x") == "x" else {"S", "N"}
        idx.add(n)
    return idx, gable_sides


def check_references(spec: dict) -> list[str]:
    """Reference errors the IFC builder would only report as an opaque KeyError: unknown volume, storey without wall, side without gable.

    Messages are written for the model's repair round (they state the valid range). Nothing is deleted or moved here."""
    out: list[str] = []
    vols = {v.get("id"): v for v in spec.get("volumes", []) if isinstance(v, dict)}
    for i, o in enumerate(spec.get("openings", []) or []):
        if not isinstance(o, dict):
            continue
        vid, side, st = o.get("volume"), o.get("side"), o.get("storey")
        label = f"Öffnung {i} (Volumen {vid}, Seite {side}, Geschoss {st})" + (" [automatisch ergänzt]" if o.get("auto") else "")
        v = vols.get(vid)
        if v is None:
            out.append(f"{label}: Volumen {vid!r} existiert nicht (vorhanden: {', '.join(map(str, vols)) or 'keines'}).")
            continue
        if side not in ("S", "N", "E", "W"):
            out.append(f"{label}: Seite muss S, N, E oder W sein.")
            continue
        try:
            st = int(st)
        except (TypeError, ValueError):
            out.append(f"{label}: storey muss eine ganze Zahl sein (Zählung ab 0 = Erdgeschoss).")
            continue
        idx, gable_sides = _volume_walls(v)
        n = int(v.get("storeys", 1))
        if st in idx and not (st == n and side not in gable_sides):
            continue
        if st == n:
            out.append(f"{label}: Geschoss {st} liegt über den {n} Vollgeschossen von Volumen {vid}. Dort gibt es nur Giebelwände bei einem Satteldach "
                       f"(Seiten {'/'.join(sorted(gable_sides)) or 'keine'}); Dach {(v.get('roof') or {}).get('type', 'flat')}, Seite {side} hat keine Wand.")
        else:
            out.append(f"{label}: Volumen {vid} hat {n} Vollgeschoss(e); gültige Geschossindizes sind 0..{n - 1} (Zählung beginnt bei 0). "
                       "Für ein höheres Geschoss storeys des Volumens erhöhen oder ein eigenes Volumen darüber setzen.")
    return out


def validate_spec(spec: dict) -> list[str]:
    """Return a list of human-readable problems (empty = valid and buildable)."""
    problems = []
    try:
        spec = expand_spec(spec)
    except ValueError as e:
        return [f"expand: {e}"]
    try:
        import jsonschema
        v = jsonschema.Draft202012Validator(SCHEMA)
        for e in sorted(v.iter_errors(spec), key=lambda e: list(e.path)):
            problems.append(f"schema {'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
    except ImportError:
        problems.append("jsonschema not installed")
    if problems:
        return problems
    refs = check_references(spec)                      # what the model wrote
    try:
        for p in check_references(normalize(spec)):    # what normalize() completed or kept (auto doors, balcony/loggia doors)
            if p not in refs:
                refs.append(p)
    except Exception as e:  # noqa: BLE001
        log.warning("normalize failed during validation", exc_info=True)
        refs.append(f"normalize: {type(e).__name__}: {e}")
    if refs:
        return refs
    try:
        from .ifcgen import Builder
        Builder(spec).build()
    except Exception as e:  # geometry/consistency errors from the deterministic builder
        frame = traceback.extract_tb(e.__traceback__)[-1]
        log.warning("IFC build failed: %s: %s", type(e).__name__, e, exc_info=True)
        problems.append(f"build: {type(e).__name__}: {e} ({Path(frame.filename).name}:{frame.lineno} in {frame.name})")
    return problems


def _compact() -> bool:
    """Small local models (Ollama, 20k context) get a shortened prompt: no component catalogue, one example. BIMRENDER_PROMPT=full|compact overrides."""
    mode = os.environ.get("BIMRENDER_PROMPT", "").lower()
    if mode in ("full", "compact"):
        return mode == "compact"
    url = os.environ.get("BIMRENDER_LLM_URL", "")
    return os.environ.get("BIMRENDER_LLM_PROVIDER") == "ollama" or ":11434" in url


def _system(compact: bool | None = None):
    compact = _compact() if compact is None else compact
    schema = "\n\n# Schema\n```json\n" + json.dumps(SCHEMA) + "\n```"
    if compact:
        return (SYSTEM_PROMPT + "\n\n" + library.prompt_table() + "\n\n" + typologies.prompt_table(compact=True) + schema
                + "\n\n# Beispiel (Satteldach, Fachwerk) – nur als Formatvorlage, NIE unverändert übernehmen\n```json\n" + EXAMPLE2 + "\n```")
    return (SYSTEM_PROMPT + "\n\n" + library.prompt_table() + "\n\n" + typologies.prompt_table() + "\n\n" + catalog.prompt_table() + schema
            + "\n\n# Beispiel\n```json\n" + EXAMPLE + "\n```\n\n# Beispiel 2 (Satteldach, Fachwerk)\n```json\n" + EXAMPLE2 + "\n```")


def _echo_of_example(data: dict) -> str | None:
    """Small local models sometimes return one of the prompt examples unchanged. Returns that example's name if the volumes are identical."""
    def sig(d):
        return [(tuple(v.get("origin", ())), tuple(v.get("size", ())), v.get("storeys", 1)) for v in d.get("volumes", [])]
    for ex in (EXAMPLE, EXAMPLE2):
        try:
            e = json.loads(ex)
        except (TypeError, json.JSONDecodeError):
            continue
        if sig(e) and sig(e) == sig(data):
            return e.get("name") or "Beispiel"
    return None


def _image_part(path: str):
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    data = base64.b64encode(Path(path).read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def _openai_compatible(messages, _length_retry=False, budget=None, phase="llm"):
    url = os.environ["BIMRENDER_LLM_URL"].rstrip("/") + "/v1/chat/completions"
    body = {"model": os.environ.get("BIMRENDER_LLM_MODEL", "llama3.2-vision"), "messages": messages,
            "temperature": 0.2, "response_format": {"type": "json_object"},
            # reasoning models spend tokens on thinking first; keep room for the JSON answer
            "max_completion_tokens": int(os.environ.get("BIMRENDER_LLM_MAX_TOKENS", "16000"))}
    if os.environ.get("BIMRENDER_LLM_REASONING"):  # low | medium | high (reasoning models only)
        body["reasoning_effort"] = os.environ["BIMRENDER_LLM_REASONING"]
    if _length_retry:
        body["max_completion_tokens"] = min(body["max_completion_tokens"] * 2, max(body["max_completion_tokens"], int(os.environ.get("BIMRENDER_LLM_MAX_RETRY_TOKENS", "24000"))))
        if "reasoning_effort" in body:
            body["reasoning_effort"] = "low"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    if os.environ.get("BIMRENDER_LLM_KEY"):
        req.add_header("Authorization", "Bearer " + os.environ["BIMRENDER_LLM_KEY"])
    tries = 1 + max(0, int(os.environ.get("BIMRENDER_LLM_RETRIES", "0")))
    label = phase + ("+length-retry" if _length_retry else "")
    t0 = time.monotonic()
    data = None
    for attempt in range(tries):                      # hosted models sometimes hang or answer 429/5xx once; retry, then raise
        timeout = int(os.environ.get("BIMRENDER_LLM_TIMEOUT", "900"))
        if budget is not None:                        # every HTTP attempt takes one unit of the shared budget and is capped by the time left
            timeout = max(5, min(timeout, int(budget.take(label))))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
                choice = data["choices"][0]
            break
        except urllib.error.HTTPError as e:
            if attempt + 1 >= tries or e.code not in (408, 429, 500, 502, 503, 504):
                raise
        except TimeoutError:
            # A timed-out generation may still be running upstream. Do not duplicate it.
            raise
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError) or attempt + 1 >= tries:
                raise
        except OSError:
            raise
        time.sleep(float(os.environ.get("BIMRENDER_LLM_RETRY_WAIT", "3")))
    meta = {"phase": label, "model": body["model"], "finish_reason": choice.get("finish_reason"), "usage": (data or {}).get("usage"),
            "seconds": round(time.monotonic() - t0, 1), "max_completion_tokens": body["max_completion_tokens"],
            "reasoning_effort": body.get("reasoning_effort")}
    _TL.meta = meta
    if budget is not None:
        budget.note(**meta)
    log.info("model call %s", json.dumps(meta, ensure_ascii=False))
    if choice.get("finish_reason") == "length":
        if not _length_retry:
            # One bounded retry, including partial JSON: a truncated specification is never safe to use.
            return _openai_compatible(messages, _length_retry=True, budget=budget, phase=phase)
        raise RuntimeError("Die Hausbeschreibung konnte innerhalb des Antwortbudgets nicht vollständig erzeugt werden. Bitte den Entwurf zunächst auf den Hauptbaukörper begrenzen und Details anschließend ergänzen.")
    if not choice["message"].get("content"):
        raise RuntimeError(f"Das Sprachmodell lieferte keine Antwort (finish_reason={choice.get('finish_reason')}); "
                           "BIMRENDER_LLM_MAX_TOKENS erhöhen oder BIMRENDER_LLM_REASONING senken")
    return choice["message"]["content"]


def _ollama(messages):
    """Native Ollama API: lets us set the context window (the OpenAI-compatible route cannot)."""
    url = os.environ["BIMRENDER_LLM_URL"].rstrip("/") + "/api/chat"
    msgs = []
    for m in messages:
        if isinstance(m["content"], list):
            text = "\n".join(p["text"] for p in m["content"] if p["type"] == "text")
            imgs = [p["image_url"]["url"].split(",", 1)[1] for p in m["content"] if p["type"] == "image_url"]
            msgs.append({"role": m["role"], "content": text, **({"images": imgs} if imgs else {})})
        else:
            msgs.append(m)
    body = {"model": os.environ.get("BIMRENDER_LLM_MODEL", "qwen3:8b"), "messages": msgs, "stream": False,
            "think": False, "format": "json",
            "options": {"num_ctx": int(os.environ.get("BIMRENDER_LLM_CTX", "20000")), "temperature": 0.2}}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read())["message"]["content"]


def _llm(messages, budget=None, phase="llm"):
    url = os.environ.get("BIMRENDER_LLM_URL", "")
    if os.environ.get("BIMRENDER_LLM_PROVIDER") == "ollama" or ":11434" in url:
        if budget is not None:
            budget.take(phase)
        _TL.meta = {"phase": phase, "model": os.environ.get("BIMRENDER_LLM_MODEL"), "finish_reason": None, "usage": None, "seconds": None}
        return _ollama(messages)
    return _openai_compatible(messages, budget=budget, phase=phase)


def _save_attempt(diag: Path, phase: str, raw: str | None, status: str, problems: list[str] | None, meta: dict | None) -> None:
    """Keep every model answer (also invalid ones) for diagnosis. No key, no prompt - only the answer and the call metadata."""
    try:
        diag.mkdir(parents=True, exist_ok=True)
        entry = {"saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "phase": phase, "status": status, "problems": problems or [],
                 "meta": meta or {}, "raw_answer": (raw or "")[:300000]}
        (diag / f"{int(time.time() * 1000)}_{phase}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        log.warning("could not save diagnostics", exc_info=True)


def interpret(text: str, images: list[str] | None = None, answers: str | None = None,
              out_dir: Path | None = None, repair_rounds: int = 2, budget: "Budget | None" = None) -> dict:
    images = images or []
    out_dir = Path(out_dir or Path(tempfile.gettempdir()) / "archaitect-bim-interpret")
    out_dir.mkdir(parents=True, exist_ok=True)
    user = text if not answers else f"{text}\n\nAntworten auf Rückfragen:\n{answers}"
    if not os.environ.get("BIMRENDER_LLM_URL"):
        bundle = out_dir / "prompt_bundle.md"
        bundle.write_text(_system() + "\n\n# Nutzereingabe\n" + user + "\n\n# Bilder\n" +
                          "\n".join(str(Path(i).resolve()) for i in images), encoding="utf-8")
        return {"status": "manual", "bundle": str(bundle),
                "next": "Antwort-JSON als Datei speichern und `python -m bimrender check <datei>` ausführen."}
    content = [{"type": "text", "text": user}] + [_image_part(i) for i in images]
    messages = [{"role": "system", "content": _system()}, {"role": "user", "content": content}]
    diag = out_dir / "diagnostics"
    problems: list[str] = []

    def invalid(msgs: list[str]) -> dict:
        return {"status": "invalid", "problems": msgs, "diagnostics": str(diag), "budget": budget.summary() if budget else None}

    for attempt in range(repair_rounds + 1):
        phase = "generate" if attempt == 0 else f"repair{attempt}"
        if attempt and budget is not None and budget.remaining() < 60:   # a repair round needs a realistic chance to finish
            return invalid(problems + [f"Reparatur übersprungen: nur noch {max(0.0, budget.remaining()):.0f} s Zeitbudget."])
        raw = _llm(messages, budget, phase)
        meta = getattr(_TL, "meta", None)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            problems = [f"Kein gültiges JSON ({e})."]
            _save_attempt(diag, phase, raw, "json_error", problems, meta)
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Kein gültiges JSON ({e}). Nur das JSON-Objekt senden."}]
            continue
        if "questions" in data:
            _save_attempt(diag, phase, raw, "questions", None, meta)
            return {"status": "questions", **data}
        problems = validate_spec(data)
        echo = _echo_of_example(data) if not problems else None
        if echo:
            problems = [f"Das Sprachmodell hat nur das Beispiel „{echo}“ kopiert."]
        _save_attempt(diag, phase, raw, "ok" if not problems else "invalid", problems, meta)
        if echo and attempt >= repair_rounds:
            return invalid([f"Das Sprachmodell hat nur das Beispiel „{echo}“ kopiert. Ein stärkeres Modell (BIMRENDER_LLM_URL) oder ein Beispielhaus aus der Bibliothek verwenden."])
        if echo:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Das ist das Beispiel „{echo}“ aus der Anleitung, unverändert kopiert. Entwirf stattdessen ein NEUES Haus, das genau zur Nutzereingabe passt "
                                                     "(Maße, Geschosse, Dach, Fassade, Öffnungen). Nur das JSON-Objekt senden."}]
            continue
        if not problems:
            data = normalize(data)
            path = out_dir / "spec.json"
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"status": "ok", "spec": str(path), "diagnostics": str(diag), "budget": budget.summary() if budget else None}
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Bitte gezielt korrigieren (nur diese Punkte ändern, alles andere unverändert lassen; Geschossindizes zählen ab 0):\n- " + "\n- ".join(problems)}]
    return invalid(problems)


# ---------------------------------------------------------------------------- revise (text change)
REVISE_PROMPT = (ROOT / "interpreter" / "REVISE_PROMPT.md").read_text(encoding="utf-8")


def _revise_system(spec: dict) -> str:
    return (REVISE_PROMPT + "\n\n" + library.prompt_table() + "\n\n" + catalog.prompt_table() + "\n\n# Schema\n```json\n" + json.dumps(SCHEMA) + "\n```\n\n# Aktuelle Spezifikation\n```json\n"
            + json.dumps(spec, indent=1, ensure_ascii=False) + "\n```")


def apply_answer(project, data, note: str = "") -> dict:
    """Apply an interpreter answer (patch dict, patch list, full spec or questions) to a project.

    A new version is saved only if the result passes schema + IFC-build validation."""
    from .projects import PatchError, apply_patch
    if isinstance(data, list):
        data = {"patch": data}
    if "questions" in data:
        return {"status": "questions", **data}
    try:
        if "patch" in data:
            new = apply_patch(project.spec(), data["patch"])
        elif "volumes" in data:
            new = data
        else:
            return {"status": "invalid", "problems": ["Antwort enthält weder patch noch Spezifikation noch Fragen"]}
    except PatchError as e:
        return {"status": "invalid", "problems": [f"patch: {e}"]}
    problems = validate_spec(new)
    if problems:
        return {"status": "invalid", "problems": problems}
    new = normalize(new)
    summary = data.get("summary", "") if isinstance(data, dict) else ""
    v = project.save(new, note or summary)
    from .checks import warnings
    return {"status": "ok", "version": v, "summary": summary, "warnings": warnings(new)}


def revise(project, request: str, repair_rounds: int = 2) -> dict:
    """Change request (plain text) + current spec -> new project version."""
    system = _revise_system(project.spec())
    if not os.environ.get("BIMRENDER_LLM_URL"):
        bundle = project.dir / "revise_bundle.md"
        bundle.write_text(system + "\n\n# Änderungswunsch\n" + request, encoding="utf-8")
        return {"status": "manual", "bundle": str(bundle),
                "next": f"Antwort als patch.json speichern und `python -m bimrender apply {project.name} patch.json` ausführen."}
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    problems: list[str] = []
    for _ in range(repair_rounds + 1):
        raw = _llm(messages)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Kein gültiges JSON ({e}). Nur das JSON-Objekt senden."}]
            continue
        result = apply_answer(project, data, note=request)
        if result["status"] != "invalid":
            return result
        problems = result["problems"]
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Bitte korrigieren:\n- " + "\n- ".join(problems)}]
    return {"status": "invalid", "problems": problems}
