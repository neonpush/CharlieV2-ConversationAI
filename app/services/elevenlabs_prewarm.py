"""
ElevenLabs pre-warm service.

Maintains a lightweight cache of recently prepared conversation context so
the agent can speak faster at call start.

Note: This is a minimal stub. Real pre-warming would open a Realtime WS
session ahead of time; here we precompute and cache variables/prompt.
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from app.db.models import Lead
from app.services.elevenlabs_service import ElevenLabsService


logger = logging.getLogger(__name__)


class PrewarmCacheEntry:
    def __init__(self, variables: Dict[str, Any], expires_at: datetime) -> None:
        self.variables = variables
        self.expires_at = expires_at


class ElevenLabsPrewarmService:
    def __init__(self) -> None:
        self._cache: Dict[int, PrewarmCacheEntry] = {}
        self._ttl = timedelta(minutes=5)
        self._vars_builder = ElevenLabsService()
        self._last_lead_id: int | None = None

    def prewarm_for_lead(self, lead: Lead) -> Dict[str, Any]:
        """
        Build and cache dynamic variables + system prompt for a lead.
        """
        variables = self._vars_builder.build_dynamic_variables(lead)
        self._cache[lead.id] = PrewarmCacheEntry(
            variables=variables,
            expires_at=datetime.utcnow() + self._ttl,
        )
        logger.info(f"Prewarmed ElevenLabs vars for lead {lead.id}")
        self._last_lead_id = lead.id
        self._cleanup()
        return variables

    def get_cached(self, lead_id: int) -> Dict[str, Any] | None:
        entry = self._cache.get(lead_id)
        if not entry:
            return None
        if datetime.utcnow() > entry.expires_at:
            del self._cache[lead_id]
            return None
        return entry.variables

    def _cleanup(self) -> None:
        now = datetime.utcnow()
        expired = [lid for lid, e in self._cache.items() if now > e.expires_at]
        for lid in expired:
            del self._cache[lid]
        if expired:
            logger.debug(f"Prewarm cache cleaned: {len(expired)} entries")


# Simple singleton accessor
_prewarm_service: ElevenLabsPrewarmService | None = None


def get_prewarm_service() -> ElevenLabsPrewarmService:
    global _prewarm_service
    if _prewarm_service is None:
        _prewarm_service = ElevenLabsPrewarmService()
    return _prewarm_service


