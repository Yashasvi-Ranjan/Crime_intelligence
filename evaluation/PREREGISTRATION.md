# Pre-registration: AEGIS (Nemotron via Nightshift) vs a Lightning-only baseline

**Status: not yet run.** Live execution date: not yet run. No live Nemotron result exists for this protocol.
This file is committed before any live run. Any change after the first live run must be a new, dated amendment
section at the bottom; the original text is never edited. Results from the scripted stand-in
(`evaluation/results.json`, stamped NOT A MODEL BENCHMARK) are not evidence for any hypothesis below.

## 1. Question and hypotheses

Does the multi-agent AEGIS pipeline (Planner, Finder, Skeptic, Reporter with the evidence verifier) produce more
trustworthy cross-station links than the single-pass Lightning-only pipeline, when both use real Nemotron models
through Nightshift on the same retrieved records?

- **H1 (precision of supported links):** AEGIS supported-link precision is higher than the baseline's.
- **H2 (recall):** AEGIS supported-link recall is not worse than the baseline's by more than 0.10 (absolute).
- **H3 (false links):** AEGIS false-link rate is lower than the baseline's.
- **H4 (decoys):** AEGIS rejects planted decoys at a rate at least equal to the baseline's, and at least 0.80 itself.
- **H0:** no difference. A result that supports H0 or the reverse is reported as is.

## 2. Systems compared

Both run through the same Nightshift account, the same production retrieval path (live Zetaris via
`ZetarisInvestigationService`), the same case set, and the same per-case time budget.

| System | What it is |
|---|---|
| `multi_agent_nemotron` | `InvestigationWorkflow` with the default role routing: Planner and Skeptic on `nvidia/nemotron-3-ultra-550b-a55b`, Finder and Reporter on `nvidia/nemotron-3.5-lightning-30b-a3b`, evidence verifier on, iteration/call budgets from `backend/app/config.py` (3 iterations, 24 calls, 900 s). |
| `baseline_lightning_only` | `LegacyInvestigationWorkflow`, the pre-existing single-pass pipeline (plan, retrieve, analyse, evaluate with at most the built-in revisions, report) on the Lightning model only. Same prompts as production, no edits for this study. |

Fairness rules for the baseline:

1. It is the unmodified legacy production pipeline, not a degraded copy, and it receives the same incident IDs and
   the same retrieval service as AEGIS.
2. It uses a real model. A baseline run whose model calls all failed is reported as a failed run, not scored as a
   baseline result.
3. The legacy pipeline can emit a code-only fallback link (`confidence_rationale` containing "adjacent county
   jurisdictions") when no model link passes. To keep the comparison from being driven by that fallback, every
   metric is reported twice: as emitted (primary) and with fallback links removed from the baseline
   (`preregistered_excluding_baseline_code_fallback`). H1 to H4 must hold under both views to be called supported.
4. The same independent re-verification (`verify_link`) is applied to both systems' outputs when deciding what is
   "supported"; the system's own `validation_status` is not used.

## 3. Case sets

All cases are incident-ID sets drawn from the synthetic data in `data/generated/` and its planted ground truth
(`data/evaluation/ground_truth.json`, read only by the harness). Truth for a case is the set of incident pairs
that belong to the same planted relationship; every other pair is false.

- **Development set (`dev`, 7 cases):** the original cases. The scripted stand-in and any prompt or threshold
  tuning were written against these, so they are not held out. Tuning is allowed only on `dev`.
- **Held-out set (`heldout`, 12 cases):** built by `evaluation/harness.py::build_heldout_cases` with seed
  **7919**. Frozen: the case-set hash below must match the hash stamped in the live result, or the run is invalid.
  - Case-set SHA-256 (heldout): `887952a4fec510fcd08084cd819845796a017e42edc74a9c18477822a9d5bdca`
  - `H-POS-*` (5): a full planted series plus one background incident (same crime type, other station) as a foil.
  - `H-DEC-006-S002`, `H-DEC-008-S003`, `H-DEC-BOTH-S007` (3): planted distractor incidents mixed into series
    pairs that `dev` did not pair them with.
  - `H-NEG-1..3` (3): three unrelated background incidents from three stations; no true link exists.
  - `H-CROSS-001-002-004` (1): one incident from each of three different planted series; no true link exists.
  - 12 true pairs in total; 12 cases contain at least one foil; 3 contain a planted decoy.
- **Limitation, stated up front:** held-out here means held out of tuning and frozen by hash, not drawn from an
  independent data source. The held-out cases reuse the same generator, the same planted series and the same
  records as `dev`. The data is synthetic, so results do not transfer to real police data. With 12 cases the
  intervals are wide; Wilson 95% intervals are reported and no significance test is claimed.

## 4. Metrics (definitions)

Computed in `evaluation/harness.py`, micro-aggregated over the cases of a split. A pair is an unordered pair of
incident IDs. "Reported" = active (non-withdrawn) links in the final output. "Supported" = reported links whose
independent re-verification status is SUPPORTED (WEAK and UNSUPPORTED do not count).

- **Supported-link precision** = supported true pairs / supported pairs.
- **Supported-link recall** = supported true pairs / true pairs.
- **Reported precision and recall** = the same, over all reported links (no verification filter).
- **False-link rate** = reported pairs not in truth / reported pairs.
- **Foil rejection rate** = cases with at least one foil in which no reported link touches a foil / cases with a foil.
- **Planted-decoy rejection rate** = same, restricted to cases with a planted distractor incident.
- Secondary, descriptive only: run failure rate, mean latency, model calls, citation accuracy, links not
  supported on re-verification, contradictions surfaced.

A ratio with a zero denominator is reported as null, never as 0 or 1.

## 5. Decision rules

On the held-out set, under both views in section 2 rule 3:

- **H1 supported** if AEGIS supported precision exceeds the baseline's by at least 0.10 (point estimate; no
  interval-overlap test is required, and the full counts and Wilson intervals are shown).
- **H2 supported** if AEGIS supported recall is at least the baseline's minus 0.10.
- **H3 supported** if AEGIS false-link rate is at least 0.10 below the baseline's.
- **H4 supported** if AEGIS planted-decoy rejection is at least 0.80 and at least the baseline's.
- The overall claim "AEGIS beats a Lightning-only baseline" is made only if H1, H2, H3 and H4 are all supported.
  Otherwise the claim is not made; the mixed result is published as is.

## 6. What counts as failure, and invalid runs

- **Failure of the system:** any decision rule not met; more than 2 of 12 AEGIS runs failing (`ok: false`); any
  AEGIS output citing an ID that does not exist in the data; any link in AEGIS output shown as SUPPORTED that
  re-verification marks UNSUPPORTED.
- **Invalid run (discard and re-run, disclosed):** case-set hash mismatch; preregistration hash mismatch; any
  model call without a Nightshift receipt id in the live result; results produced in `--offline-standin` mode;
  missing credentials (the harness exits before running).
- No case, metric, threshold or system change after the first live run. No re-running individual cases until they
  pass; if a run is repeated, all attempts are kept and reported.

## 7. Procedure and provenance

1. `python scripts/evaluate_agents.py --live` (default case set `heldout`), see `evaluation/README.md`.
2. The output (`evaluation/results_live.json`) starts with a provenance block: mode, git commit and dirty flag,
   case-set hash, preregistration file hash, ground-truth and incident-data hashes, UTC date, and the models that
   actually answered (only calls carrying a Nightshift receipt id count).
3. Live results are published unedited alongside this file, including failures.

## 8. Not yet done

Live execution requires Nightshift and Zetaris credentials that were not available when this protocol was written.
As of writing: **no live run has been performed and there are no live results.**
