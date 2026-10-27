#!/usr/bin/env sh
# Restart the Cloudflare quick tunnel to the live backend and repoint the Vercel site at the new URL.
#
#   sh scripts/restart_tunnel.sh            # restart once, update vercel.json, commit and push it
#   sh scripts/restart_tunnel.sh --watch    # keep checking every 60 s; restart + repoint when the tunnel stops answering
#
# Quick tunnels get a new random URL each time and can expire while the cloudflared process keeps running ("Tunnel not found"),
# so the URL in vercel.json must be refreshed. Needs: cloudflared, python3, git push access, and the backend on localhost:8000.
set -u
cd "$(dirname "$0")/.."
LOG=/tmp/cloudflared.log
PORT="${PORT:-8000}"

start_tunnel() {
  pkill -f "cloudflared tunnel" 2>/dev/null; sleep 1
  nohup cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
  URL=""
  for _ in $(seq 1 30); do
    URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" | head -1)
    [ -n "$URL" ] && break
    sleep 2
  done
  [ -n "$URL" ] || { echo "no tunnel URL after 60 s; see $LOG"; return 1; }
  for _ in $(seq 1 15); do curl -sf -m 8 "$URL/api/health" >/dev/null && break; sleep 2; done
  curl -sf -m 8 "$URL/api/health" >/dev/null || { echo "tunnel $URL does not answer"; return 1; }
  echo "tunnel: $URL"
}

repoint() {
  python3 - "$URL" <<'PY'
import json, sys
u = sys.argv[1]
v = json.load(open("vercel.json"))
for r in v["rewrites"]:
    if r["source"] == "/api/(.*)": r["destination"] = u + "/api/$1"
    elif r["source"] == "/api": r["destination"] = u + "/api"
json.dump(v, open("vercel.json", "w"), indent=2); open("vercel.json", "a").write("\n")
PY
  git add vercel.json && git commit -q -m "chore(vercel): point /api at the restarted tunnel" -- vercel.json && git push -q origin main && echo "pushed; Vercel will redeploy in about a minute"
}

curl -sf -m 5 "http://localhost:$PORT/health" >/dev/null || { echo "backend not answering on localhost:$PORT: start the docker container first"; exit 1; }
start_tunnel && repoint || exit 1

if [ "${1:-}" = "--watch" ]; then
  fails=0
  while sleep 60; do
    if curl -sf -m 10 "$URL/api/health" >/dev/null; then fails=0; else fails=$((fails + 1)); fi
    if [ "$fails" -ge 2 ]; then
      echo "$(date '+%H:%M:%S') tunnel stopped answering; restarting"
      fails=0
      start_tunnel && repoint
    fi
  done
fi
