'use strict';
/**
 * Runner for the vendored Meterless *reference* engines (H-MEM, Markovian), built to
 * <referenceDir>/{hmem,markovian}.cjs by scripts/build_reference_engines.sh.
 * Same stdin/stdout protocol as engine_runner.cjs (which drives the mounted Nightshift engines):
 *   stdin  JSON { engine, op, args, referenceDir, storeFile }
 *   stdout JSON { ok, engine, op, result, audit }
 */
const fs = require('fs');
const path = require('path');

(async () => {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  try {
    const { engine, op, args = {}, referenceDir, storeFile } = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!['hmem', 'markovian'].includes(engine)) throw new Error(`no reference implementation for engine: ${engine}`);
    const file = path.join(referenceDir, `${engine}.cjs`);
    if (!fs.existsSync(file)) throw new Error(`reference build not found: ${file}`);
    const { result, audit } = await require(file).handle(op, args, { storeFile });
    process.stdout.write(JSON.stringify({ ok: true, engine, op, result, audit }));
  } catch (err) {
    process.stderr.write(JSON.stringify({ ok: false, error: String((err && err.message) || err) }));
    process.exit(1);
  }
})();
