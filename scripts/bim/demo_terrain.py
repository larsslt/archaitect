"""Acceptance demo: a house from the BIM library on the real Darmstadt DGM1 fixture (graded terrain), IFC + 360° mesh + optional Blender render.

    apps/api/.venv/bin/python scripts/bim/demo_terrain.py <outdir> [spec.json] [--render preview|draft|sketch] [--camera NAME] [--shift DX DY]

Without --render only IFC, mesh JSON and a text report are written (seconds). The terrain is the repository's recorded test grid, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from archaitect.bim import api, meshexport, terrain as T  # noqa: E402
from archaitect.bim.ifcgen import build_ifc  # noqa: E402
from archaitect.bim.interpret import validate_spec  # noqa: E402
from archaitect.siteintel import terrain as ST  # noqa: E402

TIF = ROOT / "apps" / "api" / "tests" / "fixtures_siteintel" / "bin" / "dgm1__darmstadt.tif"
DEFAULT_SPEC = ROOT / "apps" / "api" / "archaitect" / "bim" / "specs" / "stadthaus.json"


def darmstadt_pack(half: float = 45.0) -> dict:
    g = ST.read_float_tiff(TIF.read_bytes())
    ox, oy = g.x0 + g.w * g.dx / 2, g.y0 - g.h * g.dy / 2
    ds = ST.downsample(g)
    ds["x_west_local"] = round(ds.pop("x_west") - ox, 2)
    ds["y_north_local"] = round(ds.pop("y_north") - oy, 2)
    ring = [[-half / 2, -half], [half / 2, -half], [half / 2, half], [-half / 2, half], [-half / 2, -half]]
    return {"terrain": {"status": "OK", "cell_m_native": g.dx, "grid": ds}, "site": {"ring_local": ring},
            "_summary": ST.summarize(g, __import__("shapely.geometry", fromlist=["box"]).box(-half / 2 + ox, -half + oy, half / 2 + ox, half + oy))}


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("out/demo_terrain")
    out.mkdir(parents=True, exist_ok=True)
    spec_path = Path(next((a for a in argv[1:] if a.endswith(".json")), DEFAULT_SPEC))
    quality = argv[argv.index("--render") + 1] if "--render" in argv else None
    camera = argv[argv.index("--camera") + 1] if "--camera" in argv else None
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pack = darmstadt_pack()
    dx, dy = (float(argv[argv.index("--shift") + 1]), float(argv[argv.index("--shift") + 2])) if "--shift" in argv else (0.0, 0.0)
    spec.setdefault("site", {})["placement"] = {"x": dx, "y": dy, "rotation_deg": 0.0}
    spec["site"]["terrain"] = T.build_terrain(pack, spec)
    problems = validate_spec(spec)
    if problems:
        print("INVALID:", problems)
        return 2
    (out / "spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    build_ifc(str(out / "spec.json"), str(out / "model.ifc"))
    mesh = meshexport.build(out / "model.ifc", spec["site"]["terrain"])
    (out / "mesh.json").write_text(json.dumps(mesh), encoding="utf-8")
    t = spec["site"]["terrain"]
    print(f"terrain {t['status']}: pad {t.get('pad_z_abs_m')} m NHN, slope {t.get('natural_slope_pct')} %, cut {t.get('cut_m3')} m3, fill {t.get('fill_m3')} m3, "
          f"max cut {t.get('max_cut_m')} m, max fill {t.get('max_fill_m')} m; mesh parts {len(mesh['parts'])}, bounds {mesh['bounds']}")
    for n in t.get("notes_de", []):
        print(" -", n)
    if quality:
        cams = api.camera_names(spec)
        cam = camera if camera in cams else cams[0]
        img = out / f"render_{cam}_{quality}.png"
        rc, tail = api.run_blender(out / "model.ifc", out / "spec.json", cam, quality, img)
        print("render", "ok" if not rc and img.exists() else f"FAILED rc={rc}\n{tail}", img)
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
