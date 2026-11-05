# Third-party notices

ArchAItect itself is MIT-licensed (see `LICENSE`). It uses the following third-party components and data. Nothing from them is modified, and each keeps its own licence.

## Bundled in the repository

| Component | Licence | Location |
|---|---|---|
| three.js | MIT | `apps/web/public/vendor/three/` (licence file included) |
| Leaflet 1.9.4 | BSD-2-Clause | `apps/web/public/vendor/leaflet/` (licence file included) |
| Outline of Hesse (GeoJSON) | derived from official administrative boundaries; see source attribution in the app | `apps/web/public/data/` |
| Test fixtures (WFS/WMS excerpts, small orthophoto) | official Hessian open geodata, see "Data" below | `apps/api/tests/fixtures_siteintel/` |

## Installed via package managers (not bundled)

Python (see `apps/api/requirements.lock.txt`): FastAPI, Starlette, Pydantic, Uvicorn, httpx, NumPy, pyproj, pypdf, jsonschema (MIT / BSD); Shapely (BSD-3-Clause); Pillow (HPND); **IfcOpenShell (LGPL-3.0-or-later)**, used unmodified as a dynamically linked library for IFC output; certifi (MPL-2.0).
JavaScript (see `apps/web/package-lock.json`): Next.js, React, lucide-react, html-to-image (MIT / ISC).
Optional, user-installed: Blender (GPL), Ollama and language models under their own terms.

## Data (fetched at runtime, not redistributed beyond the test fixtures)

- Hessian Verwaltung für Bodenmanagement und Geoinformation (HVBG): ALKIS, buildings, land use, DGM1, orthophotos, BORIS land values. Licence per service, mostly Datenlizenz Deutschland – Zero 2.0 (`DL-DE Zero 2.0`); the licence and attribution of every source are carried in `apps/api/archaitect/siteintel/sources.py` and shown in the app and in exports.
- HLNUG, HMLU, Regionalverband FrankfurtRheinMain, Landesamt für Denkmalpflege Hessen, regional planning bodies: attribution as given in the same file; use is subject to the terms published by each service.
- OpenStreetMap (Nominatim/Overpass): © OpenStreetMap contributors, ODbL. Respect the Nominatim and Overpass usage policies when running the app.
- Municipal development plans retrieved from municipal catalogues remain the property of the municipalities; they are downloaded to the user's local project store only.

## AI models

Language/image models are called only if the operator supplies a key or endpoint (e.g. the Meta Model API). Their terms of use apply to that use; no model weights or outputs are distributed with this repository.

This file is a good-faith summary, not legal advice. Check the current terms of each data service before commercial use.
