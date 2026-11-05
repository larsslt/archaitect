"""Facade detail pass: the model reads timber frames, brackets and ornaments off the reference image, one facade at a time.

Why a separate pass: the first interpretation has to decide volumes, roof, openings and style at once. Per-member detail
(every post, beam and brace of a half-timbered facade) is a different job: it needs the facade geometry (length, storey
heights, window extents) next to the image, a flat elevation of the current model to compare against, and room to think.
So each facade gets its own request, and a second round shows the model what its first answer looks like (flat elevation
render) next to the reference and lets it correct.
"""
from __future__ import annotations

import copy
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor

SYSTEM = """Du bist Bauzeichner für historische Fassaden und überträgst das Fachwerk (und andere Fassadendetails) eines Referenzbildes
millimetergenau in Bauteillisten für EINE Fassade eines Modells.

Koordinaten der Fassade: `u` läuft in Metern von 0 am **linken** Ende der Fassade (von außen gesehen) bis zur Fassadenlänge L.
`z` ist die Höhe in Metern über der Unterkante des Volumens (EG-Fußboden = 0). Alle Teile stehen 6-8 cm vor der Wand.

Bauteile (alle Maße in Metern):
- {"post": [u, z0, z1], "w": 0.14}      senkrechter Ständer, Mitte bei u
- {"beam": [u0, u1, z], "h": 0.16}      waagerechter Balken, Unterkante z
- {"brace": [u0, z0, u1, z1], "w": 0.12} Strebe (Diagonale) von Punkt (u0,z0) nach (u1,z1), w = Balkenbreite
- {"rect": [u0, u1, z0, z1]}            beliebiges Rechteck (Füllung, Knagge, Schwelle)
- {"poly": [[u, z], ...]}               beliebiges Polygon (Zierformen, Knaggen, Rauten, geschwungene Streben als 8-16 Punkte)
Optional je Bauteil `depth` (Standard 0.07) und `material` (Standard timber_dark).

Vorgehen, Schritt für Schritt (schreibe es nicht auf, arbeite es durch):
1. Bestimme, welche Fassade im Referenzbild gemeint ist. Zeigt das Bild die Fassade nicht, übernimm Stil, Balkenlagen, Ständerabstände und
   Strebenmuster der sichtbaren Fassaden und passe sie an die Öffnungen dieser Fassade an. Sage das im "hinweis".
2. Zähle im Bild je Geschoss die Gefache (Felder zwischen den Ständern) und die Fenster. Die Zahl der Felder und Fenster muss stimmen.
3. Lege die waagerechten Lagen fest: Schwelle über dem Sockel, Brüstungsriegel unter den Fenstern, Sturzriegel über den Fenstern,
   Deckenbalken/Rähm am Geschossende. Sie laufen im Bild meist durch; zeichne sie so.
4. Setze die senkrechten Ständer: breitere Eckständer, Ständer links und rechts jeder Öffnung, Zwischenständer in den Feldern wie im Bild.
5. Setze die Streben genau so, wie das Bild sie zeigt: Richtung, Anschlusspunkte (Fußband, Kopfband, Andreaskreuz, Mannfigur, K-Strebe),
   nicht ein beliebiges Muster. Streben enden an Ständern und Riegeln, nicht im freien Feld.
6. Zierformen (Knaggen, Rauten, Kreuzformen, gekerbte Balkenköpfe, geschwungene Bänder) als `poly`.
7. Nichts durch Fenster oder Türen: die Öffnungen stehen mit u- und z-Bereich im Kontext. Rahme sie mit Ständern und Riegeln.
8. Giebelfassade: das Giebeldreieck oberhalb der Traufe (z > Geschosszahl * Geschosshöhe) hat die maximale Höhe laut Tabelle im Kontext.
   Bauteile müssen innerhalb des Dreiecks bleiben.
9. Typische Größen: Ständer 0.12-0.16, Eckständer 0.18-0.22, Riegel/Rähm 0.14-0.20 hoch, Streben 0.10-0.14 breit.

Antworte nur mit JSON: {"hinweis": "2-4 Sätze: welche Bildfassade, Felder je Geschoss, Besonderheiten", "items": [ ... ]}.
Nichts weglassen und nichts erfinden, was das Bild nicht zeigt."""

CRITIQUE = """Hier ist dein erster Entwurf als flache Ansicht des Modells (letztes Bild) neben dem Referenzbild. Vergleiche Feld für Feld:
Balkenlagen (Höhe), Ständerabstände, Streben (Richtung und Anschlusspunkte), Anzahl der Fenster und Felder, Zierformen, Eckausbildung.
Gib die vollständige verbesserte Bauteilliste zurück (nicht nur Änderungen), im selben JSON-Format. Korrigiere nur, was wirklich abweicht."""


def _png_image(path):
    from .interpret import _image_part
    return _image_part(str(path))


def elevation_camera(spec: dict, vid: str, side: str) -> dict:
    """Camera far away with a long lens: a flat elevation of one facade (almost no perspective)."""
    from .geom import facade_xy, side_length
    from .ifcgen import Builder
    v = next(x for x in spec["volumes"] if x["id"] == vid)
    (ox, oy), (W, D) = v["origin"], v["size"]
    L = side_length(side, W, D)
    n, h = int(v["storeys"]), float(v.get("storey_height", spec.get("storey_height", 3.0)))
    top = float(v["base_z"]) + n * h
    roof = v.get("roof") or {}
    zmax = top
    if roof.get("type") == "gable":
        ridge_w = (W if roof.get("ridge", "x") == "y" else D) / 2
        zmax = top + ridge_w * math.tan(math.radians(float(roof.get("pitch_deg", 45)))) + 0.3
    cx, cy = facade_xy(side, ox, oy, W, D, L / 2, 0.0)
    out = Builder.FACE_DIR[side][0]
    lens = 85.0
    vw = max(L * 1.25, zmax * 1.15 * 16 / 9)
    dist = vw * lens / 36.0
    return {"name": f"elev_{vid}_{side}", "position": [round(cx + out[0] * dist, 2), round(cy + out[1] * dist, 2), round(zmax / 2, 2)],
            "target": [round(cx, 2), round(cy, 2), round(zmax / 2, 2)], "lens_mm": lens}


def facade_context(spec: dict, vid: str, side: str) -> dict:
    from .geom import side_length
    v = next(x for x in spec["volumes"] if x["id"] == vid)
    (W, D) = v["size"]
    L = side_length(side, W, D)
    n, h = int(v["storeys"]), float(v.get("storey_height", spec.get("storey_height", 3.0)))
    ops = []
    for o in spec.get("openings", []):
        if o["volume"] == vid and o["side"] == side:
            s = int(o["storey"])
            zb = s * h + float(o.get("sill", 0.0))
            ops.append({"art": "Tür" if o.get("kind") == "door" else "Fenster", "geschoss": s, "u0": round(float(o["offset"]), 2),
                        "u1": round(float(o["offset"]) + float(o["width"]), 2), "z_unten": round(zb, 2), "z_oben": round(zb + float(o["height"]), 2)})
    ctx = {"volumen": vid, "fassade": side, "fassadenlaenge_L": round(L, 2), "vollgeschosse": n, "geschosshoehe": h,
           "traufhoehe": round(n * h, 2), "oeffnungen": sorted(ops, key=lambda o: (o["geschoss"], o["u0"])),
           "sockelhoehe": float(((v.get("facade_detail") or {}).get("plinth") or {}).get("height", 0.0)),
           "holz_standard": ((v.get("facade_detail") or {}).get("timber_frame") or {})}
    roof = v.get("roof") or {}
    if roof.get("type") == "gable":
        gable_sides = ("S", "N") if roof.get("ridge", "x") == "y" else ("W", "E")
        if side in gable_sides:
            rise = (L / 2) * math.tan(math.radians(float(roof.get("pitch_deg", 45))))
            ctx["giebel"] = {"traufhoehe_z": round(n * h, 2), "firsthoehe_z": round(n * h + rise, 2),
                             "max_hoehe_ueber_traufe_bei_u": {f"{u:.1f}": round(rise * (1 - abs(2 * u / L - 1)), 2)
                                                              for u in [k * 0.5 for k in range(int(L / 0.5) + 1)]}}
        else:
            ctx["hinweis_traufseite"] = "Traufseite: das Dach beginnt oberhalb der Traufhöhe, kein Giebeldreieck."
    for b in spec.get("balconies", []):
        if b.get("volume") == vid and b.get("side") == side:
            ctx["balkon"] = {"u0": b["offset"], "u1": round(b["offset"] + b["width"], 2), "hoehe_z": b["level"]}
    for d in spec.get("dormers", []):
        if d.get("volume") == vid:
            ctx.setdefault("gauben_im_dach", []).append({"dachseite": d["slope"], "offset": d["offset"], "breite": d["width"]})
    return ctx


def _ask(messages, check, repair_rounds=2):
    from .interpret import _llm
    problems = []
    for _ in range(repair_rounds + 1):
        raw = _llm(messages)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": f"Kein gültiges JSON ({e}). Nur das JSON-Objekt senden."}]
            continue
        problems = check(data)
        if not problems:
            return data, []
        messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": "Bitte korrigieren:\n- " + "\n- ".join(problems)}]
    return None, problems


def _with_fe(spec, vid, side, items):
    new = copy.deepcopy(spec)
    new["facade_elements"] = [f for f in new.get("facade_elements", []) if not (f["volume"] == vid and f["side"] == side)]
    new["facade_elements"].append({"volume": vid, "side": side, "items": items})
    return new


def _checker(spec, vid, side):
    from .interpret import validate_spec

    def check(data):
        items = data.get("items")
        if not isinstance(items, list) or len(items) < 4:
            return ["items fehlt oder hat weniger als 4 Bauteile"]
        return validate_spec(_with_fe(spec, vid, side, items))[:8]
    return check


def run(target: str, sides=None, rounds: int = 2, progress=None) -> dict:
    """Facade detail pass for all (or the given) sides of every volume with a timber frame."""
    from . import api
    try:
        proj = api.open_project(target)
    except (FileNotFoundError, ValueError) as e:
        return api._err(str(e))
    if not os.environ.get("BIMRENDER_LLM_URL"):
        return {"status": "manual", "bundle": "", "next": "Kein Sprachmodell verbunden."}
    spec = proj.spec()
    refs = sorted(proj.dir.glob("reference_*"))
    keys = [(v["id"], s) for v in spec["volumes"] if (v.get("facade_detail") or {}).get("timber_frame")
            for s in (sides or ("S", "E", "W", "N"))]
    if not keys:
        return api._err("Kein Volumen mit facade_detail.timber_frame: kein Fachwerk zum Ausarbeiten")
    ref_parts = []
    for i, r in enumerate(refs, 1):
        ref_parts += [{"type": "text", "text": f"Referenzbild {i}:"}, _png_image(r)]

    def first(key):
        vid, side = key
        ctx = facade_context(spec, vid, side)
        content = [{"type": "text", "text": f"Fassade {side} von Volumen {vid}. Kontext:\n```json\n{json.dumps(ctx, ensure_ascii=False)}\n```"}] + ref_parts
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
        return _ask(msgs, _checker(spec, vid, side))

    notes, failed = [], []
    cur = spec
    with ThreadPoolExecutor(max_workers=int(os.environ.get("BIMRENDER_DETAIL_PARALLEL", "4"))) as ex:
        results = list(ex.map(first, keys))
    for key, (data, probs) in zip(keys, results):
        if data is None:
            failed.append(f"{key[1]}: {'; '.join(probs[:3])}")
            continue
        cur = _with_fe(cur, key[0], key[1], data["items"])
        notes.append(f"{key[1]}: {data.get('hinweis', '')}")
    if len(failed) == len(keys):
        return {"status": "invalid", "problems": failed}
    cams = cur.setdefault("render", {}).setdefault("cameras", [])
    for vid, side in keys:
        cam = elevation_camera(cur, vid, side)
        cams[:] = [c for c in cams if c["name"] != cam["name"]] + [cam]
    v = proj.save(cur, "Fassadendetails (KI) Entwurf")
    for _ in range(max(0, rounds - 1)):
        spec = copy.deepcopy(cur)
        imgs = {}
        for vid, side in keys:
            if not any(f["volume"] == vid and f["side"] == side for f in spec.get("facade_elements", [])):
                continue
            r = api.render(target, "sketch", f"elev_{vid}_{side}")
            if r.get("status") == "ok":
                imgs[(vid, side)] = r["image"]

        def second(key):
            vid, side = key
            fe = next(f for f in spec["facade_elements"] if f["volume"] == vid and f["side"] == side)
            ctx = facade_context(spec, vid, side)
            content = [{"type": "text", "text": f"Fassade {side} von Volumen {vid}. Kontext:\n```json\n{json.dumps(ctx, ensure_ascii=False)}\n```\n\n"
                                                f"Dein bisheriger Entwurf:\n```json\n{json.dumps(fe['items'])}\n```\n\n{CRITIQUE}"}] + ref_parts + \
                      [{"type": "text", "text": f"Aktuelle flache Ansicht Fassade {side} (Modell):"}, _png_image(imgs[key])]
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
            return _ask(msgs, _checker(spec, vid, side))
        todo = list(imgs)
        with ThreadPoolExecutor(max_workers=int(os.environ.get("BIMRENDER_DETAIL_PARALLEL", "4"))) as ex:
            res2 = list(ex.map(second, todo))
        changed = False
        for key, (data, probs) in zip(todo, res2):
            if data is None:
                continue
            cur = _with_fe(cur, key[0], key[1], data["items"])
            notes.append(f"{key[1]} (korrigiert): {data.get('hinweis', '')}")
            changed = True
        if changed:
            v = proj.save(cur, "Fassadendetails (KI) korrigiert")
    return {"status": "ok", "project": proj.name, "version": v, "summary": "Fassadendetails aus dem Referenzbild",
            "hinweis": "\n".join(notes + ([f"Nicht übernommen: {f}" for f in failed] if failed else [])),
            "applied": True}
