"""Richtwert-Rahmen (reference frame) for plots without a verified Bebauungsplan.

Binding values (verified B-Plan, the user's own limits) always win. Where they are missing, the building frame of the surroundings is used as a
*reference* for design and checking: storeys, height and typical distance to the plot boundary of the neighbouring buildings (ALKIS) plus the zone
attributes of the Bodenrichtwert (storeys, GFZ/GRZ if the Gutachterausschuss states them). It is NOT law: exceeding it is reported as
"vermutlich Genehmigung/Befreiung nötig", never as a violation, and an explicit wish of the user goes before it."""
from __future__ import annotations

import statistics
from typing import Any

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
STOREY_HEIGHT_M = 2.9           # same estimate as the site pack (floors * 2.9 + 1.5)
ROOF_ALLOWANCE_M = 1.5
RADIUS_M = 60.0
SETBACK_BAND_M = (0.5, 8.0)     # buildings nearer than 0.5 m are boundary buildings (Grenzbebauung), farther than 8 m do not describe a setback


def parse_zone_storeys(text: str | None) -> tuple[int | None, int | None]:
    """'II' -> (2, 2); 'II-III' -> (2, 3); '3' -> (3, 3)."""
    nums = []
    for part in str(text or "").replace("–", "-").replace("/", "-").split("-"):
        part = part.strip().upper()
        if part in ROMAN:
            nums.append(ROMAN[part])
        elif part.isdigit():
            nums.append(int(part))
    return (min(nums), max(nums)) if nums else (None, None)


def build(ctx, land_value: dict | None = None) -> dict | None:
    """Return the reference frame (dict, JSON-able) or None if nothing could be derived. Pure function of the loaded site data."""
    near = [e for e in ctx.neighbours if e.poly.distance(ctx.site) < RADIUS_M]
    frame: dict[str, Any] = {"binding": False, "basis": "CONTEXT_REFERENCE", "radius_m": RADIUS_M, "neighbours": len(near), "sources": []}

    floors = sorted(e.floors for e in near if e.floors)
    heights = sorted(e.height_m for e in near if e.height_m)
    zone_lo, zone_hi = parse_zone_storeys((land_value or {}).get("geschosszahl"))
    cand = [x for x in (floors[-1] if floors else None, zone_hi) if x]
    if cand:
        frame["max_storeys"] = max(cand)
        if floors:
            frame["sources"].append(f"{len(floors)} Nachbargebäude mit Geschosszahl (ALKIS): {floors[0]}–{floors[-1]}, Median {statistics.median(floors):g}")
            frame["floors_median"] = statistics.median(floors)
        if zone_hi:
            frame["sources"].append(f"Bodenrichtwertzone (Gutachterausschuss): Geschosszahl {(land_value or {}).get('geschosszahl')}")
        if heights:
            frame["max_height_m"] = round(heights[-1], 1)
            n_meas = sum(1 for e in near if getattr(e, "height_basis", None) == "LOD2_MEASURED")
            frame["height_basis"] = "LOD2_MEASURED" if n_meas else "ESTIMATE_FROM_FLOORS"
            if n_meas:
                frame["sources"].append(f"{n_meas} Nachbargebäude mit gemessener Höhe (LoD2 Hessen): max. {heights[-1]:.1f} m")
        else:
            frame["max_height_m"] = round(max(cand) * STOREY_HEIGHT_M + ROOF_ALLOWANCE_M, 1)
            frame["height_basis"] = "ESTIMATE_FROM_FLOORS"

    d = sorted(e.poly.distance(ctx.site) for e in near)
    band = [x for x in d if SETBACK_BAND_M[0] <= x <= SETBACK_BAND_M[1]]
    if len(band) >= 3:
        q1 = statistics.quantiles(band, n=4)[0]        # lower quartile: what the neighbours manage, not their generous cases
        frame["setback_m"] = round(q1, 1)
        frame["sources"].append(f"üblicher Grenzabstand der {len(band)} nächsten Nachbargebäude: {frame['setback_m']} m (unteres Quartil, Bereich {band[0]:.1f}–{band[-1]:.1f} m)")

    zone_grz, zone_gfz = (land_value or {}).get("grz_zone"), (land_value or {}).get("gfz_zone")
    if zone_grz:
        frame["grz"] = zone_grz
        frame["sources"].append(f"Bodenrichtwertzone: GRZ {zone_grz}")
    if zone_gfz:
        frame["gfz"] = zone_gfz
        frame["sources"].append(f"Bodenrichtwertzone: GFZ {zone_gfz}")

    if not any(k in frame for k in ("max_storeys", "setback_m", "grz", "gfz")):
        return None
    frame["note_de"] = ("Richtwert aus der Umgebung (§ 34 BauGB: Einfügen), keine Festsetzung. Überschreitungen bedeuten: vermutlich Genehmigung bzw. Befreiung nötig; "
                        "verbindlich ist nur ein Bebauungsplan oder die Entscheidung der Bauaufsicht.")
    return frame


def effective(ctx) -> dict:
    """What the design should respect: binding values first, then the reference frame. Each entry says where it comes from."""
    ref = getattr(ctx, "reference", None) or {}
    v = ctx.verified
    out: dict[str, Any] = {}
    pairs = (("max_storeys", "max_stories", "max_storeys"), ("max_height_m", "max_building_height_meters", "max_height_m"),
             ("setback_m", "setback_lines_offset_meters", "setback_m"), ("grz", "grz", "grz"), ("gfz", "gfz", "gfz"))
    for key, vfield, rfield in pairs:
        bound = getattr(v, vfield, None) if v else None
        if bound not in (None, [], 0):
            out[key] = {"value": bound, "binding": True, "basis": (ctx.src or {}).get(vfield) or "BINDING"}
        elif ref.get(rfield) is not None:
            out[key] = {"value": ref[rfield], "binding": False, "basis": "CONTEXT_REFERENCE"}
    roofs = [x for x in (getattr(v, "roof_types_allowed", None) or []) if x != "egal"] if v else []
    if roofs:
        out["roof_types"] = {"value": roofs, "binding": True, "basis": (ctx.src or {}).get("roof_types_allowed") or "BINDING"}
    for key, f in (("max_eave_height_m", "max_eave_height_meters"), ("roof_pitch_min_deg", "roof_pitch_min_deg"), ("roof_pitch_max_deg", "roof_pitch_max_deg")):
        bound = getattr(v, f, None) if v else None
        if bound not in (None, [], 0):
            out[key] = {"value": bound, "binding": True, "basis": (ctx.src or {}).get(f) or "BINDING"}
    return out
