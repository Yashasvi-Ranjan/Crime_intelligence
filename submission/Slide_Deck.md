# AEGIS Slide Deck Content

Written for: hackathon judges. Numbers come from this repo (`output_examples/`, README, `metadata.json`, `submission/`).

---

## Slide 1 · Title
**On slide:** "AEGIS: cross-station crime linking agents that show their evidence"
Track 1, Solving Fragmented Intelligence · Open Agent Hackathon 2026 · [team name]
**Sponsor strip:** Zetaris NDP · Meterless (Nightshift + engines) · NVIDIA Nemotron
**Visual:** dark background of the Overview dashboard or the knowledge graph.
**Check no secrets visible:** the header shows only the app name, and the `.env` / Nightshift token page is not on screen.

## Slide 2 · Problem and users (point 1)
**On slide:**
- **"Each station sees only its own cases."**
- The same crowbar toolmark and the same dark-grey minivan turn up in NORTH on one day and in CENTRAL the next. Two stations each file one burglary, and nobody connects them.
- The evidence is fragmented as well: police incidents, CCTV, witness statements, forensic reports and press.
- Most linked records carry no explicit link (`related_incident_ids: []`), so the link has to be deduced.
- Real evidence conflicts: eyewitnesses disagree, night IR footage is degraded, forensics are inconclusive, and a plumbing van is a decoy.
- **Users:** cross-station detectives and analysts (find and test links), supervisors (review and budget), prosecutors (need a defensible dossier).
- **Numbers (synthetic county):** 10,000 records, 5 sources, 3 stations, 8 planted relationships including 2 decoys. Say "synthetic" on the slide.

**Visual:** two station icons holding the same toolmark and minivan, with no line between them.
**Say "proposed link / lead", never "caught".**

## Slide 3 · The solution in one picture (point 2)
**On slide:** "Agents read every source through Zetaris, reason with Nemotron through Nightshift, and a deterministic verifier plus a Skeptic check every link before a report is written."
- **Input:** one plain-language question, e.g. "Are the safe burglaries across NORTH and CENTRAL linked by the same pry bar?"
- **Output:** candidate links, each with a label (SUPPORTED / WEAK / UNSUPPORTED), shared attributes, differences, missing evidence, Skeptic objections and a cited report.
- **It can say no.** Without independent corroboration the answer is "no supportable link", with the reason.
- **Judge path:** one command, no credentials: `docker run -e SAMPLE_MODE=true -p 8000:8000 oah-submission`

**Visual:** the Investigation page result (link card plus graph).

## Slide 4 · Agent workflow (point 3)
**On slide:** loop diagram:
`Scout Intent → [H-MEM recall] → Planner → Zetaris SQL (code) → Finder → Verifier (code) → Skeptic → (back to Planner?) → Reporter → citation check → H-MEM store`
- **Bounded loop:** ≤3 iterations, ≤24 model calls, ≤900 s.
- The Skeptic or the verifier can send the run back to the Planner for more retrieval.
- **Nine stopping reasons**, e.g. `evidence_sufficient`, `no_supportable_links_found`, `budget_exhausted`, `interrupted` (resumable).
- **Callout:** "Not a fixed chain: routing, re-planning, adversarial critique, and code that has the last word."

**Visual:** the ASCII diagram from README §9 redrawn as a clean graphic.

## Slide 5 · Architecture and stack (points 3 + 4)
**On slide:**
- **Web:** React 18 + Vite + TypeScript. Interactive SVG knowledge graph, execution-trace drawer, evidence pinboard and printable dossier.
- **API:** FastAPI + Pydantic. Typed contracts per agent (`PlannerDecision`, `FinderOutput`, `SkepticReview`, `ReportOutput`).
- **Data:** Zetaris NDP, five federated tables.
- **Models:** NVIDIA Nemotron behind Meterless Nightshift.
- **Engines:** Meterless World Model, H-MEM, Markovian, Scout Intent. Node runners called from Python.
- **Judge path:** Docker image plus `POST /run`, `GET /health`, JSONL traces in `logs/`, and CI that runs on every push.

**Visual:** a layered architecture diagram: Browser → API → [Zetaris | Nightshift → Nemotron | Engines] → trace and state store.

## Slide 6 · How Zetaris is used (point 5)
**On slide:**
- **Five tables in the file store:** `police_incidents` (3,000), `cctv_reports` (2,000), `witness_reports` (2,000), `forensic_reports` (1,500), `newspaper_reports` (1,500).
- **One choke point.** All retrieval goes through `zetaris_investigation_service.py`: relevance-scored per-station candidate search, lookup by incident ID, lookup by location, and bounded per-source evidence queries. The SQL is code, not a model.
- **Candidate search is relevance-scored, not newest-first.** Keyword phrases are expanded to content words, each query returns a bounded pool (at most 80 rows), and Python re-ranks by IDF-weighted overlap with two top-k slots reserved for the best-matching corroborated incidents (`backend/app/services/candidate_ranking.py`; budgets unchanged at 5 rows per station, 10 total). On the local sample, 7 of the 8 planted incidents in series 001-003 now reach the candidate set, including the oldest of each; `INC-NORTH-0294` is still missed. The new SQL scoring has not been run against live Zetaris; only the local-sample mirror is tested.
- **Governed:** read-only `SELECT`, bounded `LIMIT`, allow-listed characters, and each query's id recorded in the trace.
- **The model never touches the database.** It sees ≤14 incidents and ≤8 records per source, and the verifier re-checks every ID it cites against the retrieved rows.
- **Live mode never silently substitutes local data.** An outage gives an explicit error or a resumable `interrupted` result.
- **Ground truth is isolated.** It is never registered as a table.

**Visual:** the Zetaris UI running a live candidate query with the result grid, plus the dashboard's Zetaris Layer tab.
**Check no secrets visible:** no token/settings page, and crop the URL bar.
**Honesty note:** in sample mode, retrieval is the same four functions (with the same ranking code) over `data/generated`, and the trace says `local_sample`, not Zetaris.

## Slide 7 · How Meterless is used (point 5)
**On slide (engines):**

| Engine | What it does in a run |
|---|---|
| **World Model** | Shared ledger: every planner decision, finding revision, Skeptic objection and verifier result is appended as an observation. |
| **H-MEM** | Recalls past vetted leads as *context only*. Stores only leads that passed the verifier and the Skeptic, behind its own secret gate and 0.6 confidence floor. **Decision memory:** a prior verified lead that shares incident ids or attribute tokens with a new question has its incidents fetched first as a starting hypothesis; the effect is attributed in `memory_influence` and the trace, and a memory id is never evidence. Tested with scripted models only. |
| **Markovian** | Keeps the run bounded: validated chunk config, 800-token carry-over between iterations, a continuation prompt instead of full history, and a run-efficiency figure. |
| **Scout Intent** | Detects intent on every request as a safety signal. Routing itself is deterministic rules, and every argument is validated first. |

**On slide (Nightshift):** the only model path. Each call logs requested model, answering model, receipt id, latency and tokens. The NVIDIA key stays inside Nightshift.
**Evidence:** the open H-MEM and Markovian reference implementations (Apache-2.0, commit `1742dec`) are vendored unmodified and run inside the Docker image. `engines[]` in every response says `connected` or `engine_unavailable`, and the app never reports an engine call it didn't make.
**Say plainly:** Meterless's own conformance suites aren't shipped in the Nightshift bundle, so we don't claim conformance scores. Our tests exercise the real engine modules.
**Visual:** the `engines[]` block of a `/run` response next to a trace crop.
**Check no secrets visible:** show no env vars.

## Slide 8 · NVIDIA Nemotron (point 5)
**On slide:**

| Lane | Model | Job |
|---|---|---|
| fast | Nemotron 3.5 Lightning 30B-A3B | Planner, Finder, Reporter |
| deep | Nemotron 3 Ultra 550B-A55B | Skeptic (separate model, never shown the Finder's score) |

- "Every response names the model that answered", taken from the response and not from config.
- Fallback to Lightning is explicit, with the reason recorded.
- Ultra is slow (~20–40 s per call). That cost is spent on adversarial review, not on routine steps.
- **Footnote:** Embed 1B is listed but `/v1/embeddings` returned 404, and Rerank and Bolt aren't served. They are not used, and we say so.
- **Recorded latency evidence** (`output_examples/example_2.json`): Planner ~3.0 s, Finder ~18.4 s, Skeptic ~22.3 s.

**Visual:** the trace drawer with the model column showing `nvidia/nemotron-3-ultra-550b-a55b` on the Skeptic line and a `rcpt-*` receipt.
**Check no secrets visible:** scan the receipt/trace text for token-like strings.

## Slide 9 · What was unique (point 6)
**On slide (three big lines):**
1. **"Models propose. Code verifies. A Skeptic attacks."** A deterministic verifier checks IDs, verbatim quotes, shared attributes on *both* incidents, station, and timeline.
2. **"Duplicates aren't corroboration."** A repeated camera window, one witness reporting twice, or a newspaper article about a police-recorded incident never counts as a second source. Contradictions such as a forensic `EXCLUSION` are surfaced, never merged away.
3. **"Memory only learns what survived scrutiny."** H-MEM stores only verified, Skeptic-reviewed leads. A prior verified lead can change a later retrieval order, but it is attributed in the trace and response and is never evidence or a second source (scripted-model tests only; no real-model run shows it changing an outcome). Runs checkpoint to disk and resume (`continue_from`).

**Visual:** a link card with its Skeptic objection and "independent_source_count: 0", from `output_examples/example_2.json`.

## Slide 10 · Product visuals (point 7)
Screens to capture, all synthetic, on the 1536 px desktop layout:
1. Overview: counts by station, crime type and timeline.
2. Investigation: question box, agent run panel and result.
3. Interactive knowledge graph across precincts.
4. Link detail: status label, citation record ids with quotes, differences, missing evidence, Skeptic panel. Grounding, verifier and Skeptic status are derived from the API response (hard-coded certainty badges were removed). This UI has been type-checked and built but not viewed in a browser or tested against a real API response.
5. Execution trace drawer: models, receipts, SQL timings, engine events, and an expandable panel of Zetaris query ids and model receipts.
6. Evidence pinboard, then the printable court dossier.
7. Zetaris status and Sources pages.
8. Terminal: `python scripts/judge_compare.py`. Do not show "all three examples matching" yet: `output_examples/` and the model fixtures were recorded before the retrieval change, so a mismatch is expected until they are re-recorded with live credentials. Capture it only after re-recording.

**Check no secrets visible:** no `.env`, no settings page, and no token in terminal scrollback.

## Slide 11 · Results
**No model benchmark is claimed, and no real-model result exists.** The committed `evaluation/results.json` (7 development cases) was produced with a scripted offline stand-in for the models (stamped NOT A MODEL BENCHMARK, fake receipts removed), not Nemotron. It tests the pipeline, the verifier and the scoring mechanics, so its "100% recall" must not appear on a slide as a model result. A pre-registered evaluation (`evaluation/PREREGISTRATION.md`, status "not yet run") and a `--live` harness in `scripts/evaluate_agents.py` now exist but have never been run. It names 7 development cases plus a 12-case frozen held-out set (held out of tuning and fixed by hash, but generated by the same synthetic generator and planted series).

**Reported by the team from live runs (not independently checkable: no live trace is committed):**
- Live run through Docker (real Zetaris and Nightshift): full loop, Nemotron on all four agents, zero partial failures.
- A live safe-burglary run retrieved the planted pair, but the verifier and Skeptic refused an ungrounded link: "no supportable link" is the correct output for a link the evidence does not support.

**Judge path (fresh clone, sample mode, `output_examples/`):**
- The committed `output_examples/` were recorded BEFORE the retrieval change: example 2 gave 3 links scored 0.78 / 0.55 / 0.32, and examples 1 and 3 ended in `no_supportable_links_found`. Recall on the planted series is not demonstrated by those runs.
- Retrieval then changed, so candidate sets and prompt hashes changed and some recorded fixtures no longer match. Offline, those prompts now fall back to a labelled code-only path. Replayed/code-fallback model calls before to after: ex1 3/2 to 1/2, ex2 4/0 to 1/3, ex3 3/2 to 1/3; links before to after: ex1 1 to 0, ex2 3 to 1, ex3 1 to 1.
- `scripts/judge_compare.py` is therefore expected to fail against the committed `output_examples/` until the fixtures are re-recorded (needs live Nightshift credentials and `scripts/record_fixtures.py`). Not run since the change; not re-recorded.

**Engineering:** 234 `def test_` functions counted with `grep -rn "def test_" tests backend/tests` (parametrised cases and skips not reflected). Last full run on the integration branch, with the reference engines built and `SAMPLE_MODE=true`: root `tests/` 124 passed; `backend/` 160 passed, 7 skipped (engine/live tests skip when unavailable). Secret scan on source and image, and Docker plus CI on every push (CI results for the new commits not yet seen).
**Never say:** "zero hallucinations" or "agents beat the LLM". Scores are uncalibrated heuristics.

## Slide 12 · Responsible AI (extra)
**On slide:**
- **Leads, not verdicts.** No determination of guilt, and a human decides.
- **Explainable by construction.** Each link shows its shared attributes, differences, missing evidence, Skeptic objections, citations and query ids.
- **Numbers labelled honestly.** `confidence_score` carries the text "Uncalibrated Finder heuristic; not a probability."
- **Models can't invent evidence.** Every cited ID, quote and attribute is re-checked in code, and ungrounded citations are rejected.
- **Safety rails:** read-only SQL, secret scanning, and the Nightshift token never reaches the frontend or logs.
- **UI claims removed.** Hard-coded "Certified Admissible", "100% Citation Grounding" and "all sentinels green" displays are gone; grounding, verifier and Skeptic status now come from the API response and read "not available" when absent.
- **Memory audit trail.** When a prior verified lead changes retrieval order, the effect is recorded in `memory_influence` and the trace; memory is never counted as evidence.
- **Data:** fully synthetic (fictional stations, people, places). The ground-truth file is isolated from the agents.

**Visual:** a link card with "WEAK" and its objections, next to the "uncalibrated" label.

## Slide 13 · Future enhancements + limitations (point 8)
**Next:**
- Run the pre-registered live evaluation (`evaluation/PREREGISTRATION.md`, `--live`) and publish whatever it shows.
- Capture a live trace and re-record the fixtures and demo video after the retrieval change.
- Enable semantic retrieval and reranking (Nemotron Embed / Rerank) once the routes are served.
- Add vision analysis of CCTV stills.
- Add crime-specific Scout intents.
- Stream progress to the UI. The API is synchronous today and a live run takes roughly 3–6 min.
- Use bound SQL parameters and calibrated confidence.
- Run a larger, multi-run benchmark, add analyst feedback, and pilot on real, consented data with police oversight.

**Limitations (state plainly):**
- Synthetic data. No real-model evaluation has been run: the committed results are a scripted stand-in on 7 development cases, and the 12-case held-out set reuses the same synthetic generator.
- Retrieval still misses `INC-NORTH-0294`, and the new SQL relevance scoring has not been run against live Zetaris.
- `output_examples/` and the offline fixtures predate the retrieval change and need re-recording; offline runs for non-matching prompts use a labelled code-only path.
- Decision memory matching is lexical, and only scripted-model tests exist for it.
- Embeddings and rerank aren't enabled, so H-MEM uses its lexical scorer.
- Only the open H-MEM and Markovian run inside the container. World Model and Scout need a mounted Nightshift engine directory and show `engine_unavailable` otherwise.
- The verifier's contradiction and duplicate heuristics cover the data's known patterns, not all patterns.
- The Skeptic on Ultra is slow, and sample-mode answers are only as good as the recorded fixtures.

---

## Notes resolved before publishing
1. **Eval.** Resolved: the committed evaluation used a scripted stand-in, so it is described as a pipeline test, not a model benchmark (see Slide 11, the README and `scripts/evaluate_agents.py`).
2. **Examples 1 and 3.** Expect "why didn't it find the series?" Answer: in the committed recordings, retrieval (newest-first) did not surface independent corroborating records, so the verifier refused to assert a link. Retrieval is now relevance-scored and reaches 7 of 8 planted incidents on the local sample, but the recordings have not been redone, so we have no new recorded outcome to show.
3. **Older documents.** `SPONSOR_SUBMISSION_FINAL.md` ("195/195 tests", "vision and embedding lanes", "zero hallucinations") contradicted the code and has been removed; the accurate version is `submission/SPONSOR_TECHNOLOGY.md`.
4. **Licence.** `worldmodel.js` (proprietary) was never committed to any branch and is gitignored; the open Apache-2.0 reference engines are vendored unmodified in `third_party/meterless/`.
