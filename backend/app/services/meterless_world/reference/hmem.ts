// Adapter: our engine-runner ops -> Meterless's open H-MEM reference implementation (third_party/meterless/hmem).
// This file is ours; the vendored sources it imports are unmodified. Bundled by scripts/build_reference_engines.sh.
//
// Ops (same names and result shapes as the mounted-engine runner, see meterless_engines.HMemService):
//   retrieve {prompt, scope, app, k, minScore}  -> {hits: [...], reinjection}
//   mine     {prompt, answer, scope, app, intent, confidence, model, receiptId} -> {stored, id, domain, entities}
//   stats    {} -> counts
// Gates applied by this adapter (the reference library has none): a confidence floor of 0.6 and a secret gate,
// so only vetted, non-secret text is ever stored.

import path from "node:path";
import { HMEM } from "../../../../../third_party/meterless/hmem/src/index.ts";

const MIN_CONFIDENCE = 0.6;
// The reference's lexical scorer rates a near-duplicate ~0.33, below the 0.35 default tuned for the mounted engine's
// scorer. Retrieved memory is context only (never evidence), so this adapter uses a slightly lower default.
const DEFAULT_MIN_SCORE = 0.25;
const SECRETS = [/nvapi-[A-Za-z0-9_-]{20,}/i, /sk-[A-Za-z0-9_-]{20,}/i, /Bearer\s+[A-Za-z0-9_.\-]{25,}/i, /password\s*[:=]\s*\S{6,}/i];

interface Ctx { storeFile?: string }

export async function handle(op: string, args: any, ctx: Ctx): Promise<{ result: any; audit: any[] }> {
  const persistDir = ctx.storeFile ? path.join(path.dirname(ctx.storeFile), "hmem-reference") : undefined;
  const h = new HMEM({ persistDir, actor: "crime-intel" });
  const ledgerBefore = h.ledger.all().length;
  const audit = () => h.ledger.all().slice(ledgerBefore).map((e) => ({ action: e.action, subject: e.memoryId, details: e.details ?? {} }));

  if (op === "retrieve") {
    const scopeTag = `scope:${args.scope ?? "default"}`;
    const q = h.query(String(args.prompt ?? ""), { topN: (args.k ?? 3) * 3, threshold: args.minScore ?? DEFAULT_MIN_SCORE });
    const hits = q.memories.filter((m) => m.memory.tags.includes(scopeTag)).slice(0, args.k ?? 3).map((m) => ({
      id: m.memory.id, content: m.memory.content, confidence: m.memory.confidence, score: m.relevance,
      scope: args.scope, tags: m.memory.tags,
      source: { kind: m.memory.provenance.origin, model: m.memory.source, receiptId: (m.memory.provenance.refs ?? [])[0] ?? null },
      timestamp: m.memory.timestamp,
    }));
    h.store.persist();
    return { result: { hits, reinjection: hits.length ? q.context : null }, audit: audit() };
  }

  if (op === "mine") {
    const answer = String(args.answer ?? "");
    const confidence = Number(args.confidence ?? 0);
    const reject = (why: string) => ({ result: { stored: false, id: null, domain: null, entities: [] }, audit: [{ action: "reject", subject: why, details: {} }] });
    if (confidence < MIN_CONFIDENCE) return reject("confidence_floor");
    if (SECRETS.some((re) => re.test(answer) || re.test(String(args.prompt ?? "")))) return reject("secret_gate");
    const rec = h.add({
      content: answer, type: "factual", layer: "working", confidence,
      tags: [`scope:${args.scope ?? "default"}`, `app:${args.app ?? "default"}`, `intent:${args.intent ?? "investigation"}`],
      source: String(args.model ?? "crime-intel"),
      provenance: { origin: "model_response", learnedAt: Date.now(), label: String(args.prompt ?? "").slice(0, 120), refs: args.receiptId ? [String(args.receiptId)] : [] },
    });
    h.store.persist();
    return { result: { stored: true, id: rec.id, domain: rec.domain, entities: rec.entities }, audit: audit() };
  }

  if (op === "stats") {
    return { result: { records: h.store.all().length, ledger: h.ledger.stats(), implementation: "meterless-hmem-reference@1742dec" }, audit: [] };
  }
  throw new Error(`unknown hmem op: ${op}`);
}
