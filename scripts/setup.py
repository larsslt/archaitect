"""One-time setup (macOS, Linux, Windows): backend virtualenv + dependencies, frontend packages, .env.local.

    python scripts/setup.py
"""
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API, WEB = ROOT / "apps" / "api", ROOT / "apps" / "web"


def run(cmd, cwd):
    print("+", " ".join(map(str, cmd)))
    subprocess.check_call([str(c) for c in cmd], cwd=cwd)


def main():
    if sys.version_info < (3, 11):
        sys.exit("Python 3.11 or newer is required.")
    env_dir = API / ".venv"
    if not env_dir.exists():
        venv.create(env_dir, with_pip=True)
    py = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    run([py, "-m", "pip", "install", "-r", "requirements.lock.txt"], API)
    run([py, "-m", "pip", "install", "--no-deps", "-e", "."], API)
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Node.js / npm not found. Install Node 20 or newer, then run this script again.")
    run([npm, "ci"], WEB)
    env_file = ROOT / ".env.local"
    if not env_file.exists():
        shutil.copy(ROOT / ".env.example", env_file)
        print("Created .env.local (edit it to add an optional language-model key).")
    print("\nDone. Start everything with:  python scripts/dev.py")


if __name__ == "__main__":
    main()
