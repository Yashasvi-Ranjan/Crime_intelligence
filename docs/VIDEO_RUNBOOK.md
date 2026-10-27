# Demo video runbook (re-record as a real screen capture)

The committed `submission/media/AEGIS_Demo_Video.mp4` is narrated stills with no on-camera interaction. This runbook is for
re-recording it as a real screen capture, 1 to 4 minutes (target 3:30), with a live Zetaris + Nemotron run shown next to the
offline sample run. Nothing here has been recorded; the video files are not modified by this document.

Rule for the whole video: show what happens, say what is on screen, and never describe a screen you are not showing. Label offline
as offline and live as live.

## Pre-flight checklist (do all before pressing record)
- [ ] Zetaris NDP up, five tables present; Nightshift up with a provider key configured inside Nightshift; `.env` filled (see `docs/LIVE_RUN_RUNBOOK.md`).
- [ ] Do one dry run of the live query first (70 s to several minutes). Confirm in `logs/trace-<run_id>.jsonl` or the trace drawer that it shows `source: zetaris_live` query ids and a `receipt_id` on each model call. If it fell back, fix that before recording.
- [ ] Pick the runs to show. Candidates in the committed offline outputs: examples 1 and 3 ran 2 iterations (`output_examples/example_1.json`, `example_3.json`); confirm in their trace that iteration 2 was requested by the Skeptic (`next_action: plan_more_retrieval`, "objections requesting retrieval") before you call it a re-plan. For the duplicate-report rejection find a run whose verifier output has `duplicate_groups` non-empty or an `independence` check of status `warn` ("Duplicate/derivative reports collapsed to one source each"). Do not narrate either unless you have seen it in the run you recorded.
- [ ] Browser at 1920x1080, zoom 100 to 125 percent, dark notifications off, bookmarks and other tabs hidden, window showing only the app.
- [ ] No secrets on screen: no `.env`, no settings pane, no token in terminal scrollback (`clear` first), no Nightshift provider key page. Run `sh scripts/secret_scan.sh`.
- [ ] Hostnames: avoid showing tunnel or personal hostnames; use `localhost`.
- [ ] Screen recorder set to capture the screen at 30 fps with microphone; a second take for the long live wait is fine (cut or speed up the wait and say "sped up" on screen).
- [ ] Rehearse once against the time budget below.

## Start the app (exact commands)
Terminal 1, live backend (credentials in `.env`):
```bash
set -a; . ./.env; set +a; unset SAMPLE_MODE
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
sh scripts/build_reference_engines.sh
python run.py                                  # http://localhost:8000 ; /health must show zetaris and nightshift "live"
```
Terminal 2, a second backend in offline mode for the sample run (or switch with the page's sample control if you prefer one process):
```bash
SAMPLE_MODE=true PORT=8010 python run.py       # http://localhost:8010
```
Terminal 3, dashboard: `cd frontend && npm install && npm run dev` (http://localhost:5173). If the dev server proxies to
:8000, point the sample take at the offline backend by running the app with `SAMPLE_MODE=true` for that take instead; check
`frontend/` config for the proxy target rather than assuming.
Capturing proof alongside the video: `python scripts/capture_live_trace.py` (this makes a redacted trace you can commit; see `docs/LIVE_RUN_RUNBOOK.md`).

## Shot list (timings are targets)
| # | Time | Screen | Say | Must be visible |
|---|---|---|---|---|
| 1 | 0:00-0:15 | Dashboard overview | One sentence: three stations, five sources, a detective asks one question; leads, not verdicts. | App name, synthetic-data note |
| 2 | 0:15-1:15 | **Sample run** (offline): Investigation page, type or pick example 2 (catalytic converters), run | "This is the offline mode: local retrieval and recorded Nemotron responses." | The offline/sample badge; Planner -> Finder -> Skeptic -> Reporter progress; links with the stated reasons; the stopping reason |
| 3 | 1:15-1:45 | Trace drawer of that run | What each row is; replayed model calls are labelled `replayed`. | `source: replayed`, requested vs answering model, query ids marked `local-...`, engine events and any `engine_unavailable` |
| 4 | 1:45-2:30 | **Live run**: switch to the live backend, run example 1 (or the dry-run query). Speed up the wait on screen with a visible "sped up" caption | "Same question path, now live Zetaris SQL and live Nemotron through Nightshift." | The live badge, `/health` or Zetaris tab showing live, the run finishing |
| 5 | 2:30-3:00 | Live trace drawer, side by side with step 3 (split screen or cut) | "Real Zetaris query ids and Nightshift receipt ids." | Zetaris UUID query ids; a receipt id on each model call; requested equals answering model (zoom in so they are legible); no secrets |
| 6 | 3:00-3:25 | The Skeptic re-plan | "The Skeptic attacked the link and asked for more retrieval; the Planner ran another iteration." | The Skeptic objection that requests retrieval and the second iteration (only if confirmed in pre-flight) |
| 7 | 3:25-3:45 | The verifier rejecting a duplicate report | "Two reports of the same thing are not two witnesses; the verifier counts them once." | The `independence` check / `duplicate_groups` and the collapsed source (only if confirmed in pre-flight) |
| 8 | 3:45-4:00 | Terminal: `python scripts/judge_compare.py --url http://localhost:8010` | "Anyone can reproduce the offline answers with one command." | All three examples matching |

If time is short, drop shot 1 and shorten 3; never drop shots 4 and 5 (the live evidence is the point of the re-record) and keep sample next to live.

## What must not appear
Credentials, tokens, `.env`, the Nightshift provider page, personal hostnames or tunnel URLs, claims not on screen
("zero hallucinations", "court-admissible", benchmark scores: `evaluation/results.json` is a scripted stand-in, not a model benchmark).

## After recording
- Watch the cut once with sound off: can a viewer tell which run is live and which is offline?
- Pause on shot 5 and confirm every id is legible.
- Update `submission/README.md` row 1 to say the video is a screen capture only after it is. Keep `submission/media/narration.txt` consistent with what the new video says.
