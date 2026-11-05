"""Compact spec notation -> fully expanded spec (idempotent).

Openings may carry
  "storeys": [0,1,2]                   one copy per storey (replaces "storey")
  "repeat": {"count": 5, "pitch": 2.4} copies shifted along the facade by pitch (offset + i*pitch)
Both may be combined (storeys x repeat). The expanded spec is what gets stored and what all
consumers (ifcgen, rooms, detail, api) read.
"""
from __future__ import annotations
import copy


def expand_openings(openings: list[dict]) -> list[dict]:
    out: list[dict] = []
    for n, o in enumerate(openings):
        if not isinstance(o, dict) or ("storeys" not in o and "repeat" not in o):
            out.append(o)
            continue
        base = {k: v for k, v in o.items() if k not in ("storeys", "repeat")}
        storeys = o.get("storeys", [o.get("storey", 0)])
        if not isinstance(storeys, list) or not storeys or not all(isinstance(s, int) and s >= 0 for s in storeys):
            raise ValueError(f"openings[{n}].storeys muss eine nichtleere Liste ganzer Zahlen >= 0 sein")
        rep = o.get("repeat")
        if rep is None:
            count, pitch = 1, 0.0
        else:
            try:
                count, pitch = int(rep["count"]), float(rep["pitch"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(f"openings[{n}].repeat braucht count (int) und pitch (m)")
            if not 1 <= count <= 60:
                raise ValueError(f"openings[{n}].repeat.count muss 1..60 sein")
            if count > 1 and pitch < float(o.get("width", 0)):
                raise ValueError(f"openings[{n}].repeat.pitch ({pitch}) kleiner als width: Öffnungen würden überlappen")
        for s in storeys:
            for i in range(count):
                c = copy.deepcopy(base)
                c["storey"] = s
                c["offset"] = round(float(base.get("offset", 0)) + i * pitch, 4)
                out.append(c)
    return out


def expand_spec(spec: dict) -> dict:
    """Return a copy with compact notation expanded; the input is not modified."""
    if not isinstance(spec, dict) or "openings" not in spec:
        return spec
    new = dict(spec)
    new["openings"] = expand_openings(spec["openings"])
    return new
