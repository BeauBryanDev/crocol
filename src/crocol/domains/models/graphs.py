from dataclasses import dataclass


@dataclass(frozen=True)
class GraphResult:
    function: str
    rows: tuple[dict, ...] = ()
    source: str = ""


@dataclass(frozen=True)
class GraphEntity:
    entity_id: int
    kind: str
    name: str
    score: float
    props: dict
