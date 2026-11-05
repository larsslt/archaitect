#!/bin/sh
# Verbesserungsschleife: ein Prüflauf mit Kennzahlen. Schreibt .local/loop/check_<zeit>.txt und gibt die Kurzfassung aus.
# Nutzung: scripts/bim/improve_check.sh [--fast]    (--fast: ohne Frontend-Typecheck)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$ROOT/apps/api/.venv/bin/python"
OUT="$ROOT/.local/loop"; mkdir -p "$OUT"
TS="$(date +%Y%m%d_%H%M%S)"; LOG="$OUT/check_$TS.txt"
export PATH="/usr/local/bin:$PATH"

{
  echo "== pytest"; cd "$ROOT/apps/api" && "$PY" -m pytest -q -p no:cacheprovider 2>&1 | tail -4
  echo "== ruff (siteintel, Dateien dieser Pipeline)"; "$PY" -m ruff check --select F821,F401,F811 archaitect/siteintel archaitect/bim/terrain.py archaitect/bim/meshexport.py 2>&1 | tail -3
  echo "== terrain demo (Darmstadt-DGM1, Sprung ins Hanggelände)"
  for S in "0 0" "25 -20" "-30 30"; do
    D="$OUT/demo_$TS"; mkdir -p "$D"
    "$PY" "$ROOT/scripts/bim/demo_terrain.py" "$D/s_$(echo $S | tr ' -' '_m')" --shift $S 2>&1 | grep -i "cut\|fill\|slope\|warn\|status\|error\|Traceback" | head -6
  done
  if [ "${1:-}" != "--fast" ]; then
    echo "== web typecheck"; cd "$ROOT/apps/web" && npm run typecheck 2>&1 | tail -3
  fi
  echo "== git"; cd "$ROOT" && git status --short | wc -l | tr -d ' ' | sed 's/$/ Änderungen im Arbeitsbaum/'
} > "$LOG" 2>&1
# nur die letzten 3 Läufe behalten (Demo-Ordner sind einige MB groß)
ls -dt "$OUT"/demo_* 2>/dev/null | tail -n +4 | xargs rm -rf 2>/dev/null
ls -t "$OUT"/check_*.txt 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
cat "$LOG"
echo "Log: $LOG"
