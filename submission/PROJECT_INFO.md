# Project information

**Track:** Solving Fragmented Intelligence · **Event:** Open Agent Hackathon 2026

## Project name
**AEGIS: Cross-Station Crime Intelligence**

## One-liner
Agents that link crimes across police stations, and show the evidence, the doubts and the missing pieces behind every link.

## Short description (about 50 words)
Three police stations hold the same offender's fingerprints in different silos. AEGIS lets a detective ask one question; a Planner, Finder, Skeptic and Reporter search five Zetaris-federated sources with NVIDIA Nemotron through Nightshift, and a deterministic verifier re-checks every ID and quote. It returns leads, not verdicts, and can answer "no supportable link".

## Long description

**The problem.** Crime does not respect station boundaries, but records do. A burglar who pries open an office safe in NORTH on Monday and another in CENTRAL on Thursday leaves two incident files in two systems, plus CCTV, witness statements, forensic reports and press coverage scattered across more. Almost none of it carries an explicit link, so the pattern is only visible to someone who reads everything. Real evidence also conflicts: witnesses disagree, night footage is poor, forensics can exclude a suspected link, and some look-alike incidents are decoys.

**What we built.** AEGIS takes one plain-language question ("Are the safe burglaries across NORTH and CENTRAL linked by the same pry bar?") and runs a bounded, multi-agent investigation:

1. **Scout Intent / routing** classifies and validates the request (and refuses destructive ones).
2. **Planner** (Nemotron 3.5 Lightning) decides what to retrieve. It never claims anything was found.
3. **Retrieval is code, not a model.** Read-only SQL over five Zetaris tables (police incidents, CCTV, witness, forensic, newspaper) with bounded limits; every query id is traced. Candidates are relevance-scored rather than newest-first: a bounded candidate pool per query, an IDF-weighted re-rank, and reserved slots for corroborated incidents, so older planted incidents are no longer crowded out (one planted incident, INC-NORTH-0294, is still missed; the new SQL has been tested only against the local-sample mirror, not live Zetaris).
4. **Finder** (Lightning) proposes cross-station links with shared attributes, differences and missing evidence.
5. **A deterministic verifier** checks that every cited ID exists and matches its source type, that quotes are verbatim, that shared attributes appear in records tied to **both** incidents, that stations and timelines agree, and that duplicate reports (the same camera window, one witness reported twice, a newspaper article about a police-recorded incident) are **not** counted as independent corroboration. Each link is labelled SUPPORTED, WEAK or UNSUPPORTED.
6. **Skeptic** (Nemotron 3 Ultra 550B, a separate model, never shown the Finder's confidence) attacks the links and can send the Planner back for more evidence.
7. **Reporter** writes from validated state only; its citations are re-checked and open objections cannot be dropped.

The loop is bounded (3 iterations, 24 model calls, 900 s by default), checkpoints with Meterless Markovian so a run can be resumed, recalls and stores only vetted leads with Meterless H-MEM (a prior verified lead can change a later run's retrieval order as a starting hypothesis; that effect is attributed in the response and trace as `memory_influence`, and memory is never evidence: it cannot raise a link to SUPPORTED), and records every step, handoff, model call (requested and answering model, receipt id), query id and engine event in `logs/trace-<run_id>.jsonl`.

**What it honestly does.** It proposes *leads*, never findings of guilt. Scores are labelled uncalibrated heuristics. On our synthetic county (10,000 records, 3 stations, 8 planted relationships including 2 decoys), the recorded Nemotron runs shipped as the judge examples (recorded before the retrieval change above) are conservative: the catalytic-converter question returns three WEAK links with the reasons a series cannot be asserted, and the safe-burglary and keyless-relay questions end in "no supportable link" because no corroborating independent evidence was retrieved. The retrieval change altered the candidate sets, so some recorded responses no longer match their prompts; offline, those prompts now fall back to the labelled code-only path and the links differ from the committed examples (the three examples now yield 0, 1 and 1 links offline). The examples were not re-recorded; that needs live Nightshift credentials. We state that plainly rather than present it as a win; the verifier's job is to refuse what the evidence does not support.

**One command to see it.** `docker build -t oah-submission . && docker run -p 8000:8000 -e SAMPLE_MODE=true oah-submission` runs the same agent loop offline, with no credentials and no network: retrieval over the bundled synthetic data and recorded Nemotron responses replayed by prompt hash, each labelled `replayed` in the trace; prompts with no matching recording use a labelled code-only fallback.

**Data.** Fully synthetic: fictional stations, people and places. No real personal data is used anywhere.
