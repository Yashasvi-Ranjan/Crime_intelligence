#!/bin/sh
# Run backend + frontend on localhost against live Zetaris and live Nemotron, configured only by <repo>/.env.
# Usage: sh scripts/dev_local.sh      (Ctrl+C stops both)
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

[ -f .env ] || { echo "Missing .env (cp .env.example .env and fill it in)"; exit 1; }

# A stale value exported in the shell would override .env (real env vars win), e.g. an old NIGHTSHIFT_API_KEY -> HTTP 401.
for v in $(env | cut -d= -f1 | grep -E '^(NIGHTSHIFT_|ZETARIS_|SAMPLE_MODE|METERLESS_|WORKFLOW_|HMEM_|STATE_DIR|API_TARGET|OFFLINE_TARGET)'); do
  unset "$v"
done

# Free ports left over from earlier runs.
for p in 8000 5173; do
  pid=$(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | head -1 || true)
  if [ -n "$pid" ]; then
    if ps -p "$pid" -o command= | grep -qiE 'docker|vpnkit'; then
      echo "Note: Docker also listens on port $p (container 'live'); this script binds 127.0.0.1 and the frontend proxies there."
    else
      kill "$pid" 2>/dev/null || true
    fi
  fi
done

(cd backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM

# Wait for the backend, then show whether Nemotron and Zetaris are really live.
i=0
until curl -s -o /dev/null http://127.0.0.1:8000/api/health; do
  i=$((i+1)); [ $i -gt 30 ] && { echo "Backend did not start"; exit 1; }
  sleep 1
done
echo "Nemotron: $(curl -s -m 60 http://127.0.0.1:8000/api/ai/diagnostic | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["status"], d.get("model") or d.get("error_detail"))')"
echo "Zetaris:  $(curl -s -m 30 http://127.0.0.1:8000/api/health/zetaris | head -c 200)"
echo "Open http://localhost:5173"

cd frontend
[ -d node_modules ] || npm install
npm run dev
