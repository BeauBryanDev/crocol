from typing import Protocol

from crocol.domains.models.cracks import CrackAnalysis


class CrackAnalyzer(Protocol):
    def analyze(self, image_bytes: bytes) -> CrackAnalysis: ...
