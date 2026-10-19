from dataclasses import dataclass, field
from typing import Literal

from crocol.domains.models.citations import Citation

AnswerStatus = Literal["answered", "abstained", "partial", "error"]


@dataclass(frozen=True)
class Answer:
    """
    Answer model class
    """
    text: str = field(default="")
    status: AnswerStatus = field(default="answered")
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    caveats: tuple[str, ...] = field(default_factory=tuple)
    conflicts: tuple[dict, ...] = field(default_factory=tuple)
    partial: bool = field(default=False)
    overlay_webp: bytes = field(default=b"")
    production: tuple[dict, ...] = field(default_factory=tuple)
    simulation: dict | None = field(default=None)
    vision: dict | None = field(default=None)
