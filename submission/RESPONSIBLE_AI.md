# AI usage and responsible-AI notes

## Where AI is used
1. **Inside the product:** NVIDIA Nemotron models through Meterless Nightshift act as the Planner, Finder, Skeptic and Reporter. They plan retrieval, propose and attack candidate links between incidents, and write the report. They do not access the database, and nothing they say is trusted without a code check.
2. **To build it:** the code was written with help from **Claude Code (Anthropic)**. The team directed the work and reviewed and ran the results; the test suite and the offline Docker flow are run in CI; the team reports it also ran the live Zetaris/Nightshift flow by hand (no live trace is committed).

## What the system is for, and what it is not
It helps an analyst *find leads*: records at different stations that may belong to one series. It does **not** identify people, predict crime, score individuals, or make any determination of guilt. Output is labelled "lead / candidate link"; the report says so, and a human decides what to do.

## Design choices that limit harm
- **Models cannot invent evidence.** Every incident id, evidence id, quotation and attribute a model cites is re-checked in code against the retrieved records. Ungrounded citations are dropped or flagged, and the response says so.
- **A second model attacks the first.** The Skeptic runs on a different, larger model, is not shown the Finder's confidence, and may demand more retrieval. Open objections cannot be removed from the report.
- **"No" is allowed.** Without independent corroboration the answer is "no supportable link", with the reason. Duplicate or derivative reports are never counted as corroboration, and contradictions (a forensic exclusion, a witness/CCTV colour conflict) are surfaced, not merged away.
- **Honest numbers.** Scores are labelled "uncalibrated heuristic, not a probability". Nothing is presented as accuracy it has not earned.
- **Transparent degradation.** If a model or service is unavailable the run says which part fell back, in the trace (`fallback_reason`, `source: replayed | code_fallback | local_sample`) and the response. A replayed or code-generated step is never presented as a live model call.
- **Bounded and auditable.** Hard caps on iterations, model calls and time; read-only SQL; one JSONL trace per run (agents, handoffs, query ids, engine events, requested and answering model).
- **Memory is gated.** H-MEM stores only leads that passed the verifier and the Skeptic, behind a secret gate and a confidence floor; prior memory is context, never evidence.
- **Privacy and secrets.** All data is synthetic. No tokens reach the frontend or logs; a secret scan covers the repo and the Docker image; `.env` is never in the image.

## Known limitations and risks
- **Bias.** Linking depends on what was recorded and how. A real deployment would inherit recording and reporting biases (e.g. which areas are patrolled, how officers describe methods). We have not measured fairness because the data is synthetic.
- **Conservative results.** On the three judge examples with recorded Nemotron responses, the system produced three WEAK links for the catalytic-converter question and "no supportable link" for the other two, because the retrieved evidence did not independently corroborate the series. This is the verifier working as designed, but it also means recall on the planted series is not demonstrated by these runs.
- **Benchmark caveat.** `evaluation/results.json` was produced with a scripted offline stand-in for the models (hand-written planner/finder logic), not with Nemotron. It tests the pipeline, verifier and scoring mechanics, not model quality, and must not be read as a model benchmark. Seven cases at one run each is also too small to be statistically meaningful.
- **Model behaviour varies.** Model outputs are non-deterministic; offline sample mode replays recorded responses for reproducibility, and prompts without a recording use a weaker, labelled code-only fallback.
- **Heuristic verifier.** Its contradiction and duplicate checks cover the patterns in our data, not all real-world patterns.
- **Scope.** Synthetic data, three stations, five sources. Moving to real data would need legal basis, consent and oversight, a privacy and bias review, calibrated confidence, and a human-in-the-loop policy.
