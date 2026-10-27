# Sponsor technology

How each sponsor technology is used, which test exercises it, what each sponsor contributes, and what is unique. Everything here is something the code does and the repo can show; limits are stated next to each claim.

## 1. Zetaris NDP: the federated data layer

**Role: load-bearing.** All investigative retrieval is SQL through Zetaris; no model ever touches the database.

- **Five sources, one query surface:** `police_incidents` (3,000 rows), `cctv_reports` (2,000), `witness_reports` (2,000), `forensic_reports` (1,500), `newspaper_reports` (1,500). In Zetaris they live in separate catalogs (`crime_police_db`, `crime_cctv_db`, `crime_witness_db`, `crime_forensic`, `crime_news_db`); the app addresses each by fully qualified name from `.env`, so the same code works whatever the layout.
- **One choke point:** `backend/app/services/zetaris_investigation_service.py` (candidate search per station, lookup by incident id, by location, and bounded per-source evidence queries). Read-only `SELECT`, bounded `LIMIT`, allow-listed characters.
- **Relevance-scored candidate retrieval:** candidate search used to be newest-first and row-capped, so the oldest incidents of a planted series never reached the agents. It now asks Zetaris for a bounded pool (at most 80 rows per query) ordered by keyword term hits plus a corroboration flag, then re-ranks the pool in Python (IDF-weighted term overlap, ties by incident id) and reserves 2 top-k slots for the best-matching incidents that cite linked source records (`backend/app/services/candidate_ranking.py`, shared by the SQL service and the local-sample twin). Row budgets are unchanged (5 per station, 10 total). On the planted series 001 to 003, 7 of the 8 planted incidents reach the candidate set, including the oldest of each series; `INC-NORTH-0294` is still missed (a known limit, written into the test). **Limit:** the new SQL (CASE scoring, pool `LIMIT`) has only been exercised through the local-sample mirror; it has never been run against live Zetaris.
- **Traceable:** every query's `X-Request-ID` is recorded as a query id in `sql_meta.query_ids` of the trace, next to `source: zetaris_live`.
- **Governed access:** the model sees at most 14 incidents (Finder and Skeptic prompts) and 8 records per source (`agents.py`); every id it cites is re-checked in code against the retrieved rows.
- **Honest degradation:** with `POST /run`, if Zetaris is unreachable the run continues on local sample data and the trace says `zetaris_fallback` / `source: local_sample`. The older `/api/investigations/analyze` route never substitutes data and returns an explicit error.
- **Live run, reported by the team (2026-10-27); trace not committed:** the team reports that a container reached the host Zetaris through `host.docker.internal`, retrieved from all five tables, and returned `data_mode: zetaris_live` with real query UUIDs in the trace and no partial failures. No live trace is in this repository, so this is not independently checkable from the repo; `docs/LIVE_RUN_RUNBOOK.md` and `scripts/capture_live_trace.py` produce one.
- **Tests:** `backend/tests/test_live_integration.py::test_live_zetaris_sql_returns_provenance_fields` and `::test_live_complete_investigation_with_real_evidence` (run with `RUN_LIVE_TESTS=1`, they need a live Zetaris and skip otherwise); `backend/tests/test_api.py` (local loader and API contracts); `backend/tests/test_sample_mode.py::test_local_service_matches_zetaris_contract` (the local-sample service honours the same filters and limits, ranks keyword searches deterministically, and returns newest-first only when no keywords are given; it no longer asserts recency ordering for keyword searches); `tests/test_retrieval_planted_series.py` (the oldest planted incidents reach the agents on the local-sample mirror, a newest-first regression check, bounded budgets, deterministic non-recency ranking; the `INC-NORTH-0294` miss is recorded as a known limit). These run against local sample data, not live Zetaris.
- **Limit:** Zetaris runs on the judge's host, not inside our image. Without it the offline sample mode serves the same retrieval functions from `data/generated` and labels it `local_sample`, never as Zetaris.

## 2. Meterless engines

Each engine runs through a Node runner called from Python. Every operation is a trace event (`engine_meta`); an engine that cannot run is traced `engine_unavailable`, never faked.

| Engine | What it does in a run | Test(s) | Where it runs |
|---|---|---|---|
| **World Model** | Shared ledger between agents: the investigation entity, each Planner decision, each Finder link revision, Skeptic objections and review status, verifier results, Reporter synthesis and run status are appended as observations. | `test_meterless_engine.py`: `test_real_meterless_engine_world_operations`, `test_meterless_contradiction_preservation`, `test_meterless_agent_provenance`, `test_meterless_health_check`; live: `test_live_world_model_roundtrip` | Mounted Nightshift engine directory only (no open reference exists). |
| **H-MEM** | Recalls earlier vetted leads as *context only* (never evidence). Stores a lead only if it passed the deterministic verifier **and** a completed Skeptic review with no open high-severity objection, behind a secret gate and a 0.6 confidence floor. Our own decision-memory layer next to it (not a Meterless feature) lets such a lead change a later run's retrieval order; see below. | `test_engine_adapters.py`: `test_hmem_roundtrip_with_provenance_and_scope_wall`, `test_hmem_refuses_low_confidence_and_secrets`; reference build: `test_reference_engines.py::test_hmem_reference_gates_and_roundtrip` | In the image (open reference) **or** mounted Nightshift `hmem.js`. |
| **Markovian** | Keeps the run bounded: validated chunk config, an 800-token carry-over between iterations built through its marker rung, a continuation prompt instead of resending history, a run-efficiency figure, and resumable run state (`continue_from`). | `test_engine_adapters.py`: `test_markovian_validates_config_and_clamps_iterations`, `test_markovian_rejects_invalid_config`, `test_markovian_carryover_is_compact_and_uses_marker_rung`, `test_markovian_state_resumes_from_disk`; reference: `test_reference_engines.py::test_markovian_reference_ops` | In the image (open reference) **or** mounted `markovian.js`. |
| **Scout Intent** | Runs the detector on every request as a recorded safety signal; the application then maps the request to an investigation intent with deterministic rules after validating every argument, and refuses destructive requests. | `test_engine_adapters.py`: `test_scout_runs_real_detector`, `test_scout_selftest_runs`, `test_routing_intents`, `test_routing_validates_arguments_before_anything_runs`, `test_routing_refuses_data_mutation_and_never_executes` | Mounted Nightshift engine directory only (the open repo ships a spec, not a runnable). |

**Decision memory (our own layer next to H-MEM, `backend/app/services/decision_memory.py`; tests `backend/tests/test_memory_decision.py`):** a prior verified lead (written only after the gate above) that shares incident ids or attribute tokens with a new question has its incident ids fetched first as a starting hypothesis in iteration 1, with no model involved; verifier-rejected or withdrawn pairs are suppressed and flagged; the effect is recorded in the response field `memory_influence` and as a trace event. `DMEM-` memory ids are not evidence (the verifier drops them), and memory cannot raise a link to SUPPORTED or count as an independent source. **Limits:** matching is lexical, not semantic; the tests use scripted models (labelled), and no live run shows memory changing an outcome.

Also: `GET /api/engines/health` runs one real operation per engine; every `POST /run` response lists `engines[]` with status and backend.

**Two ways engines run, and why:**
- **Mounted (`docker-compose.engine.yml`):** the proprietary Nightshift engine modules are mounted read-only from the host. They are never copied into the repo or an image (`worldmodel.js` is gitignored and in `.dockerignore`; it was never committed to any branch).
- **Reference (default in the image):** Meterless publishes Apache-2.0 reference implementations of H-MEM and Markovian at <https://github.com/Meterless/Meterless>. We vendor them **unmodified** at commit `1742dec` (`third_party/meterless/`, with LICENSE and a NOTICE listing a sha256 per file) and drive them through our own adapters. This is what lets a judge with only Docker see real H-MEM and Markovian events. Scout Intent and World Model have no open runnable reference and show `engine_unavailable` without a mount.

**What we do not claim:** Meterless's own conformance suites are not shipped in the Nightshift bundle and we did not run them, so we report no conformance scores. Our tests exercise the real engine modules (and the open references) through our adapters. Scout's shipped registry targets software-development tasks and has no crime-investigation intents, so its label is a recorded signal, not the routing decision.

## 3. Meterless Nightshift: the only model path

- Every model call goes through Nightshift's OpenAI-compatible API (`/v1/chat/completions`); there is no direct provider call anywhere in the code.
- **Each call records** the requested model, the model the response says answered, provider, receipt id, latency, token usage, and whether a fallback happened and why. The "answering model" comes from the response, never from configuration.
- **Per-role models are verified** against Nightshift's `/v1/models`; a configured model Nightshift does not list is reported unavailable and the role falls back to Lightning, and the report says so.
- **Bounded:** each call has a timeout (`NIGHTSHIFT_TIMEOUT_SECONDS`, `NIGHTSHIFT_SKEPTIC_TIMEOUT_SECONDS`); the Skeptic gets a single attempt on the large model before an explicit fallback; and the run is capped at `WORKFLOW_MAX_MODEL_CALLS`.
- **Secrets:** the NVIDIA provider key stays inside Nightshift. The app holds only the local proxy token (`NIGHTSHIFT_API_KEY`, or a mounted `NIGHTSHIFT_API_KEY_FILE`), never exposes it to the frontend, and a secret scan covers the repo and the image.
- **Tests:** `test_nightshift_client.py` (auth, retries, timeouts, metadata), `test_model_registry.py` (role to model, fallback, catalogue checks), live: `test_live_nightshift_lightning_reports_real_model`, `test_live_registry_verifies_models_against_nightshift_catalogue`, `test_live_ultra_skeptic_model_answers_when_listed`.
- **Live run, reported by the team (2026-10-27); trace not committed:** the team reports that from inside Docker all four agents answered on real Nemotron with receipts, requested model equal to answering model. No live trace is committed (see `docs/LIVE_RUN_RUNBOOK.md`).

## 4. Where NVIDIA contributes

NVIDIA **Nemotron** models do the reasoning, each in the lane that suits it:

| Lane | Model id | Job | Status |
|---|---|---|---|
| fast | `nvidia/nemotron-3.5-lightning-30b-a3b` | Planner, Finder, Reporter | in use (live use reported by the team; no live trace committed) |
| deep | `nvidia/nemotron-3-ultra-550b-a55b` | Skeptic (a different model from the Finder, so it is not agreeing with itself; never shown the Finder's score) | in use (live use reported by the team; no live trace committed; about 20 to 40 s per call as reported, spent on adversarial review, not routine steps) |

What we deliberately **do not** use, and say so: `nvidia/nemotron-3-embed-1b` is listed by Nightshift but `POST /v1/embeddings` returned HTTP 404 on our build, so retrieval is lexical SQL, not semantic; a rerank model and Nemotron Bolt are not served; the Super-VL model id is configured in the registry but CCTV image analysis is not part of the investigation loop and we make no vision claim.

## 5. What is unique

1. **Models propose, code verifies, a Skeptic attacks.** The deterministic verifier has the last word on IDs, verbatim quotes, shared attributes on *both* incidents, stations and timelines, and it never lets a model's confidence stand in for evidence.
2. **Duplicates are not corroboration.** A repeated camera window, a witness reported twice, or a newspaper article about a police-recorded incident does not count as a second independent source; forensic exclusions and witness/CCTV conflicts are surfaced, not merged away.
3. **It can say no.** "No supportable link" is a first-class outcome with the reason, and the Reporter cannot hide open objections.
4. **Memory only learns what survived scrutiny.** H-MEM stores only verified, Skeptic-reviewed leads, and our decision-memory layer lets those leads (never rejected ones) change a later run's retrieval order as starting hypotheses, with the effect recorded as `memory_influence`; memory ids are not evidence. Shown only with scripted models in tests, not in a live run.
5. **Auditable by construction.** One JSONL trace per run: routing, agents, handoffs, the Skeptic branch, query ids, engine events and the requested and answering model on every call.
6. **Runs anywhere.** A judge with only Docker gets the real loop offline (recorded Nemotron responses replayed by prompt hash, labelled `replayed`; the retrieval change altered some candidate sets and therefore some prompt hashes, the recordings were not re-recorded, and a prompt with no recording falls back to the labelled code-only path, so fewer calls replay than before), and the same image goes live when Zetaris and Nightshift are on the host.
