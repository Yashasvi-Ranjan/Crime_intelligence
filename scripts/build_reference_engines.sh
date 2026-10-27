#!/usr/bin/env sh
# Bundle the vendored Meterless reference engines (third_party/meterless, Apache-2.0) together with our
# adapters into third_party/meterless/build/{hmem,markovian}.cjs. Needs Node 20+ and network access
# (npx fetches the pinned esbuild once). The Dockerfile runs it; on a host run it by hand ONCE before starting the
# backend or running scripts/judge_compare.py. Without it H-MEM and Markovian are traced engine_unavailable and the
# judge comparison fails (it prints this command).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/third_party/meterless/build"
ADAPTERS="$ROOT/backend/app/services/meterless_world/reference"

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "build_reference_engines: Node 20+ (node and npx) is required and was not found on PATH." >&2
  exit 1
fi
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
if [ "$NODE_MAJOR" -lt 20 ]; then
  echo "build_reference_engines: Node 20+ required, found $(node --version)." >&2
  exit 1
fi

mkdir -p "$OUT"
for engine in hmem markovian; do
  npx --yes esbuild@0.24.2 "$ADAPTERS/$engine.ts" --bundle --platform=node --format=cjs --target=node20 \
    --outfile="$OUT/$engine.cjs" --log-level=warning
done
for engine in hmem markovian; do
  [ -s "$OUT/$engine.cjs" ] || { echo "build_reference_engines: $OUT/$engine.cjs was not produced." >&2; exit 1; }
done
echo "built: $(ls "$OUT" | tr '\n' ' ')"
