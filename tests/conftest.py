import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402

import routers.search as search_module  # noqa: E402
from cache import cache  # noqa: E402
from routers import search_router  # noqa: E402
from services.fetcher import fetcher  # noqa: E402
from services.searxng import searxng_client  # noqa: E402


class SearxngRecorder:
    """Stand-in for the SearXNG client: records calls, returns synthetic hits."""

    def __init__(self):
        self.calls: list[dict] = []

    async def search(
        self,
        query: str,
        max_results: int = 10,
        engines: list[str] | None = None,
        categories: list[str] | None = None,
        language: str = "en",
    ) -> list[dict]:
        self.calls.append({
            "query": query,
            "max_results": max_results,
            "engines": engines,
            "categories": categories,
            "language": language,
        })
        return [
            {
                "url": f"https://example.com/{language}/{i}",
                "title": f"{query} result {i}",
                "snippet": f"snippet {i}",
                "engine": "testengine",
                "score": 1.0,
            }
            for i in range(max_results)
        ]


@pytest.fixture
def searxng(monkeypatch) -> SearxngRecorder:
    recorder = SearxngRecorder()
    monkeypatch.setattr(searxng_client, "search", recorder.search)
    return recorder


@pytest.fixture(autouse=True)
def offline_fetcher(monkeypatch):
    """No network: fetching and extraction are replaced by deterministic stubs."""

    async def fake_fetch(url: str, force_js: bool = False) -> tuple[str | None, str]:
        return f"<html><body><p>content of {url}</p></body></html>", url

    monkeypatch.setattr(fetcher, "fetch", fake_fetch)
    monkeypatch.setattr(
        search_module, "extract_content", lambda html, url: f"# markdown of {url}"
    )


@pytest.fixture
async def client(tmp_path, monkeypatch):
    """HTTP client for a minimal app exposing only the search router.

    The cache singleton is pointed at a fresh SQLite file per test, so cache
    behaviour is exercised for real while staying isolated.
    """
    monkeypatch.setattr(cache, "db_path", str(tmp_path / "cache.db"))
    # Each test runs in its own event loop; the singleton's lock must follow.
    monkeypatch.setattr(cache, "_lock", asyncio.Lock())
    await cache.initialize()

    app = FastAPI()
    app.include_router(search_router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    await cache.close()
