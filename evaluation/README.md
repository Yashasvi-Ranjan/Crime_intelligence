# Evaluation

Protocol: [PREREGISTRATION.md](PREREGISTRATION.md) (committed before any live run).

**Live result: pending.** No run with real Nemotron through Nightshift has been performed yet.
`results.json` is from the scripted stand-in and is stamped `NOT A MODEL BENCHMARK`; it tests the pipeline, the
verifier and the scoring, not model quality. Its baseline is a code-only fallback (no model), so its numbers must
not be read as a comparison of AEGIS with a Lightning-only baseline.

## Run it live (needs Nightshift and Zetaris credentials)

```bash
cp .env.example backend/.env   # fill in NIGHTSHIFT_* and ZETARIS_* values; never commit them
python scripts/evaluate_agents.py --live
```

Defaults to the frozen held-out set (12 cases, including decoys) and writes `evaluation/results_live.json`,
whose first block is the provenance stamp (mode, git commit, case-set hash, date, models actually called).
Without credentials the command exits immediately with a message; it never falls back to the stand-in.
Check that the stamped `case_set_hash` equals the one in PREREGISTRATION.md.

## Offline stand-in (no credentials, no model)

```bash
python scripts/evaluate_agents.py --offline-standin     # writes evaluation/results.json
```

The stand-in calls no model, so it emits no receipts or model names. Tests: `pytest tests/test_evaluation_harness.py`.
