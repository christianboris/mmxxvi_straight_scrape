"""The MCP web_search tool forwards the language to the search API."""

import importlib.util
from pathlib import Path

import pytest

SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp" / "server.py"


def load_mcp_server():
    # Loaded by path under a distinct module name: the repository's own "mcp"
    # directory must not shadow the installed "mcp" package fastmcp needs.
    spec = importlib.util.spec_from_file_location("straight_scrape_mcp_server", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"query": self._payload["query"], "results": [], "total_results": 0}


class FakeAsyncClient:
    def __init__(self, recorder: list, **kwargs):
        self._recorder = recorder

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url: str, json: dict) -> FakeResponse:
        self._recorder.append({"url": url, "payload": json})
        return FakeResponse(json)


@pytest.fixture
def mcp_server(monkeypatch):
    server = load_mcp_server()
    recorder: list = []

    class FakeHttpx:
        AsyncClient = staticmethod(lambda **kwargs: FakeAsyncClient(recorder, **kwargs))

    monkeypatch.setattr(server, "httpx", FakeHttpx)
    return server, recorder


def tool_function(tool):
    # fastmcp wraps the decorated coroutine in a Tool object.
    return getattr(tool, "fn", tool)


async def test_web_search_forwards_language(mcp_server):
    server, recorder = mcp_server

    await tool_function(server.web_search)("wetter", max_results=2, language="de")

    assert len(recorder) == 1
    assert recorder[0]["url"].endswith("/api/search")
    assert recorder[0]["payload"]["language"] == "de"


async def test_web_search_defaults_to_english(mcp_server):
    server, recorder = mcp_server

    await tool_function(server.web_search)("weather")

    assert recorder[0]["payload"]["language"] == "en"
