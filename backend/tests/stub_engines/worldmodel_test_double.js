/* TEST DOUBLE (see STUB_ENGINES.txt) - not the Meterless World Model engine. Entities + immutable observations only. */
(function () {
  const hash = (s) => { let h = 5381; for (const c of String(s)) h = ((h * 33) ^ c.charCodeAt(0)) >>> 0; return h.toString(16).padStart(8, '0'); };
  const memoryAdapter = () => ({ map: new Map() });
  const fileAdapter = (filePath, fs) => {
    let map = new Map();
    try { map = new Map(JSON.parse(fs.readFileSync(filePath, 'utf8'))); } catch (_) {}
    return { map, flush: () => fs.writeFileSync(filePath, JSON.stringify([...map])) };
  };
  function createWorld({ name, adapter }) {
    const m = adapter.map;
    const entries = () => [...m].map(([k, v]) => [k, v]);
    return {
      async upsertEntity(e) {
        const id = 'ent_' + hash(`${e.type}:${String(e.name).toLowerCase()}`) + hash(e.name);
        const ent = { ...e, id, schemaVersion: 1 };
        m.set(`${name}/entity/${id}`, JSON.stringify(ent)); return ent;
      },
      async getEntity(id) { const v = m.get(`${name}/entity/${id}`); return v ? JSON.parse(v) : null; },
      async appendObservation(o) {
        const key = `${name}/obs/${o.id}`;
        if (!m.has(key)) m.set(key, JSON.stringify({ ...o, schemaVersion: 1 }));   // immutable, de-duplicated by id
        return JSON.parse(m.get(key));
      },
      async buildContext() { return { entities: entries().filter(([k]) => k.includes('/entity/')).length }; },
      async stats() { return { schemaVersion: 1, entities: entries().filter(([k]) => k.includes('/entity/')).length,
        observations: entries().filter(([k]) => k.includes('/obs/')).length }; },
      async snapshot() { return JSON.stringify(entries()); },
    };
  }
  window.RT = window.RT || {};
  window.RT.world = { sha256Hex: hash, memoryAdapter, fileAdapter, createWorld };
})();
