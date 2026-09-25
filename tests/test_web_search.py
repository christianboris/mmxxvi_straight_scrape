"""Search falls back across sources until enough unique results are found."""
from services.browser_search import decode_bing_url, split_language
from services.searxng import searxng_client
from services.web_search import normalize_url, plan_sources


def hit(url: str, engine: str) -> dict:
    return {"url": url, "title": url, "snippet": "", "engine": engine}


async def post_search(client, expected_status=200, **overrides) -> dict:
    payload = {"query": "wetter", "max_results": 3, "extract": False}
    payload.update(overrides)
    response = await client.post("/api/search", json=payload)
    assert response.status_code == expected_status, response.text
    return response.json()


async def test_searxng_alone_suffices(client, searxng, native_sources):
    body = await post_search(client)
    assert len(body["results"]) == 3
    assert native_sources.calls == []
    assert body["source_errors"] is None


async def test_falls_back_in_order_until_enough(client, searxng, native_sources):
    searxng.hits = 1
    native_sources.responses = {
        "duckduckgo": [hit("https://a.example/1", "duckduckgo")],
        "startpage": [hit("https://b.example/1", "startpage")],
        "brave": [hit("https://c.example/1", "brave")],
    }
    body = await post_search(client)

    assert [r["engine"] for r in body["results"]] == [
        "testengine", "duckduckgo", "startpage",
    ]
    assert [c["engine"] for c in native_sources.calls] == ["duckduckgo", "startpage"]


async def test_duplicates_are_dropped(client, searxng, native_sources):
    searxng.hits = 1  # https://example.com/en/0
    native_sources.responses = {
        "duckduckgo": [
            hit("https://www.EXAMPLE.com/en/0/", "duckduckgo"),
            hit("https://example.com/other", "duckduckgo"),
        ],
    }
    body = await post_search(client, max_results=5)
    assert [r["url"] for r in body["results"]] == [
        "https://example.com/en/0",
        "https://example.com/other",
    ]


async def test_failing_source_is_reported_and_skipped(client, searxng, native_sources):
    searxng.hits = 0
    native_sources.responses = {
        "duckduckgo": RuntimeError("duckduckgo: blocked by bot detection"),
        "startpage": [hit("https://b.example/1", "startpage")],
    }
    body = await post_search(client, max_results=1)

    assert [r["engine"] for r in body["results"]] == ["startpage"]
    assert body["source_errors"] == {
        "duckduckgo": "duckduckgo: blocked by bot detection",
    }


async def test_all_sources_failing_is_503(client, monkeypatch, native_sources):
    async def broken(**kwargs):
        raise RuntimeError("SearXNG connection error")

    monkeypatch.setattr(searxng_client, "search", broken)
    native_sources.responses = {
        name: RuntimeError("blocked")
        for name in ("duckduckgo", "startpage", "brave", "bing")
    }
    body = await post_search(client, expected_status=503)
    assert "SearXNG connection error" in body["detail"]


async def test_empty_results_are_not_cached(client, searxng, native_sources):
    searxng.hits = 0
    await post_search(client)
    await post_search(client)
    assert len(searxng.calls) == 2


async def test_engines_route_to_native_and_searxng(client, searxng, native_sources):
    searxng.hits = 0
    native_sources.responses = {
        "duckduckgo": [hit("https://a.example/1", "duckduckgo")],
    }
    await post_search(client, engines=["duckduckgo", "google cse"])

    assert searxng.calls[0]["engines"] == ["google cse"]
    assert [c["engine"] for c in native_sources.calls] == ["duckduckgo"]


def test_plan_sources_default_order():
    assert [s for s, _ in plan_sources(None)] == [
        "searxng", "duckduckgo", "startpage", "brave", "bing",
    ]


def test_plan_sources_explicit_searxng():
    assert plan_sources(["brave", "searxng"]) == [("searxng", None), ("brave", None)]


def test_normalize_url():
    assert normalize_url("HTTPS://www.Example.com/a/#frag") == "https://example.com/a"
    assert normalize_url("https://example.com/a?x=1") == "https://example.com/a?x=1"


def test_split_language():
    assert split_language("de") == ("de", "DE")
    assert split_language("en") == ("en", "US")
    assert split_language("de-AT") == ("de", "AT")
    assert split_language("auto") == ("en", "US")


def test_decode_bing_url():
    wrapped = (
        "https://www.bing.com/ck/a?!&&p=abc&ptn=3&ver=2&hsh=4"
        "&u=a1aHR0cHM6Ly93d3cud2V0dGVyLmNvbS93ZXR0ZXJfYWt0dWVsbC8&ntb=1"
    )
    assert decode_bing_url(wrapped) == "https://www.wetter.com/wetter_aktuell/"
    assert decode_bing_url("https://example.com/") == "https://example.com/"
