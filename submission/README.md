# Submission package

| # | Deliverable | Where | Status |
|---|---|---|---|
| 1 | Demo video, 1 to 4 min | `media/AEGIS_Demo_Video.mp4` (narration text in `media/narration.txt`) | Generated and committed (about 6.7 MB); upload it to the portal. It was **not re-recorded** after the second-round changes below, so it predates them (and it does not show live Zetaris/Nightshift runs); see [`../docs/VIDEO_RUNBOOK.md`](../docs/VIDEO_RUNBOOK.md) to re-record. |
| 2 | Slide deck covering the 8 required points | `media/AEGIS_Slide_Deck.pptx` (14 slides; each footer says which required point it covers) | Generated and committed, but the `.pptx` was **not rebuilt** after the second-round changes below; its text may still carry the old "verified live" wording (the source text in `tools/build_media.py` and `Slide_Deck.md` was reworded). Check the point list against the portal's wording. |
| 3 | Public GitHub repo with README | this repo; [`../README.md`](../README.md) opens with an accurate summary and the Docker quick start | Repo is ready; the changes below are on `main`. **Making the repo public is yours.** See the checklist below. |
| 4 | Sponsor technology explanation (Zetaris, each Meterless engine and its test, Nightshift, NVIDIA, what is unique) | [`SPONSOR_TECHNOLOGY.md`](SPONSOR_TECHNOLOGY.md) | Done |
| 5 | Pre-existing components declaration | [`PRE_EXISTING_COMPONENTS.md`](PRE_EXISTING_COMPONENTS.md) | Done |
| 6 | Cursor field | n/a | Left out, as requested |
| 7 | Project name, one-liner, short and long description | [`PROJECT_INFO.md`](PROJECT_INFO.md) | Done (team name left for you) |
| 8 | AI usage and responsible-AI notes | [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) | Done |
| 9 | Live app link | n/a | Left out, as requested |
| 10 | Judge logins | [`JUDGE_ACCESS.md`](JUDGE_ACCESS.md) | The app has **no logins**, so none are issued; the file says so and gives the no-credentials run path |

## Before you publish the repo
1. Open the repo on GitHub and confirm `main` contains the changes described below.
2. Make the repo public; confirm `sh scripts/secret_scan.sh` passes on a fresh clone (it does on this branch) and that `.env` is not tracked.
3. `worldmodel.js` (proprietary) was never committed to any branch and is gitignored; keep it that way.
4. Replace the team-name placeholders. Earlier drafts of this repo had `SPONSOR_SUBMISSION_FINAL.md`, `TEST_READY.md` and a root `Slide_Deck.md` containing claims the code does not support (for example "195/195 tests", "zero hallucinations"). None of them exists on this branch (the deck text is `submission/Slide_Deck.md`, a different file), but check the repo you publish for stray copies of them before it is public.

## How the media were made
`tools/build_media.py` renders the video frames and the deck from the same content. The dashboard screenshots are of the real app running (frontend dev server and API); the terminal scene is built from a genuine `POST /run` response and its trace file; narration is the macOS `say` voice. Rebuild with:

```bash
python -m venv /tmp/sv && /tmp/sv/bin/pip install python-pptx pillow imageio-ffmpeg
SAMPLE_MODE=true (cd backend && python -m uvicorn app.main:app --port 8000) &   # API for the terminal scene
/tmp/sv/bin/python submission/tools/build_media.py --frames <screenshot dir> --out submission/media
```

The `.mp4` and the `.pptx` are committed; the intermediate `submission/media/video_frames/` is gitignored.

## Corrections made while preparing these deliverables
Filming the real app exposed content that the code did not support. These were fixed (and tests updated) rather than shown:
- **Trace inspector fabricated data.** The API invented a receipt id (`rcpt-<agent>-<run>-NNN`) and defaulted the model to Lightning for every step, the UI invented latencies (`~(n*320)ms`), kept a client-side fallback that generated a whole fake trace when the request failed, and unknown run ids returned a made-up trace. Now a trace is only what the run recorded: steps that made no Nightshift call show no model and no receipt, latencies come from the recorded call, and an unknown run id returns no events.
- **Knowledge graph invented entities.** When a result had no suspect or vehicle, the graph added a made-up suspect ("5'11, dark tactical hoodie, threat level HIGH") and a "grey minivan" and linked them to every incident with 88 to 95% confidence. Removed; the graph now draws only incidents, cited evidence and Finder links. Hard-coded 95% evidence confidences were removed too.
- **Static claims replaced by the actual state.** "ALL SENTINELS GREEN" next to a red violation, "4 Lanes Active & Receipted", "Zero Hallucinations", "100% Grounded in Zetaris" (even offline), "DGX Spark Eligible", "LIVE ZETARIS + NIGHTSHIFT" while offline. The sentinel and trace panels now report what the run recorded.
- **README opening** no longer claims "Full Quad-Nemotron Alignment" (vision and embeddings are not used), "100% deterministic grounding" or "court-admissible dossiers".
- **Benchmark wording.** `evaluation/results.json` came from a scripted offline stand-in for the models; the README, the script docstring and the deck now say so.
- **Replay bug found by building the video from a Docker image:** the fixture writer created files with mode 0600, which a non-root container could not read, so replay silently fell back to the code-only path. Fixed in the writer and in the Dockerfile, with a regression test.
- **New UI control:** a crime-type selector, so the dashboard can send the same request as `input_examples/example_2.json`.

## Second round: changes since the audited state
After a third-party audit of commit 595ba16, six further changes were made on branches, merged and then pushed to `main`. None of it involved a live Zetaris, Nightshift or Nemotron run. Each has a limit:
- **Relevance-scored retrieval.** Candidate retrieval was newest-first and row-capped, so the oldest planted incidents never reached the agents. It now ranks by IDF-weighted term overlap with a corroboration slot reservation (`backend/app/services/candidate_ranking.py`). 7 of the 8 planted incidents in series 001 to 003 now reach the candidate set; INC-NORTH-0294 is still missed. The new SQL was never run against live Zetaris (only the local-sample mirror is tested). Because candidate sets changed, prompt hashes changed and some recorded fixtures no longer match, so those prompts fall back to the labelled code-only path offline. `output_examples/` and the fixtures were not re-recorded (needs live credentials), so `scripts/judge_compare.py` is expected to fail against the committed `output_examples/` until they are; that has not been confirmed by running it.
- **UI overclaims removed, citations surfaced.** Hard-coded "Certified Admissible", "100% Citation Grounding", the sentinels panel and similar are gone; grounding, verifier and Skeptic status come from the API response, link cards show citation record ids, and Zetaris query ids and model receipts appear in the trace drawer. `tsc --noEmit` and the build pass; it was not viewed in a browser or tested against a real API response.
- **Pre-registered evaluation.** [`../evaluation/PREREGISTRATION.md`](../evaluation/PREREGISTRATION.md) (status: not yet run) fixes hypotheses, metrics and a hash-frozen 12-case held-out set; `scripts/evaluate_agents.py` now needs `--live` (never run) or `--offline-standin` (stamped as not a model benchmark). No real-model result exists; `evaluation/results.json` is still from the stand-in.
- **Decision memory.** A prior verified lead can seed later retrieval and is recorded in the response (`memory_influence`) and the trace; it cannot raise a link to SUPPORTED. See [`../docs/MEMORY.md`](../docs/MEMORY.md). Tested with scripted models only; matching is lexical, and no real-model run shows it changing an outcome.
- **Engine test doubles and dead-code removal.** Clearly labelled stand-ins for the proprietary engines (`backend/tests/stub_engines/`, see `STUB_ENGINES.txt`; operations they serve are labelled `backend="test_double"`) let the core workflow tests run on a machine without the Nightshift engine directory, and a missing engine is reported `engine_unavailable`. `scripts/judge_compare.py` now warns when the server runs engines that the examples were recorded without and names the environment variables to set. The dead CCTV/vision model-registry code (`analyze_cctv_frame`, the Super-VL and embed role preferences, including its locally generated `rcpt-opt-…` receipts) and the tests that covered only it were removed. This work was written by an agent that was interrupted and was reviewed afterwards; nothing was run live.
- **Docs and runbooks.** README restructured (offline path first), plus [`../docs/DOCKER_VERIFY.md`](../docs/DOCKER_VERIFY.md) (Docker path audited by reading only, never run), [`../docs/LIVE_RUN_RUNBOOK.md`](../docs/LIVE_RUN_RUNBOOK.md) and [`../docs/VIDEO_RUNBOOK.md`](../docs/VIDEO_RUNBOOK.md); trace capture/redaction scripts exist but were never run live. Earlier "Verified live" wording was changed to "reported by the team; trace not committed".

We make no vision claim: CCTV image analysis is not part of the investigation loop, and the old optical-fallback code that generated local `rcpt-opt-…` ids has been removed (see the engine bullet above).
