# ArchAItect

From a parcel to a building concept: ArchAItect pulls official geodata for a plot in Hesse (Germany), checks building-law constraints, and lets you describe a house in plain text. The result is a rule-checked 3D model on the real parcel with floor plans, an IFC4 export and optional photorealistic renders.

It is a research prototype. Everything that cannot be verified from an official source is labelled as unknown or unverified. **It is not a building-permit assessment.**

## What it does

- **Site intelligence (Hesse):** parcels (ALKIS), buildings, land use, terrain (DGM1), aerial imagery, flood and nature-protection layers, spatial-planning context.
- **Planning research:** finds municipal development plans for the parcel, stores the original PDFs, runs local OCR, and exposes quotable passages. Values are never adopted as binding without an explicit user decision.
- **Legal pre-check:** state-wide review structure (27 topics) with calculation checks and a versioned evidence log.
- **House generation (BIM):** text or photo → building spec (JSON) → IFC4. Includes a library of 36 detailed houses, typologies, an object library (garden, structures), edits by text, versions, undo, and drag-and-drop placement with automatic fit to the buildable area.
- **Outputs:** 360° 3D view, floor plans (SVG/PDF print), IFC, optional Blender/Cycles renders, JSON reports, site pack (ZIP).
- **Languages:** the UI and exports work in English and German.

## Quick start

Requirements: Python 3.11+ and Node.js 20+ (CI uses Python 3.13 / Node 24). Optional: Blender 5.x for photo renders; a language model for text-to-house (see below).

```sh
python scripts/setup.py     # virtualenv, dependencies, npm packages, .env.local
python scripts/dev.py       # backend :8000 and frontend :3000
```

Open http://127.0.0.1:3000. Works on macOS, Linux and Windows. `python scripts/dev.py api` or `web` starts only one side.

**Language model (optional).** Rules, geometry, IFC, floor plans, undo and the 36 library houses work without any model. For "house from text", edits by text and English translation of dynamic strings, put one of these into `.env.local`: `META_API_KEY` (Meta Model API), `BIMRENDER_LLM_URL` (any OpenAI-compatible server) or run a local Ollama. Details in [docs/SETUP.md](docs/SETUP.md).

## Tests

```sh
cd apps/api && .venv/bin/python -m pytest -q
cd apps/web && npm run typecheck && npm run build
```

## Repository layout

| Path | Purpose |
|---|---|
| `apps/api/archaitect/` | FastAPI backend: domain, geometry, rules, store |
| `apps/api/archaitect/siteintel/` | Hesse data services, planning research, legal review, project API |
| `apps/api/archaitect/bim/` | Building spec, IFC builder, house library, floor plans, terrain |
| `apps/api/tests/` | Backend tests |
| `apps/web/app/` | Next.js app (dashboard, parcel selection, house design) |
| `docs/` | Architecture, data sources, planning/legal pipeline, library notes |
| `scripts/` | `setup.py`, `dev.py`, helper scripts |

## Data sources and licences

Geodata comes from the Hessian geodata services (HVBG, HLNUG, HMLU, state and municipal catalogues) and OpenStreetMap-derived services; attribution is shown in the UI and written into exports. See `THIRD_PARTY_NOTICES.md` and `docs/HESSEN_SITE_INTELLIGENCE.md`.

Code: MIT, see `LICENSE`. Third-party components, data licences and the model-use note are listed in `THIRD_PARTY_NOTICES.md`.
