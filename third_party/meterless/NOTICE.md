# NOTICE - vendored Meterless reference implementations

This directory contains **unmodified** copies of source files from the Apache-2.0 licensed
repository https://github.com/Meterless/Meterless at commit `1742dec56a66e58eef9dda2d2b865823758ca8cd`
(short `1742dec`):

| Vendored here | Upstream path |
|---|---|
| `hmem/src/`      | `engines/hmem/reference/src/` |
| `markovian/src/` | `engines/markovian/reference/src/` |

`LICENSE` is the upstream Apache License 2.0 text (`/LICENSE` at that commit). The upstream repository
ships no NOTICE file. These are Meterless's open *reference* implementations of the H-MEM and Markovian
specs; they are **not** the proprietary Nightshift.app engine modules (`hmem.js`, `markovian.js`,
`worldmodel.js`, `scout-intents.js`), none of which is, or may be, copied into this repository or the Docker
image. World Model and Scout Intent have no open reference implementation and are not vendored.

Our own code that drives these files (not part of the vendored sources, licensed with this project) lives at
`backend/app/services/meterless_world/reference/` and is bundled by `scripts/build_reference_engines.sh`.

## sha256 of each vendored file (verify with `sha256sum -c` / `shasum -a 256 -c` from this directory)

```
432e8b86ed0b5883d435e5ab4a12160d1f40d194cbdb4c119d3b710cbb0301a3  hmem/src/conflictDetection.ts
d12594d667ec068690c6b81e020cd62ade91671316a1ab9b529259304aceb009  hmem/src/dreaming.ts
89433327ee1075a8049bc8518cdf5cabf51ad67802e192266841cdee727b6d10  hmem/src/embeddings.ts
9c481889afcdd70086d3bb3470842fa2330215e4d7760d826d103accdf8c1cdf  hmem/src/index.ts
6072693d654ea1c34a9adbf6ce80101eeb1eeb56273d264f6ceb4859ffde6562  hmem/src/memoryMining.ts
4fe120b1b64fe7225b9b28fda59514c114de9e885d22c5bf0aa035788b6d629d  hmem/src/memoryRetrieval.ts
a1eac8de8c0fde0e503e1212f3cb98295a661c2a8bad93ad82e51985885e6fd0  hmem/src/memoryStore.ts
3ce0d4f3233d0ad7c133a2cbaf39b6122467022e0aa378a160a0d463e2264cef  hmem/src/sleepCycle.ts
263253dd3342c488ce773d7e728d77aec983c1833873602b59ce1a6c7999e20e  hmem/src/trustLedger.ts
becb504870a67646a20a421ffe04d8732db63418393423d2186c074b182f54c7  hmem/src/types.ts
30ec1905e6238a1da806c98c854ead688e9d670b62257aba375568ab562cfd6c  markovian/src/carryover.ts
4a4e71ca2164e83a1f67ecc561c7be0dbc5e11329b2e571f75ad7642fa598855  markovian/src/configManager.ts
c08f865008a899cae55ee7b6c4506c8d73cf823bd28ecae1bdf36c6e864039f3  markovian/src/history.ts
7bbf1235c592fdaf5cc864add9451908739b8bde3e1d5f47175689a02532d003  markovian/src/index.ts
344a6d2a46d1f8ffefbd80ccd936492666e7f699a9584c7a3238190bfaa409a9  markovian/src/markers.ts
b6538a8a2092d93224526a2cb277e703d600b7ccad620b0a3fc190571163315c  markovian/src/orchestrator.ts
f29a7d49922e759b61cd9bddf06a1bee0b7955c667692d54443dce17da2ef997  markovian/src/progress.ts
ee785eb26a6f07c32f2cede8dcb4257191ac9b5f4d0ed9f8cb20e25bf481b073  markovian/src/promptBuilder.ts
94c54137dd03e17ef9e838b5b424b8195599fcf69ebcae76895bef7c22dcd667  markovian/src/types.ts
```
