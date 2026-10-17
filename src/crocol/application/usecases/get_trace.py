import uuid

from crocol.application.ports.trace_store import TraceStore


class GetTrace:
    def __init__(self, traces: TraceStore | None) -> None:

        self._traces = traces

    async def run(self, trace_id: str) -> dict | None:
        """The saved app log for one answer; None if unknown or invalid."""
        try:
            canonical = str(uuid.UUID(trace_id))
        except (ValueError, TypeError):
            return None

        if self._traces is None:
            return None

        return await self._traces.get(canonical)
