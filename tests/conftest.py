import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: needs the vmm-postgis container")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def corpus_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """General knowledge off: no evidence means abstain."""
    from crocol.application.agent import routing
    monkeypatch.setattr(routing, "ALLOW_GENERAL_KNOWLEDGE", False)
