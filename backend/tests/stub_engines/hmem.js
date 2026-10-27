/* TEST DOUBLE (see STUB_ENGINES.txt) - not the Meterless H-MEM engine. Keyword-overlap retrieval only. */
(function () {
  const RT = window.RT;
  const KEY = 'stub_hmem_records';
  const SECRET = /(nvapi-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{10,}|api[_-]?key\s*[:=])/i;
  let records = [];
  const words = (s) => new Set(String(s || '').toLowerCase().match(/[a-z0-9]{3,}/g) || []);
  const hmem = {
    async load() { records = (await RT.storage.load(KEY, [])) || []; },
    retrieve({ prompt, scope, k = 3, minScore = 0.35 }) {
      const q = words(prompt);
      return records.filter((r) => r.scope === scope).map((r) => {
        const w = words(r.content); let n = 0; q.forEach((x) => { if (w.has(x)) n++; });
        return { ...r, score: q.size ? n / q.size : 0 };
      }).filter((r) => r.score >= minScore).sort((a, b) => b.score - a.score).slice(0, k);
    },
    reinjectionBlock: (hits) => hits.map((h) => `- ${h.content}`).join('\n'),
    mineAnswer({ prompt, answer, scope, confidence, model, receiptId }) {
      if (!answer || SECRET.test(answer) || (confidence ?? 0) < RT.data.setpoints.hmemMinConfidence) return null;
      const rec = { id: `stub_${records.length + 1}`, content: answer, confidence, scope, tags: [], timestamp: 0,
        domain: 'stub', entities: [], source: { kind: 'stub', model, receiptId } };
      records.push(rec); RT.memory.ledger('create', rec.id, {}); RT.storage.save(KEY, records); return rec;
    },
    noteWrong() {}, noteHelpful() {},
    stats: () => ({ records: records.length }),
    clearAll() { records = []; RT.storage.save(KEY, records); },
  };
  RT.hmem = hmem;
})();
