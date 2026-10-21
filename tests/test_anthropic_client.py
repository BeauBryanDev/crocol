import pytest
from pydantic import BaseModel

from config.roles import EFFORT, HAIKU, SONNET
from crocol.infrastructure.llm.anthropic_client import AnthropicLLM

pytestmark = pytest.mark.anyio


class Out(BaseModel):
    value: str


class Captured(Exception):
    pass


async def sent_body(model: str) -> dict:

    llm = AnthropicLLM(api_key="test-key", timeout_s=5)
    bodies = []

    async def capture(path, *, body=None, **_):
        bodies.append(body)
        raise Captured

    llm._client.messages._post = capture
    with pytest.raises(Captured):
        await llm.complete(model, "system", "user", Out, 100)

    return bodies[0]


async def test_sonnet_runs_at_configured_effort():

    config = (await sent_body(SONNET))["output_config"]

    assert config["effort"] == EFFORT[SONNET] == "medium"
    assert config["format"]["type"] == "json_schema"


async def test_haiku_keeps_default_effort():

    config = (await sent_body(HAIKU))["output_config"]

    assert "effort" not in config
    assert config["format"]["type"] == "json_schema"
