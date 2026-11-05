"""Bilderwelt: four photo-real 4K images per project from the dimensionally exact 3D model.

Pipeline per shot: Blender renders the exact scene from an automatically chosen camera (with a fog bank along the parcel boundary), Meta's image
model (muse-image-1.0 via /v1/images/edits) turns that render into a photograph without changing the geometry, and the result is upscaled to
3840x2160 (the model itself returns at most ~2048 px). The shots are chosen so the important things are seen: main view with all buildings and the
surroundings, two close-ups from different angles, one aerial plan view."""
from __future__ import annotations

import base64
import getpass
import io
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
import uuid

META_IMG_URL = "https://api.meta.ai/v1/images/edits"
IMG_MODEL = "muse-image-1.0"
TARGET = (3840, 2160)

SHOTS = [
    ("main", "Hauptansicht", "Frontale Gesamtansicht: alle Gebäude und die Umgebung"),
    ("close1", "Close-up 1", "Nahaufnahme des Hauses von schräg links"),
    ("close2", "Close-up 2", "Nahaufnahme aus anderem Winkel (See und Hütte, sonst Haus von rechts)"),
    ("aerial", "Lageansicht", "Ansicht von oben auf das ganze Grundstück"),
]


def _rects(spec: dict) -> list[tuple[float, float, float, float, float]]:
    """(x0, y0, x1, y1, height) of every building volume."""
    out = []
    for v in spec.get("volumes", []):
        ox, oy = v["origin"]
        W, D = v["size"]
        h = float(v.get("base_z", 0.0)) + int(v.get("storeys", 1)) * float(v.get("storey_height", spec.get("storey_height", 3.0)))
        out.append((ox, oy, ox + W, oy + D, h))
    return out


def shots(spec: dict, terrain: dict | None) -> list[dict]:
    """Cameras (spec frame, metres) for the four shots."""
    rs = _rects(spec)
    comps = spec.get("components", [])
    pts = [(r[0], r[1]) for r in rs] + [(r[2], r[3]) for r in rs]
    huts = [c for c in comps if c.get("type") == "sauna_hut" and c.get("x") is not None]
    for c in huts:
        pts += [(c["x"], c["y"]), (c["x"] + float(c.get("width", 3.8)) + 1.5, c["y"] + float(c.get("depth", 3.0)) + 1.5)]
    lakes = (terrain or {}).get("lakes") or []
    for lk in lakes:
        pts += [tuple(p) for p in lk["ring"]]
    ring = (terrain or {}).get("parcel_ring") or []
    if not pts:
        pts = [(-10.0, -10.0), (10.0, 10.0)]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    span = max(x1 - x0, y1 - y0, 20.0)
    big = max(rs, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])) if rs else (cx - 5, cy - 5, cx + 5, cy + 5, 8.0)
    hx, hy = (big[0] + big[2]) / 2, (big[1] + big[3]) / 2
    hs, hh = max(big[2] - big[0], big[3] - big[1]), big[4]
    out = [{"name": "photo_main", "position": [round(cx, 2), round(y0 - (0.95 * span + 8.0), 2), round(max(6.5, 0.12 * span + 3.5), 2)],
            "target": [round(cx, 2), round(cy, 2), round(min(5.0, hh * 0.4), 2)], "lens_mm": 24, "two_point": False}]
    ux, uy = -0.55, -1.0
    n = math.hypot(ux, uy)
    out.append({"name": "photo_close1", "position": [round(hx + ux / n * (1.7 * hs + 4.0), 2), round(hy + uy / n * (1.7 * hs + 4.0), 2), 1.7],
                "target": [round(hx, 2), round(hy, 2), round(hh * 0.42, 2)], "lens_mm": 30})
    if huts or lakes:
        if huts:
            sx = huts[0]["x"] + float(huts[0].get("width", 3.8)) / 2
            sy = huts[0]["y"] + float(huts[0].get("depth", 3.0)) / 2
        else:
            ring0 = lakes[0]["ring"]
            sx, sy = sum(p[0] for p in ring0) / len(ring0), sum(p[1] for p in ring0) / len(ring0)
        if lakes:
            ring0 = lakes[0]["ring"]
            lx, ly = sum(p[0] for p in ring0) / len(ring0), sum(p[1] for p in ring0) / len(ring0)
        else:
            lx, ly = sx, sy - 6.0
        dx, dy = hx - sx, hy - sy
        ln = math.hypot(dx, dy) or 1.0
        px, py = sx + dx / ln * 12.0 + (-dy / ln) * 4.0, sy + dy / ln * 12.0 + (dx / ln) * 4.0
        out.append({"name": "photo_close2", "position": [round(px, 2), round(py, 2), 2.4], "target": [round((sx + lx) / 2, 2), round((sy + ly) / 2, 2), 0.8], "lens_mm": 26})
    else:
        ux, uy = 0.9, -0.8
        n = math.hypot(ux, uy)
        out.append({"name": "photo_close2", "position": [round(hx + ux / n * (1.6 * hs + 4.0), 2), round(hy + uy / n * (1.6 * hs + 4.0), 2), 2.0],
                    "target": [round(hx, 2), round(hy, 2), round(hh * 0.5, 2)], "lens_mm": 35})
    if len(ring) >= 3:
        px0, px1 = min(p[0] for p in ring), max(p[0] for p in ring)
        py0, py1 = min(p[1] for p in ring), max(p[1] for p in ring)
        ax, ay, asp = (px0 + px1) / 2, (py0 + py1) / 2, max(px1 - px0, py1 - py0)
    else:
        ax, ay, asp = cx, cy, span
    out.append({"name": "photo_aerial", "position": [round(ax, 2), round(ay - 0.12 * asp, 2), round(0.95 * asp + 22.0, 2)],
                "target": [round(ax, 2), round(ay, 2), 0.0], "lens_mm": 28, "two_point": False})
    if len(ring) >= 3:         # cameras stay inside the parcel: the fog bank stands on its boundary and must never be between camera and house
        from shapely.geometry import LineString, Point, Polygon
        pg = Polygon(ring).buffer(-2.5)
        if not pg.is_empty and pg.geom_type == "Polygon":
            c = pg.centroid
            for cam in out:
                x, y = cam["position"][0], cam["position"][1]
                if cam["name"] == "photo_aerial" or pg.contains(Point(x, y)):
                    continue
                cut = LineString([(c.x, c.y), (x, y)]).intersection(pg)
                if not cut.is_empty:
                    ex, ey = list(cut.coords)[-1] if cut.geom_type == "LineString" else (c.x, c.y)
                    cam["position"][0], cam["position"][1] = round(ex, 2), round(ey, 2)
                    if cam["name"] == "photo_main":
                        cam["lens_mm"] = 18
    return out


STYLE = ("This is a screenshot of a 3D model. Upscale it to a high-resolution photograph and make the existing materials look photorealistic "
         "(real timber, plaster, tiles, grass, water, foliage, natural daylight, soft shadows). ")
KEEP = ("DO NOT change anything else: same camera position, same framing, same composition, same number and position of every window, door, timber beam, "
        "tree, bush, rock, hut, path, pond and building; same proportions, same colours of the areas; do not add, remove, move or restyle any object and do not invent "
        "new objects. Only increase resolution and realism of what is already visible. The pale mist in the background stays a soft mist. ")


def prompt(shot: str, spec: dict) -> str:
    return STYLE + KEEP


def capture(shot: dict, out_png, base: str | None = None, pid: str = "", timeout: float = 240.0) -> None:
    """Real screenshot of the web viewer (headless Chrome) from the shot's camera (house frame, metres)."""
    import shutil
    import subprocess
    import urllib.parse
    chrome = os.environ.get("ARCHAITECT_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                                                                      shutil.which("google-chrome") or "", shutil.which("chromium") or "") if c and os.path.exists(c)), None)
    if not chrome:
        raise PhotoError("Chrome nicht gefunden (ARCHAITECT_CHROME setzen).")
    base = (base or os.environ.get("ARCHAITECT_WEB_URL") or "http://127.0.0.1:3000").rstrip("/")
    cam = ",".join(str(v) for v in [*shot["position"], *shot["target"], shot["lens_mm"]])
    url = f"{base}/entwurf?" + urllib.parse.urlencode({"p": pid, "cam": cam}, safe=",")
    import tempfile
    with tempfile.TemporaryDirectory() as ud:
        cmd = [chrome, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--hide-scrollbars",
               f"--user-data-dir={ud}", "--window-size=2048,1152", "--virtual-time-budget=40000", f"--screenshot={out_png}", url]
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    from pathlib import Path
    if not Path(out_png).exists() or Path(out_png).stat().st_size < 20000:
        raise PhotoError("Der Viewer-Screenshot ist fehlgeschlagen (läuft die Web-Oberfläche?).")
    from PIL import Image
    im = Image.open(out_png).convert("RGB")
    w, h = im.size
    im.paste((im.getpixel((70, h - 70))), (0, h - 64, 64, h))      # Dev-Badge unten links überdecken
    im.save(out_png)


def api_key() -> str | None:
    k = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")
    if k:
        return k
    r = subprocess.run(["/usr/bin/security", "find-generic-password", "-a", getpass.getuser(), "-s", "archaitect.meta-model-api", "-w"], capture_output=True, text=True)
    return r.stdout.strip() or None


class PhotoError(RuntimeError):
    pass


def meta_edit(image_png: bytes, text: str, size: str = "2048x1152", timeout: float = 280.0) -> tuple[bytes, dict]:
    """Photo-real version of a render. Returns (image bytes as delivered, usage)."""
    key = api_key()
    if not key:
        raise PhotoError("Meta-API-Schlüssel fehlt (./scripts/set-api-key).")
    b = uuid.uuid4().hex

    def part(name, val, fn=None, ct=None):
        h = f'--{b}\r\nContent-Disposition: form-data; name="{name}"' + (f'; filename="{fn}"' if fn else "") + "\r\n" + (f"Content-Type: {ct}\r\n" if ct else "") + "\r\n"
        return h.encode() + (val if isinstance(val, bytes) else val.encode()) + b"\r\n"
    body = part("image", image_png, "view.png", "image/png") + part("prompt", text) + part("model", IMG_MODEL) + part("size", size) + f"--{b}--\r\n".encode()
    req = urllib.request.Request(META_IMG_URL, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + b})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise PhotoError(f"Meta-Bildmodell antwortet {e.code}: {e.read()[:300].decode('utf-8', 'ignore')}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PhotoError(f"Meta-Bildmodell nicht erreichbar: {e}") from e
    d = (j.get("data") or [{}])[0]
    if not d.get("b64_json"):
        raise PhotoError("Meta-Bildmodell lieferte kein Bild.")
    return base64.b64decode(d["b64_json"]), j.get("usage") or {}


def finish(raw: bytes) -> bytes:
    """Upscale to 4K (Lanczos + gentle sharpening) and encode as high-quality JPEG."""
    from PIL import Image, ImageFilter
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if im.size != TARGET:
        im = im.resize(TARGET, Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=94, optimize=True, subsampling=0)
    return out.getvalue()
