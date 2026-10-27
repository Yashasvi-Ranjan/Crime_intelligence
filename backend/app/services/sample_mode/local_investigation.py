"""
Local-sample implementation of the Zetaris retrieval service.

Serves the four retrieval functions the workflow calls (``search_candidate_incidents``,
``get_incidents_by_ids``, ``get_incidents_by_locations``, ``retrieve_supporting_evidence``) from the
synthetic JSON in ``data/generated`` through the existing ``LocalDataLoader``, applying the same filters,
limits, ordering and ids as the SQL in ``ZetarisInvestigationService``. Nothing is invented: rows are the
records on disk. ``data/evaluation/ground_truth.json`` is never read (the loader has no entry for it).

Every call gets a generated query id (``local-<sha1[:12]>``) and the service reports
``source = "local_sample"`` so the trace never presents these rows as Zetaris results.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Set

from app.config import Settings, settings
from app.services.local_data_loader import LocalDataLoader
from app.services.zetaris_investigation_service import ZetarisInvestigationService, _parse_json_field, _sanitize_term


class LocalInvestigationService(ZetarisInvestigationService):
    source = "local_sample"

    def __init__(self, cfg: Optional[Settings] = None, loader: Optional[LocalDataLoader] = None) -> None:
        self._cfg = cfg or settings
        self._loader = loader or LocalDataLoader(self._cfg)
        self.query_count = 0
        self.errors: List[str] = []
        self._query_ids: List[str] = []
        self.events: List[Dict[str, Any]] = []

    # ── bookkeeping ──────────────────────────────────────────────────────
    def _query(self, description: Dict[str, Any]) -> None:
        self.query_count += 1
        digest = hashlib.sha1(json.dumps(description, sort_keys=True, default=str).encode()).hexdigest()[:12]
        self._query_ids.append(f"local-{digest}")

    def _rows(self, source: str) -> List[Dict[str, Any]]:
        return self._loader._get(source)

    @staticmethod
    def _normalise(r: Dict[str, Any]) -> Dict[str, Any]:
        r = dict(r)                                   # never mutate the cached file rows
        r["property_involved"] = _parse_json_field(r.get("property_involved"))
        r["source_reference_ids"] = _parse_json_field(r.get("source_reference_ids"))
        return r

    # ── retrieval (same contracts as the Zetaris service) ────────────────
    def search_candidate_incidents(
        self,
        keywords: Optional[List[str]] = None,
        crime_types: Optional[List[str]] = None,
        station_ids: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        stations = [_sanitize_term(s) for s in (station_ids or []) if _sanitize_term(s)]
        crimes = [_sanitize_term(c) for c in (crime_types or []) if _sanitize_term(c)]
        kws = [k for k in (_sanitize_term(k).lower() for k in (keywords or [])) if len(k) >= 3]
        self._query({"op": "search", "stations": stations, "crimes": crimes, "df": date_from and _sanitize_term(date_from),
                     "dt": date_to and _sanitize_term(date_to), "kws": kws, "limit": limit})
        rows = self._rows("police_incidents")
        if stations:
            rows = [r for r in rows if r.get("station_id") in stations]
        if crimes:
            rows = [r for r in rows if r.get("crime_type") in crimes]
        if date_from:
            df = _sanitize_term(date_from)
            rows = [r for r in rows if (r.get("reported_at") or "") >= df]
        if date_to:
            dt = _sanitize_term(date_to)
            rows = [r for r in rows if (r.get("reported_at") or "") <= dt]
        if kws:
            def hit(r: Dict[str, Any]) -> bool:
                method = (r.get("method_description") or "").lower()
                prop = json.dumps(r.get("property_involved") or []).lower()   # SQL LIKEs the stringified array
                return any(k in method or k in prop for k in kws)
            rows = [r for r in rows if hit(r)]
        rows = sorted(rows, key=lambda r: r.get("reported_at") or "", reverse=True)[: int(limit)]
        return [self._normalise(r) for r in rows]

    def get_incidents_by_ids(self, incident_ids: List[str]) -> List[Dict[str, Any]]:
        if not incident_ids:
            return []
        wanted = {_sanitize_term(i) for i in incident_ids if _sanitize_term(i)}
        if not wanted:
            return []
        self._query({"op": "by_ids", "ids": sorted(wanted)})
        return [self._normalise(r) for r in self._rows("police_incidents") if r.get("incident_id") in wanted]

    def get_incidents_by_locations(self, location_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        locs = {_sanitize_term(l) for l in location_ids if _sanitize_term(l)}
        if not locs:
            return []
        self._query({"op": "by_locations", "locs": sorted(locs), "limit": limit})
        rows = [r for r in self._rows("police_incidents") if r.get("location_id") in locs]
        rows = sorted(rows, key=lambda r: r.get("reported_at") or "", reverse=True)[: int(limit)]
        return [self._normalise(r) for r in rows]

    def retrieve_supporting_evidence(
        self,
        incident_ids: List[str],
        location_ids: List[str],
        limit_per_source: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        evidence: Dict[str, List[Dict[str, Any]]] = {
            "cctv_reports": [], "witness_reports": [], "forensic_reports": [], "newspaper_reports": []}
        incidents = [_sanitize_term(i) for i in incident_ids if _sanitize_term(i)]
        locations = [_sanitize_term(l) for l in location_ids if _sanitize_term(l)]
        direct_limit = min(24, limit_per_source * max(1, (len(incidents) + 1) // 2))
        context_limit = max(2, limit_per_source // 2)
        inc_l = [i.lower() for i in incidents]
        loc_l = [l.lower() for l in locations]

        def text(v: Any) -> str:
            return json.dumps(v if v is not None else []).lower() if not isinstance(v, str) else v.lower()

        # (source, primary key, direct predicate, location predicate, json fields) - mirrors the SQL specs.
        specs = [
            ("forensic_reports", "evidence_report_id",
             (lambda r: r.get("incident_id") in incidents) if incidents else None,
             (lambda r: r.get("location_id") in locations) if locations else None, ["compared_evidence_ids"]),
            ("cctv_reports", "cctv_report_id",
             (lambda r: any(i in text(r.get("related_incident_ids")) for i in inc_l)) if inc_l else None,
             (lambda r: r.get("location_id") in locations) if locations else None, ["observed_entities", "related_incident_ids"]),
            ("witness_reports", "witness_report_id",
             (lambda r: any(i in text(r.get("related_incident_ids")) for i in inc_l)) if inc_l else None,
             (lambda r: r.get("location_id") in locations) if locations else None,
             ["observed_entities", "related_incident_ids", "contradiction_flags"]),
            ("newspaper_reports", "news_id",
             (lambda r: any(i in text(r.get("related_incident_ids")) for i in inc_l)) if inc_l else None,
             (lambda r: any(l in text(r.get("mentioned_location_ids")) for l in loc_l)) if loc_l else None,
             ["crime_labels", "mentioned_property", "mentioned_location_ids", "related_incident_ids"]),
        ]
        for key, pk, direct, location, json_fields in specs:
            rows: List[Dict[str, Any]] = []
            seen: Set[Any] = set()
            for basis, pred, limit in (("direct_reference", direct, direct_limit), ("location_proximity", location, context_limit)):
                if pred is None:
                    continue
                self._query({"op": "evidence", "source": key, "basis": basis, "incidents": incidents, "locations": locations, "limit": limit})
                for r in [r for r in self._rows(key) if pred(r)][: int(limit)]:
                    if r.get(pk) in seen:
                        continue
                    seen.add(r.get(pk))
                    r = dict(r)
                    r["link_basis"] = basis
                    for f in json_fields:
                        r[f] = _parse_json_field(r.get(f))
                    rows.append(r)
            evidence[key] = rows
        return evidence
