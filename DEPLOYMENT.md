# Deployment

## Links

| What | Link |
|---|---|
| **Live website** | https://crime-intelligence-six.vercel.app/ |
| **Docker image** | https://hub.docker.com/r/yashasvir171/oah-submission (`yashasvir171/oah-submission:latest`, `linux/amd64` and `linux/arm64`) |
| **Source code** | https://github.com/Yashasvi-Ranjan/Crime_intelligence |
| **API health (through the site)** | https://crime-intelligence-six.vercel.app/api/health |
| **API docs (when the live backend is up)** | https://crime-intelligence-six.vercel.app/api/docs |

There are no logins: the website and API need no account or password.

## How it is deployed

```
Browser -> Vercel (static React site) -> /api/... -> Cloudflare tunnel -> Docker container on the developer's machine
                                                                        -> Zetaris + Nightshift (NVIDIA Nemotron) + mounted Meterless engines
                                      -> /offline-api/... -> Vercel function (offline demo)
```

- **Website:** the React build is served by Vercel. `vercel.json` rewrites `/api/...` to the live backend and `/offline-api/...` to a Vercel function (`api/index.py`) that runs the same API in offline sample mode.
- **Live backend:** the Docker image runs on the developer's machine next to Zetaris and Nightshift and is exposed through a Cloudflare tunnel. No secrets are stored in Vercel; configuration is the local `.env` read by the container.
- **Offline fallback:** if the live backend cannot be reached, the page automatically retries against `/offline-api` and shows an amber banner. That mode uses the bundled synthetic data and **recorded** Nemotron responses (labelled `replayed`), not live Zetaris or live models.

## What to expect

| Situation | What you get |
|---|---|
| Developer's backend is up | Live Zetaris SQL and live Nemotron through Nightshift. A full investigation takes about 70 to 120 seconds. |
| Backend or tunnel is down | The offline demo, with a banner saying so. The example questions replay recorded Nemotron answers; other questions use a weaker, labelled code-only fallback. |

Checking which one you are seeing: `GET /api/health/zetaris` says `zetaris_live` when live; the amber banner at the top of the page appears only in offline mode; and every model call in an investigation's trace is marked `live`, `replayed` or `code_fallback`.

## Run it yourself (no dependence on the live site)

```bash
docker run --rm -p 8000:8000 -e SAMPLE_MODE=true yashasvir171/oah-submission:latest
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json   # input_examples/ is in the repo
```
For a full local stack (API on :8000 and dashboard on :3001): `docker compose build && docker compose up`. See the README ("Run with Docker") for live mode and the Meterless engines.

## Known limits of the hosted site
- It depends on the developer's machine, Docker, Zetaris, Nightshift and the tunnel being on. The tunnel is a Cloudflare quick tunnel; its URL changes when restarted, and `vercel.json` must then be updated.
- Live runs take close to the tunnel's timeout, so an occasional long run can be cut off.
- There is no access control on the live path: anyone with the site URL can start an investigation that uses the developer's model quota.
- For a deterministic result that does not depend on any of this, use the Docker command above.
