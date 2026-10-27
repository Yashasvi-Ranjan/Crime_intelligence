#!/usr/bin/env sh
# Bundle the vendored Meterless reference engines (third_party/meterless, Apache-2.0) together with our
# adapters into third_party/meterless/build/{hmem,markovian}.cjs. Needs Node 20+ and network access
# (npx fetches the pinned esbuild once). Run by the Dockerfile; run it by hand for host runs.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/third_party/meterless/build"
ADAPTERS="$ROOT/backend/app/services/meterless_world/reference"
mkdir -p "$OUT"
for engine in hmem markovian; do
  npx --yes esbuild@0.24.2 "$ADAPTERS/$engine.ts" --bundle --platform=node --format=cjs --target=node20 \
    --outfile="$OUT/$engine.cjs" --log-level=warning
done
echo "built: $(ls "$OUT" | tr '\n' ' ')"
