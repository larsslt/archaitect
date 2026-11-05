#!/usr/bin/env python3
"""Construction bench: mutates the library houses into complex / faulty specs, runs the plausibility repairs and counts what is still wrong.

    cd apps/api && .venv/bin/python ../../scripts/construction_bench.py [N_VARIANTS=300] [SEED=1] [IFC_SAMPLE=25]

Output: issues per spec before / after ``logic.complete`` (by code), crashes, IFC build failures. No language model, no network.
Lower "after" is better; the target is 0 for every code.
"""
import copy
import json
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from archaitect.bim import logic, meshexport  # noqa: E402
from archaitect.bim.audit import audit  # noqa: E402
from archaitect.bim.ifcgen import build_ifc  # noqa: E402
from archaitect.siteintel import bim_api  # noqa: E402

SIDES = "SNEW"


def mutate(spec: dict, rnd: random.Random) -> dict:
    s = copy.deepcopy(spec)
    vols = s["volumes"]
    for v in vols:
        if rnd.random() < 0.6:
            f = rnd.uniform(0.6, 1.5)
            v["size"] = [round(max(3.0, v["size"][0] * f), 2), round(max(3.0, v["size"][1] * rnd.uniform(0.7, 1.4)), 2)]
        if rnd.random() < 0.4:
            v["storeys"] = rnd.randint(1, 5)
        if rnd.random() < 0.3:
            v["origin"] = [round(v["origin"][0] + rnd.uniform(-3, 3), 2), round(v["origin"][1] + rnd.uniform(-3, 3), 2)]
    if rnd.random() < 0.6:       # second volume stacked / attached at random
        b = vols[0]
        n = copy.deepcopy(b)
        n["id"] = "Z"
        n["name"] = "Anbau"
        n["size"] = [round(rnd.uniform(3, 8), 2), round(rnd.uniform(3, 8), 2)]
        n["origin"] = [round(b["origin"][0] + rnd.uniform(-4, b["size"][0]), 2), round(b["origin"][1] + rnd.uniform(-4, b["size"][1]), 2)]
        n["storeys"] = rnd.randint(1, 3)
        n["base_z"] = rnd.choice([0.0, 0.0, round(b.get("storey_height", 3.0) * rnd.randint(1, 2), 2), round(rnd.uniform(0.3, 2.0), 2)])
        n.pop("facade_detail", None)
        vols.append(n)
    ops = s.setdefault("openings", [])
    for _ in range(rnd.randint(0, 8)):
        v = rnd.choice(vols)
        side = rnd.choice(SIDES)
        L = v["size"][0] if side in "SN" else v["size"][1]
        w = round(rnd.uniform(0.6, 2.4), 2)
        kind = rnd.choice(["window", "window", "door"])
        ops.append({"volume": v["id"], "side": side, "storey": rnd.randint(0, max(0, int(v["storeys"]) - 1)), "offset": round(rnd.uniform(-0.3, L - w + 0.3), 2),
                    "width": w, "height": round(rnd.uniform(0.9, 2.4), 2), "sill": round(rnd.uniform(0, 1.2), 2) if kind == "window" else 0.0, "kind": kind})
    comps = s.setdefault("components", [])
    for _ in range(rnd.randint(0, 4)):
        v = rnd.choice(vols)
        t = rnd.choice(["terrace", "steps", "carport", "loggia"])
        side = rnd.choice(SIDES)
        L = v["size"][0] if side in "SN" else v["size"][1]
        c = {"type": t, "volume": v["id"], "side": side, "u": round(rnd.uniform(0, L), 2)}
        if t in ("terrace", "carport"):
            c.update({"width": round(rnd.uniform(2, 8), 2), ("depth" if t == "terrace" else "projection"): round(rnd.uniform(2, 5), 2)})
        comps.append(c)
    return s


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    ifc_n = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    rnd = random.Random(seed)
    names = bim_api.LIBRARY_HOUSES
    before, after = Counter(), Counter()
    crashes, ifc_fail, ifc_done = [], [], 0
    bad_specs = 0
    t0 = time.time()
    with tempfile.TemporaryDirectory() as td:
        for i in range(n):
            name = names[i % len(names)]
            spec = mutate(bim_api._library_spec(name), rnd)
            for code, _ in audit(spec):
                before[code] += 1
            try:
                done, _notes = logic.complete(spec)
            except Exception as e:  # noqa: BLE001
                crashes.append((name, i, repr(e)[:160]))
                continue
            issues = audit(done)
            for code, msg in issues:
                after[code] += 1
            bad_specs += 1 if issues else 0
            if i < ifc_n:
                ifc_done += 1
                try:
                    f = Path(td) / f"s{i}.json"
                    f.write_text(json.dumps(done), encoding="utf-8")
                    res = meshexport.build(build_ifc(f, Path(td) / f"m{i}.ifc"), None, done)
                    assert res["parts"]
                except Exception as e:  # noqa: BLE001
                    import traceback
                    fr = traceback.extract_tb(e.__traceback__)[-1]
                    ifc_fail.append((name, i, repr(e)[:110] + f' @{Path(fr.filename).name}:{fr.lineno}'))
    print(f"variants={n} seed={seed} time={time.time() - t0:.0f}s")
    print("BEFORE repairs:", dict(before.most_common()))
    print("AFTER  repairs:", dict(after.most_common()), f"| specs with issues: {bad_specs}/{n}")
    print(f"crashes in complete(): {len(crashes)}", crashes[:5])
    print(f"IFC build failures: {len(ifc_fail)}/{ifc_done}")
    import re as _re
    for msg, k in Counter(_re.sub(r"[0-9.]+", "#", e)[:110] for _, _, e in ifc_fail).most_common(12):
        print("   ", k, msg)
    return 0 if not crashes and not ifc_fail else 1


if __name__ == "__main__":
    sys.exit(main())
