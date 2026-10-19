from typing import Any, Protocol


class WellSimulation(Protocol):
    """Blocking simulator calls; callers run them in a worker thread."""

    def run(self, params: dict[str, Any]) -> dict[str, Any]: ...

    def sweep(self, params: dict[str, Any],
              options: dict[str, Any]) -> dict[str, Any]: ...
