"""
Code-only fallback for sample mode - used ONLY when no recorded Nightshift fixture matches a prompt.

Documented behaviour (also in the README):
  * It is not a model and is never reported as one. The trace marks the call ``code_fallback`` with
    ``reported_model: null``; the workflow's own checks (deterministic verifier, citation grounding)
    run on its output exactly as they do on a model's.
  * It computes its answer from the records inside the prompt it is given. It has no stored answers and
    knows nothing about examples, so different inputs give different outputs.
  * It is deliberately conservative: simple token overlap between incidents at different stations, tied to
    evidence that cites the incidents. Its quality is below a Nemotron call's; that is the reason the
    recorded fixtures exist.

Each ``respond_*`` takes the same user message the model would have received and returns the JSON text
the matching agent contract (``agents.py``) parses.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Tuple

STOP = {
    "with", "from", "into", "using", "used", "after", "before", "then", "that", "this", "were", "was", "been",
    "have", "which", "their", "there", "about", "over", "under", "near", "onto", "also", "than", "they", "them",
    "through", "inside", "outside", "between", "while", "during", "forced", "entry", "entered", "attempted",
    "suspect", "suspects", "reported", "found", "left", "area", "item", "items", "unknown", "stolen", "theft",
}
# words in a detective's question that describe the question, not the method (never useful as search keywords)
QUESTION_STOP = STOP | {
    "are", "the", "and", "linked", "related", "same", "series", "pattern", "across", "station", "stations", "crime", "crimes",
    "north", "central", "riverside", "between", "burglaries", "burglary", "thefts", "incidents", "incident", "any", "connected",
    "does", "show", "find", "look", "possible", "offender", "offenders", "ring", "gang", "tool", "tools",
}
QUESTION_TOKEN_RE = re.compile(r"[a-z][a-z0-9\-]{2,}")
TOKEN_RE = re.compile(r"[a-z][a-z\-]{3,}")


def _leading_json(text: str) -> Dict[str, Any]:
    """The JSON object a prompt starts with (agents.py puts the data first, instructions after)."""
    try:
        obj, _ = json.JSONDecoder().raw_decode(text.lstrip())
        return obj if isinstance(obj, dict) else {}
    except ValueError:
        return {}


def _tokens(text: str) -> List[str]:
    return [t for t in TOKEN_RE.findall((text or "").lower()) if t not in STOP]


# ── Planner ──────────────────────────────────────────────────────────────────
def respond_planner(user: str) -> str:
    data = _leading_json(user)
    if not data.get("question"):
        # continuation turn: the Markovian frame has no structured state; nothing new to plan in code
        return json.dumps({"action": "conclude", "rationale": "Code-only fallback: no further retrieval planned.",
                           "retrieval_requests": [], "outstanding_questions": []})
    seen, kws = set(), []
    for t in QUESTION_TOKEN_RE.findall(data["question"].lower()):
        if t not in seen and t not in QUESTION_STOP:
            seen.add(t)
            kws.append(t)
    reqs: List[Dict[str, Any]] = []
    if data.get("provided_incident_ids"):
        reqs.append({"kind": "by_incident_ids", "incident_ids": data["provided_incident_ids"],
                     "reason": "incidents named by the investigator"})
    if kws or not reqs:
        reqs.append({"kind": "keyword_search", "keywords": kws[:5], "station_ids": data.get("stations") or [],
                     "crime_types": [data["crime_type"]] if data.get("crime_type") else [],
                     "date_from": data.get("date_from"), "date_to": data.get("date_to"),
                     "reason": "keywords taken from the question (code-only fallback)"})
    return json.dumps({"action": "retrieve", "rationale": "Code-only fallback plan from the question's keywords.",
                       "retrieval_requests": reqs, "outstanding_questions": []})


# ── Finder ───────────────────────────────────────────────────────────────────
def respond_finder(user: str) -> str:
    data = _leading_json(user)
    incidents: List[Dict[str, Any]] = data.get("incidents") or []
    evidence: Dict[str, List[Dict[str, Any]]] = data.get("evidence") or {}
    by_id = {i["incident_id"]: i for i in incidents if i.get("incident_id")}
    toks = {iid: set(_tokens(i.get("method_description"))) | {f"prop:{p.lower()}" for p in (i.get("property_involved") or [])
                                                             if isinstance(p, str)} for iid, i in by_id.items()}
    df: Dict[str, int] = {}
    for ts in toks.values():
        for t in ts:
            df[t] = df.get(t, 0) + 1
    max_df = max(2, math.ceil(len(by_id) / 3))

    def evidence_for(a: str, b: str) -> List[str]:
        ids: List[str] = []
        for r in evidence.get("forensic_reports", []):
            if r.get("incident_id") in (a, b) and r.get("evidence_report_id"):
                ids.append(r["evidence_report_id"])
        for key, pk in (("cctv_reports", "cctv_report_id"), ("witness_reports", "witness_report_id"), ("newspaper_reports", "news_id")):
            for r in evidence.get(key, []):
                rel = r.get("related_incident_ids") or []
                if (a in rel or b in rel) and r.get(pk):
                    ids.append(r[pk])
        return list(dict.fromkeys(ids))

    cands: List[Tuple[float, Dict[str, Any]]] = []
    ids = sorted(by_id)
    for ai, a in enumerate(ids):
        for b in ids[ai + 1:]:
            ia, ib = by_id[a], by_id[b]
            if ia.get("station_id") == ib.get("station_id"):
                continue
            shared = sorted(t for t in toks[a] & toks[b] if df[t] <= max_df)
            method = [t for t in shared if not t.startswith("prop:")]
            if not method:
                continue
            ev = evidence_for(a, b)
            score = min(0.9, 0.25 + 0.12 * len(shared) + 0.04 * min(len(ev), 5))
            cands.append((score, {
                "source_incident_id": a, "target_incident_id": b,
                "stations_involved": sorted({ia.get("station_id"), ib.get("station_id")} - {None}),
                "similarity_basis": f"Both method descriptions mention {', '.join(method[:4])}.",
                "shared_attributes": [{"attribute": "property" if t.startswith("prop:") else "method",
                                       "value": t.replace("prop:", ""), "match_type": "exact", "source_ids": [a, b]}
                                      for t in shared[:6]],
                "differences": [d for d in (
                    f"Different crime types: {ia.get('crime_type')} vs {ib.get('crime_type')}"
                    if ia.get("crime_type") != ib.get("crime_type") else "",) if d],
                "missing_evidence": [] if ev else ["No evidence record in the retrieved set cites either incident."],
                "supporting_evidence_ids": ev[:6], "quotes": [], "heuristic_score": round(score, 2),
                "score_note": "code-only fallback heuristic (token overlap); not a probability"}))
    cands.sort(key=lambda c: (-c[0], c[1]["source_incident_id"], c[1]["target_incident_id"]))
    links = []
    for n, (_, link) in enumerate(cands[:4], 1):
        links.append({"link_id": f"LINK-{n:02d}", **link})
    return json.dumps({"links": links, "withdrawn_link_ids": [],
                       "notes": "Code-only fallback: token-overlap links between incidents at different stations."})


# ── Skeptic ──────────────────────────────────────────────────────────────────
def respond_skeptic(user: str) -> str:
    data = _leading_json(user)
    checks: List[Dict[str, Any]] = data.get("deterministic_checks") or []
    first_pass = all((l.get("revision") or 1) <= 1 for l in data.get("proposed_links") or [])
    objections, wants_more = [], False
    for c in checks:
        status = c.get("status")
        for con in (c.get("contradictions") or [])[:2]:
            objections.append({"link_id": c.get("link_id", ""), "kind": "contradiction", "severity": "high",
                               "description": str(con.get("description") or con)[:240],
                               "cited_ids": list(con.get("source_ids") or [])[:4]})
        if status == "UNSUPPORTED":
            objections.append({"link_id": c.get("link_id", ""), "kind": "unsupported_claim", "severity": "high",
                               "description": str(c.get("explanation"))[:240], "cited_ids": []})
        elif status == "WEAK":
            more = first_pass
            wants_more = wants_more or more
            objections.append({"link_id": c.get("link_id", ""), "kind": "missing_evidence", "severity": "medium",
                               "is_missing_evidence_only": True, "requests_retrieval": more,
                               "retrieval_hint": "records that corroborate both incidents independently",
                               "description": str(c.get("explanation"))[:240], "cited_ids": []})
    if not checks:
        status = "rejected"
    elif wants_more:
        status = "needs_more_evidence"
    elif objections:
        status = "accepted_with_objections"
    else:
        status = "accepted"
    return json.dumps({"review_status": status, "objections": objections,
                       "alternative_explanations": ["Shared tooling or practice may be coincidental across stations."],
                       "suggested_retrieval": []})


# ── Reporter ─────────────────────────────────────────────────────────────────
def respond_reporter(user: str) -> str:
    st = _leading_json(user)
    links = st.get("links") or []
    facts, hyps, sims, diffs = [], [], [], []
    for l in links:
        ids = [l["source_incident_id"], l["target_incident_id"], *(l.get("verified_evidence_ids") or [])[:4]]
        facts.append({"statement": f"{l['source_incident_id']} and {l['target_incident_id']} "
                                   f"({'/'.join(l.get('stations_involved') or [])}) were proposed as related; "
                                   f"verifier status {l.get('verifier_status')}.", "source_ids": ids})
        hyps.append({"statement": l.get("similarity_basis") or "Possible common method.", "link_id": l["link_id"]})
        sims += [f"{a['attribute']}: {a['value']}" for a in (l.get("shared_attributes") or [])[:3]]
        diffs += list(l.get("differences") or [])[:2]
    n = len(links)
    return json.dumps({
        "title": f"Cross-Station Intelligence Report: {str(st.get('question', ''))[:60]}",
        "executive_summary": (f"[Code-only fallback report - no model wrote this.] {n} candidate link(s) survived to the report; "
                              f"stopping reason: {st.get('stopping_reason')}. Links are investigative leads, not findings of fact."),
        "facts": facts, "hypotheses": hyps, "similarities": list(dict.fromkeys(sims)), "differences": list(dict.fromkeys(diffs)),
        "contradictions_and_limitations": [c.get("description", "") for c in st.get("contradictions") or []][:6],
        "unresolved_questions": list(st.get("unresolved_questions") or []),
        "follow_up_actions": ["Have an analyst review each lead against the cited source records."] if n else []})


RESPONDERS = {"planner": respond_planner, "finder": respond_finder, "skeptic": respond_skeptic, "reporter": respond_reporter}


def respond(role: str, messages: List[Dict[str, str]]) -> str:
    # the first user turn carries the data; later turns are only repair requests for malformed output
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    return RESPONDERS[role](user)
