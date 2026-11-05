"""Stress test for the Entwurf pipeline against a (copied!) project store. Usage:
   stress_test.py BASE_URL [scenario-id ...]   -> writes /tmp/stress/report.json and prints a summary.
Checks: spec valid, rules (no FAIL / hard_ok), house inside parcel (independent point-in-polygon), IFC opens and has
storeys/walls/roof, mesh finite, terrain plausible (cut/fill finite, retaining-wall note for deep cuts), no HTTP 5xx."""
import json
import math
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001").rstrip("/")
ONLY = set(sys.argv[2:])
S = BASE + "/siteintel/projects"
HANG, GROSS, KLEIN, MITTEL, KLEIN2, NEBEN, DA, FFM = ("p_1fd01fffdbdb", "p_c7baae750e7d", "p_539f94c7beeb", "p_d7b51692bba6",
                                                       "p_855b7d6bcd28", "p_476c51e57987", "p_77bd80956106", "p_e4ea51ea23e4")
SCEN = [
    ("hang_split", HANG, "Hanghaus über drei Ebenen mit Garage im Untergeschoss, Flachdach und großer Terrasse talseitig."),
    ("l_hof", HANG, "L-förmiges Haus mit Innenhof, Satteldach, zwei Vollgeschosse, Carport."),
    ("hofanlage", GROSS, "Dreiflügelige Hofanlage um einen Innenhof mit Walmdach, dazu eine Scheune als Nebengebäude und eine Zufahrt."),
    ("tiny", KLEIN, "Schmales Tiny House 4 m x 10 m mit Pultdach und Dachterrasse."),
    ("turm", MITTEL, "Turmhaus mit sechseckigem Grundriss, drei Geschosse, Kegeldach, Wendeltreppe."),
    ("staffel", KLEIN2, "Haus mit Staffelgeschoss, Flachdach mit Dachterrasse, großem Glasanteil und Carport."),
    ("mfh", NEBEN, "Mehrfamilienhaus mit vier Wohnungen, Treppenhaus mittig, Walmdach, Stellplätze."),
    ("rund", DA, "Bauhaus-Villa mit rundem Erker, Pool im Garten und Flachdach."),
    ("mansarde", FFM, "Reihenendhaus mit Mansarddach, Erker und Garten."),
    ("holz", HANG, "Skandinavisches Holzhaus mit Pultdach, Vordach, Gründach und Photovoltaik."),
    ("hochhaus", MITTEL, "Hochhaus mit 30 Geschossen."),
    ("unsinn", MITTEL, "asdf qwer"),
]
REVISE = [("hang_split", "Mach das Dach zum Satteldach, die Garage nach links und die Terrasse größer."),
          ("l_hof", "Füge einen Wintergarten an der Südseite hinzu und mach die Fenster größer.")]


def call(method, path, body=None, timeout=600):
    req = urllib.request.Request(S + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()


def jcall(method, path, body=None, timeout=600):
    st, raw = call(method, path, body, timeout)
    try:
        return st, json.loads(raw)
    except Exception:  # noqa: BLE001
        return st, {"_raw": raw[:300].decode("utf8", "replace")}


def inside(pt, ring):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def mesh_checks(pid, pl, ring, F):
    st, m = jcall("GET", f"/{pid}/bim/mesh")
    if st != 200:
        F.append(f"mesh HTTP {st}")
        return {}
    parts = [p for p in m["parts"] if p["name"] != "terrain"]
    bad = sum(1 for p in m["parts"] for v in p["positions"] if not math.isfinite(v))
    if bad:
        F.append(f"mesh: {bad} nicht endliche Werte")
    th = math.radians(pl.get("rotation_deg", 0.0))
    c, s = math.cos(th), math.sin(th)
    out, zmin, zmax = 0, 1e9, -1e9
    for p in parts:
        P = p["positions"]
        for i in range(0, len(P), 3):
            x, y, z = P[i:i + 3]
            zmin, zmax = min(zmin, z), max(zmax, z)
            X, Y = pl["x"] + x * c - y * s, pl["y"] + x * s + y * c
            if not inside((X, Y), ring):
                out += 1
    return {"parts": len(parts), "z_min": round(zmin, 2), "z_max": round(zmax, 2), "verts_outside_parcel": out}


def ifc_checks(pid, F):
    st, raw = call("GET", f"/{pid}/bim/ifc")
    if st != 200:
        F.append(f"IFC HTTP {st}")
        return {}
    import tempfile
    import ifcopenshell
    with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as t:
        t.write(raw)
    f = ifcopenshell.open(t.name)
    n = {k: len(f.by_type(k)) for k in ("IfcBuildingStorey", "IfcWall", "IfcSlab", "IfcRoof", "IfcWindow", "IfcDoor", "IfcStair", "IfcSpace")}
    if n["IfcBuildingStorey"] == 0:
        F.append("IFC ohne Geschosse")
    if n["IfcWall"] + len(f.by_type("IfcWallStandardCase")) == 0:
        F.append("IFC ohne Wände")
    if n["IfcSlab"] == 0:
        F.append("IFC ohne Decken/Bodenplatte")
    if n["IfcRoof"] == 0 and n["IfcSlab"] < 2:
        F.append("IFC ohne Dach")
    return n


def evaluate(name, pid, F):
    st, s = jcall("GET", f"/{pid}/bim")
    if st != 200:
        F.append(f"state HTTP {st}")
        return {}
    chk = s["check"]
    fails = [r["id"] + ": " + r["message_de"][:90] for r in chk["results"] if r["status"] == "FAIL"]
    if fails:
        F.append("Regel FAIL: " + "; ".join(fails))
    if not chk.get("hard_ok"):
        F.append("hard_ok false")
    t = s["terrain"]
    if t.get("status") == "OK":
        for k in ("cut_m3", "fill_m3", "max_cut_m", "max_fill_m"):
            if not isinstance(t.get(k), (int, float)) or not math.isfinite(t[k]):
                F.append(f"terrain {k} ungültig")
        if max(t.get("max_cut_m", 0), t.get("max_fill_m", 0)) >= 1.5 and not any("Stütz" in n for n in t.get("notes_de", [])):
            F.append("Tiefer Schnitt/Auftrag >=1,5 m ohne Stützmauer-Hinweis")
    else:
        F.append("terrain status " + str(t.get("status")))
    st2, d = jcall("GET", f"/{pid}/design")
    ring = (d.get("site") or {}).get("ring") or []
    pl = s["placement"]
    res = {"version": s["version"], "name": s["name"], "overall": chk["overall"], "terrain": {k: t.get(k) for k in
           ("natural_slope_pct", "cut_m3", "fill_m3", "max_cut_m", "max_fill_m")}, "warnings": s["warnings"][:4], "rooms": len(s["rooms"])}
    res["mesh"] = mesh_checks(pid, pl, ring, F) if ring else {}
    ex = next((r for r in chk["results"] if r["id"] == "PARCEL_EXTRAS"), {})
    res["extras"] = ex.get("status")
    if res["mesh"].get("verts_outside_parcel") and ex.get("status") != "WARN":          # WARN = bekannt und im UI gemeldet
        par = next((r for r in chk["results"] if r["id"] == "PARCEL"), {})
        F.append(f"{res['mesh']['verts_outside_parcel']} Netzpunkte außerhalb Flurstück (PARCEL={par.get('status')})")
    res["ifc"] = ifc_checks(pid, F)
    return res


def main():
    rep = {}
    for name, pid, text in SCEN:
        if ONLY and name not in ONLY:
            continue
        F, t0 = [], time.time()
        st, r = jcall("POST", f"/{pid}/bim/create", {"text": text})
        rec = {"project": pid, "prompt": text, "http": st, "seconds": round(time.time() - t0, 1)}
        if st >= 500 or st == 0:
            F.append(f"create HTTP {st}: {str(r)[:200]}")
        elif st == 200 and r.get("status") == "ok":
            rec.update(evaluate(name, pid, F))
        else:
            rec["answer"] = str(r)[:300]
            if name != "unsinn":
                F.append("Rückfragen statt Entwurf" if r.get("status") == "questions" else f"kein Entwurf (HTTP {st})")
        rec["findings"] = F
        rep[name] = rec
        print(name, st, rec["seconds"], "FINDINGS:" if F else "ok", F, flush=True)
    for name, text in REVISE:
        if ONLY and name not in ONLY:
            continue
        pid = next(p for n, p, _ in SCEN if n == name)
        F, t0 = [], time.time()
        st, r = jcall("POST", f"/{pid}/bim/revise", {"text": text})
        rec = {"project": pid, "prompt": text, "http": st, "seconds": round(time.time() - t0, 1)}
        if st == 200 and r.get("status") in (None, "ok"):
            rec.update(evaluate(name, pid, F))
        else:
            F.append(f"revise HTTP {st} {r.get('status')}: {str(r)[:200]}")
        rec["findings"] = F
        rep[name + "_revise"] = rec
        print(name + "_revise", st, rec["seconds"], F, flush=True)
    json.dump(rep, open("/tmp/stress/report.json", "w"), indent=1, ensure_ascii=False)


main()
