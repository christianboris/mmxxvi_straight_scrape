"""The search cache must key on every parameter that shapes the response."""


async def post_search(client, **overrides) -> dict:
    payload = {"query": "cache test", "max_results": 3, "extract": False}
    payload.update(overrides)
    response = await client.post("/api/search", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def test_extract_false_then_true_returns_markdown(client, searxng):
    first = await post_search(client, extract=False)
    assert all(r["markdown"] is None for r in first["results"])

    second = await post_search(client, extract=True)
    assert second["results"]
    assert all(r["markdown"] for r in second["results"])
    assert len(searxng.calls) == 2


async def test_extract_true_then_false_returns_no_markdown(client, searxng):
    first = await post_search(client, extract=True)
    assert all(r["markdown"] for r in first["results"])

    second = await post_search(client, extract=False)
    assert second["results"]
    assert all(r["markdown"] is None for r in second["results"])


async def test_max_results_change_is_not_served_from_cache(client, searxng):
    first = await post_search(client, max_results=3)
    assert first["total_results"] == 3

    second = await post_search(client, max_results=5)
    assert second["total_results"] == 5
    assert len(second["results"]) == 5


async def test_summarize_change_is_not_served_from_cache(client, searxng):
    await post_search(client, summarize=False)
    await post_search(client, summarize=True, extract=False)
    assert len(searxng.calls) == 2


async def test_identical_request_is_served_from_cache(client, searxng):
    first = await post_search(client, extract=True)
    second = await post_search(client, extract=True)

    assert len(searxng.calls) == 1
    assert second["results"] == first["results"]


async def test_engines_remain_part_of_the_cache_key(client, searxng):
    await post_search(client, engines=["google cse"])
    await post_search(client, engines=["wikipedia"])
    assert len(searxng.calls) == 2
