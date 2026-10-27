# AEGIS: Cross-Station Crime Intelligence
> *Track: Solving Fragmented Intelligence* | **Open Agent Hackathon 2026**

Agents that link crimes across police stations, and show the evidence, the doubts and the missing pieces behind every link.
Three stations hold related cases in separate silos (incidents, CCTV, witness statements, forensic reports, press). A detective asks one
plain-language question; a **Planner, Finder, Skeptic and Reporter** search five Zetaris-federated sources with NVIDIA Nemotron through
Meterless Nightshift, a **deterministic verifier** re-checks every ID, quotation and attribute they cite, and the answer is a set of
*leads, not verdicts* - which can be "no supportable link". All data is synthetic.

| | |
|---|---|
| **Website** | https://crime-intelligence-six.vercel.app/ (see [Live website](#live-website): live Zetaris and Nemotron while the developer's backend is up, otherwise a clearly labelled offline demo) |
| **Docker image** | [`yashasvir171/oah-submission`](https://hub.docker.com/r/yashasvir171/oah-submission) on Docker Hub (`linux/amd64` and `linux/arm64`) |
| **Demo video, slides, documents** | [`submission/`](submission/README.md) |

**Try it with only Docker (no credentials, no network, no clone needed for the image):**
```bash
docker run --rm -p 8000:8000 -e SAMPLE_MODE=true yashasvir171/oah-submission:latest
# in a second terminal (input_examples/ is in this repo):
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json
```
To build the image yourself instead: `docker build -t oah-submission .` and use `oah-submission` in place of the Docker Hub name.
Details, live mode, engines and the judge checklist: [Run with Docker](#run-with-docker). Submission documents (project text, sponsor technology,
pre-existing components, responsible AI, judge access, slide deck, demo video): [`submission/`](submission/README.md).

### What it does
- **Models propose, code verifies, a Skeptic attacks.** Retrieval is read-only SQL through Zetaris (never a model). The verifier checks that cited IDs exist and match
  their source, quotes are verbatim, shared attributes appear in records tied to **both** incidents, and stations/timelines agree. Duplicate reports are never counted as independent corroboration.
- **Models, per role:** `nvidia/nemotron-3.5-lightning-30b-a3b` (Planner, Finder, Reporter) and `nvidia/nemotron-3-ultra-550b-a55b` (Skeptic), all through Nightshift.
  Every call records the requested model, the model that answered, receipt id, latency and whether a fallback happened.
- **Meterless engines:** H-MEM and Markovian run in the image from the open Apache-2.0 reference implementations (vendored unmodified, `third_party/meterless`); World Model and Scout Intent
  run when the Nightshift engine directory is mounted and are otherwise traced `engine_unavailable`, never faked.
- **Auditable:** one JSONL trace per run (`logs/trace-<run_id>.jsonl`): routing, agents, handoffs, the Skeptic branch, query ids, engine events, requested and answering model.
- **Honest about limits:** scores are uncalibrated heuristics; embeddings, reranking and vision are **not** used (the Nightshift build in use returned 404 for `/v1/embeddings` and does not serve rerank);
  `evaluation/results.json` came from a scripted offline stand-in for the models and is **not** a model benchmark. See [`submission/RESPONSIBLE_AI.md`](submission/RESPONSIBLE_AI.md).

---

# Cross-Station Crime Intelligence: Synthetic Data Generator

> **Open Agent Hackathon 2026** — *Solving Fragmented Intelligence & Multi-Station Investigation*

This repository contains the synthetic data generation pipeline and validation suite for the **Cross-Station Crime Intelligence** system. It produces a reproducible, multi-source synthetic intelligence dataset comprising exactly **10,000 fictional records across five JSON files**, accompanied by an offline ground-truth evaluation benchmark.

These datasets are designed to be ingested into **Zetaris NDP File Store** and queried as unified tables to power agentic reasoning across siloed law enforcement jurisdictions.

---

## 1. Project Directory Structure

```text
cross_station_crime_intelligence/
├── run.py                              # entry point: starts the API on $PORT, or `--once FILE` posts one input to /run
├── Dockerfile                          # API image (python:3.11-slim + Node 20, non-root, HEALTHCHECK /health)
├── Dockerfile.web / Dockerfile.web.dockerignore   # dashboard image (Vite build behind nginx on :3001)
├── docker-compose.yml                  # api (:8000) + web (:3001); logs/ and .state/ as volumes
├── docker-compose.engine.yml           # optional: mount the host Meterless engine directory read-only
├── docker-compose.token-file.yml       # optional: Nightshift token from a mounted file
├── .env.example                        # THE one config template (copy to .env; gitignored)
├── .dockerignore, .gitignore
├── requirements.txt                    # pinned Python dependencies
├── metadata.json                       # project / track / sponsor technology / entry point
├── vercel.json                         # website: /api -> tunnel to the live backend, /offline-api -> offline fallback
├── api/index.py                        # Vercel function serving the OFFLINE fallback (forced sample mode)
├── .github/workflows/ci.yml            # pytest, docker build, judge path (SAMPLE_MODE), offline (--network none), secret scan
│
├── backend/                            # FastAPI application
│   ├── app/
│   │   ├── main.py, config.py, schemas.py
│   │   ├── routers/                    # run.py (POST /run, GET /health), investigations.py, incidents.py, sources.py, health.py
│   │   └── services/
│   │       ├── investigation_workflow.py   # the bounded Planner -> Finder -> verifier -> Skeptic -> Reporter loop
│   │       ├── agents.py, evidence_verifier.py, model_registry.py, nightshift_client.py
│   │       ├── zetaris_adapter.py, zetaris_investigation_service.py, local_data_loader.py
│   │       ├── meterless_engines.py, meterless_service.py, meta_sentinels.py, trace_logger.py, run_service.py
│   │       ├── sample_scenarios.py     # pre-built DEMO content only (demo_content=true)
│   │       ├── sample_mode/            # offline mode: local retrieval, fixture replay, code-only fallback, resilient wrappers
│   │       └── meterless_world/        # Node runners for the engines; reference/ = our adapters for the open H-MEM/Markovian
│   └── tests/                          # unit, mocked, engine (skip when unavailable) and live (RUN_LIVE_TESTS=1) tests
│
├── frontend/                           # React 18 + Vite + TypeScript dashboard
│   ├── src/ (pages/, components/, services/api.ts, types/)   # api.ts retries /offline-api when the live backend is down
│   └── nginx.conf.template             # proxy for the web image
│
├── data/
│   ├── generated/                      # the five synthetic tables (3,000 / 1,500 / 2,000 / 2,000 / 1,500 records)
│   ├── evaluation/ground_truth.json    # offline planted relationships (never loaded by the application)
│   └── sample/model_fixtures/          # recorded Nemotron responses replayed by sample mode (sha256 of role, model, prompt)
│
├── input_examples/ , output_examples/  # the three judge examples and their recorded outputs (scripts/judge_compare.py)
├── scripts/
│   ├── generate_synthetic_data.py      # deterministic data generator
│   ├── record_fixtures.py              # record fixtures from live Zetaris + Nightshift runs; regenerate output_examples/
│   ├── judge_compare.py, trace_check.py, secret_scan.sh, build_reference_engines.sh, evaluate_agents.py
├── tests/                              # synthetic-data, adversarial and end-to-end suites
├── third_party/meterless/              # Apache-2.0 H-MEM + Markovian reference sources (unmodified, commit 1742dec), LICENSE, NOTICE.md
├── submission/                         # hackathon deliverables: documents, slide deck, demo video, tools/build_media.py
├── evaluation/results.json             # scripted-stand-in evaluation (a pipeline test, not a model benchmark)
└── logs/ , .state/                     # generated at run time (gitignored): traces, run state, H-MEM store
```

---

## 2. Dataset Overview & Quotas

All datasets are valid UTF-8 JSON arrays of objects with standard ISO 8601 UTC timestamps ending in `Z`. Unknown scalars are represented as `null` and absent lists as empty arrays `[]`.

| Dataset File | Target Records | Primary Entity / Focus |
| :--- | :--- | :--- |
| `data/generated/police_incidents.json` | **3,000** | Formal police incident reports across 3 stations |
| `data/generated/newspaper_reports.json` | **1,500** | Public press coverage, investigative journalism, and police blotters |
| `data/generated/witness_reports.json` | **2,000** | Citizen and pedestrian observations, tipoffs, and vehicle sightings |
| `data/generated/cctv_reports.json` | **2,000** | Automated surveillance feeds, optical sightings, and motion analysis |
| `data/generated/forensic_reports.json` | **1,500** | Physical, biological, chemical, and digital evidence lab analyses |
| **Total primary source records** | **10,000** | **Exact Hackathon Target** |
| `data/evaluation/ground_truth.json` | **8 Scenarios** | **Offline evaluation benchmark (never exposed to Zetaris tables)** |

---

## 3. Schemas

### 3.1 Police Incidents (`police_incidents.json`)
* **`incident_id`** *(string)*: Unique identifier (e.g. `INC-NORTH-0042`, `INC-CEN-0118`).
* **`station_id`** *(string)*: Station jurisdiction (`NORTH`, `CENTRAL`, or `RIVERSIDE`).
* **`reported_at`** *(string)*: ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`).
* **`occurred_from`** *(string)*: Start of occurrence window (`YYYY-MM-DDTHH:MM:SSZ`).
* **`occurred_to`** *(string | null)*: End of occurrence window, or `null` if instantaneous or unknown.
* **`crime_type`** *(string)*: Offense category (`BURGLARY`, `VEHICLE_THEFT`, `ROBBERY`, `SHOPLIFTING`, `VANDALISM`, `FRAUD`, `CARGO_THEFT`, etc.).
* **`location_id`** *(string)*: Standardized fictional location code (e.g. `LOC-NORTH-01`).
* **`location_description`** *(string)*: Human-readable location description.
* **`method_description`** *(string)*: Narrative modus operandi description.
* **`property_involved`** *(list[string])*: Stolen, damaged, or involved property items.
* **`estimated_loss`** *(float | null)*: Monetary loss valuation in USD, or `null`.
* **`status`** *(string)*: Case status (`OPEN`, `UNDER_INVESTIGATION`, `CLOSED`, `UNRESOLVED`).
* **`source_reference_ids`** *(list[string])*: Explicitly indexed reference IDs or `[]`.
* **`data_quality`** *(string)*: Data fidelity rating (`HIGH`, `MEDIUM`, `LOW`).

### 3.2 Newspaper Reports (`newspaper_reports.json`)
* **`news_id`** *(string)*: Unique news identifier (e.g. `NEWS-0064`).
* **`publication_name`** *(string)*: Press outlet (e.g. `Metro Daily Gazette`, `Central City Chronicle`).
* **`published_at`** *(string)*: ISO 8601 UTC timestamp of publication.
* **`headline`** *(string)*: Article headline.
* **`article_text`** *(string)*: Full news report body.
* **`mentioned_date_from`** *(string | null)*: Date range referenced in article.
* **`mentioned_date_to`** *(string | null)*: Date range referenced in article.
* **`mentioned_location_ids`** *(list[string])*: Location IDs referenced in coverage.
* **`crime_labels`** *(list[string])*: Editorial crime classification tags.
* **`mentioned_property`** *(list[string])*: Property items discussed in the article.
* **`related_incident_ids`** *(list[string])*: Explicit incident references if known to the press.
* **`source_reliability`** *(string)*: Journalist credibility score (`HIGH`, `MEDIUM`, `LOW`, `UNVERIFIED`).
* **`data_quality`** *(string)*: Metadata fidelity rating (`HIGH`, `MEDIUM`, `LOW`).

### 3.3 Witness Reports (`witness_reports.json`)
* **`witness_report_id`** *(string)*: Unique witness observation ID (e.g. `WIT-0105`).
* **`submitted_at`** *(string)*: ISO 8601 UTC timestamp of statement intake.
* **`observed_from`** *(string)*: Start of observation timeframe.
* **`observed_to`** *(string | null)*: End of observation timeframe.
* **`location_id`** *(string)*: Location ID where witness made the sighting.
* **`observation_text`** *(string)*: Verbatim witness account.
* **`observed_entities`** *(list[string])*: Extracted descriptions of persons, bags, or items.
* **`vehicle_description`** *(string | null)*: Descriptive vehicle notes, or `null`.
* **`direction_of_travel`** *(string | null)*: Fleeing direction or trajectory, or `null`.
* **`confidence_level`** *(string)*: Witness certainty (`HIGH`, `MEDIUM`, `LOW`, `UNCERTAIN`).
* **`related_incident_ids`** *(list[string])*: Explicitly linked incident IDs, or `[]`.
* **`contradiction_flags`** *(list[string])*: Identified discrepancies (e.g. `["disputes_suspect_count"]`).
* **`data_quality`** *(string)*: Metadata completeness rating (`HIGH`, `MEDIUM`, `LOW`).

### 3.4 CCTV Reports (`cctv_reports.json`)
* **`cctv_report_id`** *(string)*: Unique surveillance clip ID (e.g. `CCTV-0112`).
* **`camera_id`** *(string)*: Camera infrastructure ID (e.g. `CAM-NORTH-01-01`).
* **`location_id`** *(string)*: Monitored location code.
* **`recorded_from`** *(string)*: Start timestamp of recording window.
* **`recorded_to`** *(string | null)*: End timestamp of recording window.
* **`observed_entities`** *(list[string])*: Computer vision / operator entity tags.
* **`vehicle_description`** *(string | null)*: Make, model, or body style description, or `null`.
* **`vehicle_color`** *(string | null)*: Vehicle exterior paint color, or `null`.
* **`partial_plate`** *(string | null)*: Legible plate characters (e.g. `7XK***`), or `null`.
* **`movement_description`** *(string)*: Trajectory and behavior summary.
* **`image_quality`** *(string)*: Optical fidelity (`CLEAR`, `MODERATE`, `DEGRADED`, `NIGHT_IR_LOW_RES`, `PARTIAL_GLARE`, `POOR`).
* **`observation_confidence`** *(float)*: Numeric certainty score between `0.0` and `1.0`.
* **`related_incident_ids`** *(list[string])*: Explicit incident references, or `[]`.
* **`data_quality`** *(string)*: Metadata quality (`HIGH`, `MEDIUM`, `LOW`).

### 3.5 Forensic Reports (`forensic_reports.json`)
* **`evidence_report_id`** *(string)*: Unique laboratory report ID (e.g. `FOR-0089`).
* **`incident_id`** *(string | null)*: Police incident ID if item was logged from a scene, or `null`.
* **`evidence_item_id`** *(string)*: Physical evidence barcode ID (e.g. `EVD-2025-0089`).
* **`collected_at`** *(string)*: ISO 8601 UTC timestamp of evidence collection.
* **`location_id`** *(string)*: Recovery location code.
* **`evidence_type`** *(string)*: Discipline (`TOOLMARK`, `DNA`, `FINGERPRINT`, `BALLISTICS`, `DIGITAL_FOOTPRINT`, `CHEMICAL_RESIDUE`, `TIRE_IMPRESSION`, `FIBER`).
* **`description`** *(string)*: Physical description of sample or substrate.
* **`examination_method`** *(string)*: Analytical technique (`COMPARISON_MICROSCOPY`, `STR_PROFILING`, `AFIS_LATENT_SCAN`, `GC_MS`, `LOG_AND_SIGNAL_ANALYSIS`, `TREAD_PHOTOGRAMMETRY`).
* **`result_summary`** *(string)*: Examiner's technical conclusions.
* **`result_status`** *(string)*: Outcome status (`MATCH_CONFIRMED`, `INCONCLUSIVE`, `EXCLUSION`, `PENDING_REFERENCE`, `PARTIAL_MATCH`).
* **`confidence_level`** *(string)*: Scientific certainty (`HIGH`, `MEDIUM`, `LOW`, `INCONCLUSIVE`).
* **`compared_evidence_ids`** *(list[string])*: Cross-referenced evidence item barcodes.
* **`limitations`** *(string | null)*: Known methodological constraints or sample degradation, or `null`.
* **`data_quality`** *(string)*: Quality grade (`HIGH`, `MEDIUM`, `LOW`).

---

## 4. Synthetic World Design

The synthetic environment models three fictional police precincts within a single metropolitan county:

1. **`NORTH` Precinct**:
   * Northern industrial parks, distribution terminals, and tech corridors (`LOC-NORTH-01` to `LOC-NORTH-20`).
   * Characterized by logistics parks, server facilities, and suburban residential estates.
2. **`CENTRAL` Precinct**:
   * Dense commercial downtown core, financial high-rises, transit terminals, and luxury shopping arcades (`LOC-CEN-01` to `LOC-CEN-20`).
   * High volume of pedestrian traffic, bank facilities, and municipal buildings.
3. **`RIVERSIDE` Precinct**:
   * Maritime docks, cargo shipping yards, marine slips, commuter rail terminals, and container freight storage (`LOC-RIV-01` to `LOC-RIV-20`).
   * Intermodal logistics transit points connecting rail, marine, and road freight.

* **Privacy & Ethical Safeguards**: All locations, company names, camera IDs, citizen accounts, and vehicle registrations are 100% fictional. No real personal identifiable information (PII) or real police records are used.

---

## 5. Agent Reasoning Challenges

The dataset is purposefully curated with complex multi-table reasoning features designed to challenge and evaluate autonomous AI agents:

* **Planted Multi-Station Crime Rings**:
  * *Crowbar Commercial Safe Crackers* (`REL-SERIES-001`): Series spanning `NORTH` and `CENTRAL` linked by 36mm chisel-tip toolmark striations and a dark grey minivan with a dented tailgate (`7XK***`).
  * *Commuter Rail Catalytic Converter Syndicate* (`REL-SERIES-002`): Rapid sub-90-second thefts spanning `CENTRAL` and `RIVERSIDE` linked by GC-MS titanium carbonitride blade metallurgy.
  * *Keyless Luxury SUV Relay Ring* (`REL-SERIES-003`): Push-to-start relay attacks spanning `NORTH` and `RIVERSIDE` linked by RF signal injection telemetry logs.
  * *Impostor Utility Inspector Scam* (`REL-SERIES-004`): Distraction burglaries spanning `CENTRAL` and `NORTH` linked by latent palm prints and a white utility van with roof ladder rack.
  * *Pharmaceutical Cold-Storage Diversion* (`REL-SERIES-007`): Cargo fraud spanning `RIVERSIDE` and `CENTRAL` linked by compromised digital manifest cryptographic signatures.
* **Contradictory Eyewitness Accounts**: Discrepancies in perceived suspect clothing colors (red jacket vs dark hoodie) and vehicle body styles (minivan vs SUV).
* **Discoverable vs. Explicit Links**: Many connected records have `related_incident_ids: []`, requiring the agent to deduce links from spatial-temporal proximity, vehicle partial plates, and forensic comparison IDs (`compared_evidence_ids`).
* **Degraded CCTV Feeds & Inconclusive Forensics**: Low-resolution night infrared cameras, headlights glare, partial latent fingerprints, and inconclusive lab results.
* **Intentional Distractors & Exclusions**:
  * `REL-DISTRACTOR-006`: A legitimate commercial plumbing van (`Apex Municipal Plumbing`) that was falsely reported by an anxious neighbor, forensically excluded via tire tread analysis.
  * `REL-DISTRACTOR-008`: An amateur juvenile smash-and-grab using a cinder block that occurred in the same precinct as the professional crowbar syndicate, definitively excluded via DNA.
* **Realistic Needle-in-a-Haystack Noise**: The majority of the 10,000 records comprise diverse background incidents, routine CCTV recordings, and unrelated forensic tests.

---

## 6. Offline Ground Truth Benchmark

Planted relationships are documented in `data/evaluation/ground_truth.json`.
This file is strictly for **offline evaluation** to measure precision, recall, and reasoning fidelity:
* It is **never** registered as a Zetaris table.
* It is **never** exposed to agent runtime APIs or query endpoints.
* Each scenario contains: `relationship_id`, `title`, `stations_involved`, `incident_ids`, `source_record_ids`, `why_related`, `supporting_evidence`, `contradictions_and_limitations`, and `confidence_label`.

---

## Live website

The website is a static React build on Vercel. It has no backend of its own and needs no secrets in Vercel:

```
Browser -> Vercel (static site) -> /api/... rewritten to a Cloudflare tunnel -> Docker container on the developer's machine
                                                                              -> Zetaris + Nightshift (Nemotron) + mounted Meterless engines (all private)
```

- **Live mode (default).** While the backend is up, investigations use live Zetaris SQL and live Nemotron models; `GET /api/engine/health` and `GET /api/health/zetaris` show the real state.
- **Offline fallback.** If the backend is unreachable (tunnel, Docker or the host is down), the page retries against `/offline-api`, a Vercel function that runs the same API in sample mode (bundled synthetic data, recorded Nemotron responses replayed and labelled).
  An amber banner says so, and the page recovers by itself when the live backend returns. Only the example questions replay recorded Nemotron answers; others use the labelled, weaker code-only fallback.
- **"Demo content"** (off by default) returns pre-built scenarios without running any agent.
- **Limits.** Live runs take about 70 to 120 s, close to the tunnel's timeout, so an occasional long run can be cut off; the tunnel URL of a quick tunnel changes on restart (`vercel.json` must then be updated); there is no access control on the live path.
  The site depends on the developer's machine being on. Judges should rely on the Docker path above for a deterministic result.

## Run with Docker

Everything below runs from a fresh clone. Config lives in **one place: `<repo root>/.env`** (copied from `.env.example`; gitignored and
excluded from every image). It is optional: with no `.env` the stack starts and `SAMPLE_MODE=true` needs no credentials at all.

```bash
git clone <your-repo-url> && cd <your-repo>
cp .env.example .env            # fill in your Zetaris and Nightshift settings (live mode only)

docker build -t oah-submission .            # or skip this and use yashasvir171/oah-submission:latest from Docker Hub
docker run --rm -p 8000:8000 --env-file .env oah-submission        # API on :8000

# in a second terminal
curl -X POST http://localhost:8000/run -H "Content-Type: application/json" -d @input_examples/example_1.json   # also example_2/3
curl http://localhost:8000/health        # zetaris / nightshift / engines: each "live", "sample" or "down"

# read the run
docker logs <container_id>               # every trace event is also printed to stdout as one `TRACE {...}` JSON line
docker exec <container_id> sh -c 'cat logs/trace-*.jsonl'          # the trace files live INSIDE the container...
docker run --rm -p 8000:8000 --env-file .env -v "$PWD/logs:/app/logs" oah-submission   # ...or mount ./logs to read them on the host
                                         # (on Linux add:  --user "$(id -u):$(id -g)"  so the container can write to ./logs)

# API + dashboard together:  API http://localhost:8000   web http://localhost:3001
docker compose build && docker compose up        # compose bind-mounts ./logs and ./.state for you

# Without your setup: Zetaris and Nightshift stopped, no credentials, no network
docker run --rm -p 8000:8000 --env-file .env -e SAMPLE_MODE=true oah-submission
docker run --rm -p 8000:8000 -e SAMPLE_MODE=true oah-submission                 # no .env at all
SAMPLE_MODE=true docker compose up
docker run -d --name offline --network none -e SAMPLE_MODE=true oah-submission  # no published port on --network none:
docker exec offline python scripts/judge_compare.py --url http://127.0.0.1:8000 # answers all three examples from inside

# Compare any running server's answers with output_examples/ (ignores timings, run ids and query ids)
python scripts/judge_compare.py --url http://localhost:8000
python run.py --once input_examples/example_1.json    # host alternative to curl
```

`POST /run` takes `{"run_id"?, "input": {"query", "incident_ids"?, "station_ids"?, "crime_type"?, "date_from"?, "date_to"?}, "options": {"sample_mode"?}}`
and returns exactly `run_id, status, output {links, report, stopping_reason, summary, ...}, agents, engines, trace_id, log_file, execution_time_seconds`
(an invalid body is HTTP 422).

**Live mode** reaches Zetaris (:8888/:8889) and Nightshift (:8088) running on the *host* through `host.docker.internal` (compose adds
`extra_hosts: host.docker.internal:host-gateway`, so this works on Linux too). Inside Docker these URLs are set for you; override with
`DOCKER_NIGHTSHIFT_BASE_URL`, `DOCKER_ZETARIS_BASE_URL`, `DOCKER_ZETARIS_AUTH_URL`. Every Zetaris and Nightshift call is bounded by its timeout
(`ZETARIS_TIMEOUT_SECONDS`, `NIGHTSHIFT_TIMEOUT_SECONDS`, `NIGHTSHIFT_SKEPTIC_TIMEOUT_SECONDS`) and the run by `WORKFLOW_MAX_ITERATIONS`,
`WORKFLOW_MAX_MODEL_CALLS`, `WORKFLOW_TIME_BUDGET_SECONDS`. If a service is down, `POST /run` continues that integration on the offline sample path and the
trace says so (`zetaris_fallback`, `source: local_sample`, `source: replayed` / `code_fallback`, `fallback_reason`).

**Nightshift token** - a container cannot read `~/Library/Application Support/ai.meterless.runtime/proxy-token`. Provide it either way:

| Option | How |
|---|---|
| Env var | `NIGHTSHIFT_API_KEY=<token>` in `.env` (or `docker run -e NIGHTSHIFT_API_KEY=...`) |
| Mounted file | `NIGHTSHIFT_API_KEY_FILE=<path in the container>`; with compose: `NIGHTSHIFT_TOKEN_FILE=<host file> docker compose -f docker-compose.yml -f docker-compose.token-file.yml up` |

**Meterless engines - what runs inside the container, and what does not**

| Engine | In the image | With the host engine directory mounted |
|---|---|---|
| H-MEM | open reference implementation (Apache-2.0, `third_party/meterless`, commit `1742dec`, unmodified) | Nightshift's `hmem.js` |
| Markovian | open reference implementation (same) | Nightshift's `markovian.js` |
| Scout Intent | **not available** - traced `engine_unavailable`; routing continues on deterministic rules | Nightshift's `scout-intents.js` |
| World Model | **not available** - traced `engine_unavailable`; shared state is skipped | Nightshift's `worldmodel.js` |

The Nightshift engine modules are proprietary and are **never copied into the repo or an image** (`worldmodel.js` is gitignored and in `.dockerignore`). To
run all four engines, mount the host directory read-only:

```bash
METERLESS_ENGINE_DIR_HOST=/Applications/Nightshift.app/Contents/Resources/engine/js/engine \
  docker compose -f docker-compose.yml -f docker-compose.engine.yml up
```

An engine that cannot run is recorded as `engine_unavailable` in the trace and in `engines[]`; the application never emits an engine event it did not execute.

**Sample mode** (`SAMPLE_MODE=true` or `options.sample_mode`) runs the *real* Planner -> retrieval -> Finder -> verifier -> Skeptic -> Reporter loop: retrieval is the
same four functions over `data/generated` (trace `source: local_sample`, generated query ids), and each model call is answered by a **recorded live Nemotron response**
matched by `sha256(role, model, prompt)` from `data/sample/model_fixtures/` (trace `source: replayed`; fixtures are never keyed to an example and never contain a
final answer). A prompt with no fixture runs a documented, clearly weaker code-only fallback (`source: code_fallback`, `reported_model: null`). Record fixtures on the host with `python scripts/record_fixtures.py` (needs live Zetaris + Nightshift; `--local-retrieval` records live models over local data), then rebuild the image and
regenerate `output_examples/` *inside it* (`docker run --rm -v "$PWD/output_examples:/app/output_examples" oah-submission python scripts/record_fixtures.py --outputs-only`) so the expected engine statuses match the judge's container. The old
pre-built scenarios survive only as `POST /api/investigations/analyze` with `"demo_content": true` (labelled `[DEMO CONTENT]`, no agent runs).

**Tests and scan**: `python -m pytest -q backend/tests && python -m pytest -q tests` (engine and live tests skip, not fail, when unavailable);
`sh scripts/secret_scan.sh [--image oah-submission]`.

---

## 7. How to Run & Validate

### 7.1 Setup Environment

```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 7.2 Run Automated Test Suites

```bash
# Run synthetic data generator tests (13 tests)
pytest -v tests/test_synthetic_data.py

# Run backend API and integration tests (unit + mocked + local-engine; live tests are skipped unless RUN_LIVE_TESTS=1)
pytest -v backend/tests/
```

### 7.3 Start the Application

```bash
# Terminal 1: Launch FastAPI Backend (runs on port 8000)
cd backend
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Launch React / Vite Dashboard (runs on port 5173)
cd frontend
npm run dev
```

Visit `http://localhost:5173` in your browser.

---

## 8. Backend API & Zetaris Integration Layer

The Python backend is built with **FastAPI** and **Pydantic**, providing typed response schemas and strict security boundaries.

### 8.1 Implemented Endpoints

| Category | Endpoint | Description |
| :--- | :--- | :--- |
| **Health** | `GET /api/health` | Application status, API version, and environment |
| **Health** | `GET /api/health/zetaris` | Zetaris data layer probe (`connected`, `not_configured`, `connection_failed`) |
| **Dashboard** | `GET /api/dashboard/summary` | Aggregated metrics: incident counts, station distributions, crime types, status, sources, timeline |
| **Incidents** | `GET /api/incidents` | Multi-filter pagination, search, station, crime type, status, date range, sorting |
| **Incidents** | `GET /api/incidents/{id}` | Detailed police incident record |
| **Evidence** | `GET /api/incidents/{id}/evidence` | Explicit cross-source evidence links (direct foreign keys vs. inferred spatio-temporal matches) |
| **Sources** | `GET /api/sources` | Metadata, record counts, and primary keys for all 5 registered tables |
| **Sources** | `GET /api/sources/{source}/records` | Paginated exploration of source-specific schemas |
| **Sources** | `GET /api/sources/{source}/records/{id}` | Individual source record payload |

### 8.2 Zetaris NDP Integration Adapter

The integration layer (`backend/app/services/zetaris_adapter.py`) isolates all Zetaris-specific connectivity:
- **Connection Status**: Transparently reports whether Zetaris is connected. When unconfigured, reports `NOT CONFIGURED` with active mode `local_fallback`.
- **Query Safety**: Search terms and IDs are sanitized (allow-list of characters) before being interpolated into SQL; all SQL is read-only `SELECT`. (They are not bound parameters.)
- **Fail-Safe Policy**: Never silently substitutes synthetic data when live Zetaris queries fail; explicitly tags responses with `data_mode`.
- **Ground Truth Isolation**: `data/evaluation/ground_truth.json` is completely isolated from all API routers and Zetaris queries.

### 8.3 Connecting to Live Zetaris NDP

To switch from `local_fallback` to live Zetaris execution:

1. Copy the template to the repo root: `cp .env.example .env`
2. Set your Zetaris connection (variable names as in `.env.example`):
   ```env
   ZETARIS_ENABLED=true
   ZETARIS_BASE_URL=http://localhost:8888
   ZETARIS_AUTH_URL=http://localhost:8889
   ZETARIS_USERNAME=<user>
   ZETARIS_PASSWORD=<password>      # or ZETARIS_API_TOKEN=<token>
   # Fully qualified table names are used as-is (leave ZETARIS_NAMESPACE empty); a bare name is prefixed with the namespace.
   ZETARIS_TABLE_POLICE_INCIDENTS=crime_police_db.police_incidents
   # ... likewise NEWSPAPER / WITNESS / CCTV / FORENSIC (find them with: SHOW TABLES IN <catalog>)
   ```
3. Restart the FastAPI backend. Test connectivity via `GET /api/health/zetaris` or the **Zetaris Layer** tab in the dashboard.


---

# Multi-Agent Investigation System

Everything below describes what is implemented and was verified on the development machine (macOS, Nightshift.app with the
Meterless engines installed, Zetaris running in Docker). Anything not verified is listed under **Known limitations**.

## 9. Architecture and data flow

```
Request ─► Scout Intent ─► (validate args, refuse/clarify/route)
              │
              ├─► H-MEM retrieve (prior vetted summaries: context only, never evidence)
              ├─► Markovian validate chunk config; World Model init
              ▼
        ┌──────────────────────── iteration (bounded) ────────────────────────┐
        │ Planner ──► retrieval requests                                       │
        │ Zetaris SQL (code, not a model) ──► incidents + supporting evidence  │
        │ Finder  ──► candidate links ──► World Model (new observation/rev)    │
        │ Deterministic verifier (Python) ──► SUPPORTED / WEAK / UNSUPPORTED   │
        │ Skeptic ──► objections / review status ──► World Model               │
        │ Markovian checkpoint (compact carryover, saved to disk)              │
        └── Skeptic or verifier asks for more? ──► next iteration (Planner) ───┘
              ▼
        Reporter (validated state only) ─► deterministic citation check
              ▼
        H-MEM store (only deterministic-verified, Skeptic-reviewed leads) ─► World Model run status
```

Stopping reasons: `evidence_sufficient`, `planner_concluded`, `no_new_evidence`, `no_supportable_links_found`,
`iteration_limit_reached`, `budget_exhausted` (model-call or time budget), `planner_blocked`, `finder_failed`,
`no_records_found`, `interrupted` (e.g. Zetaris went away; resumable). Defaults: 3 iterations, 24 model calls, 900 s.

| Agent | Role | Default model | Output contract |
|---|---|---|---|
| Planner | Plans retrieval; decides retrieve / conclude / blocked. Never claims records were found. | Lightning 30B A3B | `PlannerDecision` |
| Finder | Analyses records retrieved from Zetaris; proposes links with shared attributes, differences, missing evidence. Exact vs semantic match is labelled. | Lightning 30B A3B | `FinderOutput` |
| Skeptic | Attacks the links (not shown the Finder's score); contradictions, timelines, circularity, alternatives, missing-vs-contrary evidence; can request retrieval. | Nemotron 3 Ultra 550B A55B (falls back to Lightning and says so) | `SkepticReview` |
| Reporter | Writes from validated state only; cites IDs; separates facts from hypotheses. | Lightning 30B A3B | `ReportOutput` |

The deterministic verifier (`backend/app/services/evidence_verifier.py`) is not an agent. It checks that every cited incident/evidence ID exists
in the retrieved Zetaris records and matches its source type, that evidence is actually tied to the link's incidents, quotations appear
verbatim, claimed shared attributes appear in records tied to **both** incidents, stations match, timelines are compatible (missing times
are "indeterminate"), and that duplicate/derivative reports (same camera window, same witness observation, newspaper articles about a
police-recorded incident, repeat reports of one forensic item) are not counted as independent corroboration. Forensic `EXCLUSION`, witness
contradiction flags and CCTV-vs-witness vehicle colour conflicts are surfaced, never merged away. The Reporter's citations are re-checked
afterwards, and open Skeptic objections and contradictions are appended to the report even if the Reporter omitted them.

Scores such as `confidence_score` are **uncalibrated model heuristics**; the API and UI label them as such. No determination of guilt is made.

## 10. Meterless Engines: what is actually used

The engines are the real JavaScript modules shipped in `Nightshift.app/Contents/Resources/engine/js/engine/`, executed through Node
(`backend/app/services/meterless_world/runner.cjs` for World Model, `engine_runner.cjs` for the others). No SDK ships with them; the adapters call
their public `window.RT.*` functions.

| Engine | Module | Operations used in the live path | Where |
|---|---|---|---|
| World Model (shared state) | `worldmodel.js` | `init`/`stats`, `upsertEntity`, `appendObservation` (planner decisions, finder findings per revision, skeptic objections + review status, verifier results, reporter synthesis, run status), `snapshot` | `meterless_service.py` |
| H-MEM (persistent memory) | `hmem.js` | `retrieve` at start (context only); `mineAnswer` at end for deterministic-verified, Skeptic-reviewed SUPPORTED links with no open high-severity objection. H-MEM's own secret gate and confidence floor (0.6) apply; scope-isolated | `meterless_engines.py` (`HMemService`) |
| Scout Intent (routing) | `scout-intents.js` | `detectIntent` on every request; result recorded and used as a safety signal. The app maps requests to investigation intents with deterministic rules and validates every argument first | `ScoutIntentService` |
| Markovian (bounded runs) | `markovian.js` | `validateForRun`/`clampConfig` (chunk config from the iteration budget), `extractCarryover` (compact state through its marker rung, 800-token budget), `buildPrompt` (continuation frame, so later Planner calls get goal + carryover, not history), `computeRunEfficiency` | `MarkovianService` |

Design notes and honest limits:
- Markovian's `run()` loop is not used: it drives a single generator, whereas each iteration here spans several agents and SQL calls. The
  Python orchestrator runs the loop and uses Markovian's validated config, carryover cascade, continuation prompt and efficiency formula.
  Run state (`WorkingState`: objective, completed steps, retrieval requests, evidence references, validated findings, objections, outstanding
  tasks, next action, iteration, stopping reason) is saved to `.state/runs/<run_id>.json` and resumed with `continue_from`; evidence is
  rebuilt from Zetaris, not stored.
- Scout Intent's shipped registry (142 entries) targets software-development tasks and has no crime-investigation intents, so its label
  (e.g. `RESEARCH`) is a recorded signal, not the routing decision. Routing intents: `CROSS_STATION_SEARCH`, `COMPARE_INCIDENTS`,
  `INVESTIGATE_RELATIONSHIP`, `REVIEW_CONTRADICTIONS`, `CONTINUE_INVESTIGATION`, `CLARIFY`, `REFUSE`. Routing never executes anything and never bypasses Zetaris or the verifier.
- No official Meterless conformance/evaluation suites are present in the installed app bundle (the engine source files name
  `tests/*-conformance.test.mjs`, which are not shipped). The only engine-provided check run is Scout's built-in `scoutSelfTest` (<16 ms budget).
  Our own tests exercise the real engine modules; they are not Meterless's conformance suites.

## 11. Models verified through Nightshift

Verified on 2026-10-26 against `GET http://127.0.0.1:8088/v1/models` and real calls:

| Role / operation | Requested model | Result |
|---|---|---|
| Planner, Finder, Reporter (and fallback) | `nvidia/nemotron-3.5-lightning-30b-a3b` | Listed; real chat calls succeed (reported model = requested) |
| Skeptic | `nvidia/nemotron-3-ultra-550b-a55b` | Listed; real chat calls succeed (reported model = requested, ~20-40 s per Skeptic call). Needs Nightshift's per-request first-token limit raised: the client sends `meterless-ttfb-ms` (found in Nightshift's proxy source); without it larger prompts returned HTTP 504 and the registry fell back to Lightning |
| Semantic retrieval | `nvidia/nemotron-3-embed-1b` | Listed in `/v1/models`, **but `POST /v1/embeddings` returns HTTP 404 on the running Nightshift process**. Not enabled; not used in retrieval |
| Evidence reranking | Nemotron 3.5 Rerank 8B | **Not listed**, no rerank route found. Not enabled |
| Scout / lightweight planning | Nemotron 3.5 Bolt E4B | **Not listed.** Scout Intent runs as the deterministic JS engine; no LLM is used for routing |

Every model call records requested model, the model the response reports, provider, Nightshift receipt id, latency, token usage, whether a
fallback was used and why. `GET /api/models/registry?probe=true` shows the current verified assignment per role. Reports show per-agent
"answered by" models taken from responses, never from configuration. The API key stays in Nightshift's Providers configuration; the app only holds the local
Nightshift proxy token (read from the Nightshift runtime directory or `NIGHTSHIFT_API_KEY`) and never exposes it to the frontend or logs.

## 12. Zetaris tables and SQL retrieval

Tables (default namespace `lightning.ndp_filestore`, from `.env`): `police_incidents`, `cctv_reports`, `witness_reports`,
`forensic_reports`, `newspaper_reports`. Retrieval is executed by code in `zetaris_investigation_service.py` through the existing
`ZetarisAdapter`: per-station candidate search (`LIKE` on `method_description` / `property_involved`, optional crime type and date range, bounded `LIMIT`),
`get_incidents_by_ids`, `get_incidents_by_locations`, and supporting-evidence queries linked by incident ID or `location_id` (bounded per source).
Models only see a bounded, compacted subset (<= 14 incidents, <= 8 records per source); records are never invented by a model and every ID a model cites is re-checked.
Zetaris outages raise explicit errors (HTTP 502/503) when nothing was retrieved yet, or produce a resumable `interrupted` partial result.
Live mode never falls back to sample or local data.

## 13. Configuration reference (`<repo root>/.env`, copied from `.env.example`; a legacy `backend/.env` is still read)

| Variable | Default | Meaning |
|---|---|---|
| `ZETARIS_*` | see `.env.example` | Zetaris connection and table names |
| `NIGHTSHIFT_BASE_URL`, `NIGHTSHIFT_API_KEY`, `NIGHTSHIFT_API_KEY_FILE`, `NIGHTSHIFT_APP_NAME` | `http://127.0.0.1:8088/v1` (`host.docker.internal` in Docker), token from the key, else the file, else Nightshift's proxy-token (host runs only) | Nightshift endpoint/auth |
| `NIGHTSHIFT_MODEL` | `nvidia/nemotron-3.5-lightning-30b-a3b` | Default text model and fallback |
| `NIGHTSHIFT_MODEL_PLANNER` / `_FINDER` / `_REPORTER` | blank = Lightning | Per-role chat model |
| `NIGHTSHIFT_MODEL_SKEPTIC` | `nvidia/nemotron-3-ultra-550b-a55b` | Skeptic model (falls back to Lightning if unlisted/failing) |
| `NIGHTSHIFT_MODEL_EMBEDDING` / `_RERANK` | embed-1b / blank | Probed only; not used in retrieval |
| `NIGHTSHIFT_MODEL_FALLBACK`, `NIGHTSHIFT_SKEPTIC_TIMEOUT_SECONDS` | blank (= `NIGHTSHIFT_MODEL`), 180 | |
| `WORKFLOW_MAX_ITERATIONS` / `_MAX_MODEL_CALLS` / `_TIME_BUDGET_SECONDS` | 3 / 24 / 900 | Hard bounds (model-call budget is checked before each agent call; one agent call may use up to 3 requests for repair/fallback) |
| `WORKFLOW_RETRIEVAL_LIMIT`, `WORKFLOW_EVIDENCE_LIMIT_PER_SOURCE` | 10 / 8 | SQL result bounds |
| `METERLESS_ENGINE_DIR`, `METERLESS_WORLD_MODEL_PATH`, `METERLESS_WORLD_DIR` | Nightshift.app paths | Engine locations (in Docker: mount the host dir read-only at `/opt/meterless/engine`) |
| `METERLESS_ENGINE_BACKEND` | `auto` | `auto` (mounted if present, else the vendored open references for H-MEM/Markovian), `mounted`, or `reference` |
| `HMEM_ENABLED`, `HMEM_SCOPE`, `STATE_DIR` | true, `crime-intel`, `../.state` | Persistent memory scope and state dir (gitignored) |
| `SAMPLE_MODE` | false | Explicit offline sample mode (real agent loop, local data, replayed model responses) |
| `CORS_ALLOWED_ORIGINS` | localhost origins | Comma-separated browser origins allowed to call the API directly |

## 14. Run, test, verify

```bash
# Backend (needs Node on PATH and Nightshift.app installed)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000
# Frontend
cd frontend && npm install && npm run dev

# Tests: unit + mocked + local-engine (live tests skipped)
cd backend && python -m pytest -q
# LIVE integration tests (real Zetaris SQL, Nightshift calls, engines); the full-investigation test takes minutes
cd backend && RUN_LIVE_TESTS=1 python -m pytest -m live -v
# Baseline-vs-multi-agent evaluation (writes evaluation/results.json). With Zetaris + Nightshift configured it calls them; otherwise it uses a SCRIPTED
# offline stand-in for the models, which tests the pipeline/verifier/scoring mechanics, not model quality (the committed results.json is of this kind)
python scripts/evaluate_agents.py

# Verify integrations by hand
curl -s localhost:8000/api/models/registry?probe=true | jq .roles
curl -s localhost:8000/api/engines/health | jq .
curl -s localhost:8000/api/ai/diagnostic | jq .
curl -s -XPOST localhost:8000/api/investigations/analyze -H 'content-type: application/json' \
  -d '{"query":"Are INC-NORTH-0042 and INC-CEN-0118 related?"}' | jq '.run_status,.stopping_reason,.agents,.candidate_links'
```

Test taxonomy: `test_model_registry.py`, `test_evidence_verifier.py`, `test_nightshift_client.py` are unit tests with mocks or pure Python;
`test_engine_adapters.py` runs the real engine modules locally (no network); `test_multiagent_workflow.py` uses **mocked model outputs and a mocked Zetaris** with the
**real** World Model/Scout/H-MEM/Markovian engines; `test_investigation_workflow.py` covers the legacy baseline pipeline and the API with mocked Nightshift;
`test_live_integration.py` is the only live suite.

## 15. Sample mode

`SAMPLE_MODE=true` (or `"sample_mode": true` per request) runs the real agent loop offline: local retrieval over `data/generated`, recorded Nemotron responses replayed by
prompt hash, code-only fallback (labelled) for any prompt without a fixture, `data_mode: local_sample`. See **Run with Docker** above. The earlier pre-built scenarios
(`crowbar_safe_cracking`, `catalytic_converter`, `keyless_suv_relay`) are demo content only: `"demo_content": true`, `data_mode: demo_content`, no agent, model,
query or engine runs. `POST /api/investigations/analyze` in live mode still returns HTTP 503 when Zetaris or Nightshift is unconfigured; `POST /run` instead falls back, traced.

## 16. AI and Model Usage

All model calls go through Meterless Nightshift to NVIDIA Nemotron models (Lightning 30B A3B; Ultra 550B A55B for the Skeptic). Models plan,
analyse retrieved records, critique, and write the report. They do not access the database directly, and every ID, quotation and attribute they cite is
checked by deterministic code against Zetaris records. Model-generated hypotheses are labelled as hypotheses; scores are uncalibrated.
The data is fully synthetic (fictional stations, people and places). Claude Code (Anthropic) was used to help write this code.

## 17. Third-Party Code and Licences

- Python: FastAPI, Pydantic / pydantic-settings, Starlette, Uvicorn, httpx, python-dotenv, pytest (all permissive open-source licences).
- Frontend: React, Vite, TypeScript, lucide-react (MIT/ISC/Apache-style open-source licences).
- Zetaris NDP (Docker images, used under the licence supplied with them) and Meterless Nightshift + engine modules (proprietary: "Meterless Runtime - Proprietary Software License").
  The engines are **executed from the user's own Nightshift installation**.
- Meterless open reference implementations of H-MEM and Markovian (Apache-2.0, https://github.com/Meterless/Meterless commit `1742dec`) are vendored **unmodified** in
  `third_party/meterless/` with their LICENSE and a NOTICE (sha256 per file); our adapters around them are in `backend/app/services/meterless_world/reference/`.
- **Action needed before publishing this repository:** `backend/app/services/meterless_world/worldmodel.js` is a byte-for-byte copy of Meterless's proprietary
  `worldmodel.js`, kept as a fallback when Nightshift.app is absent. The Meterless licence grants no right to redistribute it without a written agreement; remove the copy (the adapter uses the installed engine first) or obtain permission.
