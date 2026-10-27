# Deployment

## Links

| What | Link |
|---|---|
| **Website (optional)** | https://crime-intelligence-six.vercel.app/ |
| **Docker image** | https://hub.docker.com/r/yashasvir171/oah-submission (`yashasvir171/oah-submission:latest`; architectures as stated by the authors, not verified from the repo) |
| **Source code** | https://github.com/Yashasvi-Ranjan/Crime_intelligence |
| **API health (through the site)** | https://crime-intelligence-six.vercel.app/api/health |
| **API docs (when the live backend is up)** | https://crime-intelligence-six.vercel.app/api/docs |

There are no logins: the website and API need no account or password.

## How it is deployed (as configured in this repo)

**Judges should use the offline path (below); it needs nothing outside the repo.** The website is optional.

```
Browser -> Vercel (static React site; vercel.json)
             /api/...         -> the backend hostname written in vercel.json (currently https://aegis-backend-1ino.onrender.com)
             /offline-api/... -> Vercel function api/index.py (same API, forced offline sample mode)
```

- **Durable option:** `render.yaml` (Render Blueprint) builds the backend from `Dockerfile` in offline sample mode (`SAMPLE_MODE=true`, `ZETARIS_ENABLED=false`, `METERLESS_ENGINE_BACKEND=reference`); no secrets, no developer machine. It replays recorded Nemotron responses (labelled `replayed`) and is **not** live Zetaris/Nemotron. Whether the Render service named in `vercel.json` is up cannot be checked from the repo; free-plan services typically sleep when idle.
- **Offline fallback:** if the backend cannot be reached, the page retries against `/offline-api` and shows an amber banner (bundled synthetic data, recorded Nemotron responses labelled `replayed`).
- **Live Zetaris + Nemotron (optional, developer-hosted):** needs the sponsor stack on the machine running the container. A Cloudflare quick tunnel (`scripts/restart_tunnel.sh`) can expose it temporarily, but it is ephemeral (URL changes on restart, can expire, dies with the laptop), has no access control, and rewrites `vercel.json`'s `/api` target; it is a developer convenience, not part of the durable deployment, and no judge check depends on it.

## What to expect

| Situation | What you get |
|---|---|
| Backend named in `vercel.json` is up | Offline sample mode (Render Blueprint), or live mode only if the developer has pointed `/api` at a live host. `GET /health` says which. |
| Backend is down | The offline demo, with a banner saying so. The example questions replay recorded Nemotron answers; other questions use a weaker, labelled code-only fallback. |

Checking which one you are seeing: `GET /health` reports `live`, `sample` or `down` for Zetaris and Nightshift; the amber banner appears only in offline fallback; and every model call in an investigation's trace is marked `live`, `replayed` or `code_fallback`.

## Run it yourself (no dependence on the live site)

```bash
docker run --rm -p 8000:8000 -e SAMPLE_MODE=true yashasvir171/oah-submission:latest
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json   # input_examples/ is in the repo
```
Or build it yourself (`docker build -t oah-submission .`) or use the host venv path (needs `sh scripts/build_reference_engines.sh`). Verification steps: `docs/DOCKER_VERIFY.md` (audited by reading, not run by its authors). Full local stack: `docker compose build && docker compose up`. See the README for live mode and the Meterless engines. A live run can be captured and redacted with `docs/LIVE_RUN_RUNBOOK.md`.

## Known limits of the hosted site
- It is a convenience, not evidence. Live-mode behaviour on it is not independently checkable from the repo (no live trace committed).
- A quick-tunnel live setup, if used, is ephemeral and has no access control: anyone with the URL could start an investigation using the developer's model quota.
- For a deterministic result use the Docker or venv offline path.
