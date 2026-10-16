from dataclasses import dataclass, field
from typing import Literal

from crocol.domains.models.citations import Citation

AnswerStatus = Literal["answered", "abstained", "partial", "error"]


@dataclass(frozen=True)
class Answer:
    text: str
    status: AnswerStatus
    citations: tuple[Citation, ...] = ()
    references: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    conflicts: tuple[dict, ...] = field(default_factory=tuple)
    partial: bool = False
