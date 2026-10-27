/* TEST DOUBLE (see STUB_ENGINES.txt) - not the Meterless Scout Intent engine. */
(function () {
  const RT = window.RT;
  const DESTRUCTIVE = /\b(rm -rf|delete|drop|truncate|wipe|erase|destroy)\b.{0,40}\b(table|database|records?|data|logs?|memory|state|evidence|node_modules)\b/i;
  RT.SCOUT_INTENTS = [{ id: 'STUB_DESTRUCTIVE', tier: 'A' }, { id: 'STUB_GENERAL', tier: 'B' }];
  RT.detectIntent = function (text) {
    const t0 = Date.now();
    const hit = DESTRUCTIVE.test(String(text || ''));
    return { mode: hit ? 'DESTRUCTIVE' : 'GENERAL', score: hit ? 1 : 0.1, candidates: [], ms: Date.now() - t0 };
  };
  RT.intentTierHint = (mode) => (mode === 'DESTRUCTIVE' ? 'A' : 'B');
  RT.scoutSelfTest = () => 0;
})();
