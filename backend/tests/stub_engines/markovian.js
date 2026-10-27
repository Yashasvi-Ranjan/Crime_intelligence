/* TEST DOUBLE (see STUB_ENGINES.txt) - not the Meterless Markovian engine. */
(function () {
  const RT = window.RT;
  const BOUNDS = { maxChunks: [1, 32], chunkSize: [1000, 64000], carryoverTokens: [100, 4000] };
  const clamp = (v, [lo, hi], d) => Math.min(hi, Math.max(lo, Number.isFinite(v) ? v : d));
  RT.markovian = {
    BOUNDS, DEFAULT_CONFIG: { chunkSize: 8000, maxChunks: 3, carryoverTokens: 800, overlapTokens: 0 },
    FINAL_MARKERS: [], STATE_MARKERS: ['[STATE_CHECKPOINT]'],
    clampConfig(c = {}) {
      return { chunkSize: clamp(c.chunkSize, BOUNDS.chunkSize, 8000), maxChunks: clamp(c.maxChunks, BOUNDS.maxChunks, 3),
        carryoverTokens: clamp(c.carryoverTokens, BOUNDS.carryoverTokens, 800), overlapTokens: c.overlapTokens || 0 };
    },
    validateForRun(c) {
      if (c.carryoverTokens * 4 >= c.chunkSize) throw new Error('carryover does not fit in chunk');
      return c;
    },
    buildPrompt: ({ prompt, carryover }) => `RESEARCH STATE\n[CARRYOVER STATE]\n${carryover || ''}\n${String(prompt || '').slice(0, 400)}`,
    async extractCarryover({ chunkText, budgetTokens = 800 }) {
      const i = String(chunkText).indexOf('[STATE_CHECKPOINT]');
      const body = i >= 0 ? String(chunkText).slice(i + 18).trim() : String(chunkText).slice(-budgetTokens * 4);
      return { strategy: i >= 0 ? 'marker' : 'tail', carryover: body.slice(0, budgetTokens * 4) };
    },
    detectMarker: () => null, cleanContent: (t) => t,
    computeRunEfficiency(chunks) {
      return { totalTokensUsed: chunks.reduce((a, c) => a + (c.tokens || 0), 0), chunks: chunks.length };
    },
  };
})();
