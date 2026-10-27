# Live run runbook: capture one real Zetaris + Nemotron investigation

Purpose: produce the evidence that is currently missing. The repo's live-mode claims (real Zetaris query ids, all five
tables, real Nemotron receipts) are **reported by the team; no live trace is committed**. Follow this once on a machine that has
the sponsor stack, then commit the redacted output. Nothing here can be done from a clean clone without Zetaris and Nightshift.

## What you need
- Zetaris NDP running with the five tables loaded (`police_incidents`, `cctv_reports`, `witness_reports`, `forensic_reports`, `newspaper_reports`), and its login.
- Meterless Nightshift running with an NVIDIA provider key configured **inside Nightshift**, and the Nightshift proxy token.
- Python 3.11+, Node 20+ (for the engines). Optional: Docker.

## 1. Configure (credentials stay in your shell/.env; both are gitignored; never paste them into a file under docs/)
```bash
cp .env.example .env     # then fill ZETARIS_USERNAME, ZETARIS_PASSWORD (or ZETARIS_API_TOKEN), ZETARIS_TABLE_* if not default
# Nightshift token: NIGHTSHIFT_API_KEY=<token>, or NIGHTSHIFT_API_KEY_FILE=<file>, or on macOS host runs the app finds
# ~/Library/Application Support/ai.meterless.runtime/proxy-token by itself.
set -a; . ./.env; set +a          # the capture script reads the credentials from ITS OWN environment as a fail-fast check
unset SAMPLE_MODE
```

## 2. Start the backend in live mode
Host (venv) path:
```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
sh scripts/build_reference_engines.sh
python run.py                              # API on :8000; Zetaris/Nightshift on localhost
```
or Docker (Zetaris/Nightshift on the host, reached via host.docker.internal):
```bash
docker build -t oah-submission .
docker run -d --name aegis-live -p 8000:8000 --env-file .env -v "$PWD/logs:/app/logs" oah-submission
#   Linux: add --user "$(id -u):$(id -g)" so the container can write ./logs; to run World Model + Scout as well mount the
#   Nightshift engine directory read-only (README "Meterless engines", docker-compose.engine.yml).
```
Check: `curl -s localhost:8000/health` must show `"zetaris": {"state": "live"...}` and `"nightshift": {"state": "live"...}`.
`sample` or `down` means the credentials were not picked up or a service is down; fix that first.

## 3. Capture
```bash
python scripts/capture_live_trace.py                       # default input: input_examples/example_1.json
# Docker without a mounted logs/ :  python scripts/capture_live_trace.py --docker-container aegis-live
```
Takes about 70 to 120 s up to several minutes (reported for the live path). The script:
1. exits 2 with `NOT RUNNING: ...` if credentials are missing from the environment or `/health` is not live for both services (no sample run is substituted);
2. POSTs to `/run` with `options.sample_mode=false`;
3. writes the RAW run and trace to `.state/live_capture/` (gitignored; **do not commit**);
4. refuses to write anything for commit (exit 1) unless every retrieval event has `source: zetaris_live`, every model call has `source: live` with a Nightshift `receipt_id`, and `data_mode` is `zetaris_live`;
5. writes `docs/live_traces/live-run-<run_id>.summary.redacted.json` (Zetaris query ids, Nightshift receipt ids, requested vs answering model, engine statuses) and `...trace.redacted.jsonl`, both passed through `scripts/redact_trace.py`.

## 4. Review and redact
```bash
python scripts/redact_trace.py docs/live_traces/live-run-<run_id>.trace.redacted.jsonl --check     # must print "clean"
sh scripts/secret_scan.sh
grep -n -i -E "password|token|bearer|@|://" docs/live_traces/*       # read every hit by eye
```
`redact_trace.py` removes: secret-looking keys and values, Bearer/Authorization, JWTs and common API-key shapes, the exact values of
`ZETARIS_PASSWORD/ZETARIS_API_TOKEN/ZETARIS_USERNAME/NIGHTSHIFT_API_KEY` from your environment, URL hosts and ports,
IP addresses, `*.internal/.local/trycloudflare/onrender/vercel` names, e-mail addresses and home-directory names. It keeps UUID query ids, receipt ids,
model names and record ids. It is a safety net: a human must read the output. Unit tests: `python -m pytest -q tests/test_redact_trace.py` (synthetic strings only).

## 5. Commit and fix the docs
```bash
git add docs/live_traces && git commit -m "docs: redacted live Zetaris + Nightshift trace"
```
Then, and only then, change the attributed wording ("reported by the team ... trace not committed") in `submission/SPONSOR_TECHNOLOGY.md`,
`submission/Slide_Deck.md`, `submission/RESPONSIBLE_AI.md`, `submission/tools/build_media.py` and README section 11 to point at the committed file.
If the capture fails the liveness check, do not edit the claims.

## 6. What a good capture shows
- `summary.zetaris_query_ids`: UUIDs (each Zetaris `X-Request-ID`), all with `source: zetaris_live`.
- `summary.nightshift_calls`: one row per model call with `receipt_id`, `requested_model` equal to `reported_model` (Planner/Finder/Reporter `nvidia/nemotron-3.5-lightning-30b-a3b`, Skeptic `nvidia/nemotron-3-ultra-550b-a55b`), and `fallback_used: false`. A fallback is not an error but must be stated, not hidden.
- To show "all five tables" the trace's SQL events must reference all five sources; check the `details`/`sql_meta` of the retrieval events yourself, the script does not assert it.
