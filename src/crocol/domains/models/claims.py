from dataclasses import dataclass
from typing import Literal

Verdict = Literal["supported", "unsupported", "contradicted"]


@dataclass(frozen=True)
class Claim:
    text: str
    labels: tuple[str, ...]
    verdict: Verdict
    numeric: bool = False

    @property
    def failing(self) -> bool:
        return self.verdict == "contradicted" or (
            self.verdict == "unsupported" and self.numeric
        )
