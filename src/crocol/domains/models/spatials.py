from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpatialCall:
    function: str
    arguments: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SpatialResult:
    function: str
    rows: tuple[dict, ...] = ()
    source: str = ""
    caveats: tuple[str, ...] = field(default_factory=tuple)
