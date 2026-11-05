"""Deterministic adaptation of a generated house to the plot: scale the plan down until it fits, and bring storeys/height inside the design frame.

The language model is asked to fit first (generation brief). This is the safety net: it never changes explicit user dimensions, and it never
touches binding planning values - it only moves the design towards them. Every change is reported in the notes."""
from __future__ import annotations

import copy
import re
from typing import Callable

MIN_SCALE = 0.5
MIN_SIDE_M = 3.5
STEP = 0.05

_EXPLICIT_DIMS = re.compile(
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:x|×|mal)\s*\d{1,3}(?:[.,]\d+)?\s*(?:m\b|meter)?|\b\d{2,4}\s*(?:m²|m2|qm|quadratmeter)|"
    r"\b\d{1,3}(?:[.,]\d+)?\s*(?:m|meter)\s*(?:breit|lang|tief|hoch|lange|breite|tiefe|höhe)", re.I)
_EXPLICIT_STOREYS = re.compile(r"\b(?:\d{1,2}|ein|zwei|drei|vier|fünf|sechs|sieben|acht)\s*-?\s*(?:geschossig|etagen|vollgeschosse|geschosse|stockwerke|stockwerk|etage|geschoss)\b", re.I)


def has_explicit_dimensions(*texts: str | None) -> bool:
    return any(_EXPLICIT_DIMS.search(t or "") for t in texts)


def has_explicit_storeys(*texts: str | None) -> bool:
    return any(_EXPLICIT_STOREYS.search(t or "") for t in texts)


def _wall_len(v: dict, side: str) -> float:
    return float(v["size"][0] if side in ("N", "S") else v["size"][1])


def scale_plan(spec: dict, s: float) -> dict:
    """Scale the plan (x/y) by s, keep heights. Openings keep usable sizes; components follow their volume."""
    from ..bim.expand import expand_spec
    out = copy.deepcopy(expand_spec(spec))          # repeats/storey lists become single openings, so offsets scale individually
    vols = {v["id"]: v for v in out.get("volumes", [])}
    for v in out.get("volumes", []):
        v["origin"] = [round(v["origin"][0] * s, 3), round(v["origin"][1] * s, 3)]
        v["size"] = [round(v["size"][0] * s, 3), round(v["size"][1] * s, 3)]
    for c in out.get("curtain_walls", []) or []:
        c["origin"] = [round(c["origin"][0] * s, 3), round(c["origin"][1] * s, 3)]
        c["size"] = [round(c["size"][0] * s, 3), round(c["size"][1] * s, 3)]
    for o in out.get("openings", []) or []:
        v = vols.get(o.get("volume"))
        if not v or "offset" not in o or "width" not in o:
            continue
        L = _wall_len(v, o.get("side", "S"))
        floor = 0.9 if o.get("kind") == "door" else 0.4
        w = min(max(floor, float(o["width"]) * s), max(floor, L - 0.4))
        off = max(0.15, min(float(o["offset"]) * s, L - w - 0.15))
        o["width"], o["offset"] = round(w, 3), round(off, 3)
    for c in out.get("components", []) or []:
        if c.get("volume") in vols:
            for k in ("u", "width", "spacing"):
                if isinstance(c.get(k), (int, float)):
                    c[k] = round(float(c[k]) * s, 3)
            L = _wall_len(vols[c["volume"]], c.get("side", "S"))
            if isinstance(c.get("u"), (int, float)):
                c["u"] = round(min(max(c["u"], 0.2), L - 0.2), 3)
            if isinstance(c.get("width"), (int, float)):
                c["width"] = round(min(max(c["width"], 0.6), L), 3)
        else:
            for k in ("x", "y"):
                if isinstance(c.get(k), (int, float)):
                    c[k] = round(float(c[k]) * s, 3)
            for k in ("width", "depth"):
                if isinstance(c.get(k), (int, float)) and c.get("type") in ("pool", "pond", "lake", "garden_set"):
                    c[k] = round(float(c[k]) * s, 3)
    return out


def candidate_scales(spec: dict) -> list[float]:
    vols = [v for v in spec.get("volumes", []) if v.get("size")]
    main = max(vols, key=lambda v: float(v["size"][0]) * float(v["size"][1])) if vols else None      # the main volume must stay habitable; annexes may get small
    side = min(map(float, main["size"])) if main else 0
    floor = max(MIN_SCALE, MIN_SIDE_M / side) if side else MIN_SCALE
    out, s = [], 1.0 - STEP
    while s >= floor - 1e-9:
        out.append(round(s, 2))
        s -= STEP
    return out


def shrink_to_fit(spec: dict, accepts: Callable[[dict], bool], fits_quick: Callable[[dict], bool] | None = None) -> tuple[dict, float] | None:
    """Largest scale (<1) for which ``accepts(candidate)`` is true. ``fits_quick`` is a cheap pre-filter (volumes only)."""
    for s in candidate_scales(spec):
        cand = scale_plan(spec, s)
        if fits_quick is not None and not fits_quick(cand):
            continue
        if accepts(cand):
            return cand, s
    return None


def spec_top_m(spec: dict) -> float:
    return max((float(v.get("base_z", 0.0)) + int(v.get("storeys", 1)) * float(v.get("storey_height", spec.get("storey_height", 3.0))) for v in spec.get("volumes", [])), default=0.0)


def reduce_to_frame(spec: dict, max_storeys: int | None, max_height_m: float | None, validate: Callable[[dict], list[str]]) -> tuple[dict, list[str]]:
    """Remove top storeys of the highest volume until the design is inside the frame. Openings on removed storeys go with them.
    Reverts (and says so) if the reduced spec is not valid."""
    notes: list[str] = []
    cur = copy.deepcopy(spec)

    def over() -> bool:
        stacked = max((round((float(v.get("base_z", 0.0)) / float(v.get("storey_height", cur.get("storey_height", 3.0)))) + int(v.get("storeys", 1)))
                       for v in cur.get("volumes", [])), default=0)
        return bool((max_storeys and stacked > max_storeys) or (max_height_m and spec_top_m(cur) > max_height_m + 1e-6))

    removed = 0
    while over():
        cand = [v for v in cur["volumes"] if int(v.get("storeys", 1)) > 1]
        if not cand:
            break
        top = max(cand, key=lambda v: float(v.get("base_z", 0.0)) + int(v["storeys"]) * float(v.get("storey_height", cur.get("storey_height", 3.0))))
        top["storeys"] = int(top["storeys"]) - 1
        cur["openings"] = [o for o in cur.get("openings", []) if not (o.get("volume") == top["id"] and int(o.get("storey", 0)) >= top["storeys"])]
        removed += 1
    if not removed:
        return spec, notes
    problems = validate(cur)
    if problems:
        return spec, [f"Geschosse/Höhe liegen über dem Rahmen; automatische Reduzierung nicht möglich ({problems[0][:120]})."]
    limit = ", ".join(x for x in (f"höchstens {max_storeys} Geschosse" if max_storeys else "", f"Höhe höchstens {max_height_m:g} m" if max_height_m else "") if x)
    notes.append(f"Entwurf automatisch an den Rahmen der Umgebung bzw. der Vorgaben angepasst ({limit}): {removed} Geschoss(e) weniger.")
    return cur, notes
