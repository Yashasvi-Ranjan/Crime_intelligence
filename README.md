# Cross-Station Crime Intelligence: Synthetic Data Generator

> **Open Agent Hackathon 2026** — *Solving Fragmented Intelligence & Multi-Station Investigation*

This repository contains the synthetic data generation pipeline and validation suite for the **Cross-Station Crime Intelligence** system. It produces a reproducible, multi-source synthetic intelligence dataset comprising exactly **10,000 fictional records across five JSON files**, accompanied by an offline ground-truth evaluation benchmark.

These datasets are designed to be ingested into **Zetaris NDP File Store** and queried as unified tables to power agentic reasoning across siloed law enforcement jurisdictions.

---

## 1. Project Directory Structure

```text
cross-station-crime-intelligence/
├── data/
│   ├── generated/
│   │   ├── police_incidents.json      # 3,000 records
│   │   ├── newspaper_reports.json     # 1,500 records
│   │   ├── witness_reports.json       # 2,000 records
│   │   ├── cctv_reports.json          # 2,000 records
│   │   └── forensic_reports.json      # 1,500 records
│   └── evaluation/
│       └── ground_truth.json          # Offline planted relationships benchmark
├── scripts/
│   └── generate_synthetic_data.py     # Deterministic data generation script
├── tests/
│   └── test_synthetic_data.py         # Pytest verification and schema validation
├── requirements.txt
└── README.md
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

# Run backend API and integration tests (16 tests)
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
- **Query Safety**: Uses parameterized queries and sanitized column filters to prevent injection.
- **Fail-Safe Policy**: Never silently substitutes synthetic data when live Zetaris queries fail; explicitly tags responses with `data_mode`.
- **Ground Truth Isolation**: `data/evaluation/ground_truth.json` is completely isolated from all API routers and Zetaris queries.

### 8.3 Connecting to Live Zetaris NDP

To switch from `local_fallback` to live Zetaris execution:

1. Copy `backend/.env.example` to `backend/.env`:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Configure your Zetaris connection parameters:
   ```env
   ZETARIS_ENABLED=true
   ZETARIS_BASE_URL=https://<your-zetaris-ndp-host>:<port>
   ZETARIS_AUTH_MODE=token
   ZETARIS_TOKEN=<your-bearer-token>
   ZETARIS_DATABASE=default
   ```
3. Restart the FastAPI backend. Test connectivity via `GET /api/health/zetaris` or the **Zetaris Layer** tab in the dashboard.
