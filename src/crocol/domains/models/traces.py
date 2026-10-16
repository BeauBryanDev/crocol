from dataclasses import asdict, dataclass, field
from typing import Literal

NodeStatus = Literal["ok", "skipped", "timeout", "error", "fallback"]


@dataclass(frozen=True)
class TraceEvent:
    node: str
    status: NodeStatus
    duration_ms: int
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
