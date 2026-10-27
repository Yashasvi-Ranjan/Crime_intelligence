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
python scripts/judge_compare.py --url http://localhost:8000     # all three examples, compared with output_examples/
```
Add `--network none` (and run `docker exec` instead of publishing a port) to prove it needs no network; see the README "Run with Docker" section.

## Read the evidence
- `docker logs <container>`: every trace event is printed as one `TRACE {...}` JSON line.
- `docker exec <container> sh -c 'cat logs/trace-*.jsonl'`, or mount `-v "$PWD/logs:/app/logs"` to read it on the host.
- The trace shows: routing, named agents, handoffs, the Skeptic branch, query ids, engine events, and the requested and answering Nemotron model on every call.

## Dashboard
`docker compose build && docker compose up` serves the API on http://localhost:8000 and the dashboard on http://localhost:3001 (no login).

## Live mode (optional)
Needs the sponsor stack running on the host (Zetaris on :8888/:8889, Nightshift on :8088) and a filled-in `.env`; see `.env.example`. Judges without that stack should use sample mode above.
