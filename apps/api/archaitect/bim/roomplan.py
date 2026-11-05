"""Automatic room layout for one level with the interpreter (LLM).

Two modes:
  divide - the model proposes rooms (rectangles + function) for the whole level from the usable floor area,
           the facade openings (windows/doors per side) and the rooms of the other levels.
  assign - rectangles drawn by hand already exist; the model only picks name and function.
Everything the model returns is checked geometrically; invalid answers go back to it (repair rounds).
"""
from __future__ import annotations

import copy
import json
import os

from shapely.geometry import box
from shapely.ops import unary_union

from . import rooms as R

SYSTEM = """Du bist Entwurfsarchitekt für Wohngebäude im deutschsprachigen Raum und teilst ein Geschoss in Räume auf.
Antworte ausschließlich mit einem JSON-Objekt, ohne Text davor oder danach.

Koordinaten: Meter, x = Ost, y = Nord. Süd liegt bei kleinem y, Nord bei großem y. Rechtecke sind [x0, y0, x1, y1] mit x0<x1, y0<y1.
Du bekommst die nutzbaren Innenflächen des Geschosses (Rechtecke, innen an den Außenwänden), die Fassadenöffnungen je Seite
(Fenster, Glaswände, Außentüren mit Lage entlang der Seite und Höhe) und die Räume der anderen Geschosse.

Planungsregeln (Entwurfsstand, Faustregeln, keine Prüfung nach Bauordnung):
1. Teile jede Innenfläche vollständig auf. Flure, Dielen und Treppenhaus zählen als Räume. Rechtecke dürfen sich nicht überlappen und nicht über die Innenfläche hinausragen. Kanten benachbarter Räume liegen exakt aufeinander.
2. Die Innenfläche mit kind "tower" ist das Treppenhaus: genau ein Raum, function "treppe", Rechteck = die gegebene Fläche.
3. Jeder Aufenthaltsraum (wohnen, essen, kueche, schlafen, kind, arbeiten, atelier) braucht eine Außenwand mit Fenster. Die Fensteröffnungen sollen mindestens 1/8 der Raumfläche ergeben (HBO § 50). Räume, die an keiner Fassade mit Öffnung liegen, sind Flur, Bad, WC, Technik, Abstell oder Ankleide.
4. Nutze die vorhandenen Öffnungen: große Verglasungen zur Gartenseite für Wohnen, Essen, Küche und das Hauptschlafzimmer (Panoramafenster). Schlafräume eher zur ruhigeren Seite, Wohnräume zur Gartenseite. Die Gartenseite erkennst du an der größten Verglasung.
5. Erdgeschoss: Eingang (Außentür) führt in eine Diele (flur) mit Zugang zur Treppe, Gäste-WC in der Nähe der Diele, Küche neben dem Essbereich, Wohnen und Essen offen zueinander, Hauswirtschaft oder Technik innen liegend.
6. Obergeschosse: Schlafräume und Kinderzimmer an einem Flur, Bäder an den Installationsschacht: Bäder und WCs liegen möglichst übereinander und an einer gemeinsamen Wand. Hauptschlafzimmer mit Ankleide oder Bad direkt daneben.
7. Jeder Raum grenzt an einen Flur, das Treppenhaus oder einen anderen Raum, keine gefangenen Räume. Flure und Dielen mindestens 1,4 m breit (besser 1,5 m), damit eine 0,9 m Tür aufschwingen kann und zwei Personen aneinander vorbeikommen. Bäder mindestens 1,6 m breit, andere Räume mindestens 2,0 m. Kein Raum ist länger als dreimal so lang wie breit. Jeder Raum teilt mit seinem Flur, dem Treppenhaus oder einem Nachbarraum eine gemeinsame Kante von mindestens 1,2 m, damit dort eine Tür sitzen kann (Türen und Wände werden aus deinen Räumen automatisch erzeugt).
8. Richtwerte Fläche: Wohnen 25-50 m², Essen 12-25, Küche 8-18, Schlafen 12-25, Kind 10-16, Arbeiten 9-16, Bad 6-12, WC 2-3, Ankleide 4-10, Hauswirtschaft 5-10, Flur nur so groß wie nötig. Harte Obergrenzen: Wohnen 70 m², Essen 32, Küche 24, Schlafen 30, Kind 20, Arbeiten 24, Atelier 40, Bad 16, WC 5, Ankleide 14, Hauswirtschaft 16, Technik 14, Abstell 8, Flur 25. Große Baukörper teilst du in mehrere Räume auf (z. B. mehrere Schlafzimmer, Bäder, Ankleide, Arbeitszimmer) statt einen riesigen Raum zu machen. Möbelbare Räume sollen so geschnitten sein, dass ein Bett oder Sofa an einer Wand stehen kann, ohne die Tür zu blockieren.
9. Beachte die Wünsche des Nutzers ("Wunsch"). Widerspricht ein Wunsch der Geometrie, setze ihn so gut wie möglich um und nenne die Abweichung in "hinweis".
10. Wenn dir für eine sinnvolle Aufteilung etwas Entscheidendes fehlt (z. B. Anzahl Schlafzimmer bei großer Fläche), triff eine plausible Annahme und nenne sie in "hinweis". Stelle keine Rückfragen.

functions: """ + ", ".join(R.FUNCTIONS) + """

Antwortformat (divide): {"rooms": [{"name": "Wohnen", "function": "wohnen", "rect": [x0, y0, x1, y1]}, ...], "hinweis": "kurze Begründung der Aufteilung, 2-4 Sätze"}
Antwortformat (assign): {"assign": [{"id": "r001", "name": "Schlafen 1", "function": "schlafen"}, ...], "hinweis": "..."}
"""


def _features(spec: dict, level: str) -> list[dict]:
    """Per usable floor rectangle: openings per side with their range along that side."""
    out = []
    segs = R._segments(spec, level)
    for fp in R.footprints(spec, level):
        r = fp["rect"]
        items = []
        for s in segs:
            share = R._seg_on_room(s, r)
            if share <= 0.05:
                continue
            (x0, y0), (x1, y1) = s["p"]
            horiz = abs(y0 - y1) < 1e-6
            a, b = (min(x0, x1), max(x0, x1)) if horiz else (min(y0, y1), max(y0, y1))
            lo, hi = (max(a, r[0]), min(b, r[2])) if horiz else (max(a, r[1]), min(b, r[3]))
            items.append({"side": s["side"], "von": round(lo, 2), "bis": round(hi, 2), "hoehe": round(s["height"], 2),
                          "art": {"window": "Fenster", "door": "Außentür"}[s["kind"]] if s["src"] == "Öffnung" else "Glaswand"})
        out.append({"id": fp["id"], "name": fp["name"], "kind": fp["kind"], "rect": r, "oeffnungen": items})
    return out


def context(spec: dict, level: str) -> dict:
    others = [{"level": r["level"], "name": r["name"], "function": r["function"], "rect": r["rect"]}
              for r in spec.get("rooms", []) if r["level"] != level]
    return {"geschoss": level, "hoehe": round(R.level_height(spec, level), 2),
            "geschosse": [l["name"] for l in R.levels(spec)],
            "innenflaechen": _features(spec, level), "raeume_andere_geschosse": others,
            "projekt": spec.get("name", ""), "beschreibung": spec.get("description", "")}


def validate_divide(spec: dict, level: str, rooms: list) -> tuple[list[dict], list[str]]:
    problems, clean = [], []
    fps = R.footprints(spec, level)
    if not isinstance(rooms, list) or not rooms:
        return [], ["rooms fehlt oder ist leer"]
    for i, r in enumerate(rooms):
        try:
            fn = r["function"]
            rect = R.snap_rect(r["rect"])
            name = str(r.get("name") or R.FUNCTIONS[fn][0])
        except (KeyError, TypeError, ValueError):
            problems.append(f"Raum {i + 1}: name/function/rect unvollständig")
            continue
        if fn not in R.FUNCTIONS:
            problems.append(f"{name}: function '{fn}' unbekannt (erlaubt: {', '.join(R.FUNCTIONS)})")
            continue
        w, d = rect[2] - rect[0], rect[3] - rect[1]
        if min(w, d) < 0.9:
            problems.append(f"{name}: Rechteck zu schmal ({w:.2f} x {d:.2f} m)")
        elif fn == "flur" and min(w, d) < R.MIN_CORRIDOR - 0.02:
            problems.append(f"{name}: Flur nur {min(w, d):.2f} m breit, mindestens {R.MIN_CORRIDOR} m nötig (Türen müssen aufschwingen)")
        elif fn == "bad" and min(w, d) < R.MIN_BATH - 0.02:
            problems.append(f"{name}: Bad nur {min(w, d):.2f} m breit, mindestens {R.MIN_BATH} m")
        elif fn not in ("flur", "bad", "wc", "treppe", "ankleide", "abstell", "technik", "hwr") and min(w, d) < R.MIN_ROOM - 0.02:
            problems.append(f"{name}: nur {min(w, d):.2f} m breit, mindestens {R.MIN_ROOM} m")
        if fn in R.MAX_AREA and w * d > R.MAX_AREA[fn] + 0.5:
            problems.append(f"{name}: {w * d:.0f} m² sind zu groß für {fn} (höchstens {R.MAX_AREA[fn]} m²), teile den Bereich in mehrere Räume")
        if fn in R.MIN_AREA and w * d < R.MIN_AREA[fn] - 0.3:
            problems.append(f"{name}: {w * d:.1f} m² sind zu klein für {fn} (mindestens {R.MIN_AREA[fn]} m²)")
        if fn not in ("flur", "treppe") and max(w, d) > 3.5 * min(w, d):
            problems.append(f"{name}: Seitenverhältnis {max(w, d) / min(w, d):.1f}:1 ist zu gestreckt (höchstens 3,5:1)")
        if not any(box(*rect).within(box(*f["rect"]).buffer(0.06)) for f in fps):
            problems.append(f"{name}: liegt nicht vollständig in einer Innenfläche")
        clean.append({"name": name, "function": fn, "rect": rect})
    for i, a in enumerate(clean):
        for b in clean[i + 1:]:
            ov = box(*a["rect"]).intersection(box(*b["rect"])).area
            if ov > 0.05:
                problems.append(f"{a['name']} und {b['name']} überlappen um {ov:.2f} m²")
    def _fp(c):  # index of the usable floor rectangle a room lies in
        cx, cy = (c["rect"][0] + c["rect"][2]) / 2, (c["rect"][1] + c["rect"][3]) / 2
        return next((k for k, f in enumerate(fps) if f["rect"][0] - 0.06 <= cx <= f["rect"][2] + 0.06
                     and f["rect"][1] - 0.06 <= cy <= f["rect"][3] + 0.06), None)
    for a in clean:  # every room sharing a floor rectangle with others needs a place for a door
        peers = [b for b in clean if b is not a and _fp(b) == _fp(a)]
        if not peers:
            continue
        need = 0.9 + 0.3
        if not any((e := R.shared_edge(a["rect"], b["rect"])) and e[3] - e[2] >= need for b in peers):
            problems.append(f"{a['name']}: grenzt an keinen anderen Raum mit einer Kante von mindestens {need:.1f} m (Tür unmöglich)")
    for f in fps:
        fb = box(*f["rect"])
        covered = unary_union([box(*c["rect"]) for c in clean]).intersection(fb).area if clean else 0.0
        if covered < 0.9 * fb.area:
            problems.append(f"Innenfläche {f['name']} {f['rect']} nur zu {100 * covered / fb.area:.0f} % aufgeteilt "
                            f"(mindestens 90 % nötig, Flure mitzählen)")
        if f["kind"] == "tower" and not any(c["function"] == "treppe" and box(*c["rect"]).intersection(fb).area > 0.5 * fb.area
                                             for c in clean):
            problems.append("Treppenhaus fehlt: function 'treppe' mit der Fläche des Glasturms")
    return clean, problems


def _ask(messages: list, check, repair_rounds: int):
    """LLM call + JSON parse + domain check, with repair rounds. check(data) -> (result, problems)."""
    from .interpret import _llm
    problems: list[str] = []
    for _ in range(repair_rounds + 1):
        raw = _llm(messages)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Kein gültiges JSON ({e}). Nur das JSON-Objekt senden."}]
            continue
        result, problems = check(data)
        if not problems:
            return result, data, []
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Bitte korrigieren:\n- " + "\n- ".join(problems)}]
    return None, None, problems


def auto_rooms(project, level: str, brief: str = "", mode: str = "divide", repair_rounds: int = 2) -> dict:
    """Propose rooms for one level and save them as a new project version."""
    from .interpret import validate_spec
    spec = project.spec()
    try:
        R.level_elev(spec, level)
    except KeyError:
        return {"status": "error", "message": f"Geschoss '{level}' gibt es nicht ({', '.join(l['name'] for l in R.levels(spec))})"}
    if not R.footprints(spec, level):
        return {"status": "error", "message": f"Auf Geschoss {level} gibt es keine Innenfläche"}
    if mode == "assign" and not [r for r in spec.get("rooms", []) if r["level"] == level]:
        return {"status": "error", "message": "Keine gezeichneten Räume auf diesem Geschoss"}
    if not os.environ.get("BIMRENDER_LLM_URL"):
        return {"status": "manual", "bundle": "", "next": "Kein Sprachmodell verbunden (BIMRENDER_LLM_URL setzen)."}
    ctx = context(spec, level)
    if mode == "assign":
        ctx["gezeichnete_raeume"] = [{"id": r["id"], "rect": r["rect"], "name": r["name"], "function": r["function"]}
                                     for r in R.analyze(spec) if r["level"] == level]
        for r in ctx["gezeichnete_raeume"]:
            a = next(x for x in R.analyze(spec) if x["id"] == r["id"])
            r["fenster"] = [f"{w['side']} {w['width']} m breit, {w['height']} m hoch" for w in a["windows"]]
            r["treppe"] = a["stair"]
    user = f"Modus: {mode}\nWunsch: {brief or '(keiner, nimm eine sinnvolle Standardaufteilung)'}\n\n```json\n" + \
           json.dumps(ctx, ensure_ascii=False, indent=1) + "\n```"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    ids = {r["id"] for r in spec.get("rooms", []) if r["level"] == level}

    def check_divide(d):
        return validate_divide(spec, level, d.get("rooms"))

    def check_assign(d):
        items, probs = [], []
        for a in d.get("assign", []):
            if a.get("id") not in ids:
                probs.append(f"unbekannte Raum-ID {a.get('id')}")
            elif a.get("function") not in R.FUNCTIONS:
                probs.append(f"{a.get('id')}: function '{a.get('function')}' unbekannt")
            else:
                items.append(a)
        if {a["id"] for a in items} != ids and not probs:
            probs.append("Nicht alle gezeichneten Räume zugewiesen: fehlend " + ", ".join(sorted(ids - {a['id'] for a in items})))
        return items, probs

    result, data, problems = _ask(messages, check_divide if mode == "divide" else check_assign, repair_rounds)
    if result is None:
        return {"status": "invalid", "problems": problems}
    new = copy.deepcopy(spec)
    if mode == "divide":
        keep = [r for r in new.get("rooms", []) if r["level"] != level]
        new["rooms"] = keep
        for c in result:
            new["rooms"].append({"id": R.next_id(new), "name": c["name"], "function": c["function"], "level": level, "rect": c["rect"]})
    else:
        by_id = {a["id"]: a for a in result}
        for r in new["rooms"]:
            if r["id"] in by_id:
                r["function"] = by_id[r["id"]]["function"]
                r["name"] = by_id[r["id"]].get("name") or R.FUNCTIONS[r["function"]][0]
    probs = validate_spec(new)
    if probs:
        return {"status": "invalid", "problems": probs}
    note = f"KI-Raumaufteilung {level}" + (f": {brief}" if brief else "")
    v = project.save(new, note[:140])
    return {"status": "ok", "version": v, "summary": note, "hinweis": data.get("hinweis", ""),
            "rooms": len([r for r in new["rooms"] if r["level"] == level])}
