# Docker verification procedure (for a judge with Docker)

Status: the Dockerfile, compose files and these commands were **audited statically only**. The authors of this
document did not run Docker for it, so nothing below is a claim that it was run. CI (`.github/workflows/ci.yml`)
contains the same steps (`docker-build`, `judge-path`, `offline`); its results are the only run evidence in the repo's history.

Needs: Docker, network for the *build* (it pulls `node:20-slim`, `python:3.11-slim`, and `npx` fetches `esbuild@0.24.2`
once). Running the built image needs no network and no credentials.

## A. Build the image from this checkout (preferred; tests the committed Dockerfile)

```bash
docker build -t oah-submission .
docker run -d --name aegis -p 8000:8000 -e SAMPLE_MODE=true oah-submission     # entrypoint: CMD ["python","run.py"]
```

Expected, each line independent:

```bash
docker inspect -f '{{.State.Health.Status}}' aegis     # "healthy" within ~20-60 s (starting -> healthy)
docker exec aegis ls third_party/meterless/build       # hmem.cjs markovian.cjs  (the engine bundle built in stage 1)
docker exec aegis node --version                       # v20.x
curl -s localhost:8000/health                          # zetaris/nightshift state "sample"
docker exec aegis python scripts/judge_compare.py --url http://127.0.0.1:8000   # all three examples match, exit 0
docker exec aegis python scripts/trace_check.py        # every trace file: OK
```

In `engines[]` of a run (`curl -s -X POST localhost:8000/run -H 'Content-Type: application/json' -d @input_examples/example_1.json`)
you should see `h_mem` and `markovian` with `status: connected, backend: ["reference"]`, and `scout_intent` and `world_model`
with `status: engine_unavailable`. That is the committed expectation in `output_examples/`; it is correct, not a failure
(the proprietary engines are never in the image).

Failure meaning: no `hmem.cjs`/`markovian.cjs` means stage 1 (`scripts/build_reference_engines.sh`) did not produce output, so
`judge_compare.py` will report engine differences; `judge_compare.py` differences in links/report text would be a real regression.

## B. Offline proof

```bash
docker run -d --name offline --network none -e SAMPLE_MODE=true oah-submission
sleep 20
docker exec offline python scripts/judge_compare.py --url http://127.0.0.1:8000
```

## C. The published image (what the README quick start uses)

```bash
docker pull yashasvir171/oah-submission:latest
docker run -d --name aegis-hub -p 8001:8000 -e SAMPLE_MODE=true yashasvir171/oah-submission:latest
docker exec aegis-hub ls third_party/meterless/build
docker exec aegis-hub python scripts/judge_compare.py --url http://127.0.0.1:8000
docker image inspect yashasvir171/oah-submission:latest -f '{{.Architecture}} {{.Created}}'
```

Whether the Hub image was built from this exact commit is **not verifiable from the repo**; if A passes and C does not, trust A.
The README says the Hub image has `linux/amd64` and `linux/arm64` variants; check with `docker buildx imagetools inspect yashasvir171/oah-submission:latest`.

## D. Compose stack (API :8000 + dashboard :3001)

```bash
SAMPLE_MODE=true docker compose up -d --build          # needs Docker Compose >= 2.24 (optional env_file `required: false`)
curl -s localhost:8000/health && curl -sI localhost:3001/ | head -1 && curl -s localhost:3001/health
docker compose down
```

## Clean up
`docker rm -f aegis offline aegis-hub`

## Static audit notes (what was checked by reading, and what was not)
- Stage 1 copies `third_party/`, the two adapter `.ts` files and `scripts/build_reference_engines.sh`, runs it, and stage 2 copies
  only `third_party/meterless/build` from it. Paths in the script (`$ROOT/third_party/meterless/build`, adapters under
  `backend/app/services/meterless_world/reference`) match the Dockerfile's `COPY` destinations. The adapters import
  `../../../../../third_party/meterless/*/src/index.ts`, which is why `third_party` is copied whole into stage 1.
- `.dockerignore` excludes `third_party/meterless/build` (a host-built bundle never leaks in; the image builds its own), `worldmodel.js`,
  `.env*`, `frontend`. `Dockerfile.web` has its own `Dockerfile.web.dockerignore` (BuildKit), which keeps `frontend/` in its context.
- The judge path needs no `ENTRYPOINT` override: `CMD ["python","run.py"]` serves on `$PORT` (8000), non-root user `app`.
- Not verifiable by reading: the `node` binary copied from `node:20-slim` into `python:3.11-slim` loading its shared libraries
  (both Debian-based; CI runs it), the multi-arch Hub manifest, and image size/time.
