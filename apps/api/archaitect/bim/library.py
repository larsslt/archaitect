"""Material library: one JSON file (materials/library.json) feeds the IFC colours, the schema,
the interpreter prompt and the Blender shaders, so a new material is added in exactly one place."""
from __future__ import annotations

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent / "materials" / "library.json"
KINDS = {"plaster", "concrete", "paving", "painted", "metal", "glass", "water", "foliage", "gravel",
         "wood", "fabric", "brick", "lawn_soil", "grass_hair", "leaf", "stone", "tile", "slate", "thatch"}


def load() -> dict:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def spec_styles() -> list[str]:
    """Keys the interpreter may use in a spec (everything that is not render-only)."""
    return [k for k, v in load().items() if not v.get("render_only")]


def rgb(name: str, default=(0.8, 0.8, 0.8)) -> tuple:
    entry = load().get(name)
    return tuple(entry["rgb"]) if entry else default


def prompt_table() -> str:
    groups: dict[str, list[str]] = {}
    for k, v in load().items():
        if v.get("render_only"):
            continue
        al = v.get("aliases") or []
        groups.setdefault(v["group"], []).append(f"{k}={v['label']}" + (f" ({al[0]})" if al else ""))
    rows = [f"- {g}: " + "; ".join(items) for g, items in groups.items()]
    return "# Materialien (nur diese Schlüssel sind erlaubt; Format schluessel=Bezeichnung (Synonym))\n" + "\n".join(rows)


def problems() -> list[str]:
    out = []
    for k, v in load().items():
        if v.get("shader", {}).get("kind") not in KINDS:
            out.append(f"{k}: unbekannte shader-kind {v.get('shader', {}).get('kind')!r}")
        if len(v.get("rgb", [])) != 3:
            out.append(f"{k}: rgb fehlt")
    return out
