"""
Relevance-scored candidate retrieval (replaces "newest N rows").

The old candidate query was ``ORDER BY reported_at DESC LIMIT n``: with ~1000 incidents per station sharing the
same vocabulary, the n newest keyword hits were returned and older records of a real series never reached the
agents. Here the database narrows by the hard filters (station / crime type / dates / any keyword term), orders
a *bounded* pool by a cheap relevance score, and ``rank_candidates`` re-ranks that pool and keeps the top-k:

* terms: each keyword phrase plus its content words, so "heavy pry bar" also finds "Heavy pry tool";
* IDF weighting inside the pool: a term only a few rows share outranks one nearly every row shares;
* corroboration: a bounded number of top-k slots (CORROBORATED_SLOTS) go to the best-matching incidents that
  already cite linked witness/CCTV/forensic records, because a series claim needs cross-source evidence. Only
  rows that match a term are eligible, so corroboration never replaces relevance;
* ties break on the incident id so the order never depends on recency or on storage order.

Pure functions only; shared by the Zetaris SQL service and the local-sample service so both rank identically.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Sequence

STOPWORDS = frozenset(
    "the and for with that this from into onto were was are has have had using use used via near over under across "
    "after before between same share shared series linked link thefts theft cases case incident incidents".split())
POOL_FACTOR = 6          # SQL pool = limit * POOL_FACTOR, hard-capped below
POOL_MAX = 80
CORROBORATED_SLOTS = 2      # of the top-k, held for the best-matching incidents that cite linked source records


def expand_terms(keywords: Sequence[str]) -> List[str]:
    """Lower-cased phrases + their content words (len >= 3, no stopwords), de-duplicated, order preserved."""
    out: List[str] = []
    for kw in keywords or []:
        kw = (kw or "").strip().lower()
        words = [w for w in re.findall(r"[a-z0-9]{3,}", kw) if w not in STOPWORDS]
        for t in ([kw] if len(kw) >= 3 and " " in kw else []) + words:
            if t not in out:
                out.append(t)
    return out


def pool_size(limit: int) -> int:
    return max(int(limit), min(POOL_MAX, int(limit) * POOL_FACTOR))


def row_text(row: Dict[str, Any]) -> str:
    return f"{row.get('method_description') or ''} {json.dumps(row.get('property_involved') or [])}".lower()


def is_corroborated(row: Dict[str, Any]) -> bool:
    refs = row.get("source_reference_ids")
    if isinstance(refs, str):
        refs = refs.strip()
        return refs not in ("", "[]", "null")
    return bool(refs)


def pool_score(row: Dict[str, Any], terms: Sequence[str]) -> int:
    """Unweighted score the database computes to pick the bounded pool: terms matched + 1 if corroborated."""
    text = row_text(row)
    return sum(t in text for t in terms) + int(is_corroborated(row))


def rank_candidates(rows: List[Dict[str, Any]], terms: Sequence[str], limit: int) -> List[Dict[str, Any]]:
    """Top ``limit`` rows: IDF-weighted overlap (+ one top-term bonus if corroborated), with slots reserved for corroborated rows."""
    texts = [row_text(r) for r in rows]
    n = len(rows) or 1
    weight = {t: math.log(1 + n / df) for t in terms if (df := sum(t in x for x in texts))}

    def key(i: int):
        bonus = max(weight.values(), default=0.0) if is_corroborated(rows[i]) else 0.0
        return (-(sum(w for t, w in weight.items() if t in texts[i]) + bonus), str(rows[i].get("incident_id") or ""))

    order = sorted(range(len(rows)), key=key)
    reserved = [i for i in order if is_corroborated(rows[i])][: min(CORROBORATED_SLOTS, int(limit) // 3)]
    rest = [i for i in order if i not in reserved]
    return [rows[i] for i in sorted(reserved, key=key) + rest][: int(limit)]
