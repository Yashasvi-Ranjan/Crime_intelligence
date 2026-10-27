"""Live Zetaris with a traced fallback to the local sample data (used by POST /run in live mode)."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from app.config import Settings, settings
from app.services.sample_mode.local_investigation import LocalInvestigationService
from app.services.zetaris_adapter import ZetarisAuthError, ZetarisConnectionError, ZetarisNotConfiguredError, ZetarisQueryError
from app.services.zetaris_investigation_service import ZetarisInvestigationService

logger = logging.getLogger(__name__)
ZETARIS_FAILURES = (ZetarisConnectionError, ZetarisQueryError, ZetarisNotConfiguredError, ZetarisAuthError)


class ResilientInvestigationService:
    """Same retrieval interface as ZetarisInvestigationService. A Zetaris failure (each call is bounded by
    ZETARIS_TIMEOUT_SECONDS) switches the rest of the run to local sample data and records a
    ``zetaris_fallback`` event the workflow writes to the trace; ``source`` always says where the last
    rows came from."""

    def __init__(self, live: ZetarisInvestigationService, local: LocalInvestigationService) -> None:
        self._live, self._local = live, local
        self.down: Optional[str] = None
        self.source = live.source
        self.events: List[Dict[str, Any]] = []

    @property
    def query_count(self) -> int:
        return self._live.query_count + self._local.query_count

    @property
    def errors(self) -> List[str]:
        return [*self._live.errors, *self._local.errors]

    def take_query_ids(self) -> List[str]:
        return [*self._live.take_query_ids(), *self._local.take_query_ids()]

    def take_events(self) -> List[Dict[str, Any]]:
        ev, self.events = self.events, []
        return ev

    def _call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if self.down is None:
            try:
                res = getattr(self._live, name)(*args, **kwargs)
                self.source = self._live.source
                return res
            except ZETARIS_FAILURES as exc:
                self.down = f"{type(exc).__name__}: {str(exc)[:160]}"
                self.events.append({"event": "zetaris_fallback", "reason": self.down, "fallback": "local_sample"})
                logger.warning("Zetaris unavailable (%s); serving retrieval from local sample data", self.down)
        self.source = self._local.source
        return getattr(self._local, name)(*args, **kwargs)

    def search_candidate_incidents(self, *a: Any, **k: Any) -> List[Dict[str, Any]]:
        return self._call("search_candidate_incidents", *a, **k)

    def get_incidents_by_ids(self, *a: Any, **k: Any) -> List[Dict[str, Any]]:
        return self._call("get_incidents_by_ids", *a, **k)

    def get_incidents_by_locations(self, *a: Any, **k: Any) -> List[Dict[str, Any]]:
        return self._call("get_incidents_by_locations", *a, **k)

    def retrieve_supporting_evidence(self, *a: Any, **k: Any) -> Dict[str, List[Dict[str, Any]]]:
        return self._call("retrieve_supporting_evidence", *a, **k)
