// Adapter: our engine-runner ops -> Meterless's open Markovian reference implementation (third_party/meterless/markovian).
// This file is ours; the vendored sources it imports are unmodified. Bundled by scripts/build_reference_engines.sh.
//
// Ops (same names and result shapes as the mounted-engine runner, see meterless_engines.MarkovianService):
//   validate          {config}                                  -> {config}   (throws on out-of-bounds, never clamps silently)
//   build_prompt      {mode, isFirst, prompt, carryover, ...}   -> {prompt}
//   extract_carryover {chunkText, prevCarryover, budgetTokens}  -> {carryover, strategy}  (marker -> heuristic -> truncation)
//   efficiency        {chunks: [{tokens}], config}              -> run efficiency numbers
// The reference's own run() loop is not used: the Python orchestrator runs the loop, as with the mounted engine.

import { CarryoverService, buildPrompt, parseMarkers, resolveConfig, runEfficiency } from "../../../../../third_party/meterless/markovian/src/index.ts";

export async function handle(op: string, args: any): Promise<{ result: any; audit: any[] }> {
  if (op === "validate") {
    return { result: { config: resolveConfig(args.config ?? {}) }, audit: [] };
  }
  if (op === "build_prompt") {
    const prompt = buildPrompt({
      mode: args.mode === "ARCHITECT" ? "ARCHITECT" : "RESEARCH", goal: String(args.prompt ?? ""), step: args.isFirst ? 1 : 2,
      carryover: String(args.carryover ?? ""), overlapText: String(args.overlapText ?? ""), memoryContext: args.memoryContext,
      attachments: [], config: resolveConfig({}),
    });
    return { result: { prompt }, audit: [] };
  }
  if (op === "extract_carryover") {
    const chunkText = String(args.chunkText ?? "");
    const r = await new CarryoverService().next({
      markerState: parseMarkers(chunkText).state, previousCarryover: String(args.prevCarryover ?? ""), chunkText,
      config: resolveConfig({ carryoverTokens: args.budgetTokens ?? 800 }),
    });
    return { result: { carryover: r.carryover, strategy: r.level }, audit: [] };
  }
  if (op === "efficiency") {
    return { result: runEfficiency(args.chunks ?? [], resolveConfig(args.config ?? {})), audit: [] };
  }
  throw new Error(`unknown markovian op: ${op}`);
}
