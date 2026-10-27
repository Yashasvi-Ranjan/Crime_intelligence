#!/usr/bin/env sh
# Secret scan over tracked files (and, with --image NAME, over the files inside a built image).
# Fails (exit 1) on: NVIDIA/OpenAI-style keys, private key blocks, bearer tokens, tracked .env/.pem/.key files.
set -u
cd "$(dirname "$0")/.."
fail=0
PATTERN='nvapi-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN ([A-Z]+ )?PRIVATE KEY-----|Bearer [A-Za-z0-9._-]{30,}'

echo "== tracked files: key patterns"
if git grep -nIE "$PATTERN" -- . ; then echo "FOUND secret-like content"; fail=1; else echo "none"; fi

echo "== tracked .env / .pem / .key files"
bad=$(git ls-files | grep -E '(^|/)\.env(\.|$)|\.pem$|\.key$' | grep -v '\.env\.example$' || true)
if [ -n "$bad" ]; then echo "$bad"; fail=1; else echo "none"; fi

echo "== proprietary engine copy not tracked"
if git ls-files | grep -E '(^|/)worldmodel\.js$'; then fail=1; else echo "none"; fi

if [ "${1:-}" = "--image" ]; then
  echo "== image $2: filesystem scan"
  if docker run --rm --entrypoint sh "$2" -c "grep -rIEl '$PATTERN' /app 2>/dev/null; ls /app/.env /app/backend/.env 2>/dev/null; find / -name worldmodel.js -not -path '/proc/*' 2>/dev/null" | grep . ; then
    echo "FOUND in image"; fail=1; else echo "none"; fi
  echo "== image $2: history/env"
  if docker history --no-trunc "$2" | grep -E "$PATTERN"; then fail=1; else echo "none"; fi
fi
[ "$fail" -eq 0 ] && echo "SECRET SCAN: PASS" || echo "SECRET SCAN: FAIL"
exit "$fail"
