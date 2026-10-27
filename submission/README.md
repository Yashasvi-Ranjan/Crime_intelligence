# Submission package

| # | Deliverable | Where | Status |
|---|---|---|---|
| 1 | Demo video, 1 to 4 min | `media/AEGIS_Demo_Video.mp4` (narration text in `media/narration.txt`) | Generated and committed (about 6.7 MB); upload it to the portal. |
| 2 | Slide deck covering the 8 required points | `media/AEGIS_Slide_Deck.pptx` (14 slides; each footer says which required point it covers) | Generated and committed. Check the point list against the portal's wording. |
| 3 | Public GitHub repo with README | this repo; [`../README.md`](../README.md) opens with an accurate summary and the Docker quick start | Repo is ready; **publishing is yours** (nothing is pushed). See the checklist below. |
| 4 | Sponsor technology explanation (Zetaris, each Meterless engine and its test, Nightshift, NVIDIA, what is unique) | [`SPONSOR_TECHNOLOGY.md`](SPONSOR_TECHNOLOGY.md) | Done |
| 5 | Pre-existing components declaration | [`PRE_EXISTING_COMPONENTS.md`](PRE_EXISTING_COMPONENTS.md) | Done |
| 6 | Cursor field | n/a | Left out, as requested |
| 7 | Project name, one-liner, short and long description | [`PROJECT_INFO.md`](PROJECT_INFO.md) | Done (team name left for you) |
| 8 | AI usage and responsible-AI notes | [`RESPONSIBLE_AI.md`](RESPONSIBLE_AI.md) | Done |
| 9 | Live app link | n/a | Left out, as requested |
| 10 | Judge logins | [`JUDGE_ACCESS.md`](JUDGE_ACCESS.md) | The app has **no logins**, so none are issued; the file says so and gives the no-credentials run path |

## Before you publish the repo
1. `git push` the branch and open the PR when you are ready (nothing has been pushed).
2. Make the repo public; confirm `sh scripts/secret_scan.sh` passes on a fresh clone (it does on this branch) and that `.env` is not tracked.
3. `worldmodel.js` (proprietary) was never committed to any branch and is gitignored; keep it that way.
4. Replace the team-name placeholders, and read `SPONSOR_SUBMISSION_FINAL.md`, `TEST_READY.md` and `Slide_Deck.md` at the repo root: they predate this package and contain claims the code does not support (for example "195/195 tests", "working vision and embedding lanes", "zero hallucinations", a benchmark described as live-model). Consider deleting or correcting them before the repo is public.

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

Not changed, but worth knowing: `model_registry.analyze_cctv_frame` still returns a locally generated `rcpt-opt-…` id when its optical fallback runs (flagged `fallback_used: true`). It is not part of the investigation loop and we make no vision claim.
