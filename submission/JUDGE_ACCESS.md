# Judge access

**There are no logins.** The application has no user accounts, passwords or authentication, so there are no judge credentials to issue, and none are needed to evaluate it. (We have not invented accounts that do not exist.)

## See it work with nothing but Docker (no credentials, no network)
```bash
git clone <repo-url> && cd <repo>
docker build -t oah-submission .
docker run --rm -p 8000:8000 -e SAMPLE_MODE=true oah-submission

# second terminal
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json
curl http://localhost:8000/health
python scripts/judge_compare.py --url http://localhost:8000     # all three examples, diffed against output_examples/
```
**Expect `judge_compare.py` to print FAIL for all three examples right now; that is not breakage.** It POSTs each `input_examples/example_N.json`, drops run ids, timestamps, latencies and query ids, and diffs the rest of the response against `output_examples/example_N.json` (the first 15 differences per example; exit code 1 if any differ). Candidate retrieval was changed after those files were recorded, so the candidate sets, prompt hashes and therefore the recorded-model fixture lookups differ; `output_examples/` and the fixtures have not been re-recorded, which needs live Nightshift credentials and `scripts/record_fixtures.py`. What you will see instead: some model calls report `code_fallback` (no recorded fixture for that prompt; the code-only path ran and no model answered), others `replayed`, and the `links` counts differ from the committed files (we measured 0, 1 and 1 links for examples 1, 2 and 3, against 1, 3 and 1 in the committed outputs). If the engines were built (`scripts/build_reference_engines.sh`), `engines[*].status` also differs, because the committed outputs were recorded with engines unavailable. In a run of this server on the host (SAMPLE_MODE=true, engines built) all three examples printed FAIL with `status=completed`; we did not run the Docker image for this check.
`judge_compare.py` also prints a WARNING when your server runs Scout Intent or World Model (for example because a Nightshift engine directory is mounted) while the examples were recorded with them `engine_unavailable`; the diff will then show engine-status differences. Set `METERLESS_ENGINE_DIR=/nonexistent` and `METERLESS_WORLD_MODEL_PATH=/nonexistent` on the server to compare like with like.
For the host venv path run `sh scripts/build_reference_engines.sh` first (README "Host (venv) path"); exact Docker checks are in `docs/DOCKER_VERIFY.md`.
Add `--network none` (and run `docker exec` instead of publishing a port) to prove it needs no network; see the README "Run with Docker" section.

## Read the evidence
- `docker logs <container>`: every trace event is printed as one `TRACE {...}` JSON line.
- `docker exec <container> sh -c 'cat logs/trace-*.jsonl'`, or mount `-v "$PWD/logs:/app/logs"` to read it on the host.
- The trace shows: routing, named agents, handoffs, the Skeptic branch, query ids, engine events, and the requested and answering Nemotron model on every call.
- The response carries a `memory_influence` field (decision memory: whether a prior verified lead changed which incidents were fetched first); when it applies, the trace has a matching `memory_influence` event. See `docs/MEMORY.md`.
- In the dashboard, the execution trace drawer has an expandable panel listing the Zetaris query ids and model receipts taken from the trace. We have not viewed it in a browser.

## Dashboard
`docker compose build && docker compose up` serves the API on http://localhost:8000 and the dashboard on http://localhost:3001 (no login).

## Live mode (optional)
Needs the sponsor stack running on the host (Zetaris on :8888/:8889, Nightshift on :8088) and a filled-in `.env`; the live path was not run by the reviewers of this documentation, and `docs/LIVE_RUN_RUNBOOK.md` describes how to capture a redacted trace. see `.env.example`. Judges without that stack should use sample mode above.
