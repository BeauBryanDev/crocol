from typing import Protocol


class TraceStore(Protocol):
    async def save(self, record: dict) -> None: ...

    async def get(self, trace_id: str) -> dict | None: ...
