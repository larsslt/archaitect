#!/usr/bin/env python3
"""Übernimmt gelungene Nachtlauf-Entwürfe als Beispielhäuser in die Bibliothek (bim/specs/<typ>.json + LIBRARY_HOUSES).
Aufruf: promote_to_library.py typ1 typ2 ...   (nimmt je Typ den letzten fehlerfreien Zyklus ohne Spec-Probleme)"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NIGHT = ROOT / ".local" / "night"
SPECS = ROOT / "apps" / "api" / "archaitect" / "bim" / "specs"
API = ROOT / "apps" / "api" / "archaitect" / "siteintel" / "bim_api.py"
PID = (NIGHT / "pid.txt").read_text().strip()
LABEL = {"alpin": "Alpenhaus", "bungalow": "Bungalow", "stadtvilla": "Stadtvilla", "doppelhaus": "Doppelhaus", "mfh": "Mehrfamilienhaus",
         "kubus": "Moderner Kubus mit Pool", "landhaus": "Landhaus", "scheune": "Scheunenhaus", "loft": "Loft (Klinker)", "holzhaus": "Skandinavisches Holzhaus",
         "passivhaus": "Passivhaus", "gewerbe": "Gewerbehalle", "hochhaus": "Wohnhochhaus", "reihenhaus": "Reihenendhaus", "einfamilienhaus": "Einfamilienhaus",
         "bauhaus": "Bauhaus-Villa", "gruenderzeit": "Gründerzeit-Stadthaus", "tiny": "Tiny House", "kita": "Kita", "cafe": "Café", "turmhaus": "Haus mit Turm"}


def main(types):
    rows = [json.loads(l) for l in open(NIGHT / "results.jsonl", encoding="utf-8")]
    done = []
    for t in types:
        good = [r for r in rows if r.get("type") == t and not r.get("error") and r.get("render") == "done" and not (r.get("checks") or {}).get("problems")]
        if not good:
            print("kein sauberer Lauf für", t)
            continue
        r = good[-1]
        sp = json.load(urllib.request.urlopen(f"http://127.0.0.1:8000/siteintel/projects/{PID}/bim/spec/{r['version']}"))
        sp = sp.get("spec", sp)
        site = sp.get("site") or {}
        for k in ("terrain", "placement"):
            site.pop(k, None)
        sp["site"] = site
        sp.pop("auto_notes", None)
        sp["name"] = LABEL.get(t, t)
        sp["description"] = r["prompt"]
        name = re.sub(r"[^a-z0-9_]", "", t.lower())
        (SPECS / f"{name}_lib.json").write_text(json.dumps(sp, ensure_ascii=False, indent=1), encoding="utf-8")
        done.append(f"{name}_lib")
        print("ok", name, "v", r["version"])
    src = API.read_text(encoding="utf-8")
    m = re.search(r"LIBRARY_HOUSES = \(([^)]*)\)", src)
    have = re.findall(r'"([a-z0-9_]+)"', m.group(1))
    new = have + [d for d in done if d not in have]
    src = src.replace(m.group(0), "LIBRARY_HOUSES = (" + ", ".join(f'"{n}"' for n in new) + ")")
    API.write_text(src, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
