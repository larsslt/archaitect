"""Start the backend and/or frontend for local development (macOS, Linux, Windows).

    python scripts/dev.py          # both
    python scripts/dev.py api      # backend only  -> http://127.0.0.1:8000
    python scripts/dev.py web      # frontend only -> http://127.0.0.1:3000

Settings come from .env.local in the repository root (see .env.example).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API, WEB = ROOT / "apps" / "api", ROOT / "apps" / "web"


def load_env():
    env = os.environ.copy()
    f = ROOT / ".env.local"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:  # empty placeholders from .env.example are ignored
                    env.setdefault(k.strip(), v)
    # the backend reads either name; accept whichever one is set
    key = env.get("META_API_KEY") or env.get("MODEL_API_KEY")
    if key:
        env["META_API_KEY"] = env["MODEL_API_KEY"] = key
    db = Path(env.get("ARCHAITECT_DB_PATH", ".local/archaitect.sqlite3")).expanduser()
    db = db if db.is_absolute() else ROOT / db
    db.parent.mkdir(parents=True, exist_ok=True)
    env["ARCHAITECT_DB_PATH"] = str(db)
    return env


def python_exe():
    venv_py = API / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(venv_py) if venv_py.exists() else sys.executable


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    if what not in ("api", "web", "both"):
        sys.exit(__doc__)
    env = load_env()
    procs = []
    if what in ("api", "both"):
        procs.append(subprocess.Popen([python_exe(), "-m", "uvicorn", "archaitect.main:app", "--host", "127.0.0.1", "--port", env.get("ARCHAITECT_API_PORT", "8000"), "--reload"], cwd=API, env=env))
    if what in ("web", "both"):
        npm = shutil.which("npm")
        if not npm:
            sys.exit("npm not found: install Node.js 20+ first (python scripts/setup.py).")
        wenv = dict(env, NEXT_PUBLIC_API_URL=env.get("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000"), NEXT_TELEMETRY_DISABLED="1")
        wenv.pop("MODEL_API_KEY", None); wenv.pop("META_API_KEY", None)  # keys never reach the browser build
        procs.append(subprocess.Popen([npm, "run", "dev", "--", "--hostname", "127.0.0.1", "--port", env.get("ARCHAITECT_WEB_PORT", "3000")], cwd=WEB, env=wenv))
    print("Backend http://127.0.0.1:8000  ·  Frontend http://127.0.0.1:3000  ·  Ctrl+C stops")
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
