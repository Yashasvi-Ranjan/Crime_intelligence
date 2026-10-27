# Decision memory

H-MEM stores summaries of verified leads. `backend/app/services/decision_memory.py` adds a deterministic layer that lets
those prior leads change a later run's retrieval, with the effect recorded.

**Write gate (unchanged).** A lead is written only if the verifier marked the link SUPPORTED, the Skeptic review
completed, and no high-severity objection is open. `DecisionMemory.write_verified` re-checks `status == SUPPORTED` and
refuses links flagged with an open high objection. Verifier-REJECTED or Finder-withdrawn links are written as separate
`rejected` records that can only suppress.

**Read effect (iteration 1 only, no model involved).** If the new question shares incident IDs or shared-attribute tokens
(e.g. `chisel-tip`) with a prior verified lead, that lead's incident IDs are fetched first as a `by_incident_ids` request
(a starting hypothesis). A prior rejected pair matching the question is flagged and its verified lead is not used.
The Planner prompt also receives `memory_influence` (only when non-empty, so empty memory leaves prompts unchanged).

**Auditability.** Each run response has `memory_influence` (`applied`, `starting_hypotheses`, `flagged_rejected`,
`priority_incident_ids`, `source_memory_ids`); the trace has a `memory_influence` event; the retrieval request reason
names the `DMEM-` ids.

**Never evidence.** Memory ids (`DMEM-...`) have no source type, so the verifier drops them. Prior evidence IDs not
retrieved in the current run are not in the index and are dropped too. The Finder, verifier and Skeptic run unchanged, so
memory cannot raise a link to SUPPORTED or count as an independent source.

Tests: `backend/tests/test_memory_decision.py` (scripted models and fake Zetaris; real H-MEM engine and verifier).
Not covered: no live-model run showing a changed outcome; matching is lexical (IDs and attribute tokens), not semantic.
