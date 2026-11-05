# Setup

## One command

```sh
python scripts/setup.py     # creates apps/api/.venv, installs backend + frontend dependencies, copies .env.example to .env.local
python scripts/dev.py       # starts backend (http://127.0.0.1:8000) and frontend (http://127.0.0.1:3000)
```

Manual equivalent:

```sh
cd apps/api && python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.lock.txt && .venv/bin/python -m pip install --no-deps -e .
cd ../web && npm ci
```

On Windows use `.venv\Scripts\python.exe`.

## Configuration (`.env.local`, never committed)

| Variable | Purpose |
|---|---|
| `META_API_KEY` | Meta Model API key (default model `muse-spark-1.3`, override with `ARCHAITECT_META_MODEL`) |
| `BIMRENDER_LLM_URL`, `BIMRENDER_LLM_KEY`, `BIMRENDER_LLM_MODEL` | any OpenAI-compatible endpoint |
| `ARCHAITECT_OLLAMA_MODEL`, `ARCHAITECT_OLLAMA_VISION`, `OLLAMA_HOST` | local Ollama (defaults `qwen3:8b`, photo references `qwen2.5vl:7b`) |
| `ARCHAITECT_BIM_LLM` | force a provider: `ollama` or `meta` |
| `ARCHAITECT_DB_PATH` | SQLite store (default `.local/archaitect.sqlite3`) |
| `BLENDER` | path to the Blender executable (photo renders only) |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEFAULT_LANG` | frontend: API address, initial language `en` or `de` (put into `apps/web/.env.local`) |

Provider priority for the language model: custom endpoint, then Meta key, then local Ollama. Keys are read only by the backend process and are never sent to the browser.

## What works without a model

Parcel and geodata lookup, building-law pre-check, planning-document research, geometry and rule checks, the house library, drag-and-drop placement, IFC export, floor plans, JSON/ZIP exports and undo. A model is needed only for "house from text", edits by text and translating dynamic strings into English.

## Rendering (optional)

Install Blender 5.x and set `BLENDER`. Render jobs run one at a time per project. Without Blender the 360-degree view, plans and IFC export still work.

## Planning-document OCR (optional, macOS)

`scripts/planning-ocr.swift` provides local OCR. Without it, planning PDFs are downloaded and searched for embedded text only.

## Tests

```sh
cd apps/api && .venv/bin/python -m pytest -q
cd apps/web && npm run typecheck && npm run build
```
