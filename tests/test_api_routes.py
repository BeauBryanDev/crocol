import io
import json
import logging

import httpx
import pytest
from PIL import Image
from fakes import FakeGraph, graph_rows

from crocol.app.api.guards import RateLimiter, RunSlots, SpendCounter
from crocol.app.deps import AppContainer
from crocol.app.main import create_app
from crocol.application.usecases.get_entity import GetEntity
from crocol.domains.models.spatials import SpatialResult
from crocol.infrastructure.vision.image_store import LocalImageStore

pytestmark = pytest.mark.anyio
TRACE = "5b0f6f9e-3c1a-4c55-9a43-2f1d8c7e9a10"
SECRET = "pregunta secreta sobre la Formacion La Luna"


class FakeAsk:
    def __init__(self) -> None:

        self.calls: list[tuple[str, bytes | None]] = []
        self.wells: list[dict | None] = []

    def final(self) -> dict:

        return {"event": "final", "trace_id": TRACE, "status": "answered",
                "usage": {"llm_calls": 4, "tokens": 1000},
                "answer": "La Luna es rica en materia organica [1].",
                "citations": ["(Rueda, 2016, p. 4)"], "references": [],
                "caveats": [], "conflicts": [], "overlay_webp_b64": None}

    async def ask(self, question: str, image: bytes | None,
                  well: dict | None = None) -> dict:

        self.calls.append((question, image))
        self.wells.append(well)
        return self.final()

    async def stream(self, question: str, image: bytes | None,
                     well: dict | None = None):

        self.calls.append((question, image))
        self.wells.append(well)
        yield {"event": "node", "node": "analyze", "ms": 5}
        yield self.final()


class FakeTraces:
    async def run(self, trace_id: str) -> dict | None:

        if trace_id != TRACE:
            return None
        return {"trace_id": TRACE, "created_at": "2026-10-17T10:00:00",
                "status": "answered", "llm_calls": 4, "trace": [],
                "chunks": []}


class FakeSpatial:
    async def run(self, function: str, arguments: dict) -> SpatialResult:

        rows = ()
        if arguments["name"].lower() == "casabe":
            rows = ({"kind": "field", "name": "CASABE", "source": "ANH",
                     "geojson": '{"type": "Point", "coordinates": [1, 2]}'},)
        return SpatialResult(function=function, rows=rows, source="ANH")


def make_state(tmp_path, per_minute: int = 5, day_cap: int = 30
               ) -> AppContainer:

    return AppContainer(
        pool=None, ask=FakeAsk(), get_trace=FakeTraces(),
        spatial=FakeSpatial(), vision=None,
        images=LocalImageStore(tmp_path, 72),
        question_limiter=RateLimiter(per_minute, 12),
        other_limiter=RateLimiter(60),
        spend=SpendCounter(day_cap, 800_000),
        slots=RunSlots(2, 0.1))


def client_for(state: AppContainer) -> httpx.AsyncClient:

    app = create_app()
    app.state.container = state
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def png_bytes() -> bytes:

    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (120, 110, 100)).save(buffer, "PNG")
    return buffer.getvalue()


async def test_chat_json_shape_and_spend(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        response = await client.post("/api/chat",
                                     json={"question": "  que es  la Luna "})
    body = response.json()
    assert response.status_code == 200
    assert body["trace_id"] == TRACE and body["usage"]["tokens"] == 1000
    assert state.ask.calls == [("que es la Luna", None)]
    assert state.spend.snapshot()["tokens_today"] == 1000
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]


async def test_short_question_is_rejected_without_spending(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        response = await client.post("/api/chat", json={"question": "a"})
    assert response.status_code == 422
    assert set(response.json()) == {"error", "request_id"}
    assert state.spend.snapshot()["questions_today"] == 0


async def test_rate_limit_returns_retry_after(tmp_path) -> None:

    state = make_state(tmp_path, per_minute=1)
    async with client_for(state) as client:
        await client.post("/api/chat", json={"question": "primera"})
        response = await client.post("/api/chat",
                                     json={"question": "segunda"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


async def test_daily_budget_returns_503(tmp_path) -> None:

    state = make_state(tmp_path, day_cap=0)
    async with client_for(state) as client:
        response = await client.post("/api/chat",
                                     json={"question": "pregunta"})
    assert response.status_code == 503


async def test_stream_event_order(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        response = await client.post("/api/chat/stream",
                                     json={"question": "pregunta"})
    events = [line.split(":", 1)[1].strip()
              for line in response.text.splitlines()
              if line.startswith("event:")]
    assert response.status_code == 200
    assert events == ["node", "final"]
    assert '"trace_id"' in response.text


async def test_image_upload_is_sanitized_and_stored(tmp_path) -> None:

    state = make_state(tmp_path)
    files = {"image": ("roca.png", png_bytes(), "image/png")}
    async with client_for(state) as client:
        response = await client.post("/api/image", files=files,
                                     data={"question": "que roca es"})
    assert response.status_code == 200
    question, image = state.ask.calls[0]
    assert question == "que roca es" and image[:2] == b"\xff\xd8"
    assert (tmp_path / f"{TRACE}.jpg").exists()


async def test_image_errors(tmp_path) -> None:

    state = make_state(tmp_path)
    bad = {"image": ("x.png", b"not an image", "image/png")}
    gif = io.BytesIO()
    Image.new("RGB", (8, 8)).save(gif, "GIF")
    async with client_for(state) as client:
        invalid = await client.post("/api/image", files=bad,
                                    data={"question": "que roca es"})
        unsupported = await client.post(
            "/api/image", data={"question": "que roca es"},
            files={"image": ("x.gif", gif.getvalue(), "image/gif")})
    assert invalid.status_code == 400
    assert unsupported.status_code == 415
    assert state.spend.snapshot()["questions_today"] == 0


async def test_oversized_request_is_413(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        response = await client.post(
            "/api/chat", content=b"{}",
            headers={"content-length": str(12 * 1024 * 1024),
                     "content-type": "application/json"})
    assert response.status_code == 413


async def test_trace_map_meta_and_cors(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        found = await client.get(f"/api/traces/{TRACE}")
        missing = await client.get("/api/traces/not-a-uuid")
        place = await client.get("/api/map/locate",
                                 params={"name": "Casabe"})
        nowhere = await client.get("/api/map/locate",
                                   params={"name": "Atlantis"})
        meta = await client.get("/api/meta")
        preflight = await client.options(
            "/api/chat", headers={
                "origin": "http://localhost:5173",
                "access-control-request-method": "POST"})
    assert found.status_code == 200 and missing.status_code == 404
    assert place.json()["geojson"]["type"] == "Point"
    assert nowhere.status_code == 404
    assert meta.json()["limits"]["questions_per_day"] == 30
    assert preflight.headers["access-control-allow-origin"] == (
        "http://localhost:5173")


async def test_ready_reports_down_dependencies(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        response = await client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["postgres"]["ok"] is False


async def test_logs_never_contain_user_text(tmp_path, caplog) -> None:

    state = make_state(tmp_path)
    caplog.set_level(logging.DEBUG)
    async with client_for(state) as client:
        await client.post("/api/chat", json={"question": SECRET})
        await client.post("/api/chat", json={"question": "x" * 3000})
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "Luna" not in logged and "xxxx" not in logged
    assert json.dumps(SECRET) not in logged


async def test_graph_entity_card(tmp_path) -> None:

    state = make_state(tmp_path)
    graph = FakeGraph(graph_rows())
    state.get_entity = GetEntity(graph)
    async with client_for(state) as client:
        response = await client.get("/api/graph/entity",
                                    params={"name": "La Luna",
                                            "kind": "formation"})
    body = response.json()
    assert response.status_code == 200
    assert body["entity"] == {"kind": "formation", "name": "La Luna",
                              "score": 1.0, "mentions": 464,
                              "props": {"age": "Turoniano–Santoniano"}}
    assert body["relations"][0]["names"] == ["Galembo", "Pujamana", "Salada"]
    assert body["documents"][0]["citation"] == "Rueda Acevedo, 2016"
    assert body["source"] == "Crocol-KG-2026"
    assert graph.calls[0] == ("resolve", {"name": "La Luna",
                                          "kinds": ["formation"],
                                          "max_rows": 5})


async def test_graph_entity_not_found_and_unavailable(tmp_path) -> None:

    state = make_state(tmp_path)
    async with client_for(state) as client:
        unavailable = await client.get("/api/graph/entity",
                                       params={"name": "La Luna"})
        state.get_entity = GetEntity(FakeGraph({}))
        missing = await client.get("/api/graph/entity",
                                   params={"name": "Atlantis"})
        bad_kind = await client.get("/api/graph/entity",
                                    params={"name": "La Luna",
                                            "kind": "planet"})
    assert unavailable.status_code == 503
    assert missing.status_code == 404
    assert missing.json()["error"] == "entity not found"
    assert bad_kind.status_code == 422
